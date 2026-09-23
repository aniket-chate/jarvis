package com.jarvis.client

import android.app.Application
import android.util.Log
import com.jarvis.client.repository.JarvisRepository
import com.jarvis.client.settings.JarvisSettingsManager
import com.jarvis.client.skill.AndroidSkillExecutor
import com.jarvis.client.voice.JarvisTTSManager
import com.jarvis.client.voice.SpeechRecognitionManager

/**
 * Application singleton managing shared lifecycle of settings, repository, and voice layer.
 */
class JarvisApp : Application() {

    lateinit var settingsManager: JarvisSettingsManager
        private set

    lateinit var speechRecognitionManager: SpeechRecognitionManager
        private set

    lateinit var ttsManager: JarvisTTSManager
        private set

    lateinit var skillExecutor: AndroidSkillExecutor
        private set

    lateinit var calibrationStorageManager: com.jarvis.client.voice.calibration.CalibrationStorageManager
        private set

    lateinit var speakerVerificationEngine: com.jarvis.client.voice.calibration.SpeakerVerificationEngine
        private set

    lateinit var repository: JarvisRepository
        private set

    override fun onCreate() {
        super.onCreate()
        instance = this

        settingsManager = JarvisSettingsManager(applicationContext)
        speechRecognitionManager = SpeechRecognitionManager(applicationContext)
        ttsManager = JarvisTTSManager(applicationContext)
        skillExecutor = AndroidSkillExecutor(applicationContext)
        calibrationStorageManager = com.jarvis.client.voice.calibration.CalibrationStorageManager(applicationContext)
        speakerVerificationEngine = com.jarvis.client.voice.calibration.NoOpSpeakerVerificationEngine(settingsManager.userId)

        repository = JarvisRepository(
            settingsManager = settingsManager,
            skillExecutor = skillExecutor,
            ttsManager = ttsManager,
            speechRecognitionManager = speechRecognitionManager
        )

        Log.i("JarvisApp", "JarvisApp initialized with shared repository and voice layer.")
    }

    companion object {
        lateinit var instance: JarvisApp
            private set
    }
}
