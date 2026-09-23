package com.jarvis.client.skill

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.media.AudioManager
import android.net.Uri
import android.os.Build
import android.os.SystemClock
import android.provider.AlarmClock
import android.provider.MediaStore
import android.provider.Settings
import android.util.Log
import android.view.KeyEvent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.jarvis.client.R
import com.jarvis.client.accessibility.ForegroundAppResult
import com.jarvis.client.accessibility.JarvisAccessibilityService
import com.jarvis.client.accessibility.NavigationResult
import com.jarvis.client.accessibility.ScreenStateResult
import com.jarvis.client.model.WsSkillResult

/**
 * Safe, allowlisted skill executor for Android client.
 * Strictly executes only approved device actions without shell or arbitrary code execution.
 */
class AndroidSkillExecutor(private val context: Context) {

    private val tag = "AndroidSkillExecutor"

    companion object {
        val APP_PACKAGE_MAP: Map<String, String> = mapOf(
            "youtube" to "com.google.android.youtube",
            "youtube_music" to "com.google.android.apps.youtube.music",
            "music" to "com.google.android.apps.youtube.music",
            "chrome" to "com.android.chrome",
            "browser" to "com.android.chrome",
            "settings" to "com.android.settings",
            "camera" to "com.android.camera",
            "clock" to "com.google.android.deskclock",
            "calculator" to "com.google.android.calculator",
            "calendar" to "com.google.android.calendar",
            "gallery" to "com.google.android.apps.photos",
            "photos" to "com.google.android.apps.photos",
            "maps" to "com.google.android.apps.maps",
            "gmail" to "com.google.android.gm",
            "files" to "com.google.android.apps.nbu.files"
        )

        val ALLOWLISTED_APPS = setOf(
            "youtube",
            "youtube_music",
            "settings",
            "camera",
            "browser",
            "chrome",
            "clock",
            "calculator",
            "music",
            "calendar",
            "gallery",
            "photos",
            "maps",
            "gmail",
            "files"
        )

        val ALLOWLISTED_MEDIA_ACTIONS = setOf(
            "play",
            "pause",
            "resume",
            "next",
            "previous",
            "stop"
        )

        private const val NOTIFICATION_CHANNEL_ID = "jarvis_notifications"
        private const val NOTIFICATION_CHANNEL_NAME = "Jarvis Alerts"
    }

    init {
        createNotificationChannel()
    }

