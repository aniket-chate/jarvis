package com.jarvis.client.voice

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.Locale
import java.util.UUID

/**
 * Text-to-Speech manager for Jarvis spoken vocalization.
 */
class JarvisTTSManager(
    context: Context
) : TextToSpeech.OnInitListener {

    private val tag = "JarvisTTSManager"

    private var tts: TextToSpeech? = TextToSpeech(context.applicationContext, this)
    private var isInitialized = false

    private val _isSpeaking = MutableStateFlow(false)
    val isSpeaking: StateFlow<Boolean> = _isSpeaking.asStateFlow()

    private var currentOnDoneCallback: (() -> Unit)? = null

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            val result = tts?.setLanguage(Locale.US)
            if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                Log.w(tag, "TTS language US not supported, falling back to default locale.")
                tts?.setLanguage(Locale.getDefault())
            }

            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {
                    _isSpeaking.value = true
                    Log.d(tag, "TTS started vocalizing: $utteranceId")
                }

                override fun onDone(utteranceId: String?) {
                    _isSpeaking.value = false
                    Log.d(tag, "TTS finished vocalizing: $utteranceId")
                    currentOnDoneCallback?.invoke()
                    currentOnDoneCallback = null
                }

                override fun onError(utteranceId: String?) {
                    _isSpeaking.value = false
                    Log.w(tag, "TTS error occurred on utterance: $utteranceId")
                    currentOnDoneCallback?.invoke()
                    currentOnDoneCallback = null
                }
            })

            isInitialized = true
            Log.i(tag, "TextToSpeech engine initialized successfully.")
        } else {
            Log.e(tag, "Failed to initialize TextToSpeech engine (status: $status).")
            isInitialized = false
        }
    }

    /**
     * Speak response, preferring spokenText over visual text.
     */
    fun speak(text: String, spokenText: String? = null, onDone: (() -> Unit)? = null) {
        if (!isInitialized || tts == null) {
            Log.w(tag, "TTS not initialized, skipping vocalization.")
            onDone?.invoke()
            return
        }

        val textToVocalize = if (!spokenText.isNullOrBlank()) {
            spokenText
        } else {
            text
        }.trim()

        if (textToVocalize.isEmpty()) {
            onDone?.invoke()
            return
        }

        currentOnDoneCallback = onDone
        val utteranceId = "jarvis_utt_" + UUID.randomUUID().toString()

        Log.i(tag, "Vocalizing: '$textToVocalize'")
        tts?.speak(textToVocalize, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
    }

    fun stopSpeaking() {
        try {
            tts?.stop()
            _isSpeaking.value = false
            currentOnDoneCallback = null
            Log.i(tag, "TTS vocalization stopped.")
        } catch (e: Exception) {
            Log.w(tag, "Error stopping TTS: ${e.message}")
        }
    }

    fun shutdown() {
        try {
            stopSpeaking()
            tts?.shutdown()
            tts = null
            isInitialized = false
            Log.i(tag, "TTS engine shutdown cleanly.")
        } catch (e: Exception) {
            Log.w(tag, "Error shutting down TTS: ${e.message}")
        }
    }
}
