package com.jarvis.client.security

import android.content.Context
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.jarvis.client.settings.JarvisSettingsManager
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class SecureFieldVaultInstrumentedTest {

    private val context: Context
        get() = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun secretRoundTripsWithoutPlaintextPreferenceStorage() {
        val vault = SecureFieldVault(context)
        val preferences = context.getSharedPreferences("jarvis_secure_fields", Context.MODE_PRIVATE)
        val field = "instrumentation_${UUID.randomUUID()}"
        val secret = "test-only-secret-${UUID.randomUUID()}"

        try {
            assertTrue(vault.put(field, secret))
            assertEquals(secret, vault.get(field))

            val storedValue = preferences.getString(field, null)
            assertNotNull(storedValue)
            assertNotEquals(secret, storedValue)
        } finally {
            vault.remove(field)
        }

        assertNull(vault.get(field))
    }

    @Test
    fun backendUrlNormalizationAndWebSocketSchemeAreConsistent() {
        val settings = JarvisSettingsManager(context)
        val originalUrl = settings.backendBaseUrl
        val originalDeviceId = settings.deviceId

        try {
            settings.deviceId = "device id/one"
            settings.backendBaseUrl = "https://gateway.example/base/"

            assertEquals("https://gateway.example/base", settings.backendBaseUrl)
            assertEquals(
                "wss://gateway.example/base/api/v1/ws?device_id=device+id%2Fone",
                settings.getWebSocketUrl()
            )

            settings.backendBaseUrl = "http://gateway.example:8000/"
            assertEquals(
                "ws://gateway.example:8000/api/v1/ws?device_id=device+id%2Fone",
                settings.getWebSocketUrl()
            )
        } finally {
            settings.backendBaseUrl = originalUrl
            settings.deviceId = originalDeviceId
        }
    }
}
