package com.jarvis.client.voice.calibration

/**
 * Result score from evaluating an acoustic embedding sequence against an enrolled user voiceprint.
 */
data class SpeakerVerificationScore(
    val isMatched: Boolean,
    val similarityScore: Float,
    val confidence: Float,
    val details: String = ""
)

/**
 * Voice enrollment status for a target user.
 */
data class SpeakerEnrollmentStatus(
    val isEnrolled: Boolean = false,
    val userId: String = "",
    val sampleCount: Int = 0,
    val enrolledAt: Long = 0L
)

/**
 * Interface contract for future Speaker Verification / Voice Biometrics (Phase 7 Step 4B).
 *
 * NOTE: Speaker verification is NOT enabled during Phase 7 Step 4A.
 * This interface establishes the clean boundary so that acoustic wake-word calibration
 * and future voice biometric modules connect cleanly without touching the ONNX engine.
 */
interface SpeakerVerificationEngine {
    val isEnrolled: Boolean
    val activeUserId: String

    /**
     * Compares 96-dimensional acoustic embeddings against the enrolled user model.
     */
    fun verifySpeaker(embeddingSequence: List<FloatArray>): SpeakerVerificationScore

    /**
     * Checks enrollment status for the specified user.
     */
    fun getEnrollmentStatus(userId: String): SpeakerEnrollmentStatus
}

/**
 * Default pass-through speaker verification implementation for Phase 7 Step 4A.
 */
class NoOpSpeakerVerificationEngine(
    override val activeUserId: String = "default_user"
) : SpeakerVerificationEngine {

    override val isEnrolled: Boolean = false

    override fun verifySpeaker(embeddingSequence: List<FloatArray>): SpeakerVerificationScore {
        return SpeakerVerificationScore(
            isMatched = true,
            similarityScore = 1.0f,
            confidence = 1.0f,
            details = "Speaker verification disabled (Phase 7 Step 4A baseline)"
        )
    }

    override fun getEnrollmentStatus(userId: String): SpeakerEnrollmentStatus {
        return SpeakerEnrollmentStatus(
            isEnrolled = false,
            userId = userId,
            sampleCount = 0,
            enrolledAt = 0L
        )
    }
}
