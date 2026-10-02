package com.jarvis.client.assistant

import android.content.Intent
import android.os.Bundle
import android.service.voice.VoiceInteractionService
import android.util.Log
import com.jarvis.client.JarvisApp

/**
 * System-level Android assistant entry point.
 *
 * Keep this service lightweight. The platform owns its lifecycle when JARVIS is selected
 * as the user's assistant. Actual assistant UI/work is handled by the session service.
 */
class JarvisVoiceInteractionService : VoiceInteractionService() {
    private val tag = "JarvisVoiceInteractionService"

    override fun onReady() {
        super.onReady()
        Log.i(tag, "JARVIS is the active Android assistant.")
        JarvisApp.instance.repository.start()
    }

    override fun onShutdown() {
        Log.i(tag, "JARVIS assistant service shutting down.")
        super.onShutdown()
    }

    override fun onLaunchVoiceAssistFromKeyguard() {
        val intent = Intent(this, JarvisAssistantActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            putExtra(EXTRA_FROM_KEYGUARD, true)
        }
        startActivity(intent)
    }

    override fun onPrepareToShowSession(args: Bundle, flags: Int) {
        super.onPrepareToShowSession(args, flags)
        Log.d(tag, "Preparing JARVIS assistant session.")
    }

    companion object {
        const val EXTRA_FROM_KEYGUARD = "jarvis_from_keyguard"
    }
}
