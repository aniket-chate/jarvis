package com.jarvis.client.voice.kws

/**
 * State machine for guided custom wake-word enrollment session.
 */
enum class EnrollmentState {
    IDLE,
    PREPARING,
    RECORDING,
    SAMPLE_COMPLETE,
    COMPLETED,
    CANCELLED,
    FAILED
}

/**
 * Single guided enrollment step prompt.
 */
data class EnrollmentStep(
    val stepIndex: Int,
    val totalSteps: Int = 5,
    val title: String,
    val promptInstruction: String,
    val speakingStyle: String,
    val targetDurationMs: Long = 3500L
)

/**
 * Non-sensitive statistical acoustic & quality metrics captured during a single enrollment sample.
 * Strictly avoids storing raw PCM audio data.
 */
data class EnrollmentAcousticMetrics(
    val totalPcmFrames: Int = 0,
    val sampleCount: Int = 0,
    val minRms: Float = 0f,
    val maxRms: Float = 0f,
    val averageRms: Float = 0f,
    val peakRms: Float = 0f,
    val noiseFloorRms: Float = 0f,
    val speechRms: Float = 0f,
    val speechFrameCount: Int = 0,
    val speechDurationMs: Long = 0L,
    val speechThreshold: Float = 0f,
    val clippingCount: Int = 0,
    val estimatedSnrDb: Float = 0f,
    val durationMs: Long = 0L,
    val pcmChunkCount: Int = 0,
    val hasSpeechPresence: Boolean = false,
    val isClipping: Boolean = false,
    val qualityClassification: String = "GOOD", // "GOOD", "ACCEPTABLE", "TOO_QUIET", "CLIPPING", "HIGH_NOISE", "TOO_SHORT"
    val keywordScore: Float = 0f,
    val isKeywordDetected: Boolean = false,
    val confidenceTrace: List<Float> = emptyList(),
    val validationStatus: String = "GOOD_AUDIO"
)

/**
 * Summary result of a single enrollment recording step.
 */
data class EnrollmentSampleResult(
    val stepIndex: Int,
    val sampleId: String,
    val speakingStyle: String,
    val metrics: EnrollmentAcousticMetrics,
    val isValid: Boolean,
    val timestamp: Long = System.currentTimeMillis()
)

/**
 * Phrase validation outcome before beginning enrollment.
 */
data class PhraseValidationResult(
    val isValid: Boolean,
    val normalizedPhrase: String,
    val tokenizedKeyword: String,
    val errorMessage: String? = null
)

/**
 * Aggregated result of a complete 5-sample enrollment session.
 * Contains data-driven adapted hyperparameters for Sherpa-ONNX KeywordSpotter.
 * Does NOT persist raw audio or automatically activate the profile.
 */
data class WakeWordEnrollmentResult(
    val userId: String,
    val phrase: String,
    val normalizedPhrase: String,
    val tokenizedPhrase: String,
    val totalSamples: Int = 5,
    val validAudioSamples: Int = 0,
    val successfulSamples: Int = 0, // Backwards compatible alias for validAudioSamples
    val detectedSamples: Int = 0,
    val averageRms: Float = 0f,
    val averagePeak: Float = 0f,
    val averageNoiseFloor: Float = 0f,
    val averageSpeechRms: Float = 0f,
    val averageSnrDb: Float = 0f,
    val averageKeywordScore: Float = 0f,
    val minConfidence: Float = 0f,
    val maxConfidence: Float = 0f,
    val recommendedKeywordsThreshold: Float = 0.40f,
    val recommendedKeywordsScore: Float = 1.0f,
    val recommendedNumTrailingBlanks: Int = 1,
    val isReliable: Boolean = false,
    val reliabilityReason: String = "Unenrolled",
    val sampleResults: List<EnrollmentSampleResult> = emptyList(),
    val timestamp: Long = System.currentTimeMillis()
)
