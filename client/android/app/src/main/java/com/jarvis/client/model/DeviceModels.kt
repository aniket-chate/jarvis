package com.jarvis.client.model

import com.google.gson.annotations.SerializedName

/** Request/response models matching server.app DeviceRegisterRequest and gateway registry payloads. */
data class DeviceRegisterRequest(
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("name") val name: String,
    @SerializedName("client_type") val clientType: String = "phone",
    @SerializedName("ip_address") val ipAddress: String? = null,
    @SerializedName("capabilities") val capabilities: List<String>? = null
)

data class DeviceResponse(
    @SerializedName("device_id") val deviceId: String = "",
    @SerializedName("name") val name: String = "",
    @SerializedName("client_type") val clientType: String = "",
    @SerializedName("ip_address") val ipAddress: String? = null,
    @SerializedName("capabilities") val capabilities: List<String> = emptyList(),
    @SerializedName("trust_state") val trustState: String = "untrusted",
    @SerializedName("online") val online: Boolean = false,
    @SerializedName("latency_ms") val latencyMs: Double? = null,
    @SerializedName("has_active_ws") val hasActiveWebSocket: Boolean = false,
    @SerializedName("last_seen_epoch") val lastSeenEpoch: Double? = null,
    @SerializedName("paired_at") val pairedAt: String? = null
) {
    val isOnline: Boolean
        get() = online
}

/** The gateway heartbeat response is {status: alive|unknown_device, device_id: ...}. */
data class HeartbeatResponse(
    @SerializedName("device_id") val deviceId: String = "",
    @SerializedName("status") val status: String = "unknown_device"
) {
    val success: Boolean
        get() = status == "alive"
}
