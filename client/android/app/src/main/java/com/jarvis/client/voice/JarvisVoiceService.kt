package com.jarvis.client.voice

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.jarvis.client.JarvisApp
import com.jarvis.client.R
import com.jarvis.client.model.WakeWordEvent
import com.jarvis.client.ui.MainActivity
import com.jarvis.client.voice.kws.WakeWordProfile
import com.jarvis.client.voice.kws.WakeWordProfileManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.atomic.AtomicLong

/**
 * Mutually-exclusive microphone owner tracking.
 */
enum class MicOwner {
    NONE,
    KWS_SPOTTER,
    SPEECH_RECOGNIZER,
    CONFIRMATION_LISTENER
}

/**
 * Service lifecycle states for transparent user feedback and atomic state machine tracking.
 */
enum class ServiceVoiceState {
    NONE,
    STARTING_STANDBY,
    STANDBY_RECORDING,
    WAKE_DETECTED,
    LISTENING_COMMAND,
    WAITING_CONFIRMATION,
    LISTENING_CONFIRMATION,
    EXECUTING,
    TTS,
    RECOVERING,
    PAUSED,
    ERROR,
    STOPPED;

    companion object {
        val STANDBY: ServiceVoiceState get() = STANDBY_RECORDING
        val LISTENING: ServiceVoiceState get() = LISTENING_COMMAND
        val PROCESSING: ServiceVoiceState get() = EXECUTING
        val SPEAKING: ServiceVoiceState get() = TTS
        val REARMING: ServiceVoiceState get() = RECOVERING
        val MIC_RELEASED: ServiceVoiceState get() = RECOVERING
        val MIC_HANDOFF: ServiceVoiceState get() = RECOVERING
        val COMMAND_RECEIVED: ServiceVoiceState get() = EXECUTING
    }
}

/**
 * Dedicated Foreground Service managing Background Voice Standby, Wake-Word detection,
 * sequential microphone handoff, and command routing.
 */
class JarvisVoiceService : Service() {

    private val tag = TAG_KWS
    private val scope = CoroutineScope(Dispatchers.Main + Job())
    private val timeFormat = SimpleDateFormat("HH:mm:ss.SSS", Locale.US)

    private val _voiceState = MutableStateFlow(ServiceVoiceState.STARTING_STANDBY)
    val voiceState: StateFlow<ServiceVoiceState> = _voiceState.asStateFlow()

    private lateinit var wakeWordDetector: WakeWordDetector
    private var isServiceActive = false
    private var handoffJob: Job? = null
    private var rearmJob: Job? = null
    private val sessionGeneration = AtomicLong(0L)

    // Latency & transition diagnostics
    private var wakeDetectedTime = 0L
    private var listeningStartTime = 0L
    private var commandReceivedTime = 0L
    private var commandCompleteTime = 0L
    private var kwsRestartTime = 0L

    // Correlated confirmation state
    private var pendingVoiceTurnId: String? = null
    private var pendingActionId: String? = null
    private var isAwaitingVoiceConfirmation: Boolean = false
    private var confirmationRetryCount = 0

    private fun getActiveWakeProfile(): WakeWordProfile {
        return if (::wakeWordDetector.isInitialized) {
            (wakeWordDetector as? SherpaKwsDetector)?.getActiveProfile()
                ?: WakeWordProfileManager(applicationContext).loadProfile(JarvisApp.instance.settingsManager.userId)
        } else {
            WakeWordProfileManager(applicationContext).loadProfile(JarvisApp.instance.settingsManager.userId)
        }
    }

