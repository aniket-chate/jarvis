package com.jarvis.client.voice.calibration

import java.util.Locale
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * Pure statistical and algorithmic evaluation engine for Personal Wake-Word Calibration.
 * Computes confidence distributions, FAR/FRR curves, safety margins, and optimal operating thresholds.
 */
object CalibrationEvaluator {

    const val DEFAULT_THRESHOLD = 0.32f
    const val DEFAULT_CONSECUTIVE_HITS = 3
    const val MIN_THRESHOLD_BOUND = 0.20f
    const val MAX_THRESHOLD_BOUND = 0.70f

    /**
     * Calculates statistical distribution for a list of confidence floats.
     */
    fun calculateDistribution(values: List<Float>): ConfidenceDistribution {
        if (values.isEmpty()) {
            return ConfidenceDistribution(histogramBins = List(10) { 0 })
        }

        val sorted = values.sorted()
        val count = sorted.size
        val minVal = sorted.first()
        val maxVal = sorted.last()
        val meanVal = sorted.sum() / count
        val medianVal = if (count % 2 == 1) {
            sorted[count / 2]
        } else {
            (sorted[count / 2 - 1] + sorted[count / 2]) / 2.0f
        }

        val p90Idx = (count * 0.90f).toInt().coerceIn(0, count - 1)
        val p95Idx = (count * 0.95f).toInt().coerceIn(0, count - 1)

        val bins = IntArray(10) { 0 }
        for (v in values) {
            val binIdx = (v * 10.0f).toInt().coerceIn(0, 9)
            bins[binIdx]++
        }

        return ConfidenceDistribution(
            min = minVal,
            max = maxVal,
            mean = meanVal,
            median = medianVal,
            p90 = sorted[p90Idx],
            p95 = sorted[p95Idx],
            histogramBins = bins.toList()
        )
    }

    /**
     * Calculates the maximum number of consecutive frames exceeding the specified threshold.
     */
    fun maxConsecutiveHits(confidenceTrace: List<Float>, threshold: Float): Int {
        var maxHits = 0
        var currentHits = 0
        for (conf in confidenceTrace) {
            if (conf >= threshold) {
                currentHits++
                if (currentHits > maxHits) {
                    maxHits = currentHits
                }
            } else {
                currentHits = 0
            }
        }
        return maxHits
    }

    /**
     * Evaluates FAR and FRR for a given threshold and consecutive hit requirement against collected samples.
     */
    fun evaluateFarFrrPoint(
        samples: List<CalibrationSampleSummary>,
        threshold: Float,
        consecutiveHitsRequired: Int = DEFAULT_CONSECUTIVE_HITS
    ): FarFrrCurvePoint {
        val positives = samples.filter { it.sampleType == CalibrationSampleType.POSITIVE_WAKE }
        val negatives = samples.filter { it.sampleType != CalibrationSampleType.POSITIVE_WAKE }

        var falseRejections = 0
        for (pos in positives) {
            val hits = maxConsecutiveHits(pos.confidenceTrace, threshold)
            if (hits < consecutiveHitsRequired) {
                falseRejections++
            }
        }
        val frr = if (positives.isNotEmpty()) {
            falseRejections.toFloat() / positives.size.toFloat()
        } else {
            0.0f
        }

        var falseAcceptances = 0
        for (neg in negatives) {
            val hits = maxConsecutiveHits(neg.confidenceTrace, threshold)
            if (hits >= consecutiveHitsRequired) {
                falseAcceptances++
            }
        }
        val far = if (negatives.isNotEmpty()) {
            falseAcceptances.toFloat() / negatives.size.toFloat()
        } else {
            0.0f
        }

        return FarFrrCurvePoint(
            threshold = threshold,
            consecutiveHitsRequired = consecutiveHitsRequired,
            falseAcceptanceRate = far,
            falseRejectionRate = frr
        )
    }

    /**
     * Generates a full FAR vs. FRR Detection Error Tradeoff (DET) / ROC curve across a threshold sweep.
     */
    fun generateRocCurve(
        samples: List<CalibrationSampleSummary>,
        consecutiveHitsRequired: Int = DEFAULT_CONSECUTIVE_HITS,
        startThreshold: Float = 0.10f,
        endThreshold: Float = 0.90f,
        step: Float = 0.02f
    ): List<FarFrrCurvePoint> {
        val points = mutableListOf<FarFrrCurvePoint>()
        var t = startThreshold
        while (t <= endThreshold + 0.001f) {
            points.add(evaluateFarFrrPoint(samples, t, consecutiveHitsRequired))
            t += step
        }
        return points
    }

