package com.jarvis.client.voice.kws

import android.content.Context
import java.io.BufferedReader
import java.io.InputStream
import java.io.InputStreamReader

/**
 * Pure on-device SentencePiece Viterbi BPE tokenizer for the sherpa-onnx KWS GigaSpeech model.
 * Tokenizes arbitrary user phrases into the exact BPE subwords present in tokens.txt.
 */
class SherpaBpeTokenizer(private val context: Context? = null) {

    private val vocab = HashMap<String, Float>()
    private val vocabIds = HashMap<String, Int>()
    private var isInitialized = false

    companion object {
        const val PREFIX_SPACE = "\u2581"
        const val ASSET_TOKENS_SCORES = "models/kws/tokens_with_scores.txt"
        const val ASSET_TOKENS = "models/kws/tokens.txt"
    }

    init {
        context?.let {
            loadFromAssets(it)
        }
    }

    /**
     * Loads vocabulary tokens and their log-probability scores from assets.
     */
    fun loadFromAssets(ctx: Context) {
        if (isInitialized) return
        try {
            val stream = ctx.assets.open(ASSET_TOKENS_SCORES)
            loadFromStream(stream)
        } catch (_: Exception) {
            // Fallback to reading tokens.txt with linear rank penalties if scores file unavailable
            try {
                val stream = ctx.assets.open(ASSET_TOKENS)
                loadFromTokensStream(stream)
            } catch (_: Exception) {}
        }
    }

    fun loadFromStream(stream: InputStream) {
        BufferedReader(InputStreamReader(stream, Charsets.UTF_8)).use { reader ->
            reader.forEachLine { line ->
                val parts = line.split("\t")
                if (parts.size >= 2) {
                    val piece = parts[0]
                    val score = parts[1].toFloatOrNull() ?: 0.0f
                    val id = if (parts.size >= 3) parts[2].toIntOrNull() ?: 0 else 0
                    vocab[piece] = score
                    vocabIds[piece] = id
                }
            }
        }
        isInitialized = true
    }

    fun loadFromTokensStream(stream: InputStream) {
        BufferedReader(InputStreamReader(stream, Charsets.UTF_8)).use { reader ->
            var idx = 0
            reader.forEachLine { line ->
                val parts = line.trim().split(Regex("\\s+"))
                if (parts.isNotEmpty() && parts[0].isNotBlank()) {
                    val piece = parts[0]
                    val id = if (parts.size >= 2) parts[1].toIntOrNull() ?: idx else idx
                    val score = -0.01f * id
                    vocab[piece] = score
                    vocabIds[piece] = id
                    idx++
                }
            }
        }
        isInitialized = true
    }

    /**
     * Encodes a phrase (e.g. "Hey Aniket") into BPE pieces (e.g. [" HE", "Y", " AN", "I", "KE", "T"]).
     */
    fun tokenize(text: String): List<String> {
        val normalized = text.uppercase().trim()
        val words = normalized.split(Regex("\\s+")).filter { it.isNotBlank() }
        val allPieces = mutableListOf<String>()

        for (w in words) {
            val s = PREFIX_SPACE + w
            val n = s.length
            val dp = FloatArray(n + 1) { Float.NEGATIVE_INFINITY }
            val prev = IntArray(n + 1) { -1 }
            dp[0] = 0.0f

            for (i in 1..n) {
                val maxLen = minOf(i, 20)
                for (len in 1..maxLen) {
                    val j = i - len
                    val sub = s.substring(j, i)
                    val score = vocab[sub]
                    if (score != null) {
                        val sc = dp[j] + score
                        if (sc > dp[i]) {
                            dp[i] = sc
                            prev[i] = j
                        }
                    }
                }
            }

            var curr = n
            val pieces = mutableListOf<String>()
            while (curr > 0) {
                val p = prev[curr]
                if (p == -1) {
                    // Fallback to single character if subword not in vocab
                    pieces.add(s.substring(curr - 1, curr))
                    curr -= 1
                } else {
                    pieces.add(s.substring(p, curr))
                    curr = p
                }
            }
            pieces.reverse()
            allPieces.addAll(pieces)
        }

        return allPieces
    }

    /**
     * Formats BPE pieces into sherpa-onnx keywords.txt line format (space-separated pieces).
     */
    fun formatKeywordsLine(pieces: List<String>): String {
        return pieces.joinToString(" ")
    }

    /**
     * Complete helper: phrase -> " HE Y  AN I KE T"
     */
    fun tokenizeToKeywordLine(text: String): String {
        val pieces = tokenize(text)
        return formatKeywordsLine(pieces)
    }

    fun isReady(): Boolean = isInitialized && vocab.isNotEmpty()
}
