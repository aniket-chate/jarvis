package com.jarvis.client.voice.calibration

/**
 * Types of acoustic calibration samples captured during a guided calibration session.
 */
enum class CalibrationSampleType {
    POSITIVE_WAKE,        // Intentional "Hey Jarvis" utterance by the target user
    NEGATIVE_SILENCE,     // Baseline ambient quiet room
    NEGATIVE_FAN_NOISE,   // Ambient cooler, fan, or AC noise
    NEGATIVE_SPEECH,      // Natural conversational speech without wake word
    NEGATIVE_MEDIA        // YouTube, podcast, TV, or external video playback
}

/**
 * Statistical distribution of confidence values over an audio segment.
 */
data class ConfidenceDistribution(
    val min: Float = 0f,
    val max: Float = 0f,
    val mean: Float = 0f,
    val median: Float = 0f,
    val p90: Float = 0f,
    val p95: Float = 0f,
    val histogramBins: List<Int> = emptyList() // 10 bins: [0.0-0.1, 0.1-0.2, ... 0.9-1.0]
)

/**
 * Non-sensitive acoustic & KWS feature summary extracted from an audio sample.
 * Strictly avoids storing raw PCM audio data.
 */
data class CalibrationSampleSummary(
    val sampleId: String,
    val sampleType: CalibrationSampleType,
    val durationMs: Long,
    val pcmChunkCount: Int,
    val averageRms: Float,
    val peakRms: Float,
    val estimatedSnrDb: Float,
    val maxConfidence: Float,
    val meanConfidence: Float,
    val confidenceDistribution: ConfidenceDistribution = ConfidenceDistribution(),
    val confidenceTrace: List<Float> = emptyList(), // 80ms inference frame confidence values
    val consecutiveHitsAtDefault: Int = 0,
    val timestamp: Long = System.currentTimeMillis()
)

/**
 * Single evaluation point along the False Acceptance Rate (FAR) and False Rejection Rate (FRR) curve.
 */
data class FarFrrCurvePoint(
    val threshold: Float,
    val consecutiveHitsRequired: Int,
    val falseAcceptanceRate: Float, // Rate of false wake triggers on negative samples [0.0, 1.0]
    val falseRejectionRate: Float   // Rate of missed wake triggers on positive samples [0.0, 1.0]
)

/**
 * Data-driven operating threshold recommendation generated from empirical calibration data.
 */
data class CalibrationRecommendation(
    val recommendedThreshold: Float = 0.32f,
    val recommendedConsecutiveHits: Int = 3,
    val expectedFar: Float = 0f,
    val expectedFrr: Float = 0f,
    val noiseFloorMaxConfidence: Float = 0f,
    val positiveMinConfidence: Float = 0f,
    val confidenceMargin: Float = 0f,
    val isReliable: Boolean = false,
    val reliabilityReason: String = "Uncalibrated baseline default"
)

/**
 * Persistent calibration profile for a specific user and device.
 */
data class CalibrationProfile(
    val profileId: String,
    val userId: String,
    val deviceId: String,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
    val version: Int = 1,
    val positiveSampleCount: Int = 0,
    val negativeSampleCount: Int = 0,
    val recommendation: CalibrationRecommendation = CalibrationRecommendation(),
    val sampleSummaries: List<CalibrationSampleSummary> = emptyList(),
    val isCustomThresholdActive: Boolean = false
)

/**
 * Progress states of a calibration session.
 */
enum class CalibrationSessionState {
    IDLE,
    PROMPT_READY,
    RECORDING_SAMPLE,
    PROCESSING_SAMPLE,
    EVALUATING_RESULTS,
    COMPLETED,
    ERROR
}

/**
 * Prompt instruction guiding the user through capturing a calibration sample.
 */
data class CalibrationStepPrompt(
    val stepIndex: Int,
    val totalSteps: Int,
    val sampleType: CalibrationSampleType,
    val title: String,
    val instruction: String,
    val targetDurationMs: Long = 3000L
)
