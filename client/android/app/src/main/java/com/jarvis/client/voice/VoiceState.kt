package com.jarvis.client.voice

/**
 * Visual and operational state of the Android Voice Layer.
 */
enum class VoiceState {
    IDLE,
    LISTENING,
    PROCESSING,
    SPEAKING,
    ERROR;

    val isBusy: Boolean
        get() = this == LISTENING || this == PROCESSING || this == SPEAKING
}
