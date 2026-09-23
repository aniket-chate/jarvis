package com.jarvis.client.model

import com.google.gson.annotations.SerializedName

/**
 * WebSocket Protocol Data Models matching Jarvis Phase 4 & 5 Backend specifications.
 */

// Outgoing messages
data class WsAuthMessage(
    @SerializedName("type") val type: String = "auth",
    @SerializedName("token") val token: String,
    @SerializedName("device_id") val deviceId: String? = null
)

data class WsPingMessage(
    @SerializedName("type") val type: String = "ping"
)

data class WsChatRequest(
    @SerializedName("type") val type: String = "chat",
    @SerializedName("message") val message: String,
    @SerializedName("device_id") val deviceId: String? = null,
    @SerializedName("session_id") val sessionId: String? = null
)

data class WakeWordEvent(
    val userId: String,
    val profileId: String,
    val phrase: String,
    val timestamp: Long = System.currentTimeMillis(),
    val confidence: Float = 1.0f,
    val source: String = "sherpa_kws"
)

data class WsVoiceTurn(
    @SerializedName("type") val type: String = "voice_turn",
    @SerializedName("voice_turn_id") val voiceTurnId: String? = null,
    @SerializedName("user_id") val userId: String? = null,
    @SerializedName("device_id") val deviceId: String? = null,
    @SerializedName("wake_profile_id") val wakeProfileId: String? = null,
    @SerializedName("wake_phrase") val wakePhrase: String? = null,
    @SerializedName("text") val text: String,
    @SerializedName("timestamp") val timestamp: String? = null
)

data class WsSkillResult(
    @SerializedName("type") val type: String = "skill_result",
    @SerializedName("request_id") val requestId: String,
    @SerializedName("success") val success: Boolean,
    @SerializedName("result") val result: Any? = null,
    @SerializedName("error") val error: String? = null
)

// Incoming messages
data class WsAuthSuccess(
    @SerializedName("type") val type: String = "auth_success",
    @SerializedName("user_id") val userId: String,
    @SerializedName("username") val username: String
)

data class WsPong(
    @SerializedName("type") val type: String = "pong"
)

data class WsError(
    @SerializedName("type") val type: String = "error",
    @SerializedName("code") val code: String,
    @SerializedName("message") val message: String
)

data class WsSkillRequest(
    @SerializedName("type") val type: String = "skill_request",
    @SerializedName("request_id") val requestId: String,
    @SerializedName("skill_id") val skillId: String,
    @SerializedName("parameters") val parameters: Map<String, Any>? = null
)

data class ActionResultData(
    @SerializedName("action_name") val actionName: String,
    @SerializedName("success") val success: Boolean,
    @SerializedName("result") val result: Any? = null,
    @SerializedName("error") val error: String? = null
)

data class ChatResponsePayload(
    @SerializedName("text") val text: String,
    @SerializedName("spoken_text") val spokenText: String? = null,
    @SerializedName("intent") val intent: String = "unknown",
    @SerializedName("confidence") val confidence: Double = 1.0,
    @SerializedName("requires_confirmation") val requiresConfirmation: Boolean = false,
    @SerializedName("is_exit") val isExit: Boolean = false,
    @SerializedName("action_result") val actionResult: ActionResultData? = null,
    @SerializedName("error") val error: String? = null,
    @SerializedName("metadata") val metadata: Map<String, Any>? = null
)

data class WsChatResponse(
    @SerializedName("type") val type: String = "chat_response",
    @SerializedName("payload") val payload: ChatResponsePayload
)

data class WsVoiceResponse(
    @SerializedName("type") val type: String = "voice_response",
    @SerializedName("voice_turn_id") val voiceTurnId: String? = null,
    @SerializedName("request_id") val requestId: String? = null,
    @SerializedName("status") val status: String = "success",
    @SerializedName("text") val text: String = "",
    @SerializedName("spoken_response") val spokenResponse: String? = null,
    @SerializedName("requires_confirmation") val requiresConfirmation: Boolean = false,
    @SerializedName("pending_action_id") val pendingActionId: String? = null,
    @SerializedName("capability_id") val capabilityId: String? = null,
    @SerializedName("explanation") val explanation: Map<String, Any>? = null,
    @SerializedName("action_result") val actionResult: ActionResultData? = null,
    @SerializedName("error") val error: String? = null
)
