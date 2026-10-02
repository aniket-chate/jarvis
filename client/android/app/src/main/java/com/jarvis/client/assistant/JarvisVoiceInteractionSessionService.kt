package com.jarvis.client.assistant

import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSessionService

/**
 * Creates the short-lived assistant session used by the Android system assistant UI.
 */
class JarvisVoiceInteractionSessionService : VoiceInteractionSessionService() {
    override fun onNewSession(args: android.os.Bundle?): VoiceInteractionSession {
        return JarvisVoiceInteractionSession(this)
    }
}
