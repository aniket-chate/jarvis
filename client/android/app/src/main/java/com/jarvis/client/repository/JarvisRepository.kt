package com.jarvis.client.repository

import android.util.Log
import com.jarvis.client.accessibility.JarvisAccessibilityService
import com.jarvis.client.device.DeviceHeartbeatManager
import com.jarvis.client.model.ChatMessage
import com.jarvis.client.model.ConnectionState
import com.jarvis.client.model.DeviceRegisterRequest
import com.jarvis.client.model.MessageSender
import com.jarvis.client.model.WsChatResponse
import com.jarvis.client.model.WsVoiceResponse
import com.jarvis.client.network.JarvisApiClient
import com.jarvis.client.settings.JarvisSettingsManager
import com.jarvis.client.skill.AndroidSkillExecutor
import com.jarvis.client.voice.JarvisTTSManager
import com.jarvis.client.voice.SpeechRecognitionManager
import com.jarvis.client.voice.VoiceState
import com.jarvis.client.websocket.JarvisWebSocketClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Single repository coordinating network, WebSocket, device registration, voice layer, and chat state.
 */
class JarvisRepository(
    val settingsManager: JarvisSettingsManager,
    private val apiClient: JarvisApiClient = JarvisApiClient(settingsManager),
    val skillExecutor: AndroidSkillExecutor? = null,
    val webSocketClient: JarvisWebSocketClient = JarvisWebSocketClient(settingsManager, skillExecutor),
    private val heartbeatManager: DeviceHeartbeatManager = DeviceHeartbeatManager(apiClient, settingsManager),
    val ttsManager: JarvisTTSManager? = null,
    val speechRecognitionManager: SpeechRecognitionManager? = null,
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.IO + Job())
) {

    private val tag = "JarvisRepository"

    private var lastRegisteredCapabilities: List<String>? = null

    val connectionState: StateFlow<ConnectionState> = webSocketClient.connectionState
    val chatResponses: SharedFlow<WsChatResponse> = webSocketClient.chatResponses
    val voiceResponses: SharedFlow<WsVoiceResponse> = webSocketClient.voiceResponses

    private val _chatMessages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val chatMessages: StateFlow<List<ChatMessage>> = _chatMessages.asStateFlow()

    private val _pendingConfirmation = MutableStateFlow<ChatMessage?>(null)
    val pendingConfirmation: StateFlow<ChatMessage?> = _pendingConfirmation.asStateFlow()

    private val _ttsEnabled = MutableStateFlow(true)
    val ttsEnabled: StateFlow<Boolean> = _ttsEnabled.asStateFlow()

    val isSpeaking: StateFlow<Boolean> = ttsManager?.isSpeaking ?: MutableStateFlow(false)
    val speechVoiceState: StateFlow<VoiceState> = speechRecognitionManager?.voiceState ?: MutableStateFlow(VoiceState.IDLE)

    init {
        // Hook heartbeat tick to verify capability freshness
        heartbeatManager.onHeartbeatTick = {
            checkAndRefreshCapabilities()
        }

        // Hook Accessibility Service lifecycle callback
        JarvisAccessibilityService.serviceStateListener = { isEnabled ->
            Log.i(tag, "JarvisAccessibilityService connection changed: enabled=$isEnabled -> checking capability sync")
            checkAndRefreshCapabilities()
        }

        // Observe WebSocket incoming responses
        scope.launch {
            webSocketClient.chatResponses.collect { wsResponse ->
                val payload = wsResponse.payload
                val isConfirmation = payload.requiresConfirmation

                val jarvisMsg = ChatMessage(
                    sender = MessageSender.JARVIS,
                    text = payload.text,
                    spokenText = payload.spokenText,
                    intent = payload.intent,
                    confidence = payload.confidence,
                    requiresConfirmation = isConfirmation
                )

                _chatMessages.value = _chatMessages.value + jarvisMsg

                if (isConfirmation) {
                    _pendingConfirmation.value = jarvisMsg
                } else {
                    _pendingConfirmation.value = null
                }

                // Vocalize response if TTS is enabled and background voice service is NOT managing TTS
                if (_ttsEnabled.value && ttsManager != null && !com.jarvis.client.voice.JarvisVoiceService.isRunning.value) {
                    ttsManager.speak(text = payload.text, spokenText = payload.spokenText)
                }
            }
        }

        // Observe speech recognition transcriptions ONLY when background voice service is not running
        speechRecognitionManager?.let { recognizer ->
            scope.launch {
                recognizer.transcriptionResults.collect { recognizedText ->
                    if (!com.jarvis.client.voice.JarvisVoiceService.isRunning.value) {
                        Log.i(tag, "Received manual voice transcription: '$recognizedText' -> Sending via WebSocket")
                        sendMessage(recognizedText)
                    }
                }
            }
        }

        // Observe WebSocket state transitions
        scope.launch {
            webSocketClient.connectionState.collect { state ->
                Log.i(tag, "Observed connection state transition: $state")
                if (state.isOnline) {
                    registerDeviceOnBackend()
                } else {
                    heartbeatManager.stopHeartbeat()
                }
            }
        }

        // Observe errors
        scope.launch {
            webSocketClient.errorEvents.collect { err ->
                val errMsg = ChatMessage(
                    sender = MessageSender.SYSTEM,
                    text = "System [${err.code}]: ${err.message}"
                )
                _chatMessages.value = _chatMessages.value + errMsg
            }
        }

        // Observe pong
        scope.launch {
            webSocketClient.pongEvents.collect {
                Log.d(tag, "Received Pong from backend.")
            }
        }
    }

    fun start() {
        webSocketClient.connect()
    }

    fun stop() {
        ttsManager?.stopSpeaking()
        speechRecognitionManager?.stopListening()
        heartbeatManager.stopHeartbeat()
        webSocketClient.disconnect()
    }

    fun sendPing() {
        webSocketClient.sendPing()
    }

    fun setTtsEnabled(enabled: Boolean) {
        _ttsEnabled.value = enabled
        if (!enabled) {
            ttsManager?.stopSpeaking()
        }
    }

    fun startVoiceListening() {
        ttsManager?.stopSpeaking()
        speechRecognitionManager?.startListening()
    }

    fun stopVoiceListening() {
        speechRecognitionManager?.stopListening()
    }

    fun cancelVoiceListening() {
        speechRecognitionManager?.cancel()
    }

    fun stopSpeaking() {
        ttsManager?.stopSpeaking()
    }

    fun sendMessage(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) return

        // If currently vocalizing, stop speaking before processing new input
        ttsManager?.stopSpeaking()

        val userMsg = ChatMessage(
            sender = MessageSender.USER,
            text = trimmed
        )
        _chatMessages.value = _chatMessages.value + userMsg

        val sent = webSocketClient.sendChatMessage(trimmed)
        if (!sent) {
            val failedMsg = ChatMessage(
                sender = MessageSender.SYSTEM,
                text = "Failed to send message: client is currently disconnected."
            )
            _chatMessages.value = _chatMessages.value + failedMsg
        }
    }

    fun sendVoiceTurn(text: String, wakeProfileId: String? = null, wakePhrase: String? = null) {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) return

        ttsManager?.stopSpeaking()

        val userMsg = ChatMessage(
            sender = MessageSender.USER,
            text = trimmed
        )
        _chatMessages.value = _chatMessages.value + userMsg

        val sent = webSocketClient.sendVoiceTurn(
            text = trimmed,
            wakeProfileId = wakeProfileId,
            wakePhrase = wakePhrase
        )
        if (!sent) {
            val failedMsg = ChatMessage(
                sender = MessageSender.SYSTEM,
                text = "Failed to send voice turn: client is currently disconnected."
            )
            _chatMessages.value = _chatMessages.value + failedMsg
        }
    }

    fun confirmAction(approved: Boolean) {
        val responseText = if (approved) "yes" else "no"
        _pendingConfirmation.value = null
        sendMessage(responseText)
    }

    fun computeCurrentCapabilities(): List<String> {
        val capabilities = settingsManager.defaultCapabilities.toMutableList()
        if (JarvisAccessibilityService.isServiceEnabled(settingsManager.context)) {
            if (!capabilities.contains("accessibility")) {
                capabilities.add("accessibility")
            }
        }
        return capabilities
    }

    fun registerDeviceOnBackend() {
        scope.launch {
            val capabilities = computeCurrentCapabilities()
            val req = DeviceRegisterRequest(
                deviceId = settingsManager.deviceId,
                name = settingsManager.deviceName,
                deviceType = "android",
                platform = "android",
                capabilities = capabilities,
                metadata = mapOf("model" to "Vivo V29", "client" to "Jarvis Mobile Android")
            )
            val result = apiClient.registerDevice(req)
            result.onSuccess {
                lastRegisteredCapabilities = capabilities
                Log.i(tag, "Device registered successfully with backend: ${it.deviceId} (${it.name}), capabilities=$capabilities")
                heartbeatManager.startHeartbeat()
            }.onFailure {
                Log.w(tag, "Device registration failed: ${it.message}")
            }
        }
    }

    fun checkAndRefreshCapabilities() {
        if (!webSocketClient.connectionState.value.isOnline) {
            return
        }
        val current = computeCurrentCapabilities()
        if (lastRegisteredCapabilities == null || lastRegisteredCapabilities != current) {
            Log.i(tag, "Capabilities set changed ($lastRegisteredCapabilities -> $current). Refreshing backend registration.")
            registerDeviceOnBackend()
        }
    }

    fun updateConfiguration(
        backendUrl: String,
        userId: String,
        deviceId: String,
        deviceName: String,
        authToken: String
    ) {
        settingsManager.backendBaseUrl = backendUrl
        settingsManager.userId = userId
        settingsManager.deviceId = deviceId
        settingsManager.deviceName = deviceName
        settingsManager.authToken = authToken

        // Reconnect with new settings
        stop()
        start()
    }
}