    companion object {
        const val TAG_KWS = "JARVIS_KWS"
        const val NOTIFICATION_ID = 2001
        const val CHANNEL_ID = "jarvis_voice_standby_channel"
        const val CHANNEL_NAME = "Jarvis Voice Standby"

        const val ACTION_START = "com.jarvis.client.action.START_VOICE_SERVICE"
        const val ACTION_STOP = "com.jarvis.client.action.STOP_VOICE_SERVICE"
        const val ACTION_TRIGGER_LISTEN = "com.jarvis.client.action.TRIGGER_LISTEN"
        const val ACTION_EMERGENCY_STOP = "com.jarvis.client.action.EMERGENCY_STOP"
        const val ACTION_PAUSE_STANDBY = "com.jarvis.client.action.PAUSE_VOICE_STANDBY"
        const val ACTION_RESUME_STANDBY = "com.jarvis.client.action.RESUME_VOICE_STANDBY"
        const val ACTION_RELOAD_PROFILE = "com.jarvis.client.action.RELOAD_VOICE_PROFILE"

        private val _isRunning = MutableStateFlow(false)
        val isRunning: StateFlow<Boolean> = _isRunning.asStateFlow()

        private val _currentState = MutableStateFlow(ServiceVoiceState.STOPPED)
        val currentState: StateFlow<ServiceVoiceState> = _currentState.asStateFlow()

        private val _micOwner = MutableStateFlow(MicOwner.NONE)
        val micOwner: StateFlow<MicOwner> = _micOwner.asStateFlow()

        private val _diagnostics = MutableStateFlow(VoiceDiagnostics())
        val diagnostics: StateFlow<VoiceDiagnostics> = _diagnostics.asStateFlow()

        private val _micDiagnostics = MutableStateFlow(MicrophoneDiagnostics())
        val micDiagnostics: StateFlow<MicrophoneDiagnostics> = _micDiagnostics.asStateFlow()

        fun isStandbyPaused(): Boolean {
            return _currentState.value == ServiceVoiceState.PAUSED
        }

        fun startService(context: Context) {
            val intent = Intent(context, JarvisVoiceService::class.java).apply {
                action = ACTION_START
            }
            ContextCompat.startForegroundService(context, intent)
        }

        fun stopService(context: Context) {
            val intent = Intent(context, JarvisVoiceService::class.java).apply {
                action = ACTION_STOP
            }
            context.startService(intent)
        }

        fun triggerListen(context: Context) {
            val intent = Intent(context, JarvisVoiceService::class.java).apply {
                action = ACTION_TRIGGER_LISTEN
            }
            context.startService(intent)
        }

        fun pauseStandby(context: Context) {
            val intent = Intent(context, JarvisVoiceService::class.java).apply {
                action = ACTION_PAUSE_STANDBY
            }
            context.startService(intent)
        }

        fun resumeStandby(context: Context) {
            val intent = Intent(context, JarvisVoiceService::class.java).apply {
                action = ACTION_RESUME_STANDBY
            }
            context.startService(intent)
        }

        fun reloadActiveProfile(context: Context) {
            val intent = Intent(context, JarvisVoiceService::class.java).apply {
                action = ACTION_RELOAD_PROFILE
            }
            context.startService(intent)
        }
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        val app = JarvisApp.instance
        val detector = SherpaKwsDetector(applicationContext, activeUserId = app.settingsManager.userId)
        detector.onWatchdogFailureListener = { reason ->
            if (isServiceActive && _voiceState.value == ServiceVoiceState.STANDBY_RECORDING) {
                Log.w(tag, "VOICE_STATE: WATCHDOG_TRIGGERED_SELF_HEALING reason='$reason'")
                recoverToStandby("Watchdog failure: $reason")
            }
        }
        wakeWordDetector = detector

        val repository = app.repository
        val speechRecognizer = app.speechRecognitionManager
        val ttsManager = app.ttsManager

        // Sync basic diagnostics
        scope.launch {
            wakeWordDetector.diagnostics.collect { diag ->
                _diagnostics.value = diag
            }
        }

        // Sync detailed microphone & ONNX capture diagnostics
        scope.launch {
            wakeWordDetector.micDiagnostics.collect { micDiag ->
                _micDiagnostics.value = micDiag
                if (isServiceActive && _voiceState.value == ServiceVoiceState.STANDBY_RECORDING) {
                    updateNotification(
                        title = formatStandbyTitle(micDiag),
                        content = formatStandbySummary(micDiag)
                    )
                }
            }
        }

        // Observe speech recognition results
        scope.launch {
            speechRecognizer.transcriptionResults.collect { recognizedText ->
                if (!isServiceActive) return@collect
                val state = _voiceState.value
                if (state != ServiceVoiceState.LISTENING_COMMAND && state != ServiceVoiceState.LISTENING_CONFIRMATION) {
                    Log.d(tag, "Ignored late transcription '$recognizedText' while state=$state")
                    return@collect
                }

                val now = System.currentTimeMillis()
                val latFromListen = if (listeningStartTime > 0) now - listeningStartTime else 0L
                Log.i(tag, "VOICE_STATE: SPEECH_RESULT text='$recognizedText' elapsed_since_listening=${latFromListen}ms")
                val profile = getActiveWakeProfile()

                if (isAwaitingVoiceConfirmation || state == ServiceVoiceState.LISTENING_CONFIRMATION) {
                    val turnId = pendingVoiceTurnId
                    val actionId = pendingActionId
                    val trimmed = recognizedText.trim()
                    val lower = trimmed.lowercase(Locale.US)
                    val isApproval = listOf("yes", "allow", "confirm", "proceed", "sure", "ok", "okay", "do it", "yeah", "yep", "accept").any { lower.contains(it) }
                    val isDenial = listOf("no", "deny", "cancel", "stop", "don't", "dont", "nope", "never", "reject").any { lower.contains(it) }

                    Log.i(
                        tag,
                        "CONFIRMATION_RECOGNIZED text='$trimmed' voice_turn_id=$turnId pending_action=$actionId is_approval=$isApproval is_denial=$isDenial timestamp=$now"
                    )

                    val dispatchText = if (isApproval) "yes" else if (isDenial) "no" else trimmed
                    transitionTo(ServiceVoiceState.EXECUTING, MicOwner.NONE, "Confirmation recognized: '$dispatchText'")
                    updateNotification("Processing Confirmation", "Dispatching: \"$dispatchText\"")

                    isAwaitingVoiceConfirmation = false
                    confirmationRetryCount = 0
                    pendingVoiceTurnId = null
                    pendingActionId = null

                    Log.i(
                        tag,
                        "CONFIRMATION_SENT voice_turn_id=$turnId pending_action=$actionId text='$dispatchText' timestamp=$now"
                    )

                    repository.sendVoiceTurn(
                        text = dispatchText,
                        wakeProfileId = profile.profileId,
                        wakePhrase = profile.phrase
                    )
                    return@collect
                }

                val cleanedCommand = cleanWakePrefix(recognizedText, profile)

                if (cleanedCommand.isBlank()) {
                    Log.i(tag, "Recognized text was only wake phrase ('$recognizedText') -> No command -> Returning to standby")
                    recoverToStandby("Wake-only utterance without command")
                    return@collect
                }

                commandReceivedTime = now
                Log.i(
                    tag,
                    "LATENCY_METRIC: LISTENING_COMMAND -> VOICE_TURN_RECEIVED ${now - listeningStartTime}ms (turn='$cleanedCommand')"
                )

                transitionTo(ServiceVoiceState.EXECUTING, MicOwner.NONE, "Command recognized: '$cleanedCommand'")
                updateNotification("Processing...", "Processing: \"$cleanedCommand\"")

                repository.sendVoiceTurn(
                    text = cleanedCommand,
                    wakeProfileId = profile.profileId,
                    wakePhrase = profile.phrase
                )
            }
        }

        var lastProcessedVoiceTurnId: String? = null

        // Observe backend voice responses for vocalization
        scope.launch {
            repository.voiceResponses.collect { voiceResp ->
                if (!isServiceActive) return@collect
                if (_voiceState.value != ServiceVoiceState.EXECUTING) return@collect

                lastProcessedVoiceTurnId = voiceResp.voiceTurnId
                val text = voiceResp.text.ifBlank { "Done." }
                val spoken = voiceResp.spokenResponse ?: text
                val requiresConf = voiceResp.requiresConfirmation

                if (requiresConf) {
                    pendingVoiceTurnId = voiceResp.voiceTurnId
                    pendingActionId = voiceResp.pendingActionId ?: voiceResp.capabilityId
                    isAwaitingVoiceConfirmation = true
                    confirmationRetryCount = 0
                    Log.i(
                        tag,
                        "CONFIRMATION_PENDING_REGISTERED voice_turn_id='$pendingVoiceTurnId' pending_action='$pendingActionId'"
                    )
                    transitionTo(ServiceVoiceState.WAITING_CONFIRMATION, MicOwner.NONE, "Awaiting voice confirmation response")
                } else {
                    transitionTo(ServiceVoiceState.TTS, MicOwner.NONE, "TTS vocalizing response: '$spoken'")
                }

                updateNotification("Jarvis Speaking", text)

                val curTurnId = pendingVoiceTurnId
                val curActionId = pendingActionId
                val currentGen = sessionGeneration.get()

                scope.launch {
                    var callbackInvoked = false
                    val invokeNextState = {
                        if (!callbackInvoked && sessionGeneration.get() == currentGen) {
                            callbackInvoked = true
                            if (requiresConf) {
                                Log.i(tag, "VOICE_STATE: AWAITING_CONFIRMATION -> Starting confirmation listener")
                                startSequentialHandoffToListening(
                                    isConfirmation = true,
                                    turnId = curTurnId,
                                    actionId = curActionId
                                )
                            } else {
                                commandCompleteTime = System.currentTimeMillis()
                                recoverToStandby("TTS finished speaking", t0 = commandCompleteTime)
                            }
                        }
                    }

                    ttsManager.speak(text = text, spokenText = spoken) {
                        Log.i(tag, "VOICE_STATE: TTS_COMPLETE text='$spoken'")
                        invokeNextState()
                    }

                    // Timeout safeguard: calculate duration based on word count + buffer
                    val wordCount = spoken.split(Regex("\\s+")).filter { it.isNotBlank() }.size
                    val timeoutMs = maxOf(4000L, wordCount * 150L + 3000L)
                    delay(timeoutMs)
                    if (!callbackInvoked && isServiceActive && (_voiceState.value == ServiceVoiceState.TTS || _voiceState.value == ServiceVoiceState.WAITING_CONFIRMATION) && sessionGeneration.get() == currentGen) {
                        Log.w(tag, "TTS playback safety timeout after ${timeoutMs}ms -> auto-progressing")
                        invokeNextState()
                    }
                }
            }
        }

        // Observe backend chat responses as fallback vocalization if not processed by voiceResponses
        scope.launch {
            repository.chatResponses.collect { wsResponse ->
                if (!isServiceActive) return@collect
                if (_voiceState.value != ServiceVoiceState.EXECUTING) return@collect

                val payload = wsResponse.payload
                val turnMeta = payload.metadata?.get("voice_turn_id")?.toString()
                if (turnMeta != null && turnMeta == lastProcessedVoiceTurnId) {
                    return@collect
                }

                val text = payload.text.ifBlank { "Done." }
                val spoken = payload.spokenText ?: text
                val requiresConf = payload.requiresConfirmation

                if (requiresConf) {
                    pendingVoiceTurnId = turnMeta ?: pendingVoiceTurnId
                    pendingActionId = payload.intent
                    isAwaitingVoiceConfirmation = true
                    confirmationRetryCount = 0
                    Log.i(
                        tag,
                        "CONFIRMATION_PENDING_REGISTERED_FALLBACK voice_turn_id='$pendingVoiceTurnId' pending_action='$pendingActionId'"
                    )
                    transitionTo(ServiceVoiceState.WAITING_CONFIRMATION, MicOwner.NONE, "Awaiting voice confirmation response (fallback)")
                } else {
                    transitionTo(ServiceVoiceState.TTS, MicOwner.NONE, "TTS vocalizing fallback response: '$text'")
                }

                updateNotification("Jarvis Speaking", text)

                val curTurnId = pendingVoiceTurnId
                val curActionId = pendingActionId
                val currentGen = sessionGeneration.get()

                scope.launch {
                    var callbackInvoked = false
                    val invokeNextState = {
                        if (!callbackInvoked && sessionGeneration.get() == currentGen) {
                            callbackInvoked = true
                            if (requiresConf) {
                                Log.i(tag, "VOICE_STATE: AWAITING_CONFIRMATION fallback -> Starting confirmation listener")
                                startSequentialHandoffToListening(
                                    isConfirmation = true,
                                    turnId = curTurnId,
                                    actionId = curActionId
                                )
                            } else {
                                commandCompleteTime = System.currentTimeMillis()
                                recoverToStandby("TTS finished speaking fallback", t0 = commandCompleteTime)
                            }
                        }
                    }

                    ttsManager.speak(text = text, spokenText = spoken) {
                        Log.i(tag, "VOICE_STATE: TTS_COMPLETE fallback text='$spoken'")
                        invokeNextState()
                    }

                    val wordCount = spoken.split(Regex("\\s+")).filter { it.isNotBlank() }.size
                    val timeoutMs = maxOf(4000L, wordCount * 150L + 3000L)
                    delay(timeoutMs)
                    if (!callbackInvoked && isServiceActive && (_voiceState.value == ServiceVoiceState.TTS || _voiceState.value == ServiceVoiceState.WAITING_CONFIRMATION) && sessionGeneration.get() == currentGen) {
                        Log.w(tag, "TTS fallback playback safety timeout after ${timeoutMs}ms -> auto-progressing")
                        invokeNextState()
                    }
                }
            }
        }

        // Observe speech recognition errors / timeouts
        scope.launch {
            speechRecognizer.errorEvents.collect { err ->
                if (!isServiceActive) return@collect
                val state = _voiceState.value
                if (state == ServiceVoiceState.LISTENING_COMMAND || state == ServiceVoiceState.LISTENING_CONFIRMATION) {
                    if (state == ServiceVoiceState.LISTENING_CONFIRMATION && confirmationRetryCount < 2) {
                        confirmationRetryCount++
                        Log.w(
                            tag,
                            "CONFIRMATION_SPEECH_ERROR error='$err' -> Attempting retry $confirmationRetryCount of 2 for confirmation listening"
                        )
                        startSequentialHandoffToListening(
                            isConfirmation = true,
                            turnId = pendingVoiceTurnId,
                            actionId = pendingActionId
                        )
                        return@collect
                    }

                    if (isAwaitingVoiceConfirmation) {
                        Log.w(
                            tag,
                            "CONFIRMATION_FAILED voice_turn_id=$pendingVoiceTurnId error='$err' -> Re-arming to standby"
                        )
                        isAwaitingVoiceConfirmation = false
                        confirmationRetryCount = 0
                        pendingVoiceTurnId = null
                        pendingActionId = null
                    } else {
                        Log.w(tag, "VOICE_STATE: SPEECH_ERROR error='$err' in $state -> Recovering to standby")
                    }
                    recoverToStandby("SpeechRecognizer error: $err")
                }
            }
        }

        // Observe WebSocket connection state drops during voice turns
        scope.launch {
            repository.connectionState.collect { connState ->
                if (!isServiceActive) return@collect
                if (!connState.isOnline && (_voiceState.value == ServiceVoiceState.EXECUTING || _voiceState.value == ServiceVoiceState.TTS)) {
                    Log.w(tag, "WebSocket disconnected during turn -> recovering to standby")
                    recoverToStandby("WebSocket disconnected")
                }
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                Log.i(tag, "Received ACTION_STOP -> stopping service")
                stopForegroundService()
                return START_NOT_STICKY
            }
            ACTION_TRIGGER_LISTEN -> {
                Log.i(tag, "Received ACTION_TRIGGER_LISTEN -> manual listen trigger")
                startSequentialHandoffToListening()
            }
            ACTION_EMERGENCY_STOP -> {
                Log.i(tag, "Received ACTION_EMERGENCY_STOP -> emergency stop")
                handleEmergencyStop()
            }
            ACTION_PAUSE_STANDBY -> {
                Log.i(tag, "Received ACTION_PAUSE_STANDBY -> pausing wake detector for calibration")
                pauseStandbyForCalibration()
            }
            ACTION_RESUME_STANDBY -> {
                Log.i(tag, "Received ACTION_RESUME_STANDBY -> resuming wake detector after calibration")
                resumeStandbyFromCalibration()
            }
            ACTION_RELOAD_PROFILE -> {
                Log.i(tag, "Received ACTION_RELOAD_PROFILE -> reloading active profile and re-arming")
                reloadProfileAndRestartStandby()
            }
            else -> {
                startForegroundService()
            }
        }
        return START_STICKY
    }

