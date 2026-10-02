package com.jarvis.client.assistant

import android.graphics.Color
import android.os.Bundle
import android.service.voice.VoiceInteractionSession
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import com.jarvis.client.JarvisApp

/**
 * Lightweight assistant surface. The real reasoning remains in the JARVIS backend.
 * The session only exposes the Android invocation surface and starts the existing
 * speech pipeline; it does not duplicate the brain or invent a second command router.
 */
class JarvisVoiceInteractionSession(
    service: VoiceInteractionSessionService
) : VoiceInteractionSession(service) {

    private var statusView: TextView? = null

    override fun onCreateContentView(): View {
        val root = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(48, 36, 48, 36)
            setBackgroundColor(Color.rgb(18, 20, 24))
        }

        val title = TextView(context).apply {
            text = "JARVIS"
            textSize = 28f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
        }

        val status = TextView(context).apply {
            text = "Ready"
            textSize = 16f
            setTextColor(Color.LTGRAY)
            gravity = Gravity.CENTER
        }
        statusView = status

        val listen = Button(context).apply {
            text = "Talk to JARVIS"
            setOnClickListener {
                status.text = "Listening…"
                JarvisApp.instance.repository.startVoiceListening()
            }
        }

        val openApp = Button(context).apply {
            text = "Open full JARVIS"
            setOnClickListener {
                startAssistantActivity(
                    android.content.Intent(context, com.jarvis.client.assistant.JarvisAssistantActivity::class.java)
                )
            }
        }

        root.addView(title, LinearLayout.LayoutParams(-1, -2))
        root.addView(status, LinearLayout.LayoutParams(-1, -2).apply {
            topMargin = 16
        })
        root.addView(listen, LinearLayout.LayoutParams(-1, -2).apply {
            topMargin = 24
        })
        root.addView(openApp, LinearLayout.LayoutParams(-1, -2).apply {
            topMargin = 8
        })
        return root
    }

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        statusView?.text = "Ready"
    }

    override fun onHide() {
        JarvisApp.instance.repository.stopVoiceListening()
        statusView?.text = "Ready"
        super.onHide()
    }
}
