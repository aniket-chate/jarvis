package com.jarvis.client.device

import android.util.Log
import com.jarvis.client.network.JarvisApiClient
import com.jarvis.client.settings.JarvisSettingsManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Manages periodic device heartbeat transmission while the Android client is connected.
 */
class DeviceHeartbeatManager(
    private val apiClient: JarvisApiClient,
    private val settingsManager: JarvisSettingsManager,
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.IO + Job())
) {

    private val tag = "DeviceHeartbeatManager"
    private var heartbeatJob: Job? = null

    var onHeartbeatTick: (() -> Unit)? = null

    fun startHeartbeat(intervalSeconds: Long = 25L) {
        if (heartbeatJob?.isActive == true) {
            return
        }

        Log.i(tag, "Starting device heartbeat every ${intervalSeconds}s for device '${settingsManager.deviceId}'")
        heartbeatJob = scope.launch {
            while (isActive) {
                try {
                    onHeartbeatTick?.invoke()
                    val result = apiClient.sendHeartbeat(settingsManager.deviceId)
                    result.onSuccess {
                        Log.d(tag, "Device heartbeat sent successfully: ${it.lastSeen}")
                    }.onFailure {
                        Log.w(tag, "Device heartbeat failed: ${it.message}")
                    }
                } catch (e: Exception) {
                    Log.w(tag, "Error during heartbeat transmission: ${e.message}")
                }
                delay(intervalSeconds * 1000L)
            }
        }
    }

    fun stopHeartbeat() {
        if (heartbeatJob?.isActive == true) {
            Log.i(tag, "Stopping device heartbeat.")
            heartbeatJob?.cancel()
            heartbeatJob = null
        }
    }
}
