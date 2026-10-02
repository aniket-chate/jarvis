package com.jarvis.client.integration

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.jarvis.client.model.ConnectionState
import com.jarvis.client.repository.JarvisRepository
import com.jarvis.client.settings.JarvisSettingsManager
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

/**
 * End-to-end sandbox test:
 *
 * Android application repository -> real FastAPI JARVIS gateway -> authenticated WebSocket
 * -> deterministic JARVIS command -> Android receives the real chat response.
 *
 * The sandbox gateway is started by .github/workflows/android-sandbox.yml on the emulator host.
 */
@RunWith(AndroidJUnit4::class)
class JarvisAppGatewaySandboxTest {

    @Test
    fun appConnectsToJarvisAndOperatesThroughGateway() = runBlocking {
        val context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation()
            .targetContext
        val settings = JarvisSettingsManager(context)
        val args = androidx.test.platform.app.InstrumentationRegistry
            .getArguments()

        settings.backendBaseUrl = requireArgument(args, "backendUrl")
        settings.userId = requireArgument(args, "userId")
        settings.authToken = requireArgument(args, "authToken")
        settings.deviceName = requireArgument(args, "deviceName")

        val repository = JarvisRepository(settings)

        try {
            repository.start()

            withTimeout(CONNECTION_TIMEOUT_MS) {
                repository.connectionState
                    .filter { it == ConnectionState.AUTHENTICATED }
                    .first()
            }

            val pong = async {
                withTimeout(COMMAND_TIMEOUT_MS) {
                    repository.webSocketClient.pongEvents.first()
                }
            }

            repository.sendPing()
            pong.await()

            val response = async {
                withTimeout(COMMAND_TIMEOUT_MS) {
                    repository.chatResponses
                        .filter { it.payload.text == "Stopped." }
                        .first()
                }
            }

            repository.sendMessage("stop")
            val result = response.await()

            assertEquals("Stopped.", result.payload.text)
            assertEquals("cancel", result.payload.intent)
            assertEquals(false, result.payload.requiresConfirmation)

            val voiceResponse = async {
                withTimeout(COMMAND_TIMEOUT_MS) {
                    repository.voiceResponses.first()
                }
            }

            repository.sendVoiceTurn("stop")
            val voiceResult = voiceResponse.await()

            assertEquals("success", voiceResult.status)
            assertEquals(true, voiceResult.text.isNotBlank())
        } finally {
            repository.stop()
            settings.authToken = ""
        }
    }

    private fun requireArgument(
        args: android.os.Bundle,
        key: String,
    ): String = args.getString(key)?.takeIf { it.isNotBlank() }
        ?: error("Missing instrumentation argument: $key")

    companion object {
        private const val CONNECTION_TIMEOUT_MS = 30_000L
        private const val COMMAND_TIMEOUT_MS = 30_000L
    }
}
