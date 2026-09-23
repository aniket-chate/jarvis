package com.jarvis.client.model

import com.google.gson.annotations.SerializedName

/**
 * Device registration and status models matching backend DeviceRegisterRequest and DeviceResponse.
 */
data class DeviceRegisterRequest(
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("name") val name: String,
    @SerializedName("device_type") val deviceType: String = "android",
    @SerializedName("platform") val platform: String = "android",
    @SerializedName("capabilities") val capabilities: List<String>,
    @SerializedName("metadata") val metadata: Map<String, Any>? = null
)

data class DeviceResponse(
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("user_id") val userId: String,
    @SerializedName("name") val name: String,
    @SerializedName("device_type") val deviceType: String,
    @SerializedName("platform") val platform: String,
    @SerializedName("capabilities") val capabilities: List<String>,
    @SerializedName("status") val status: String,
    @SerializedName("last_seen") val lastSeen: String,
    @SerializedName("metadata") val metadata: Map<String, Any>? = null
) {
    val isOnline: Boolean
        get() = status.equals("online", ignoreCase = true)
}

data class HeartbeatResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("status") val status: String,
    @SerializedName("last_seen") val lastSeen: String
)
