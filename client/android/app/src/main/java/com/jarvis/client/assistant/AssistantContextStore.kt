package com.jarvis.client.assistant

import android.app.assist.AssistStructure
import android.text.InputType
import java.util.concurrent.atomic.AtomicReference

/**
 * Short-lived, in-memory screen context captured by the system assistant.
 *
 * Only non-input visible text/content descriptions are retained. Editable/input nodes
 * are deliberately excluded so credentials and private form contents are not forwarded
 * as assistant context.
 */
object AssistantContextStore {
    data class Snapshot(
        val packageName: String? = null,
        val text: String = "",
        val capturedAtEpochMs: Long = 0L
    )

    private val snapshotRef = AtomicReference(Snapshot())

    fun update(structure: AssistStructure?) {
        if (structure == null) return

        val lines = mutableListOf<String>()
        var packageName: String? = null

        for (windowIndex in 0 until structure.windowNodeCount) {
            val window = structure.getWindowNodeAt(windowIndex)
            val root = window.rootViewNode
            if (packageName == null) {
                packageName = root.idPackage
            }
            collect(root, lines, 0)
            if (lines.size >= MAX_LINES) break
        }

        snapshotRef.set(
            Snapshot(
                packageName = packageName,
                text = lines.joinToString("
").take(MAX_CONTEXT_CHARS),
                capturedAtEpochMs = System.currentTimeMillis()
            )
        )
    }

    fun current(): Snapshot = snapshotRef.get()

    fun clear() {
        snapshotRef.set(Snapshot())
    }

    private fun collect(
        node: AssistStructure.ViewNode,
        lines: MutableList<String>,
        depth: Int
    ) {
        if (depth > MAX_DEPTH || lines.size >= MAX_LINES || node.isAssistBlocked) return

        // Do not copy text from likely input fields. This is a conservative privacy boundary.
        val inputType = node.inputType
        val looksLikeInput = inputType != InputType.TYPE_NULL

        if (!looksLikeInput) {
            val text = node.text?.toString()?.trim().orEmpty()
            val description = node.contentDescription?.toString()?.trim().orEmpty()
            val value = when {
                text.isNotEmpty() -> text
                description.isNotEmpty() -> description
                else -> ""
            }
            if (value.isNotEmpty()) {
                lines += value.take(MAX_LINE_CHARS)
            }
        }

        for (childIndex in 0 until node.childCount) {
            collect(node.getChildAt(childIndex), lines, depth + 1)
            if (lines.size >= MAX_LINES) break
        }
    }

    private const val MAX_DEPTH = 18
    private const val MAX_LINES = 120
    private const val MAX_LINE_CHARS = 240
    private const val MAX_CONTEXT_CHARS = 12000
}