    private fun reloadProfileAndRestartStandby() {
        handoffJob?.cancel()
        rearmJob?.cancel()
        if (::wakeWordDetector.isInitialized) {
            wakeWordDetector.stopListening()
        }
        scope.launch {
            delay(SherpaKwsDetector.AUDIO_HANDOFF_SETTLE_MS)
            if (!isServiceActive) return@launch

            val reloaded = (wakeWordDetector as? SherpaKwsDetector)?.reloadProfile() ?: false
            val newProfile = getActiveWakeProfile()
            Log.i(
                tag,
                "Detector reload outcome: $reloaded | " +
                "Active Profile: '${newProfile.phrase}' (User: ${newProfile.userId})"
            )
            recoverToStandby("Reloaded profile '${newProfile.phrase}'")
        }
    }

    private fun applyThresholdConfiguration() {
        if (!::wakeWordDetector.isInitialized) return
        val profile = getActiveWakeProfile()
        (wakeWordDetector as? SherpaKwsDetector)?.applyExplicitThresholds(
            score = profile.keywordsScore,
            threshold = profile.keywordsThreshold
        )
    }

    private fun transitionTo(newState: ServiceVoiceState, newOwner: MicOwner, reason: String) {
        val oldState = _voiceState.value
        val oldOwner = _micOwner.value
        if (oldState == newState && oldOwner == newOwner) return

        _voiceState.value = newState
        _currentState.value = newState
        _micOwner.value = newOwner

        val timestamp = timeFormat.format(Date())
        Log.i(
            tag,
            "STATE_TRANSITION [$timestamp] state: $oldState -> $newState | mic: $oldOwner -> $newOwner | reason: $reason | gen=${sessionGeneration.get()}"
        )
    }

