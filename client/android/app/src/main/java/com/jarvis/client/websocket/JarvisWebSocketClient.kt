package com.jarvis.client.websocket

import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.jarvis.client.model.ConnectionState
import com.jarvis.client.model.WsAuthMessage
import com.jarvis.client.model.WsAuthSuccess
import com.jarvis.client.model.WsChatRequest
import com.jarvis.client.model.WsChatResponse
import com.jarvis.client.model.WsError
import com.jarvis.client.model.WsPingMessage
import com.jarvis.client.model.WsPong
import com.jarvis.client.model.WsSkillRequest
import com.jarvis.client.model.WsSkillResult
import com.jarvis.client.model.WsVoiceResponse
import com.jarvis.client.model.WsVoiceTurn
import com.jarvis.client.settings.JarvisSettingsManager
import com.jarvis.client.skill.AndroidSkillExecutor
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.util.concurrent.TimeUnit
import kotlin.math.min

/**
 * WebSocket client communicating with Jarvis Backend API /api/v1/ws.
 */
class JarvisWebSocketClient(
    private val settingsManager: JarvisSettingsManager,
    var skillExecutor: AndroidSkillExecutor? = null,
    private val okHttpClient: OkHttpClient = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS) // Indefinite read timeout for WebSockets
        .pingInterval(30, TimeUnit.SECONDS)
        .build(),
    private val gson: Gson = Gson(),
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.IO + Job())
) : WebSocketListener() {

    private val tag = "JarvisWebSocket"

    private var webSocket: WebSocket? = null
    private var reconnectJob: Job? = null
    private var isManualDisconnect = false
    private var reconnectAttempts = 0

    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    private val _chatResponses = MutableSharedFlow<WsChatResponse>()
    val chatResponses: SharedFlow<WsChatResponse> = _chatResponses.asSharedFlow()

    private val _voiceResponses = MutableSharedFlow<WsVoiceResponse>()
    val voiceResponses: SharedFlow<WsVoiceResponse> = _voiceResponses.asSharedFlow()

    private val _pongEvents = MutableSharedFlow<WsPong>()
    val pongEvents: SharedFlow<WsPong> = _pongEvents.asSharedFlow()

    private val _authEvents = MutableSharedFlow<WsAuthSuccess>()
    val authEvents: SharedFlow<WsAuthSuccess> = _authEvents.asSharedFlow()

    private val _errorEvents = MutableSharedFlow<WsError>()
    val errorEvents: SharedFlow<WsError> = _errorEvents.asSharedFlow()

    fun connect() {
        if (_connectionState.value == ConnectionState.CONNECTED || _connectionState.value == ConnectionState.AUTHENTICATED) {
            Log.d(tag, "WebSocket already connected.")
            return
        }

        isManualDisconnect = false
        _connectionState.value = ConnectionState.CONNECTING

        val wsUrl = settingsManager.getWebSocketUrl()
        Log.i(tag, "Connecting WebSocket to: $wsUrl")

        val request = Request.Builder()
            .url(wsUrl)
            .build()

        webSocket = okHttpClient.newWebSocket(request, this)
    }

    fun disconnect() {
        isManualDisconnect = true
        reconnectJob?.cancel()
        webSocket?.close(1000, "Client disconnect")
        webSocket = null
        _connectionState.value = ConnectionState.DISCONNECTED
        reconnectAttempts = 0
        Log.i(tag, "WebSocket manually disconnected.")
    }

    fun sendPing(): Boolean {
        val pingMsg = WsPingMessage()
        val json = gson.toJson(pingMsg)
        return sendRaw(json)
    }

    fun sendAuth(token: String): Boolean {
        val authMsg = WsAuthMessage(token = token, deviceId = settingsManager.deviceId)
        val json = gson.toJson(authMsg)
        return sendRaw(json)
    }

    fun sendChatMessage(message: String): Boolean {
        val chatReq = WsChatRequest(
            message = message,
            deviceId = settingsManager.deviceId,
            sessionId = settingsManager.sessionId
        )
        val json = gson.toJson(chatReq)
        return sendRaw(json)
    }

    fun sendVoiceTurn(
        text: String,
        wakeProfileId: String? = null,
        wakePhrase: String? = null
    ): Boolean {
        val turnId = "vt_${java.util.UUID.randomUUID().toString().take(8)}"
        val voiceTurn = WsVoiceTurn(
            type = "voice_turn",
            voiceTurnId = turnId,
            userId = settingsManager.userId,
            deviceId = settingsManager.deviceId,
            wakeProfileId = wakeProfileId,
            wakePhrase = wakePhrase,
            text = text,
            timestamp = System.currentTimeMillis().toString()
        )
        val json = gson.toJson(voiceTurn)
        val sent = sendRaw(json)
        if (sent) {
            Log.i(tag, "VOICE_STATE: VOICE_TURN_SENT $turnId | text='$text' | wake='$wakePhrase' (profile=$wakeProfileId)")
        }
        return sent
    }

    private fun sendRaw(text: String): Boolean {
        val ws = webSocket
        val currentState = _connectionState.value
        if (ws == null || (currentState != ConnectionState.CONNECTED &&
                           currentState != ConnectionState.AUTHENTICATING &&
                           currentState != ConnectionState.AUTHENTICATED)) {
            Log.w(tag, "Cannot send message, WebSocket not connected (state: $currentState)")
            return false
        }
        return ws.send(text)
    }

    // WebSocketListener overrides
    override fun onOpen(webSocket: WebSocket, response: Response) {
        Log.i(tag, "WebSocket successfully opened.")
        reconnectAttempts = 0

        // Authenticate immediately if required
        val token = settingsManager.authToken.ifBlank { settingsManager.userId }
        if (token.isNotBlank()) {
            _connectionState.value = ConnectionState.AUTHENTICATING
            sendAuth(token)
        } else {
            _connectionState.value = ConnectionState.AUTHENTICATED
        }
    }

    override fun onMessage(webSocket: WebSocket, text: String) {
        Log.d(tag, "Received WebSocket message: $text")
        scope.launch {
            try {
                val jsonObject: JsonObject = JsonParser.parseString(text).asJsonObject
                val msgType = if (jsonObject.has("type")) jsonObject.get("type").asString else ""

                when (msgType) {
                    "auth_success" -> {
                        val authSuccess = gson.fromJson(jsonObject, WsAuthSuccess::class.java)
                        _connectionState.value = ConnectionState.AUTHENTICATED
                        _authEvents.emit(authSuccess)
                    }
                    "pong" -> {
                        _pongEvents.emit(WsPong())
                    }
                    "chat_response" -> {
                        val chatResp = gson.fromJson(jsonObject, WsChatResponse::class.java)
                        _chatResponses.emit(chatResp)
                    }
                    "voice_response" -> {
                        val voiceResp = gson.fromJson(jsonObject, WsVoiceResponse::class.java)
                        val respId = voiceResp.voiceTurnId ?: voiceResp.requestId ?: "unknown"
                        Log.i(tag, "VOICE_STATE: VOICE_RESPONSE_RECEIVED $respId | status='${voiceResp.status}' | text='${voiceResp.text}'")
                        _voiceResponses.emit(voiceResp)
                    }
                    "skill_request" -> {
                        val skillReq = gson.fromJson(jsonObject, WsSkillRequest::class.java)
                        Log.i(tag, "Handling incoming skill request: ${skillReq.skillId} (req_id=${skillReq.requestId})")
                        val result = skillExecutor?.execute(
                            requestId = skillReq.requestId,
                            skillId = skillReq.skillId,
                            parameters = skillReq.parameters
                        ) ?: WsSkillResult(
                            requestId = skillReq.requestId,
                            success = false,
                            error = "No AndroidSkillExecutor attached to client"
                        )
                        val resultJson = gson.toJson(result)
                        webSocket.send(resultJson)
                    }
                    "error" -> {
                        val err = gson.fromJson(jsonObject, WsError::class.java)
                        if (err.code == "auth_failed") {
                            _connectionState.value = ConnectionState.ERROR
                        }
                        _errorEvents.emit(err)
                    }
                    else -> {
                        Log.w(tag, "Unhandled message type: $msgType")
                    }
                }
            } catch (e: Exception) {
                Log.e(tag, "Error parsing WebSocket message payload: ${e.message}", e)
                _errorEvents.emit(WsError(code = "parse_error", message = e.message ?: "Invalid JSON"))
            }
        }
    }

    override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
        Log.i(tag, "WebSocket closing: $code / $reason")
        webSocket.close(1000, null)
        _connectionState.value = ConnectionState.DISCONNECTED
    }

    override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
        Log.i(tag, "WebSocket closed: $code / $reason")
        _connectionState.value = ConnectionState.DISCONNECTED
        if (!isManualDisconnect) {
            scheduleReconnect()
        }
    }

    override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
        Log.e(tag, "WebSocket failure: ${t.message}", t)
        _connectionState.value = ConnectionState.ERROR
        if (!isManualDisconnect) {
            scheduleReconnect()
        }
    }

    private fun scheduleReconnect() {
        reconnectJob?.cancel()
        reconnectJob = scope.launch {
            _connectionState.value = ConnectionState.RECONNECTING
            reconnectAttempts++
            // Non-aggressive exponential backoff: 2s, 4s, 8s, max 16s
            val delaySeconds = min(2 * (1 shl (reconnectAttempts - 1)), 16)
            Log.i(tag, "Scheduling reconnection attempt #$reconnectAttempts in ${delaySeconds}s...")
            delay(delaySeconds * 1000L)
            connect()
        }
    }
}
