package com.jarvis.client.accessibility

import android.content.Context
import android.os.Bundle
import android.util.Log
import android.view.accessibility.AccessibilityNodeInfo
import com.jarvis.client.model.WsSkillResult

/**
 * Generic semantic Android UI observation/action layer.
 *
 * It deliberately avoids app-specific selectors. The caller supplies semantic text or
 * content descriptions observed from the current screen. Password fields are never filled
 * by remote skill requests.
 */
object UiAutomationEngine {
    private const val TAG = "JarvisUiAutomation"
    private const val MAX_ELEMENTS = 160
    private const val MAX_DEPTH = 18
    private const val ACTION_SETTLE_MS = 250L

    fun observe(context: Context, requestId: String): WsSkillResult {
        val service = JarvisAccessibilityService.getInstance()
            ?: return failure(requestId, "Accessibility service is not enabled.", "accessibility_disabled")
        val root = service.rootInActiveWindow
            ?: return failure(requestId, "The active window is not accessible.", "screen_unavailable")

        return try {
            val elements = mutableListOf<Map<String, Any?>>()
            var visited = 0

            fun walk(node: AccessibilityNodeInfo?, depth: Int) {
                if (node == null || depth > MAX_DEPTH || visited >= MAX_ELEMENTS) return
                visited++
                if (node.isVisibleToUser) {
                    val text = node.text?.toString()?.trim().orEmpty()
                    val desc = node.contentDescription?.toString()?.trim().orEmpty()
                    val hint = node.hintText?.toString()?.trim().orEmpty()
                    val resourceId = node.viewIdResourceName?.trim().orEmpty()
                    if (text.isNotEmpty() || desc.isNotEmpty() || hint.isNotEmpty() ||
                        node.isClickable || node.isEditable || node.isScrollable) {
                        elements += mapOf(
                            "index" to elements.size,
                            "text" to text.take(240),
                            "content_description" to desc.take(240),
                            "hint" to hint.take(240),
                            "resource_id" to resourceId.take(240),
                            "class_name" to node.className?.toString()?.take(160).orEmpty(),
                            "clickable" to node.isClickable,
                            "editable" to node.isEditable,
                            "password" to node.isPassword,
                            "scrollable" to node.isScrollable,
                            "enabled" to node.isEnabled,
                            "visible" to node.isVisibleToUser
                        )
                    }
                }
                for (i in 0 until node.childCount) {
                    if (visited >= MAX_ELEMENTS) break
                    walk(node.getChild(i), depth + 1)
                }
            }

            walk(root, 0)
            WsSkillResult(
                requestId = requestId,
                success = true,
                result = mapOf(
                    "status" to "observed",
                    "package" to root.packageName?.toString().orEmpty(),
                    "element_count" to elements.size,
                    "elements" to elements
                )
            )
        } catch (e: Exception) {
            Log.e(TAG, "Screen observation failed", e)
            failure(requestId, "Screen observation failed: ${e.message}", "observation_error")
        }
    }