    fun pauseStandbyForCalibration() {
        handoffJob?.cancel()
        rearmJob?.cancel()
        if (::wakeWordDetector.isInitialized) {
            wakeWordDetector.stopListening()
        }
        val app = JarvisApp.instance
        app.speechRecognitionManager.stopListening()
        app.ttsManager.stopSpeaking()

        transitionTo(ServiceVoiceState.PAUSED, MicOwner.NONE, "Wake-Word calibration session in progress")
        updateNotification("Jarvis Standby Paused", "Wake-Word calibration session active")
    }

    fun resumeStandbyFromCalibration() {
        applyThresholdConfiguration()
        recoverToStandby("Resumed from calibration")
    }

    fun startStandby() {
        if (!isServiceActive) {
            startForegroundService()
        } else {
            recoverToStandby("Manual startStandby requested")
        }
    }

    fun stopStandby() {
        stopForegroundService()
    }

    private fun startForegroundService() {
        if (isServiceActive) {
            Log.d(tag, "startForegroundService called while already active -> verifying KWS is listening")
            recoverToStandby("startForegroundService while active")
            return
        }
        isServiceActive = true
        _isRunning.value = true

        applyThresholdConfiguration()
        val profile = getActiveWakeProfile()
        val notification = buildNotification(
            title = "Jarvis Voice Standby",
            content = "Initializing microphone standby...",
            state = ServiceVoiceState.STARTING_STANDBY
        )

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }

