package com.jarvis.client.accessibility

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.app.KeyguardManager
import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.provider.Settings
import android.text.TextUtils
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityManager
import android.view.accessibility.AccessibilityNodeInfo
import java.lang.ref.WeakReference

/**
 * Structured information about an editable or input field on screen.
 */
data class ScreenField(
    val description: String,
    val text: String? = null,
    val isPassword: Boolean = false,
    val isEditable: Boolean = false
) {
    fun toMap(): Map<String, Any> {
        val map = mutableMapOf<String, Any>(
            "description" to description,
            "password" to isPassword,
            "editable" to isEditable
        )
        if (!isPassword && !text.isNullOrBlank()) {
            map["text"] = text
        }
        return map
    }
}

/**
 * Immutable read-only representation of the visible screen state.
 */
data class ScreenState(
    val foregroundApp: String,
    val packageName: String,
    val texts: List<String>,
    val buttons: List<String>,
    val textFields: List<ScreenField>,
    val nodeCount: Int
) {
    fun toMap(): Map<String, Any> = mapOf(
        "foreground_app" to foregroundApp,
        "package" to packageName,
        "texts" to texts,
        "buttons" to buttons,
        "text_fields" to textFields.map { it.toMap() },
        "node_count" to nodeCount
    )
}

sealed class ScreenStateResult {
    data class Success(val state: ScreenState) : ScreenStateResult()
    data class Locked(val message: String) : ScreenStateResult()
    data class Error(val error: String) : ScreenStateResult()
}

sealed class NavigationResult {
    data class Success(val action: String) : NavigationResult()
    data class Locked(val message: String) : NavigationResult()
    data class Disabled(val message: String) : NavigationResult()
    data class Error(val error: String) : NavigationResult()
}

sealed class ForegroundAppResult {
    data class Success(
        val packageName: String,
        val appName: String,
        val isLocked: Boolean = false
    ) : ForegroundAppResult() {
        fun toMap(): Map<String, Any> = mapOf(
            "package" to packageName,
            "app" to appName,
            "locked" to isLocked
        )
    }
    data class Locked(val message: String) : ForegroundAppResult()
    data class Disabled(val message: String) : ForegroundAppResult()
    data class Error(val error: String) : ForegroundAppResult()
}

/**
 * Read-Only & Controlled Navigation Accessibility Service for Jarvis Assistant.
 * Strictly executes only approved system navigation and UI inspection without arbitrary coordinate clicks or typing.
 */
class JarvisAccessibilityService : AccessibilityService() {

    private val tag = "JarvisAccessibility"

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = WeakReference(this)
        Log.i(tag, "JarvisAccessibilityService connected and ready for read-only inspection.")
        serviceStateListener?.invoke(true)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return