    fun execute(requestId: String, skillId: String, parameters: Map<String, Any>?): WsSkillResult {
        Log.i(tag, "Executing skill '$skillId' (req_id=$requestId) with params: $parameters")

        return when (skillId.trim().lowercase()) {
            "open_app", "app.open", "openapp", "launch_app" -> executeOpenApp(requestId, parameters)
            "media_control", "media.play", "media.control" -> executeMediaControl(requestId, parameters)
            "send_notification", "notification.send" -> executeNotification(requestId, parameters)
            "read_screen_state", "screen.read" -> executeReadScreenState(requestId, parameters)
            "press_back", "device.navigate_back", "device.navigate.back" -> executePressBack(requestId, parameters)
            "press_home", "device.navigate_home", "device.navigate.home" -> executePressHome(requestId, parameters)
            "get_foreground_app" -> executeGetForegroundApp(requestId, parameters)
            "accessibility_service_status" -> executeAccessibilityStatus(requestId, parameters)
            "flashlight.toggle", "flashlight_toggle", "toggle_flashlight", "flashlight" -> executeFlashlight(requestId, parameters)
            else -> {
                Log.w(tag, "Unknown skill rejected: $skillId")
                WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = "Unknown or unsupported skill: '$skillId'"
                )
            }
        }
    }

    private fun executeReadScreenState(requestId: String, params: Map<String, Any>?): WsSkillResult {
        Log.i(tag, "Executing read_screen_state (req_id=$requestId)")

        if (!JarvisAccessibilityService.isServiceEnabled()) {
            Log.w(tag, "read_screen_state failed: JarvisAccessibilityService is not enabled")
            return WsSkillResult(
                requestId = requestId,
                success = false,
                error = "Accessibility service is not enabled. Please enable Jarvis in Android Accessibility Settings to read the screen.",
                result = mapOf(
                    "status" to "disabled",
                    "action_required" to "enable_accessibility_service"
                )
            )
        }

        return when (val screenResult = JarvisAccessibilityService.readScreenState(context)) {
            is ScreenStateResult.Success -> {
                Log.i(
                    tag,
                    "read_screen_state successful for ${screenResult.state.foregroundApp} (${screenResult.state.nodeCount} nodes inspected)"
                )
                WsSkillResult(
                    requestId = requestId,
                    success = true,
                    result = screenResult.state.toMap()
                )
            }
            is ScreenStateResult.Locked -> {
                Log.w(tag, "read_screen_state blocked: device is locked")
                WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = screenResult.message,
                    result = mapOf("status" to "device_locked")
                )
            }
            is ScreenStateResult.Error -> {
                Log.e(tag, "read_screen_state error: ${screenResult.error}")
                WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = screenResult.error
                )
            }
        }
    }

    private fun executePressBack(requestId: String, params: Map<String, Any>?): WsSkillResult {
        Log.i(tag, "Executing press_back (req_id=$requestId)")
        return when (val res = JarvisAccessibilityService.pressBack(context)) {
            is NavigationResult.Success -> {
                WsSkillResult(
                    requestId = requestId,
                    success = true,
                    result = mapOf("action" to "press_back", "status" to "executed")
                )
            }
            is NavigationResult.Locked -> {
                WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = res.message,
                    result = mapOf("status" to "device_locked")
                )
            }
            is NavigationResult.Disabled -> {
                WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = res.message,
                    result = mapOf("status" to "disabled")
                )
            }
            is NavigationResult.Error -> {
                WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = res.error
                )
            }
        }
    }

    private fun executePressHome(requestId: String, params: Map<String, Any>?): WsSkillResult {
        Log.i(tag, "Executing press_home (req_id=$requestId)")
        return when (val res = JarvisAccessibilityService.pressHome(context)) {
            is NavigationResult.Success -> {
                WsSkillResult(
                    requestId = requestId,
                    success = true,
                    result = mapOf("action" to "press_home", "status" to "executed")
                )
            }
            is NavigationResult.Locked -> {
                WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = res.message,
                    result = mapOf("status" to "device_locked")
                )
            }
            is NavigationResult.Disabled -> {
                WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = res.message,
                    result = mapOf("status" to "disabled")
                )
            }
            is NavigationResult.Error -> {
                WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = res.error
                )
            }
        }
    }

    private fun executeGetForegroundApp(requestId: String, params: Map<String, Any>?): WsSkillResult {
        Log.i(tag, "Executing get_foreground_app (req_id=$requestId)")
        return when (val res = JarvisAccessibilityService.getForegroundApp(context)) {
            is ForegroundAppResult.Success -> {
                WsSkillResult(
                    requestId = requestId,
                    success = true,
                    result = res.toMap()
                )
            }
            is ForegroundAppResult.Locked -> {
                WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = res.message,
                    result = mapOf("locked" to true, "status" to "device_locked")
                )
            }
            is ForegroundAppResult.Disabled -> {
                WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = res.message,
                    result = mapOf("status" to "disabled")
                )
            }
            is ForegroundAppResult.Error -> {
                WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = res.error
                )
            }
        }
    }

    private fun executeAccessibilityStatus(requestId: String, params: Map<String, Any>?): WsSkillResult {
        val isEnabled = JarvisAccessibilityService.isServiceEnabled()
        Log.i(tag, "Executing accessibility_service_status (req_id=$requestId): enabled=$isEnabled")
        return WsSkillResult(
            requestId = requestId,
            success = true,
            result = mapOf("enabled" to isEnabled)
        )
    }

    private fun executeOpenApp(requestId: String, params: Map<String, Any>?): WsSkillResult {
        val rawAppName = params?.get("app")?.toString()?.trim()
        if (rawAppName.isNullOrEmpty()) {
            return WsSkillResult(
                requestId = requestId,
                success = false,
                error = "Missing required parameter: 'app'"
            )
        }

        val appName = rawAppName.lowercase().replace(" ", "_")
        Log.i(tag, "open_app requested: $rawAppName (normalized: $appName)")

        if (appName !in ALLOWLISTED_APPS) {
            Log.w(tag, "Application '$appName' is not in the allowlist.")
            return WsSkillResult(
                requestId = requestId,
                success = false,
                error = "Application '$appName' is not in the allowlist"
            )
        }

        return try {
            val pm = context.packageManager
            val targetPackage = APP_PACKAGE_MAP[appName]
            if (targetPackage != null) {
                Log.i(tag, "Resolved app $appName -> $targetPackage")
            }

            var launchIntent: Intent? = null

            // 1. Try resolving package launch intent from PackageManager
            if (!targetPackage.isNullOrEmpty()) {
                launchIntent = pm.getLaunchIntentForPackage(targetPackage)
            }

            // 2. Fallback to standard system action intent if package launch intent was not found
            if (launchIntent == null) {
                Log.i(tag, "No package launch intent for '$targetPackage', evaluating fallback intent for '$appName'")
                launchIntent = when (appName) {
                    "settings" -> Intent(Settings.ACTION_SETTINGS)
                    "camera" -> Intent(MediaStore.ACTION_IMAGE_CAPTURE)
                    "clock" -> Intent(AlarmClock.ACTION_SHOW_ALARMS)
                    "browser", "chrome" -> Intent(Intent.ACTION_VIEW, Uri.parse("https://www.google.com"))
                    "music", "youtube_music" -> Intent.makeMainSelectorActivity(
                        Intent.ACTION_MAIN,
                        Intent.CATEGORY_APP_MUSIC
                    )
                    else -> null
                }
            }

            if (launchIntent == null) {
                Log.w(tag, "Failed to resolve launch intent for app '$appName' (package: $targetPackage)")
                return WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = "Application '$appName' is not installed or cannot be launched"
                )
            }

            // Set required flags for launching activity from background/service context
            launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED)

            val resolvedComponent = launchIntent.component?.className ?: targetPackage ?: launchIntent.action
            Log.i(tag, "Launch intent resolved: $resolvedComponent")
            Log.i(tag, "Calling startActivity()")

            context.startActivity(launchIntent)

            Log.i(tag, "startActivity() completed successfully")

            WsSkillResult(
                requestId = requestId,
                success = true,
                result = mapOf(
                    "app" to appName,
                    "package" to (targetPackage ?: "system_intent"),
                    "status" to "launched"
                )
            )
        } catch (e: ActivityNotFoundException) {
            Log.e(tag, "Failed to launch app '$appName': Activity not found: ${e.message}", e)
            WsSkillResult(
                requestId = requestId,
                success = false,
                error = "Activity not found for '$appName': ${e.message}"
            )
        } catch (e: SecurityException) {
            Log.e(tag, "Failed to launch app '$appName': Security exception: ${e.message}", e)
            WsSkillResult(
                requestId = requestId,
                success = false,
                error = "Permission denied launching '$appName': ${e.message}"
            )
        } catch (e: Exception) {
            Log.e(tag, "Failed to launch app '$appName': ${e.message}", e)
            WsSkillResult(
                requestId = requestId,
                success = false,
                error = "Error launching '$appName': ${e.message}"
            )
        }
    }

    private fun executeMediaControl(requestId: String, params: Map<String, Any>?): WsSkillResult {
        val action = params?.get("action")?.toString()?.trim()?.lowercase()
        if (action.isNullOrEmpty()) {
            return WsSkillResult(
                requestId = requestId,
                success = false,
                error = "Missing required parameter: 'action'"
            )
        }

        if (action !in ALLOWLISTED_MEDIA_ACTIONS) {
            return WsSkillResult(
                requestId = requestId,
                success = false,
                error = "Unsupported media action: '$action'"
            )
        }

        Log.i(tag, "Executing media control: action='$action'")

        return try {
            val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager
            if (audioManager == null) {
                return WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = "AudioManager is not available on this device"
                )
            }

            val keyCode = when (action) {
                "play", "resume" -> KeyEvent.KEYCODE_MEDIA_PLAY
                "pause" -> KeyEvent.KEYCODE_MEDIA_PAUSE
                "stop" -> KeyEvent.KEYCODE_MEDIA_STOP
                "next" -> KeyEvent.KEYCODE_MEDIA_NEXT
                "previous" -> KeyEvent.KEYCODE_MEDIA_PREVIOUS
                else -> KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE
            }

            val eventTime = SystemClock.uptimeMillis()
            val downEvent = KeyEvent(eventTime, eventTime, KeyEvent.ACTION_DOWN, keyCode, 0)
            val upEvent = KeyEvent(eventTime, eventTime, KeyEvent.ACTION_UP, keyCode, 0)

            // 1. Dispatch through AudioManager
            audioManager.dispatchMediaKeyEvent(downEvent)
            audioManager.dispatchMediaKeyEvent(upEvent)
            Log.i(tag, "Dispatched media key event: keyCode=$keyCode ($action)")

            // 2. For play / resume: if music is not currently active, launch/trigger music app
            var appLaunched: String? = null
            if (action in setOf("play", "resume") && !audioManager.isMusicActive) {
                Log.i(tag, "Music is not active. Attempting to start/open music application.")
                val musicPackages = listOf(
                    "com.google.android.apps.youtube.music",
                    "com.google.android.youtube"
                )
                val pm = context.packageManager
                for (pkg in musicPackages) {
                    val launchIntent = pm.getLaunchIntentForPackage(pkg)
                    if (launchIntent != null) {
                        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED)
                        Log.i(tag, "Launching music application: $pkg")
                        context.startActivity(launchIntent)
                        appLaunched = pkg
                        break
                    }
                }

                // If package launch was not found, fallback to MEDIA_PLAY_FROM_SEARCH or CATEGORY_APP_MUSIC
                if (appLaunched == null) {
                    try {
                        val searchPlayIntent = Intent(MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH).apply {
                            flags = Intent.FLAG_ACTIVITY_NEW_TASK
                        }
                        if (searchPlayIntent.resolveActivity(pm) != null) {
                            context.startActivity(searchPlayIntent)
                            appLaunched = "default_music_player"
                        }
                    } catch (e: Exception) {
                        Log.d(tag, "Fallback media play intent: ${e.message}")
                    }
                }
            }

            WsSkillResult(
                requestId = requestId,
                success = true,
                result = mapOf(
                    "action" to action,
                    "status" to "dispatched",
                    "music_active" to audioManager.isMusicActive,
                    "target_app" to (appLaunched ?: "active_media_session")
                )
            )
        } catch (e: Exception) {
            Log.e(tag, "Failed to execute media control '$action': ${e.message}", e)
            WsSkillResult(
                requestId = requestId,
                success = false,
                error = "Media control error: ${e.message}"
            )
        }
    }

    private fun executeNotification(requestId: String, params: Map<String, Any>?): WsSkillResult {
        val title = params?.get("title")?.toString()?.trim() ?: "Jarvis Alert"
        val message = params?.get("message")?.toString()?.trim() ?: ""

        if (message.isEmpty() && title.isEmpty()) {
            return WsSkillResult(
                requestId = requestId,
                success = false,
                error = "Notification title or message is required"
            )
        }

        return try {
            val notificationManager =
                context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
            if (notificationManager == null) {
                Log.e(tag, "NotificationManager is not available on this device")
                return WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = "NotificationManager is unavailable on this device"
                )
            }

            // Check runtime notification permission on Android 13+ (API 33+)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                if (ContextCompat.checkSelfPermission(
                        context,
                        Manifest.permission.POST_NOTIFICATIONS
                    ) != PackageManager.PERMISSION_GRANTED
                ) {
                    Log.w(tag, "Cannot post notification: POST_NOTIFICATIONS permission not granted")
                    return WsSkillResult(
                        requestId = requestId,
                        success = false,
                        error = "POST_NOTIFICATIONS permission not granted by user"
                    )
                }
            }

            // Also check NotificationManagerCompat.areNotificationsEnabled()
            if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) {
                Log.w(tag, "Cannot post notification: notifications are disabled for Jarvis in system settings")
                return WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = "Notifications are disabled for Jarvis in device settings"
                )
            }

            // Ensure channel exists
            createNotificationChannel()

            val notification = NotificationCompat.Builder(context, NOTIFICATION_CHANNEL_ID)
                .setSmallIcon(R.drawable.bg_status_badge)
                .setContentTitle(title)
                .setContentText(message)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setAutoCancel(true)
                .build()

            val notificationId = (System.currentTimeMillis() % 10000).toInt()
            Log.i(tag, "Posting notification id=$notificationId, title='$title', message='$message'")
            notificationManager.notify(notificationId, notification)
            Log.i(tag, "Notification posted successfully")

            WsSkillResult(
                requestId = requestId,
                success = true,
                result = mapOf("title" to title, "message" to message, "status" to "posted")
            )
        } catch (e: SecurityException) {
            Log.e(tag, "SecurityException posting notification: ${e.message}", e)
            WsSkillResult(
                requestId = requestId,
                success = false,
                error = "Security exception posting notification: ${e.message}"
            )
        } catch (e: Exception) {
            Log.e(tag, "Failed to post notification: ${e.message}", e)
            WsSkillResult(
                requestId = requestId,
                success = false,
                error = "Notification error: ${e.message}"
            )
        }
    }

    private var isTorchOn = false

    private fun executeFlashlight(requestId: String, params: Map<String, Any>?): WsSkillResult {
        Log.i(tag, "Executing flashlight toggle (req_id=$requestId) with params: $params")
        return try {
            val cameraManager = context.getSystemService(Context.CAMERA_SERVICE) as? CameraManager
            if (cameraManager == null) {
                return WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = "CameraManager is not available on this device"
                )
            }

            var cameraIdWithFlash: String? = null
            for (id in cameraManager.cameraIdList) {
                val chars = cameraManager.getCameraCharacteristics(id)
                val hasFlash = chars.get(CameraCharacteristics.FLASH_INFO_AVAILABLE) == true
                val facing = chars.get(CameraCharacteristics.LENS_FACING)
                if (hasFlash && facing == CameraCharacteristics.LENS_FACING_BACK) {
                    cameraIdWithFlash = id
                    break
                }
                if (hasFlash && cameraIdWithFlash == null) {
                    cameraIdWithFlash = id
                }
            }

            if (cameraIdWithFlash == null) {
                cameraIdWithFlash = cameraManager.cameraIdList.firstOrNull()
            }

            if (cameraIdWithFlash == null) {
                return WsSkillResult(
                    requestId = requestId,
                    success = false,
                    error = "No camera with flashlight found on this device"
                )
            }

            val rawState = params?.get("state")?.toString()?.trim()?.lowercase()
            val rawEnabled = params?.get("enabled") as? Boolean

            val targetState = if (rawEnabled != null) {
                rawEnabled
            } else if (rawState == "on") {
                true
            } else if (rawState == "off") {
                false
            } else {
                !isTorchOn
            }

            cameraManager.setTorchMode(cameraIdWithFlash, targetState)
            isTorchOn = targetState
            Log.i(tag, "Flashlight set to $targetState on camera $cameraIdWithFlash")

            WsSkillResult(
                requestId = requestId,
                success = true,
                result = mapOf(
                    "action" to "flashlight",
                    "status" to if (targetState) "on" else "off",
                    "enabled" to targetState
                )
            )
        } catch (e: Exception) {
            Log.e(tag, "Failed to control flashlight: ${e.message}", e)
            WsSkillResult(
                requestId = requestId,
                success = false,
                error = "Flashlight control error: ${e.message}"
            )
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val notificationManager =
                context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
            if (notificationManager != null && notificationManager.getNotificationChannel(NOTIFICATION_CHANNEL_ID) == null) {
                val channel = NotificationChannel(
                    NOTIFICATION_CHANNEL_ID,
                    NOTIFICATION_CHANNEL_NAME,
                    NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "Notifications and reminders dispatched by Jarvis Assistant"
                    enableVibration(true)
                    enableLights(true)
                }
                notificationManager.createNotificationChannel(channel)
                Log.i(tag, "Created notification channel '$NOTIFICATION_CHANNEL_ID'")
            }
        }
    }
}