        recoverToStandby("Initial service foreground start")
        Log.i(tag, "JarvisVoiceService started in foreground for active phrase: '${profile.phrase}' (user='${profile.userId}')")
    }

    private fun onWakeWordDetected() {
        if (!isServiceActive) return
        if (_voiceState.value != ServiceVoiceState.STANDBY_RECORDING) {
            Log.d(tag, "Ignored wake trigger while in state ${_voiceState.value}")
            return
        }

        val now = System.currentTimeMillis()
        wakeDetectedTime = now
        val profile = getActiveWakeProfile()
        val wakeEvent = WakeWordEvent(
            userId = profile.userId,
            profileId = profile.profileId,
            phrase = profile.phrase,
            timestamp = now,
            confidence = _micDiagnostics.value.lastConfidence,
            source = "sherpa_kws"
        )
        Log.i(tag, "VOICE_STATE: STANDBY_EXIT | Wake detected for phrase='${profile.phrase}'")
        Log.i(tag, "WakeWordEvent triggered: phrase='${wakeEvent.phrase}' (profile='${wakeEvent.profileId}', user='${wakeEvent.userId}')")

        transitionTo(ServiceVoiceState.WAKE_DETECTED, MicOwner.NONE, "KWS spotter detected wake phrase '${profile.phrase}'")

        wakeWordDetector.stopListening()
        Log.i(tag, "VOICE_STATE: KWS_STOPPED")

        // Handoff to SpeechRecognizer
        startSequentialHandoffToListening()
    }

    private fun startSequentialHandoffToListening(
        isConfirmation: Boolean = false,
        turnId: String? = null,
        actionId: String? = null,
    ) {
        handoffJob?.cancel()
        rearmJob?.cancel()
        val currentGen = sessionGeneration.incrementAndGet()

        handoffJob = scope.launch {
            if (::wakeWordDetector.isInitialized) {
                wakeWordDetector.stopListening()
            }
            transitionTo(
                ServiceVoiceState.RECOVERING,
                MicOwner.NONE,
                if (isConfirmation) "Handoff to confirmation listening" else "Handoff to speech recognizer"
            )

            val settleMs = SherpaKwsDetector.AUDIO_HANDOFF_SETTLE_MS
            delay(settleMs)
            if (!isServiceActive || sessionGeneration.get() != currentGen) return@launch

            val now = System.currentTimeMillis()
            listeningStartTime = now
            if (wakeDetectedTime > 0) {
                Log.i(
                    tag,
                    "LATENCY_METRIC: WAKE_DETECTED -> LISTENING_COMMAND ${now - wakeDetectedTime}ms (HAL settle=${settleMs}ms)"
                )
            }

            val app = JarvisApp.instance
            if (isConfirmation) {
                transitionTo(
                    ServiceVoiceState.LISTENING_CONFIRMATION,
                    MicOwner.CONFIRMATION_LISTENER,
                    "Confirmation listening started"
                )
                updateNotification("Awaiting Confirmation", "Say 'Yes' to allow, 'No' to deny...")
                Log.i(
                    tag,
                    "CONFIRMATION_LISTENING_STARTED voice_turn_id=${turnId ?: pendingVoiceTurnId} pending_action=${actionId ?: pendingActionId} mic_owner=CONFIRMATION_LISTENER timestamp=$now"
                )
            } else {
                transitionTo(
                    ServiceVoiceState.LISTENING_COMMAND,
                    MicOwner.SPEECH_RECOGNIZER,
                    "SpeechRecognizer started"
                )
                updateNotification("Jarvis Listening", "Speak your command now...")
            }

            app.speechRecognitionManager.startListening()
            Log.i(tag, "VOICE_STATE: SPEECH_RECOGNIZER_STARTED (isConfirmation=$isConfirmation, gen=$currentGen)")
        }
    }

    /**
     * Post-command window continuous diagnostics to trace KWS readiness and PCM continuity.
     */
    private fun launchPostCommandWindowDiagnostics(t0: Long, gen: Long) {
        scope.launch {
            val offsets = listOf(100L, 250L, 500L, 1000L, 2000L, 5000L)
            for (offset in offsets) {
                val targetTime = t0 + offset
                val delayMs = targetTime - System.currentTimeMillis()
                if (delayMs > 0) delay(delayMs)
                if (!isServiceActive || sessionGeneration.get() != gen) break

                val detector = wakeWordDetector as? SherpaKwsDetector
                val kwsReady = detector?.isKeywordSpotterReady() ?: false
                val pcmHealthy = detector?.isPcmHealthy(1500L) ?: false
                val loopAlive = detector?.isDetectionLoopAlive() ?: false
                val micDiag = _micDiagnostics.value

                Log.i(
                    TAG_KWS,
                    "KWS_WINDOW_DIAG offset_ms=$offset KWS_READY=$kwsReady PCM_HEALTHY=$pcmHealthy " +
                    "DETECTION_LOOP_ALIVE=$loopAlive RMS=${micDiag.currentRms} PEAK=${micDiag.currentPeak} " +
                    "sessionGen=$gen micOwner=${_micOwner.value} state=${_voiceState.value}"
                )
            }
        }
    }

    /**
     * Single authoritative recovery function for all terminal states:
     * SUCCESS, FAILURE, TIMEOUT, CANCEL, CONFIRMATION_DENIED, SPEECH_ERROR, KWS_ERROR.
     */
    private fun recoverToStandby(reason: String, t0: Long = System.currentTimeMillis()) {
        if (!isServiceActive) return
        handoffJob?.cancel()
        rearmJob?.cancel()
        val currentGen = sessionGeneration.incrementAndGet()

        launchPostCommandWindowDiagnostics(t0, currentGen)

        rearmJob = scope.launch {
            val app = JarvisApp.instance
            app.speechRecognitionManager.stopListening()
            app.ttsManager.stopSpeaking()

            transitionTo(ServiceVoiceState.RECOVERING, MicOwner.NONE, "Audio settle before KWS re-arm ($reason)")
            val settleMs = SherpaKwsDetector.AUDIO_HANDOFF_SETTLE_MS
            delay(settleMs)
            if (!isServiceActive || sessionGeneration.get() != currentGen) {
                Log.w(TAG_KWS, "STALE_CALLBACK_IGNORED callback='recoverToStandby.settle' callbackGeneration=$currentGen currentGeneration=${sessionGeneration.get()}")
                return@launch
            }

            kwsRestartTime = System.currentTimeMillis()
            if (commandCompleteTime > 0) {
                Log.i(
                    TAG_KWS,
                    "LATENCY_METRIC: COMMAND_COMPLETE -> KWS_RESTART ${kwsRestartTime - commandCompleteTime}ms"
                )
            }

            Log.i(TAG_KWS, "VOICE_STATE: KWS_RESTART_REQUEST reason='$reason' gen=$currentGen")
            applyThresholdConfiguration()

            if (::wakeWordDetector.isInitialized) {
                val detector = wakeWordDetector as? SherpaKwsDetector
                val initialChunks = detector?.getPcmChunksRead() ?: 0L
                wakeWordDetector.startListening {
                    onWakeWordDetected()
                }

                // Authoritative microphone verification: verify active PCM chunk delivery within 600ms
                var verified = false
                var firstPcmTime = 0L
                for (i in 1..12) {
                    delay(50L)
                    if (!isServiceActive || sessionGeneration.get() != currentGen) {
                        Log.w(TAG_KWS, "STALE_CALLBACK_IGNORED callback='recoverToStandby.verifyLoop' callbackGeneration=$currentGen currentGeneration=${sessionGeneration.get()}")
                        return@launch
                    }
                    val isRecAndStreaming = detector?.isActuallyRecordingAndStreaming(initialChunks) ?: detector?.isActuallyRecording() ?: true
                    val kwsReady = detector?.isKeywordSpotterReady() ?: true
                    val loopAlive = detector?.isDetectionLoopAlive() ?: true
                    if (isRecAndStreaming && kwsReady && loopAlive) {
                        verified = true
                        firstPcmTime = System.currentTimeMillis()
                        break
                    }
                }

                val audioRecordState = detector?.getAudioRecordState() ?: "INITIALIZED"
                val recordingState = detector?.getRecordingState() ?: "RECORDING"
                val pcmChunks = detector?.getPcmChunksRead() ?: 0L
                val lastPcmReadAgeMs = detector?.getPcmHeartbeatAgeMs() ?: 0L
                val keywordSpotterReady = detector?.isKeywordSpotterReady() ?: true
                val detectionLoopAlive = detector?.isDetectionLoopAlive() ?: true
                val micOwner = MicOwner.KWS_SPOTTER

                if (verified && audioRecordState == "INITIALIZED" && recordingState == "RECORDING" && pcmChunks > 0 && lastPcmReadAgeMs <= 1500L && keywordSpotterReady && detectionLoopAlive) {
                    val now = System.currentTimeMillis()
                    Log.i(
                        TAG_KWS,
                        "LATENCY_METRIC: KWS_RESTART -> FIRST_PCM ${firstPcmTime - kwsRestartTime}ms | FIRST_PCM -> STANDBY_CONFIRMED ${now - firstPcmTime}ms"
                    )

                    Log.i(
                        TAG_KWS,
                        "KWS_STANDBY_READY sessionGeneration=$currentGen audioRecordState=$audioRecordState recordingState=$recordingState pcmChunks=$pcmChunks lastPcmReadAgeMs=$lastPcmReadAgeMs keywordSpotterReady=$keywordSpotterReady detectionLoopAlive=$detectionLoopAlive micOwner=$micOwner"
                    )

                    transitionTo(
                        ServiceVoiceState.STANDBY_RECORDING,
                        MicOwner.KWS_SPOTTER,
                        "KWS spotter active & verified recording ($reason)"
                    )
                    val micDiag = _micDiagnostics.value
                    updateNotification(
                        formatStandbyTitle(micDiag),
                        formatStandbySummary(micDiag)
                    )
                    Log.i(TAG_KWS, "VOICE_STATE: STANDBY_CONFIRMED recording=true verified_pcm=true gen=$currentGen reason='$reason'")
                } else {
                    Log.e(
                        TAG_KWS,
                        "VOICE_STATE: STANDBY_FAILED_VERIFICATION audioRecordState=$audioRecordState recordingState=$recordingState pcmChunks=$pcmChunks lastPcmReadAgeMs=$lastPcmReadAgeMs keywordSpotterReady=$keywordSpotterReady detectionLoopAlive=$detectionLoopAlive"
                    )
                    transitionTo(ServiceVoiceState.ERROR, MicOwner.NONE, "Standby microphone restart failed: Verification incomplete")
                    updateNotification("Jarvis Standby Error", "Microphone capture stalled. Tap to retry.")
                }
            }
        }
    }

    private fun handleEmergencyStop() {
        handoffJob?.cancel()
        rearmJob?.cancel()
        val app = JarvisApp.instance
        app.speechRecognitionManager.stopListening()
        app.ttsManager.stopSpeaking()
        app.repository.sendMessage("stop")
        recoverToStandby("Emergency stop requested")
    }

    private fun stopForegroundService() {
        isServiceActive = false
        handoffJob?.cancel()
        rearmJob?.cancel()
        sessionGeneration.incrementAndGet()
        _isRunning.value = false
        transitionTo(ServiceVoiceState.STOPPED, MicOwner.NONE, "Service stopped")

        if (::wakeWordDetector.isInitialized) {
            wakeWordDetector.stopListening()
        }
        val app = JarvisApp.instance
        app.speechRecognitionManager.stopListening()
        app.ttsManager.stopSpeaking()

        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
        Log.i(tag, "JarvisVoiceService stopped cleanly.")
    }

    private fun cleanWakePrefix(text: String, profile: WakeWordProfile): String {
        if (text.isBlank()) return ""
        val trimmed = text.trim()

        val phraseTokens = profile.phrase.split(Regex("\\s+")).filter { it.isNotBlank() }
        val rawTokens = profile.tokenizedKeyword.split(Regex("\\s+")).filter { it.isNotBlank() }
        val variants = (listOf(profile.phrase, profile.normalizedPhrase) + profile.phraseVariants + phraseTokens + rawTokens).distinct()

        if (variants.any { trimmed.equals(it, ignoreCase = true) }) {
            return ""
        }

        val escapedPattern = variants.joinToString("|") { Regex.escape(it) }
        val wakeRegex = Regex(
            """^(?:(?:um|uh|ah|please|hey|hello|hi|okay|ok)\s+)?(?:$escapedPattern)[,\s\:\.\!\-]*(.*)$""",
            RegexOption.IGNORE_CASE
        )
        val match = wakeRegex.matchEntire(trimmed)
        if (match != null && match.groupValues.size > 1) {
            val trailing = match.groupValues[1].trim().trimStart(',', ':', '.', '!', '-', ' ')
            if (variants.any { trailing.equals(it, ignoreCase = true) }) {
                return ""
            }
            return trailing
        }

        return trimmed
    }

    private fun formatStandbyTitle(diag: MicrophoneDiagnostics): String {
        return if (diag.pcmChunksRead > 0) {
            String.format(
                Locale.US,
                "Jarvis Voice Standby (RMS: %.3f | Peak: %.2f)",
                diag.currentRms,
                diag.currentPeak
            )
        } else {
            "Jarvis Voice Standby"
        }
    }

    private fun formatStandbySummary(diag: MicrophoneDiagnostics): String {
        return String.format(
            Locale.US,
            "Conf: %.3f | Max: %.3f | Thr: %.2f | Hits: %d/%d | W:%d",
            diag.lastConfidence,
            diag.maxConfidence,
            diag.threshold,
            diag.consecutiveHits,
            diag.consecutiveRequired,
            diag.wakeDetections
        )
    }

    private fun updateNotification(title: String, content: String) {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
        val notification = buildNotification(title, content, _voiceState.value)
        manager?.notify(NOTIFICATION_ID, notification)
    }

    private fun buildNotification(
        title: String,
        content: String,
        state: ServiceVoiceState
    ): Notification {
        val openAppIntent = Intent(this, MainActivity::class.java)
        val pendingOpen = PendingIntent.getActivity(
            this,
            0,
            openAppIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val listenIntent = Intent(this, JarvisVoiceService::class.java).apply {
            action = ACTION_TRIGGER_LISTEN
        }
        val pendingListen = PendingIntent.getService(
            this,
            1,
            listenIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val stopIntent = Intent(this, JarvisVoiceService::class.java).apply {
            action = ACTION_STOP
        }
        val pendingStop = PendingIntent.getService(
            this,
            2,
            stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val stateIcon = when (state) {
            ServiceVoiceState.STANDBY_RECORDING -> "🎙️"
            ServiceVoiceState.STARTING_STANDBY -> "⏳"
            ServiceVoiceState.WAKE_DETECTED -> "✨"
            ServiceVoiceState.LISTENING_COMMAND -> "🔴"
            ServiceVoiceState.WAITING_CONFIRMATION -> "❓"
            ServiceVoiceState.LISTENING_CONFIRMATION -> "🔴"
            ServiceVoiceState.EXECUTING -> "⚡"
            ServiceVoiceState.TTS -> "🔊"
            ServiceVoiceState.RECOVERING -> "🔁"
            ServiceVoiceState.PAUSED -> "⏸️"
            ServiceVoiceState.ERROR -> "⚠️"
            ServiceVoiceState.STOPPED -> "⏹️"
            ServiceVoiceState.NONE -> "⏹️"
        }

        val fullTitle = "$stateIcon $title"
        val micDiag = _micDiagnostics.value

        val bigText = if (state == ServiceVoiceState.STANDBY_RECORDING) {
            """
            AudioRecord: ${micDiag.recordingState} (${micDiag.audioSource} @ ${micDiag.sampleRate}Hz)
            Permission: ${if (micDiag.isPermissionGranted) "GRANTED" else "DENIED"} | State: ${micDiag.audioRecordState}
            PCM Frames: ${micDiag.pcmChunksRead} (Errors: ${micDiag.readErrors} [${micDiag.lastReadError}])
            RMS: ${String.format(Locale.US, "%.4f", micDiag.currentRms)} | Peak: ${String.format(Locale.US, "%.3f", micDiag.currentPeak)} (Max: ${String.format(Locale.US, "%.3f", micDiag.maxPeak)})
            Inferences: ${micDiag.inferencesEvaluated} | Conf: ${String.format(Locale.US, "%.3f", micDiag.lastConfidence)}
            Wake: ${micDiag.wakeDetections} | Rejected: ${micDiag.rejectedDetections}
            """.trimIndent()
        } else {
            content
        }

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_mic)
            .setContentTitle(fullTitle)
            .setContentText(content)
            .setStyle(NotificationCompat.BigTextStyle().bigText(bigText))
            .setContentIntent(pendingOpen)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .addAction(R.drawable.ic_mic, "Listen", pendingListen)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Stop", pendingStop)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Shows active status for Jarvis Background Voice Assistant"
                setShowBadge(false)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(channel)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        stopForegroundService()
        if (::wakeWordDetector.isInitialized) {
            wakeWordDetector.destroy()
        }
    }
}