        when (event.eventType) {
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> {
                val pkg = event.packageName?.toString()
                if (!pkg.isNullOrBlank()) {
                    currentPackageName = pkg
                }
            }
            AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED,
            AccessibilityEvent.TYPE_VIEW_FOCUSED,
            AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED -> {
                // Event monitored passively for state freshness
            }
        }
    }

    override fun onInterrupt() {
        Log.w(tag, "JarvisAccessibilityService interrupted.")
    }

    override fun onDestroy() {
        super.onDestroy()
        if (instance?.get() == this) {
            instance = null
        }
        Log.i(tag, "JarvisAccessibilityService destroyed.")
        serviceStateListener?.invoke(false)
    }

    companion object {
        // Dynamic callback for notifying repository of service connection changes
        var serviceStateListener: ((Boolean) -> Unit)? = null

        // Enforced deterministic limits to avoid payload bloat
        const val MAX_NODE_COUNT = 100
        const val MAX_TREE_DEPTH = 15
        const val MAX_TEXT_LENGTH = 200
        const val MAX_TOTAL_TEXTS = 40
        const val MAX_TOTAL_BUTTONS = 25
        const val MAX_TOTAL_FIELDS = 15

        private var instance: WeakReference<JarvisAccessibilityService>? = null
        private var currentPackageName: String = ""

        fun isServiceEnabled(context: Context? = null): Boolean {
            if (instance?.get() != null) {
                return true
            }
            if (context != null) {
                return isAccessibilitySettingsEnabled(context)
            }
            return false
        }

        fun isAccessibilitySettingsEnabled(context: Context): Boolean {
            try {
                val am = context.getSystemService(Context.ACCESSIBILITY_SERVICE) as? AccessibilityManager
                if (am != null) {
                    val enabledServices = am.getEnabledAccessibilityServiceList(AccessibilityServiceInfo.FEEDBACK_ALL_MASK)
                    for (serviceInfo in enabledServices) {
                        val serviceId = serviceInfo.id
                        if (serviceId.contains(context.packageName) && serviceId.contains("JarvisAccessibilityService")) {
                            return true
                        }
                    }
                }
            } catch (e: Exception) {
                Log.w("JarvisAccessibility", "Error checking AccessibilityManager: ${e.message}")
            }

            try {
                val enabledServices = Settings.Secure.getString(
                    context.contentResolver,
                    Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
                ) ?: return false
                val colonSplitter = TextUtils.SimpleStringSplitter(':')
                colonSplitter.setString(enabledServices)
                while (colonSplitter.hasNext()) {
                    val component = colonSplitter.next()
                    if (component.contains(context.packageName, ignoreCase = true) &&
                        component.contains("JarvisAccessibilityService", ignoreCase = true)) {
                        return true
                    }
                }
            } catch (e: Exception) {
                Log.w("JarvisAccessibility", "Error reading ENABLED_ACCESSIBILITY_SERVICES: ${e.message}")
            }
            return false
        }

        fun getInstance(): JarvisAccessibilityService? {
            return instance?.get()
        }

        /**
         * Safely inspect the active window hierarchy and return a structured, read-only ScreenState.
         */
        fun readScreenState(context: Context): ScreenStateResult {
            val service = instance?.get()
                ?: return ScreenStateResult.Error(
                    "Accessibility service is not enabled. Please enable Jarvis in Android Accessibility Settings."
                )

            // 1. Lock Screen Safety Check
            val keyguardManager = context.getSystemService(Context.KEYGUARD_SERVICE) as? KeyguardManager
            if (keyguardManager != null && (keyguardManager.isDeviceLocked || keyguardManager.isKeyguardLocked)) {
                return ScreenStateResult.Locked(
                    "Device is currently locked. Unlock your phone to inspect the screen."
                )
            }

            // 2. Obtain root node in active window
            val rootNode = service.rootInActiveWindow
                ?: return ScreenStateResult.Error(
                    "Cannot access current screen content (active window is not accessible)."
                )

            return try {
                val pkgName = rootNode.packageName?.toString()
                    ?: currentPackageName.ifBlank { "unknown_app" }

                val appName = resolveApplicationLabel(context, pkgName)

                val texts = LinkedHashSet<String>()
                val buttons = LinkedHashSet<String>()
                val fields = mutableListOf<ScreenField>()
                var totalNodes = 0

                fun traverse(node: AccessibilityNodeInfo?, depth: Int) {
                    if (node == null || depth > MAX_TREE_DEPTH || totalNodes >= MAX_NODE_COUNT) {
                        return
                    }
                    totalNodes++

                    if (!node.isVisibleToUser) {
                        return
                    }

                    val isPass = node.isPassword
                    val isEdit = node.isEditable
                    val isClick = node.isClickable

                    val textVal = if (!isPass) node.text?.toString()?.trim() else null
                    val descVal = node.contentDescription?.toString()?.trim()

                    // Text Field Extraction (Strict Password Safety)
                    if (isEdit || isPass) {
                        if (fields.size < MAX_TOTAL_FIELDS) {
                            val fieldDesc = descVal
                                ?: (if (isPass) "Password Field" else (node.hintText?.toString()?.trim() ?: "Text Input"))
                            val safeText = if (isPass) null else textVal
                            fields.add(
                                ScreenField(
                                    description = fieldDesc.take(MAX_TEXT_LENGTH),
                                    text = safeText?.take(MAX_TEXT_LENGTH),
                                    isPassword = isPass,
                                    isEditable = isEdit
                                )
                            )
                        }
                    }

                    // Button Extraction
                    if (isClick && !isEdit) {
                        val btnLabel = (descVal ?: textVal)?.take(MAX_TEXT_LENGTH)
                        if (!btnLabel.isNullOrBlank() && buttons.size < MAX_TOTAL_BUTTONS) {
                            buttons.add(btnLabel)
                        }
                    }

                    // General Visible Text Extraction (Skip passwords completely)
                    if (!isPass) {
                        if (!textVal.isNullOrBlank() && texts.size < MAX_TOTAL_TEXTS) {
                            texts.add(textVal.take(MAX_TEXT_LENGTH))
                        }
                        if (!descVal.isNullOrBlank() && descVal != textVal && texts.size < MAX_TOTAL_TEXTS) {
                            texts.add(descVal.take(MAX_TEXT_LENGTH))
                        }
                    }

                    val childCount = node.childCount
                    for (i in 0 until childCount) {
                        if (totalNodes >= MAX_NODE_COUNT) break
                        val child = node.getChild(i)
                        traverse(child, depth + 1)
                    }
                }

                traverse(rootNode, 0)

                ScreenStateResult.Success(
                    ScreenState(
                        foregroundApp = appName,
                        packageName = pkgName,
                        texts = texts.toList(),
                        buttons = buttons.toList(),
                        textFields = fields,
                        nodeCount = totalNodes
                    )
                )
            } catch (e: Exception) {
                Log.e(service.tag, "Error reading screen state: ${e.message}", e)
                ScreenStateResult.Error("Error inspecting screen: ${e.message}")
            }
        }

        /**
         * Safely performs Back navigation via GLOBAL_ACTION_BACK.
         */
        fun pressBack(context: Context): NavigationResult {
            val keyguardManager = context.getSystemService(Context.KEYGUARD_SERVICE) as? KeyguardManager
            if (keyguardManager != null && (keyguardManager.isDeviceLocked || keyguardManager.isKeyguardLocked)) {
                return NavigationResult.Locked(
                    "Your phone is locked. Please unlock it before interacting with the screen."
                )
            }

            val service = instance?.get()
                ?: return NavigationResult.Disabled(
                    "Accessibility service is not enabled. Please enable Jarvis in Android Accessibility Settings."
                )

            return try {
                val success = service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
                if (success) {
                    NavigationResult.Success("press_back")
                } else {
                    NavigationResult.Error("Android system could not execute Back action in current state.")
                }
            } catch (e: Exception) {
                Log.e(service.tag, "Error performing Back navigation: ${e.message}", e)
                NavigationResult.Error("Error performing Back navigation: ${e.message}")
            }
        }

        /**
         * Safely performs Home navigation via GLOBAL_ACTION_HOME.
         */
        fun pressHome(context: Context): NavigationResult {
            val keyguardManager = context.getSystemService(Context.KEYGUARD_SERVICE) as? KeyguardManager
            if (keyguardManager != null && (keyguardManager.isDeviceLocked || keyguardManager.isKeyguardLocked)) {
                return NavigationResult.Locked(
                    "Your phone is locked. Please unlock it before interacting with the screen."
                )
            }

            val service = instance?.get()
                ?: return NavigationResult.Disabled(
                    "Accessibility service is not enabled. Please enable Jarvis in Android Accessibility Settings."
                )

            return try {
                val success = service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME)
                if (success) {
                    NavigationResult.Success("press_home")
                } else {
                    NavigationResult.Error("Android system could not execute Home action in current state.")
                }
            } catch (e: Exception) {
                Log.e(service.tag, "Error performing Home navigation: ${e.message}", e)
                NavigationResult.Error("Error performing Home navigation: ${e.message}")
            }
        }

        /**
         * Detects the currently active foreground application safely.
         */
        fun getForegroundApp(context: Context): ForegroundAppResult {
            val keyguardManager = context.getSystemService(Context.KEYGUARD_SERVICE) as? KeyguardManager
            if (keyguardManager != null && (keyguardManager.isDeviceLocked || keyguardManager.isKeyguardLocked)) {
                return ForegroundAppResult.Locked(
                    "Your phone is locked. Unlock it to inspect the active application."
                )
            }

            val service = instance?.get()
                ?: return ForegroundAppResult.Disabled(
                    "Accessibility service is not enabled. Please enable Jarvis in Android Accessibility Settings."
                )

            return try {
                val rootNode = service.rootInActiveWindow
                val pkgName = rootNode?.packageName?.toString()
                    ?: currentPackageName.ifBlank { "unknown" }
                val appName = resolveApplicationLabel(context, pkgName)
                ForegroundAppResult.Success(
                    packageName = pkgName,
                    appName = appName,
                    isLocked = false
                )
            } catch (e: Exception) {
                Log.e(service.tag, "Error detecting foreground app: ${e.message}", e)
                ForegroundAppResult.Error("Error detecting foreground app: ${e.message}")
            }
        }

        private fun resolveApplicationLabel(context: Context, packageName: String): String {
            return try {
                val pm = context.packageManager
                val appInfo = pm.getApplicationInfo(packageName, 0)
                pm.getApplicationLabel(appInfo).toString()
            } catch (e: PackageManager.NameNotFoundException) {
                packageName.substringAfterLast('.').replaceFirstChar { it.uppercase() }
            } catch (e: Exception) {
                packageName
            }
        }
    }
}
