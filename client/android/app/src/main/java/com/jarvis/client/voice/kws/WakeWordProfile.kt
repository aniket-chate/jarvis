package com.jarvis.client.voice.kws

/**
 * User-scoped dynamic wake phrase profile.
 * Defines the active wake phrase, normalized tokens, and detection sensitivities for sherpa-onnx KWS.
 *
 * Privacy & Security Contract:
 * - Strictly stores mathematical, configuration, and statistical scalars.
 * - Zero raw PCM, WAV recordings, continuous audio buffers, or biometric embeddings.
 * - Multi-user isolated and scoped by sanitized userId.
 */
data class WakeWordProfile(
    val profileId: String = "default_profile",
    val userId: String = "default_user",
    val phrase: String = "Hey Jarvis",
    val normalizedPhrase: String = "HEY JARVIS",
    val tokenizedKeyword: String = " HE Y  JA R VI S",
    val keywordsScore: Float = 1.0f,
    val keywordsThreshold: Float = 0.50f,
    val numTrailingBlanks: Int = 1,
    val enrolledSampleCount: Int = 0,
    val averageSnrDb: Float = 0f,
    val averageRms: Float = 0f,
    val averagePeak: Float = 0f,
    val isCustomEnrolled: Boolean = false,
    val isActive: Boolean = true,
    val enabled: Boolean = true, // Alias for backward compatibility
    val profileVersion: Int = 1,
    val phraseVariants: List<String> = emptyList(),
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis()
)