    fun tap(context: Context, requestId: String, target: String, humanApproved: Boolean = false): WsSkillResult {
        val service = JarvisAccessibilityService.getInstance()
            ?: return failure(requestId, "Accessibility service is not enabled.", "accessibility_disabled")
        val root = service.rootInActiveWindow
            ?: return failure(requestId, "The active window is not accessible.", "screen_unavailable")
        val policy = UiActionPolicy.evaluateTap(target, humanApproved)
        if (policy == UiActionPolicy.Decision.REQUIRE_HUMAN_APPROVAL) {
            return failure(requestId, "The action '$target' requires explicit human approval before JARVIS can perform it.", "human_approval_required")
        }
        if (policy == UiActionPolicy.Decision.DENY_HUMAN_INPUT) {
            return failure(requestId, "Biometric/security actions must be completed directly by the human.", "human_only_action")
        }

        val node = findBestNode(root, target, clickableOnly = true)
            ?: return failure(requestId, "No unique clickable UI element matched '$target'.", "target_not_found")

        return try {
            val clicked = node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            if (!clicked) {
                failure(requestId, "Android rejected the click for '$target'.", "action_rejected")
            } else {
                Thread.sleep(ACTION_SETTLE_MS)
                WsSkillResult(
                    requestId = requestId,
                    success = true,
                    result = mapOf("action" to "tap", "target" to target, "status" to "executed")
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "Tap failed for '$target'", e)
            failure(requestId, "Tap failed: ${e.message}", "action_error")
        } finally {
            node.recycle()
        }
    }

    fun typeText(
        context: Context,
        requestId: String,
        target: String?,
        text: String
    ): WsSkillResult {
        val service = JarvisAccessibilityService.getInstance()
            ?: return failure(requestId, "Accessibility service is not enabled.", "accessibility_disabled")
        val root = service.rootInActiveWindow
            ?: return failure(requestId, "The active window is not accessible.", "screen_unavailable")
        val node = if (!target.isNullOrBlank()) {
            findBestNode(root, target, clickableOnly = false, editableOnly = true)
        } else {
            findSingleEditable(root)
        } ?: return failure(requestId, "No unique editable field matched the requested target.", "input_target_not_found")

        return try {
            when (UiActionPolicy.evaluateTextInput(
                isPassword = node.isPassword,
                hint = node.hintText?.toString(),
                resourceId = node.viewIdResourceName,
                target = target
            )) {
                UiActionPolicy.Decision.DENY_HUMAN_INPUT -> {
                    return failure(
                        requestId,
                        "Password, OTP, CAPTCHA, PIN, CVV and biometric/security input must be completed directly by the human.",
                        "sensitive_input_requires_human"
                    )
                }
                UiActionPolicy.Decision.REQUIRE_HUMAN_APPROVAL -> {
                    return failure(requestId, "This input requires explicit human approval.", "human_approval_required")
                }
                UiActionPolicy.Decision.ALLOW -> Unit
            }
            if (!node.isEditable) {
                return failure(requestId, "Target '$target' is not editable.", "target_not_editable")
            }
            val args = Bundle().apply {
                putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
            }
            val changed = node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
            if (!changed) {
                failure(requestId, "Android rejected text input for '$target'.", "action_rejected")
            } else {
                Thread.sleep(ACTION_SETTLE_MS)
                WsSkillResult(
                    requestId = requestId,
                    success = true,
                    result = mapOf(
                        "action" to "type_text",
                        "target" to (target ?: "single_editable_field"),
                        "status" to "executed",
                        "characters" to text.length
                    )
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "Type action failed", e)
            failure(requestId, "Text input failed: ${e.message}", "action_error")
        } finally {
            node.recycle()
        }
    }

    fun scroll(requestId: String, direction: String): WsSkillResult {
        val service = JarvisAccessibilityService.getInstance()
            ?: return failure(requestId, "Accessibility service is not enabled.", "accessibility_disabled")
        val root = service.rootInActiveWindow
            ?: return failure(requestId, "The active window is not accessible.", "screen_unavailable")
        val action = when (direction.trim().lowercase()) {
            "down", "forward", "next" -> AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
            "up", "back", "previous" -> AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
            else -> return failure(requestId, "Unsupported scroll direction '$direction'.", "invalid_direction")
        }
        val scrollable = findFirstScrollable(root)
            ?: return failure(requestId, "No scrollable container is visible.", "scroll_target_not_found")

        return try {
            val ok = scrollable.performAction(action)
            WsSkillResult(
                requestId = requestId,
                success = ok,
                result = mapOf(
                    "action" to "scroll",
                    "direction" to direction,
                    "status" to if (ok) "executed" else "rejected"
                ),
                error = if (ok) null else "Android rejected the scroll action."
            )
        } catch (e: Exception) {
            Log.e(TAG, "Scroll failed", e)
            failure(requestId, "Scroll failed: ${e.message}", "action_error")
        } finally {
            scrollable.recycle()
        }
    }

    private fun findBestNode(
        root: AccessibilityNodeInfo,
        target: String,
        clickableOnly: Boolean,
        editableOnly: Boolean = false
    ): AccessibilityNodeInfo? {
        val wanted = target.trim()
        if (wanted.isEmpty()) return null
        val exact = mutableListOf<AccessibilityNodeInfo>()
        val fuzzy = mutableListOf<AccessibilityNodeInfo>()

        fun walk(node: AccessibilityNodeInfo?, depth: Int) {
            if (node == null || depth > MAX_DEPTH) return
            if (node.isVisibleToUser && node.isEnabled) {
                val candidates = listOf(
                    node.text?.toString().orEmpty(),
                    node.contentDescription?.toString().orEmpty(),
                    node.hintText?.toString().orEmpty(),
                    node.viewIdResourceName.orEmpty()
                ).map { it.trim() }.filter { it.isNotEmpty() }
                val matchesExact = candidates.any { it.equals(wanted, ignoreCase = true) }
                val matchesFuzzy = candidates.any {
                    it.contains(wanted, ignoreCase = true) || wanted.contains(it, ignoreCase = true)
                }
                if ((!clickableOnly || node.isClickable) && (!editableOnly || node.isEditable)) {
                    if (matchesExact) exact += node else if (matchesFuzzy) fuzzy += node
                }
            }
            for (i in 0 until node.childCount) walk(node.getChild(i), depth + 1)
        }

        walk(root, 0)
        return when {
            exact.size == 1 -> exact[0]
            exact.size > 1 -> null
            fuzzy.size == 1 -> fuzzy[0]
            else -> null
        }
    }

    private fun findSingleEditable(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        val fields = mutableListOf<AccessibilityNodeInfo>()
        fun walk(node: AccessibilityNodeInfo?, depth: Int) {
            if (node == null || depth > MAX_DEPTH || fields.size > 1) return
            if (node.isVisibleToUser && node.isEnabled && node.isEditable) fields += node
            for (i in 0 until node.childCount) walk(node.getChild(i), depth + 1)
        }
        walk(root, 0)
        return if (fields.size == 1) fields[0] else null
    }

    private fun findFirstScrollable(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        var found: AccessibilityNodeInfo? = null
        fun walk(node: AccessibilityNodeInfo?, depth: Int) {
            if (node == null || depth > MAX_DEPTH || found != null) return
            if (node.isVisibleToUser && node.isEnabled && node.isScrollable) {
                found = node
                return
            }
            for (i in 0 until node.childCount) walk(node.getChild(i), depth + 1)
        }
        walk(root, 0)
        return found
    }

    private fun failure(requestId: String, message: String, code: String): WsSkillResult =
        WsSkillResult(
            requestId = requestId,
            success = false,
            error = message,
            result = mapOf("status" to code)
        )
}
