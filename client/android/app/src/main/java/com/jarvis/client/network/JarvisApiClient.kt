package com.jarvis.client.network

import com.google.gson.Gson
import com.jarvis.client.model.DeviceRegisterRequest
import com.jarvis.client.model.DeviceResponse
import com.jarvis.client.model.HeartbeatResponse
import com.jarvis.client.settings.JarvisSettingsManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * REST API client for Jarvis backend operations (Health, Device Registration, Heartbeat).
 */
class JarvisApiClient(
    private val settingsManager: JarvisSettingsManager,
    private val httpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build(),
    private val gson: Gson = Gson()
) {

    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    private fun buildRequestHeaders(builder: Request.Builder): Request.Builder {
        val token = settingsManager.authToken
        if (token.isNotBlank()) {
            builder.addHeader("Authorization", "Bearer $token")
        } else {
            builder.addHeader("X-User-ID", settingsManager.userId)
        }
        return builder
    }

    suspend fun checkHealth(): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val url = "${settingsManager.backendBaseUrl.trimEnd('/')}/api/v1/health"
            val request = Request.Builder().url(url).get().build()
            httpClient.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    Result.success(true)
                } else {
                    Result.failure(Exception("Health check returned status ${response.code}"))
                }
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun registerDevice(requestData: DeviceRegisterRequest): Result<DeviceResponse> =
        withContext(Dispatchers.IO) {
            try {
                val url = "${settingsManager.backendBaseUrl.trimEnd('/')}/api/v1/devices/register"
                val jsonBody = gson.toJson(requestData)
                val body = jsonBody.toRequestBody(jsonMediaType)

                val reqBuilder = Request.Builder().url(url).post(body)
                buildRequestHeaders(reqBuilder)

                httpClient.newCall(reqBuilder.build()).execute().use { response ->
                    val respBody = response.body?.string() ?: ""
                    if (response.isSuccessful || response.code == 200 || response.code == 201) {
                        val deviceResp = gson.fromJson(respBody, DeviceResponse::class.java)
                        Result.success(deviceResp)
                    } else {
                        Result.failure(Exception("Registration failed (${response.code}): $respBody"))
                    }
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    suspend fun sendHeartbeat(deviceId: String): Result<HeartbeatResponse> =
        withContext(Dispatchers.IO) {
            try {
                val url = "${settingsManager.backendBaseUrl.trimEnd('/')}/api/v1/devices/$deviceId/heartbeat"
                val body = "".toRequestBody(jsonMediaType)

                val reqBuilder = Request.Builder().url(url).post(body)
                buildRequestHeaders(reqBuilder)

                httpClient.newCall(reqBuilder.build()).execute().use { response ->
                    val respBody = response.body?.string() ?: ""
                    if (response.isSuccessful) {
                        val heartbeatResp = gson.fromJson(respBody, HeartbeatResponse::class.java)
                        Result.success(heartbeatResp)
                    } else {
                        Result.failure(Exception("Heartbeat failed (${response.code}): $respBody"))
                    }
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
}
