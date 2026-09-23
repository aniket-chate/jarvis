package com.jarvis.client.voice

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.Locale

/**
 * Speech Recognition Manager using Android SpeechRecognizer API.
 */
class SpeechRecognitionManager(
    private val context: Context,
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.Main + Job())
) : RecognitionListener {

    private val tag = "SpeechRecognizerManager"

    private var speechRecognizer: SpeechRecognizer? = null

    private val _voiceState = MutableStateFlow(VoiceState.IDLE)
    val voiceState: StateFlow<VoiceState> = _voiceState.asStateFlow()

    private val _transcriptionResults = MutableSharedFlow<String>()
    val transcriptionResults: SharedFlow<String> = _transcriptionResults.asSharedFlow()

    private val _partialResults = MutableSharedFlow<String>()
    val partialResults: SharedFlow<String> = _partialResults.asSharedFlow()

    private val _errorEvents = MutableSharedFlow<String>()
    val errorEvents: SharedFlow<String> = _errorEvents.asSharedFlow()

    fun hasPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
    }

    fun isRecognitionAvailable(): Boolean {
        return SpeechRecognizer.isRecognitionAvailable(context)
    }

    fun startListening(isConfirmation: Boolean = false) {
        if (!hasPermission()) {
            Log.w(tag, "Cannot start listening: RECORD_AUDIO permission missing.")
            _voiceState.value = VoiceState.ERROR
            scope.launch { _errorEvents.emit("Microphone permission denied.") }
            return
        }

        if (!isRecognitionAvailable()) {
            Log.w(tag, "Speech recognition is not available on this device.")
            _voiceState.value = VoiceState.ERROR
            scope.launch { _errorEvents.emit("Speech recognition service not available.") }
            return
        }

        scope.launch {
            try {
                destroyRecognizer()

                speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context).apply {
                    setRecognitionListener(this@SpeechRecognitionManager)
                }

                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(
                        RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
                    )
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                    putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                    putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)

                    if (isConfirmation) {
                        // Allow comfortable natural pause for hands-free confirmation
                        putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 3000L)
                        putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 2500L)
                        putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 2500L)
                    }
                }

                speechRecognizer?.startListening(intent)
                _voiceState.value = VoiceState.LISTENING
                Log.i(tag, "Speech recognition started listening (isConfirmation=$isConfirmation)...")
            } catch (e: Exception) {
                Log.e(tag, "Failed to start speech recognition: ${e.message}", e)
                _voiceState.value = VoiceState.ERROR
                _errorEvents.emit("Failed to initialize speech recognizer: ${e.message}")
            }
        }
    }

    fun stopListening() {
        try {
            speechRecognizer?.stopListening()
            if (_voiceState.value == VoiceState.LISTENING) {
                _voiceState.value = VoiceState.PROCESSING
            }
            Log.i(tag, "Speech recognition stopped.")
        } catch (e: Exception) {
            Log.w(tag, "Error stopping speech recognition: ${e.message}")
        }
    }

    fun cancel() {
        try {
            speechRecognizer?.cancel()
            _voiceState.value = VoiceState.IDLE
            Log.i(tag, "Speech recognition cancelled.")
        } catch (e: Exception) {
            Log.w(tag, "Error cancelling speech recognition: ${e.message}")
        }
    }

    fun destroy() {
        destroyRecognizer()
        _voiceState.value = VoiceState.IDLE
    }

    private fun destroyRecognizer() {
        try {
            speechRecognizer?.cancel()
            speechRecognizer?.destroy()
            speechRecognizer = null
        } catch (e: Exception) {
            Log.w(tag, "Error destroying speech recognizer: ${e.message}")
        }
    }

    // RecognitionListener Callbacks
    override fun onReadyForSpeech(params: Bundle?) {
        Log.d(tag, "onReadyForSpeech")
        _voiceState.value = VoiceState.LISTENING
    }

    override fun onBeginningOfSpeech() {
        Log.d(tag, "onBeginningOfSpeech")
        _voiceState.value = VoiceState.LISTENING
    }

    override fun onRmsChanged(rmsdB: Float) {
        // Amplitude feedback could be hooked here if needed
    }

    override fun onBufferReceived(buffer: ByteArray?) {}

    override fun onEndOfSpeech() {
        Log.d(tag, "onEndOfSpeech")
        _voiceState.value = VoiceState.PROCESSING
    }

    override fun onError(error: Int) {
        val errorMessage = when (error) {
            SpeechRecognizer.ERROR_AUDIO -> "Audio recording error"
            SpeechRecognizer.ERROR_CLIENT -> "Client-side recognition error"
            SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Insufficient permissions"
            SpeechRecognizer.ERROR_NETWORK -> "Network communication error"
            SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Network operation timeout"
            SpeechRecognizer.ERROR_NO_MATCH -> "No speech match found"
            SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Recognition service busy"
            SpeechRecognizer.ERROR_SERVER -> "Recognition server error"
            SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "No speech input detected"
            else -> "Speech recognition error ($error)"
        }

        Log.w(tag, "Speech recognition onError: $errorMessage ($error)")
        _voiceState.value = VoiceState.ERROR
        scope.launch {
            _errorEvents.emit(errorMessage)
            _voiceState.value = VoiceState.IDLE
        }
    }

    override fun onResults(results: Bundle?) {
        val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
        val text = matches?.firstOrNull()?.trim() ?: ""
        Log.i(tag, "Speech recognition final result: '$text'")

        _voiceState.value = VoiceState.IDLE
        if (text.isNotEmpty()) {
            scope.launch {
                _transcriptionResults.emit(text)
            }
        } else {
            scope.launch {
                _errorEvents.emit("No speech detected.")
            }
        }
    }

    override fun onPartialResults(partialResults: Bundle?) {
        val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
        val partialText = matches?.firstOrNull()?.trim() ?: ""
        if (partialText.isNotEmpty()) {
            Log.d(tag, "Speech recognition partial result: '$partialText'")
            scope.launch {
                _partialResults.emit(partialText)
            }
        }
    }

    override fun onEvent(eventType: Int, params: Bundle?) {}
}