    /**
     * Computes a data-driven operating threshold recommendation based on actual positive & negative samples.
     */
    fun recommendThreshold(
        samples: List<CalibrationSampleSummary>,
        targetMaxFar: Float = 0.0f,
        minPositivesRequired: Int = 3,
        minNegativesRequired: Int = 3,
        noiseMargin: Float = 0.05f,
        wakeMargin: Float = 0.05f
    ): CalibrationRecommendation {
        val positives = samples.filter { it.sampleType == CalibrationSampleType.POSITIVE_WAKE }
        val negatives = samples.filter { it.sampleType != CalibrationSampleType.POSITIVE_WAKE }

        if (positives.size < minPositivesRequired || negatives.size < minNegativesRequired) {
            return CalibrationRecommendation(
                recommendedThreshold = DEFAULT_THRESHOLD,
                recommendedConsecutiveHits = DEFAULT_CONSECUTIVE_HITS,
                expectedFar = 0.0f,
                expectedFrr = 0.0f,
                isReliable = false,
                reliabilityReason = String.format(
                    Locale.US,
                    "Insufficient sample count: got %d positives, %d negatives (need >= %d pos, >= %d neg)",
                    positives.size,
                    negatives.size,
                    minPositivesRequired,
                    minNegativesRequired
                )
            )
        }

        // Noise floor peak across all negative samples
        val maxNegConf = negatives.map { it.maxConfidence }.maxOrNull() ?: 0.0f

        // Positive confidence distribution
        val posPeaks = positives.map { it.maxConfidence }.sorted()
        val minPosConf = posPeaks.first()
        val p10Idx = (posPeaks.size * 0.10f).toInt().coerceIn(0, posPeaks.size - 1)
        val p10PosConf = posPeaks[p10Idx]

        val lowerSafeBound = maxNegConf + noiseMargin
        val upperSafeBound = p10PosConf - wakeMargin
        val margin = p10PosConf - maxNegConf

        if (lowerSafeBound >= upperSafeBound || margin < 0.05f) {
            return CalibrationRecommendation(
                recommendedThreshold = DEFAULT_THRESHOLD,
                recommendedConsecutiveHits = DEFAULT_CONSECUTIVE_HITS,
                expectedFar = 0.0f,
                expectedFrr = 0.0f,
                noiseFloorMaxConfidence = maxNegConf,
                positiveMinConfidence = minPosConf,
                confidenceMargin = margin,
                isReliable = false,
                reliabilityReason = String.format(
                    Locale.US,
                    "Acoustic overlap detected: Max noise peak (%.2f) too close to positive wake score (%.2f)",
                    maxNegConf,
                    p10PosConf
                )
            )
        }

        // Weighted threshold favoring noise rejection safety (40% lower bound + 60% upper bound)
        val rawOptimal = 0.40f * lowerSafeBound + 0.60f * upperSafeBound
        val rounded = ((rawOptimal * 100.0f).roundToInt() / 100.0f)
        val clampedThreshold = rounded.coerceIn(MIN_THRESHOLD_BOUND, MAX_THRESHOLD_BOUND)

        val evalPoint = evaluateFarFrrPoint(samples, clampedThreshold, DEFAULT_CONSECUTIVE_HITS)
        val isReliable = evalPoint.falseAcceptanceRate <= targetMaxFar && evalPoint.falseRejectionRate <= 0.20f

        return CalibrationRecommendation(
            recommendedThreshold = clampedThreshold,
            recommendedConsecutiveHits = DEFAULT_CONSECUTIVE_HITS,
            expectedFar = evalPoint.falseAcceptanceRate,
            expectedFrr = evalPoint.falseRejectionRate,
            noiseFloorMaxConfidence = maxNegConf,
            positiveMinConfidence = minPosConf,
            confidenceMargin = margin,
            isReliable = isReliable,
            reliabilityReason = if (isReliable) {
                String.format(
                    Locale.US,
                    "Calibrated successfully: FAR=%.1f%%, FRR=%.1f%%, Margin=%.2f",
                    evalPoint.falseAcceptanceRate * 100f,
                    evalPoint.falseRejectionRate * 100f,
                    margin
                )
            } else {
                String.format(
                    Locale.US,
                    "Marginal calibration reliability: FAR=%.1f%%, FRR=%.1f%%",
                    evalPoint.falseAcceptanceRate * 100f,
                    evalPoint.falseRejectionRate * 100f
                )
            }
        )
    }
}
