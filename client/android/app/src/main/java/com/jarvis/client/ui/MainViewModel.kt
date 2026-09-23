package com.jarvis.client.ui

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.jarvis.client.JarvisApp
import com.jarvis.client.model.ChatMessage
import com.jarvis.client.model.ConnectionState
import com.jarvis.client.repository.JarvisRepository
import com.jarvis.client.settings.JarvisSettingsManager
import com.jarvis.client.skill.AndroidSkillExecutor
import com.jarvis.client.voice.JarvisTTSManager
import com.jarvis.client.voice.JarvisVoiceService
import com.jarvis.client.voice.MicrophoneDiagnostics
import com.jarvis.client.voice.ServiceVoiceState
import com.jarvis.client.voice.SpeechRecognitionManager
import com.jarvis.client.voice.VoiceDiagnostics
import com.jarvis.client.voice.VoiceState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * ViewModel bridging UI components with the JarvisRepository and Voice Layer.
 */
class MainViewModel(application: Application) : AndroidViewModel(application) {

    private val app = JarvisApp.instance
    val settingsManager: JarvisSettingsManager = app.settingsManager
    val speechRecognitionManager: SpeechRecognitionManager = app.speechRecognitionManager
    val ttsManager: JarvisTTSManager = app.ttsManager
    val skillExecutor: AndroidSkillExecutor = app.skillExecutor
    val calibrationStorageManager = app.calibrationStorageManager
    val speakerVerificationEngine = app.speakerVerificationEngine
    val wakeWordProfileManager = com.jarvis.client.voice.kws.WakeWordProfileManager(application)
    private val repository: JarvisRepository = app.repository

    val connectionState: StateFlow<ConnectionState> = repository.connectionState
    val chatMessages: StateFlow<List<ChatMessage>> = repository.chatMessages
    val pendingConfirmation: StateFlow<ChatMessage?> = repository.pendingConfirmation
    val ttsEnabled: StateFlow<Boolean> = repository.ttsEnabled

    val isVoiceServiceRunning: StateFlow<Boolean> = JarvisVoiceService.isRunning
    val serviceVoiceState: StateFlow<ServiceVoiceState> = JarvisVoiceService.currentState
    val voiceDiagnostics: StateFlow<VoiceDiagnostics> = JarvisVoiceService.diagnostics
    val micDiagnostics: StateFlow<MicrophoneDiagnostics> = JarvisVoiceService.micDiagnostics

    private val _activeCalibrationProfile = MutableStateFlow<com.jarvis.client.voice.calibration.CalibrationProfile?>(null)
    val activeCalibrationProfile: StateFlow<com.jarvis.client.voice.calibration.CalibrationProfile?> = _activeCalibrationProfile.asStateFlow()

    private val _activeWakeWordProfile = MutableStateFlow(wakeWordProfileManager.loadProfile(settingsManager.userId))
    val activeWakeWordProfile: StateFlow<com.jarvis.client.voice.kws.WakeWordProfile> = _activeWakeWordProfile.asStateFlow()

    private val _compositeVoiceState = MutableStateFlow(VoiceState.IDLE)
    val compositeVoiceState: StateFlow<VoiceState> = _compositeVoiceState.asStateFlow()

    private val _partialTranscript = MutableStateFlow("")
    val partialTranscript: StateFlow<String> = _partialTranscript.asStateFlow()

    init {
        repository.start()

        // Sync speech recognition state
        viewModelScope.launch {
            speechRecognitionManager.voiceState.collect { speechState ->
                if (speechState != VoiceState.IDLE) {
                    _compositeVoiceState.value = speechState
                } else if (!ttsManager.isSpeaking.value) {
                    _compositeVoiceState.value = VoiceState.IDLE
                }
            }
        }

        // Sync TTS speaking state
        viewModelScope.launch {
            ttsManager.isSpeaking.collect { isSpeaking ->
                if (isSpeaking) {
                    _compositeVoiceState.value = VoiceState.SPEAKING
                } else if (speechRecognitionManager.voiceState.value == VoiceState.IDLE) {
                    _compositeVoiceState.value = VoiceState.IDLE
                }
            }
        }

        // Sync partial results
        viewModelScope.launch {
            speechRecognitionManager.partialResults.collect { partial ->
                _partialTranscript.value = partial
            }
        }

        viewModelScope.launch {
            speechRecognitionManager.transcriptionResults.collect {
                _partialTranscript.value = ""
            }
        }
    }

