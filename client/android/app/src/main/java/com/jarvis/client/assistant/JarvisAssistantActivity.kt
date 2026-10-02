package com.jarvis.client.assistant

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.jarvis.client.R

/**
 * Full-screen fallback opened from the system assistant session.
 * Normal app navigation remains in MainActivity; this activity only bridges the
 * system assistant layer to the existing UI without creating another brain.
 */
class JarvisAssistantActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        startActivity(Intent(this, com.jarvis.client.ui.MainActivity::class.java))
        finish()
    }
}
