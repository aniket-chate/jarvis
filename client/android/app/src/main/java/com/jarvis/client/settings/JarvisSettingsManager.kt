package com.jarvis.client.settings

import android.content.Context
import android.content.SharedPreferences
import android.os.Build
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.util.UUID

/**
 * Manages persistent configuration for the Android Jarvis Client.
 */
class JarvisSettingsManager(context: Context) {

    val context: Context = context.applicationContext

    private val prefs: SharedPreferences =
        this.context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    var backendBaseUrl: String
        get() = prefs.getString(KEY_BACKEND_URL, DEFAULT_BACKEND_URL) ?: DEFAULT_BACKEND_URL
        set(value) = prefs.edit().putString(KEY_BACKEND_URL, normalizeUrl(value)).apply()

    var userId: String
        get() = prefs.getString(KEY_USER_ID, DEFAULT_USER_ID) ?: DEFAULT_USER_ID
        set(value) = prefs.edit().putString(KEY_USER_ID, value.trim()).apply()

    var deviceId: String
        get() {
            val existing = prefs.getString(KEY_DEVICE_ID, null)
            if (!existing.isNullOrBlank()) return existing
            val generated = "android_" + UUID.randomUUID().toString()
            prefs.edit().putString(KEY_DEVICE_ID, generated).apply()
            return generated
        }
        set(value) = prefs.edit().putString(KEY_DEVICE_ID, value.trim()).apply()

    var deviceName: String
        get() = prefs.getString(KEY_DEVICE_NAME, null)
            ?: "${Build.MANUFACTURER} ${Build.MODEL}".trim().ifBlank { "Android Device" }
        set(value) = prefs.edit().putString(KEY_DEVICE_NAME, value.trim()).apply()

    var authToken: String
        get() = prefs.getString(KEY_AUTH_TOKEN, "") ?: ""
        set(value) = prefs.edit().putString(KEY_AUTH_TOKEN, value.trim()).apply()

    val sessionId: String by lazy {
        val existing = prefs.getString(KEY_SESSION_ID, null)
        if (existing.isNullOrBlank()) {
            val newSession = "android_sess_" + UUID.randomUUID().toString().take(8)
            prefs.edit().putString(KEY_SESSION_ID, newSession).apply()
            newSession
        } else {
            existing
        }
    }

    var customWakeThreshold: Float
        get() = prefs.getFloat(KEY_CUSTOM_THRESHOLD, DEFAULT_WAKE_THRESHOLD)
        set(value) = prefs.edit().putFloat(KEY_CUSTOM_THRESHOLD, value).apply()

    var isCustomThresholdEnabled: Boolean
        get() = prefs.getBoolean(KEY_CUSTOM_THRESHOLD_ENABLED, false)
        set(value) = prefs.edit().putBoolean(KEY_CUSTOM_THRESHOLD_ENABLED, value).apply()

    var activeCalibrationProfileId: String
        get() = prefs.getString(KEY_ACTIVE_PROFILE_ID, "") ?: ""
        set(value) = prefs.edit().putString(KEY_ACTIVE_PROFILE_ID, value.trim()).apply()

    val defaultCapabilities: List<String> = listOf(
        "microphone",
        "speaker",
        "camera",
        "flashlight",
        "notifications",
        "messaging",
        "apps",
        "media",
        "youtube",
        "screen_observation",
        "ui_actions",
        "background_connection",
        "voice_assistant"
    )

    /**
     * Dynamically derive the WebSocket URL from backendBaseUrl.
     *
     * Authentication is sent in the WebSocket Authorization header, not in the URL,
     * so credentials do not become part of request URLs/logs.
     */
    fun getWebSocketUrl(): String {
        val base = backendBaseUrl.trimEnd('/')
        val wsBase = when {
            base.startsWith("https://", ignoreCase = true) -> "wss://" + base.substring(8)
            base.startsWith("http://", ignoreCase = true) -> "ws://" + base.substring(7)
            base.startsWith("wss://", ignoreCase = true) || base.startsWith("ws://", ignoreCase = true) -> base
            else -> "ws://$base"
        }
        val encodedDeviceId = URLEncoder.encode(deviceId, StandardCharsets.UTF_8.name())
        return "$wsBase/api/v1/ws?device_id=$encodedDeviceId"
    }

    private fun normalizeUrl(url: String): String {
        var clean = url.trim().trimEnd('/')
        if (!clean.startsWith("http://") && !clean.startsWith("https://")) {
            clean = "http://$clean"
        }
        return clean
    }

    companion object {
        private const val PREFS_NAME = "jarvis_client_prefs"
        private const val KEY_BACKEND_URL = "backend_url"
        private const val KEY_USER_ID = "user_id"
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_DEVICE_NAME = "device_name"
        private const val KEY_AUTH_TOKEN = "auth_token"
        private const val KEY_SESSION_ID = "session_id"
        private const val KEY_CUSTOM_THRESHOLD = "custom_wake_threshold"
        private const val KEY_CUSTOM_THRESHOLD_ENABLED = "custom_threshold_enabled"
        private const val KEY_ACTIVE_PROFILE_ID = "active_calibration_profile_id"

        const val DEFAULT_WAKE_THRESHOLD = 0.32f
        const val DEFAULT_BACKEND_URL = "http://10.0.2.2:8000"
        const val DEFAULT_USER_ID = "default_user"
    }
}
