package com.jarvis.client.assistant

import android.content.Intent
import android.os.Bundle
import android.view.WindowManager
import androidx.appcompat.app.AppCompatActivity

/**
 * Full-screen fallback opened from the system assistant session.
 * Normal app navigation remains in MainActivity; this activity only bridges the
 * system assistant layer to the existing UI without creating another brain.
 */
class JarvisAssistantActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        if (intent.getBooleanExtra(EXTRA_FROM_KEYGUARD, false)) {
            window.addFlags(
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                    WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
            )
        }
        super.onCreate(savedInstanceState)
        startActivity(Intent(this, com.jarvis.client.ui.MainActivity::class.java).apply { if (intent.getBooleanExtra(EXTRA_FROM_KEYGUARD, false)) { addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON) } })
        finish()
    }

    companion object {
        const val EXTRA_FROM_KEYGUARD = JarvisVoiceInteractionService.EXTRA_FROM_KEYGUARD
    }
}
