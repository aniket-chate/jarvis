package com.jarvis.client.device

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import com.jarvis.client.JarvisApp
import com.jarvis.client.R
import android.content.pm.ServiceInfo

/**
 * Keeps the JARVIS device-mesh connection alive when the app UI is not visible.
 *
 * The user explicitly starts/stops this service. Android shows a persistent notification
 * while it is active. It reuses the application's single Repository/WebSocket instance.
 */
class JarvisConnectionService : Service() {
    private val tag = "JarvisConnectionService"

    override fun onCreate() {
        super.onCreate()
        createChannel()
        val notification = buildNotification()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceCompat.startForeground(
                this,
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
        JarvisApp.instance.repository.start()
        Log.i(tag, "JARVIS background connection service started.")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopConnectionService()
            return START_NOT_STICKY
        }
        JarvisApp.instance.repository.start()
        return START_STICKY
    }

    override fun onDestroy() {
        // Android may recreate/destroy this service independently of the Activity/assistant.
        // Keep the shared repository alive unless the user explicitly stops the connection.
        Log.i(tag, "JARVIS background connection service destroyed.")
        super.onDestroy()
    }

    private fun stopConnectionService() {
        JarvisApp.instance.repository.stop()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(
                NotificationChannel(
                    CHANNEL_ID,
                    "JARVIS Device Connection",
                    NotificationManager.IMPORTANCE_LOW
                ).apply {
                    description = "Keeps the JARVIS device connection available in the background."
                    setShowBadge(false)
                }
            )
        }
    }

    private fun buildNotification(): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_mic)
            .setContentTitle("JARVIS Device Connection")
            .setContentText("Maintaining the JARVIS device connection in the background.")
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val ACTION_STOP = "com.jarvis.client.device.STOP_CONNECTION"
        private const val CHANNEL_ID = "jarvis_device_connection"
        private const val NOTIFICATION_ID = 4101
    }
}
