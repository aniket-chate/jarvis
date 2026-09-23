package com.jarvis.client.voice

import kotlinx.coroutines.flow.StateFlow

/**
 * State machine for wake-word detection lifecycle.
 */
enum class WakeWordState {
    IDLE,
    LISTENING_FOR_WAKE,
    WAKE_DETECTED,
    COOLDOWN,
    ERROR
}

/**
 * Diagnostic tracking counters (privacy-safe, zero raw audio).
 */
data class VoiceDiagnostics(
    val standbyCycles: Int = 0,
    val wakeDetections: Int = 0,
    val rejectedEvents: Int = 0,
    val directCommands: Int = 0,
    val handoffSuccesses: Int = 0,
    val handoffErrors: Int = 0
)

/**
 * Real-time non-sensitive Microphone and KWS pipeline diagnostic metrics.
 */
data class MicrophoneDiagnostics(
    val isPermissionGranted: Boolean = false,
    val audioRecordState: String = "UNINITIALIZED", // "INITIALIZED", "UNINITIALIZED", "ERROR"
    val recordingState: String = "STOPPED", // "RECORDING", "STOPPED"
    val sampleRate: Int = 16000,
    val channelConfig: String = "CHANNEL_IN_MONO",
    val audioSource: String = "VOICE_RECOGNITION",
    val pcmChunksRead: Long = 0L,
    val readErrors: Long = 0L,
    val lastReadError: String = "None",
    val currentRms: Float = 0f,
    val currentPeak: Float = 0f,
    val maxPeak: Float = 0f,
    val melFramesProcessed: Long = 0L,
    val embeddingsGenerated: Long = 0L,
    val inferencesEvaluated: Long = 0L,
    val lastConfidence: Float = 0f,
    val maxConfidence: Float = 0f,
    val threshold: Float = 0.32f,
    val consecutiveHits: Int = 0,
    val consecutiveRequired: Int = 3,
    val wakeDetections: Int = 0,
    val rejectedDetections: Int = 0
)

/**
 * Pluggable interface for on-device wake-word detection.
 * Operates strictly on-device without streaming continuous raw audio to the backend.
 */
interface WakeWordDetector {
    val state: StateFlow<WakeWordState>
    val diagnostics: StateFlow<VoiceDiagnostics>
    val micDiagnostics: StateFlow<MicrophoneDiagnostics>
    fun startListening(onWakeDetected: (commandAfterWake: String) -> Unit)
    fun stopListening()
    fun destroy()
}