    fun sendMessage(text: String) {
        repository.sendMessage(text)
    }

    fun confirmAction(approved: Boolean) {
        repository.confirmAction(approved)
    }

    fun sendPing() {
        repository.sendPing()
    }

    fun startVoiceListening() {
        _partialTranscript.value = ""
        repository.startVoiceListening()
    }

    fun stopVoiceListening() {
        repository.stopVoiceListening()
    }

    fun stopSpeaking() {
        repository.stopSpeaking()
    }

    fun toggleTts() {
        repository.setTtsEnabled(!repository.ttsEnabled.value)
    }

    fun toggleVoiceService(context: Context) {
        if (isVoiceServiceRunning.value) {
            JarvisVoiceService.stopService(context)
        } else {
            JarvisVoiceService.startService(context)
        }
    }

    fun reconnect() {
        repository.stop()
        repository.start()
    }

    fun checkAndRefreshCapabilities() {
        repository.checkAndRefreshCapabilities()
    }

    fun updateSettings(
        backendUrl: String,
        userId: String,
        deviceId: String,
        deviceName: String,
        authToken: String
    ) {
        repository.updateConfiguration(backendUrl, userId, deviceId, deviceName, authToken)
        loadActiveCalibrationProfile()
        loadActiveWakeWordProfile()
    }

    fun loadActiveWakeWordProfile() {
        val profile = wakeWordProfileManager.loadProfile(settingsManager.userId)
        _activeWakeWordProfile.value = profile
    }

    fun activateWakeWordProfile(profile: com.jarvis.client.voice.kws.WakeWordProfile, context: Context): com.jarvis.client.voice.kws.ProfileActivationResult {
        val result = wakeWordProfileManager.activateProfile(settingsManager.userId, profile) {
            if (isVoiceServiceRunning.value) {
                JarvisVoiceService.reloadActiveProfile(context)
            }
            true
        }
        if (result.success && result.activeProfile != null) {
            _activeWakeWordProfile.value = result.activeProfile
        }
        return result
    }

    fun resetWakeWordToDefault(context: Context): com.jarvis.client.voice.kws.ProfileActivationResult {
        val result = wakeWordProfileManager.resetToDefault(settingsManager.userId) {
            if (isVoiceServiceRunning.value) {
                JarvisVoiceService.reloadActiveProfile(context)
            }
            true
        }
        if (result.success && result.activeProfile != null) {
            _activeWakeWordProfile.value = result.activeProfile
        }
        return result
    }

    fun loadActiveCalibrationProfile() {
        val profile = calibrationStorageManager.loadProfile(settingsManager.userId)
        _activeCalibrationProfile.value = profile
    }

    fun applyCalibrationProfile(profile: com.jarvis.client.voice.calibration.CalibrationProfile, context: Context? = null) {
        calibrationStorageManager.saveProfile(profile)
        settingsManager.customWakeThreshold = profile.recommendation.recommendedThreshold
        settingsManager.isCustomThresholdEnabled = profile.isCustomThresholdActive
        settingsManager.activeCalibrationProfileId = profile.profileId
        _activeCalibrationProfile.value = profile

        if (context != null && isVoiceServiceRunning.value) {
            JarvisVoiceService.pauseStandby(context)
            JarvisVoiceService.resumeStandby(context)
        }
    }

    fun disableCustomCalibration(context: Context? = null) {
        settingsManager.isCustomThresholdEnabled = false
        val current = _activeCalibrationProfile.value
        if (current != null) {
            val updated = current.copy(isCustomThresholdActive = false)
            calibrationStorageManager.saveProfile(updated)
            _activeCalibrationProfile.value = updated
        }
        if (context != null && isVoiceServiceRunning.value) {
            JarvisVoiceService.pauseStandby(context)
            JarvisVoiceService.resumeStandby(context)
        }
    }
}
