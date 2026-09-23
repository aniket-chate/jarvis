package com.jarvis.client.voice.calibration

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import android.os.Build
import android.util.Log
import androidx.core.content.ContextCompat
import com.jarvis.client.voice.kws.WakeWordProfile
import com.jarvis.client.voice.kws.WakeWordProfileManager
import com.k2fsa.sherpa.onnx.FeatureConfig
import com.k2fsa.sherpa.onnx.KeywordSpotter
import com.k2fsa.sherpa.onnx.KeywordSpotterConfig
import com.k2fsa.sherpa.onnx.OnlineModelConfig
import com.k2fsa.sherpa.onnx.OnlineStream
import com.k2fsa.sherpa.onnx.OnlineTransducerModelConfig
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.abs
import kotlin.math.log10
import kotlin.math.sqrt

/**
 * On-device session orchestrator for Personal Wake-Word Calibration.
 * Records guided positive and negative audio samples in memory, extracts non-sensitive
 * acoustic & confidence summaries using the production Sherpa-ONNX KeywordSpotter engine,
 * and discards all raw PCM audio.
 */
class CalibrationEngine(
    private val context: Context,
    private val activeUserId: String = "default_user",
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.Default + Job())
) {

    private val tag = "CalibrationEngine"

    private val _sessionState = MutableStateFlow(CalibrationSessionState.IDLE)
    val sessionState: StateFlow<CalibrationSessionState> = _sessionState.asStateFlow()

    private val _currentRms = MutableStateFlow(0f)
    val currentRms: StateFlow<Float> = _currentRms.asStateFlow()

    private val _currentPeak = MutableStateFlow(0f)
    val currentPeak: StateFlow<Float> = _currentPeak.asStateFlow()

    private val _lastConfidence = MutableStateFlow(0f)
    val lastConfidence: StateFlow<Float> = _lastConfidence.asStateFlow()

    private val _elapsedRecordingMs = MutableStateFlow(0L)
    val elapsedRecordingMs: StateFlow<Long> = _elapsedRecordingMs.asStateFlow()

    private val isRecording = AtomicBoolean(false)
    private var recordingJob: Job? = null
    private var audioRecord: AudioRecord? = null

    // Sherpa KWS engine components
    private var spotter: KeywordSpotter? = null
    private val spotterLock = Any()

    private val collectedSummaries = mutableListOf<CalibrationSampleSummary>()
    private var currentPrompt: CalibrationStepPrompt? = null
    private var promptList: List<CalibrationStepPrompt> = emptyList()
    private var currentStepIdx = 0

    companion object {
        const val SAMPLE_RATE = 16000
        const val CHUNK_SAMPLES = 1280 // 80ms

        const val ASSET_ENCODER = "models/kws/encoder-epoch-12-avg-2-chunk-16-left-64.onnx"
        const val ASSET_DECODER = "models/kws/decoder-epoch-12-avg-2-chunk-16-left-64.onnx"
        const val ASSET_JOINER = "models/kws/joiner-epoch-12-avg-2-chunk-16-left-64.onnx"
        const val ASSET_TOKENS = "models/kws/tokens.txt"

        /**
         * Standard guided calibration prompts (6 positive wake samples + 5 negative noise/speech samples).
         */
        fun createDefaultPrompts(phrase: String = "Hey Jarvis"): List<CalibrationStepPrompt> {
            return listOf(
                // 6 Positive Samples
                CalibrationStepPrompt(
                    stepIndex = 1,
                    totalSteps = 11,
                    sampleType = CalibrationSampleType.POSITIVE_WAKE,
                    title = "Normal Voice (1/6)",
                    instruction = "Say '$phrase' normally.",
                    targetDurationMs = 3500L
                ),
                CalibrationStepPrompt(
                    stepIndex = 2,
                    totalSteps = 11,
                    sampleType = CalibrationSampleType.POSITIVE_WAKE,
                    title = "Soft Voice (2/6)",
                    instruction = "Say '$phrase' slightly softly.",
                    targetDurationMs = 3500L
                ),
                CalibrationStepPrompt(
                    stepIndex = 3,
                    totalSteps = 11,
                    sampleType = CalibrationSampleType.POSITIVE_WAKE,
                    title = "Conversational Distance (3/6)",
                    instruction = "Say '$phrase' at normal conversational distance.",
                    targetDurationMs = 3500L
                ),
                CalibrationStepPrompt(
                    stepIndex = 4,
                    totalSteps = 11,
                    sampleType = CalibrationSampleType.POSITIVE_WAKE,
                    title = "Distant Utterance (4/6)",
                    instruction = "Say '$phrase' from approximately 2 meters away.",
                    targetDurationMs = 3500L
                ),
                CalibrationStepPrompt(
                    stepIndex = 5,
                    totalSteps = 11,
                    sampleType = CalibrationSampleType.POSITIVE_WAKE,
                    title = "Fast Utterance (5/6)",
                    instruction = "Say '$phrase' slightly faster.",
                    targetDurationMs = 3500L
                ),
                CalibrationStepPrompt(
                    stepIndex = 6,
                    totalSteps = 11,
                    sampleType = CalibrationSampleType.POSITIVE_WAKE,
                    title = "Natural Speaking Style (6/6)",
                    instruction = "Say '$phrase' naturally in your normal speaking style.",
                    targetDurationMs = 3500L
                ),
                // 5 Negative Samples
                CalibrationStepPrompt(
                    stepIndex = 7,
                    totalSteps = 11,
                    sampleType = CalibrationSampleType.NEGATIVE_SILENCE,
                    title = "Silence / Room Ambience (1/5)",
                    instruction = "Silence / room ambience.",
                    targetDurationMs = 3500L
                ),
                CalibrationStepPrompt(
                    stepIndex = 8,
                    totalSteps = 11,
                    sampleType = CalibrationSampleType.NEGATIVE_FAN_NOISE,
                    title = "Cooler / Fan Running (2/5)",
                    instruction = "Cooler/fan running.",
                    targetDurationMs = 3500L
                ),
                CalibrationStepPrompt(
                    stepIndex = 9,
                    totalSteps = 11,
                    sampleType = CalibrationSampleType.NEGATIVE_SPEECH,
                    title = "Normal Conversation (3/5)",
                    instruction = "Normal conversation without saying the wake word.",
                    targetDurationMs = 3500L
                ),
                CalibrationStepPrompt(
                    stepIndex = 10,
                    totalSteps = 11,
                    sampleType = CalibrationSampleType.NEGATIVE_SPEECH,
                    title = "Similar Phonetic Words (4/5)",
                    instruction = "Random words containing sounds somewhat similar to '$phrase'.",
                    targetDurationMs = 3500L
                ),
                CalibrationStepPrompt(
                    stepIndex = 11,
                    totalSteps = 11,
                    sampleType = CalibrationSampleType.NEGATIVE_MEDIA,
                    title = "Media / Video Audio (5/5)",
                    instruction = "YouTube/video/media playing in the background.",
                    targetDurationMs = 3500L
                )
            )
        }
    }

    private fun copyAssetToFile(assetName: String): File {
        val modelsDir = File(context.filesDir, "kws_models")
        if (!modelsDir.exists()) modelsDir.mkdirs()

        val fileName = File(assetName).name
        val outFile = File(modelsDir, fileName)

        if (!outFile.exists() || outFile.length() == 0L) {
            try {
                context.assets.open(assetName).use { input ->
                    FileOutputStream(outFile).use { output ->
                        input.copyTo(output)
                    }
                }
                Log.d(tag, "Extracted KWS asset: $fileName (${outFile.length()} bytes)")
            } catch (e: Exception) {
                Log.e(tag, "Failed to copy KWS asset: $assetName", e)
            }
        }
        return outFile
    }

    fun ensureKwsInitialized(): Boolean {
        synchronized(spotterLock) {
            if (spotter != null) return true
            return try {
                val profileManager = WakeWordProfileManager(context)
                val activeProfile = profileManager.loadProfile(activeUserId)
                val keywordsFile = profileManager.syncKeywordsFile(activeProfile)

                val encoderFile = copyAssetToFile(ASSET_ENCODER)
                val decoderFile = copyAssetToFile(ASSET_DECODER)
                val joinerFile = copyAssetToFile(ASSET_JOINER)
                val tokensFile = copyAssetToFile(ASSET_TOKENS)

                val featConfig = FeatureConfig(
                    sampleRate = SAMPLE_RATE,
                    featureDim = 80
                )

                val transducerConfig = OnlineTransducerModelConfig(
                    encoder = encoderFile.absolutePath,
                    decoder = decoderFile.absolutePath,
                    joiner = joinerFile.absolutePath
                )

                val modelConfig = OnlineModelConfig(
                    transducer = transducerConfig,
                    tokens = tokensFile.absolutePath,
                    numThreads = 2,
                    debug = false,
                    provider = "cpu"
                )

                val kwsConfig = KeywordSpotterConfig(
                    featConfig = featConfig,
                    modelConfig = modelConfig,
                    maxActivePaths = 4,
                    keywordsFile = keywordsFile.absolutePath,
                    keywordsScore = activeProfile.keywordsScore,
                    keywordsThreshold = activeProfile.keywordsThreshold,
                    numTrailingBlanks = activeProfile.numTrailingBlanks
                )

                spotter = KeywordSpotter(assetManager = null, config = kwsConfig)
                Log.i(tag, "Sherpa KeywordSpotter initialized successfully for CalibrationEngine (User: $activeUserId, Phrase: '${activeProfile.phrase}')")
                true
            } catch (t: Throwable) {
                Log.e(tag, "Failed to initialize Sherpa KeywordSpotter for calibration: ${t.javaClass.name} - ${t.message}", t)
                _sessionState.value = CalibrationSessionState.ERROR
                false
            }
        }
    }

    fun hasPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
    }

    /**
     * Starts a structured calibration session with guided prompts.
     */
    fun startSession(prompts: List<CalibrationStepPrompt>? = null): Boolean {
        if (!hasPermission()) {
            Log.w(tag, "Cannot start calibration: RECORD_AUDIO permission missing.")
            _sessionState.value = CalibrationSessionState.ERROR
            return false
        }

        if (!ensureKwsInitialized()) {
            Log.e(tag, "Cannot start calibration: Sherpa KWS initialization failed.")
            _sessionState.value = CalibrationSessionState.ERROR
            return false
        }

        val profileManager = WakeWordProfileManager(context)
        val activeProfile = profileManager.loadProfile(activeUserId)
        val actualPrompts = prompts ?: createDefaultPrompts(activeProfile.phrase)

        collectedSummaries.clear()
        promptList = actualPrompts
        currentStepIdx = 0
        if (promptList.isNotEmpty()) {
            currentPrompt = promptList[0]
            _sessionState.value = CalibrationSessionState.PROMPT_READY
        } else {
            _sessionState.value = CalibrationSessionState.IDLE
        }
        return true
    }

    fun getCurrentPrompt(): CalibrationStepPrompt? {
        return if (currentStepIdx < promptList.size) promptList[currentStepIdx] else null
    }

    /**
     * Starts audio capture for the active step prompt.
     */
    fun startRecordingStep(onStepCompleted: (CalibrationSampleSummary) -> Unit) {
        val prompt = getCurrentPrompt() ?: return
        if (isRecording.getAndSet(true)) return

        _sessionState.value = CalibrationSessionState.RECORDING_SAMPLE

        recordingJob = scope.launch(Dispatchers.IO) {
            if (!ensureKwsInitialized()) {
                _sessionState.value = CalibrationSessionState.ERROR
                isRecording.set(false)
                return@launch
            }

            val minBufSize = AudioRecord.getMinBufferSize(
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT
            )
            val bufferSize = maxOf(minBufSize, CHUNK_SAMPLES * 2 * 4)

            var record: AudioRecord? = null
            try {
                record = AudioRecord(
                    MediaRecorder.AudioSource.VOICE_RECOGNITION,
                    SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    bufferSize
                )
            } catch (_: Exception) {}

            if (record == null || record.state != AudioRecord.STATE_INITIALIZED) {
                record = AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    bufferSize
                )
            }

            audioRecord = record
            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                Log.e(tag, "AudioRecord init failed for calibration step.")
                _sessionState.value = CalibrationSessionState.ERROR
                isRecording.set(false)
                return@launch
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN) {
                val sid = audioRecord!!.audioSessionId
                if (AcousticEchoCanceler.isAvailable()) AcousticEchoCanceler.create(sid)?.enabled = true
                if (NoiseSuppressor.isAvailable()) NoiseSuppressor.create(sid)?.enabled = true
            }

            audioRecord?.startRecording()

            val shortBuffer = ShortArray(CHUNK_SAMPLES)
            val floatBuffer = FloatArray(CHUNK_SAMPLES)

            var localStream: OnlineStream? = null
            synchronized(spotterLock) {
                localStream = spotter?.createStream()
            }

            val confidenceTrace = mutableListOf<Float>()
            var totalRmsSum = 0.0
            var peakRms = 0.0f
            var chunkCount = 0
            val startTime = System.currentTimeMillis()

            try {
                while (isActive && isRecording.get()) {
                    var samplesRead = 0
                    while (samplesRead < CHUNK_SAMPLES && isActive && isRecording.get()) {
                        val read = audioRecord?.read(shortBuffer, samplesRead, CHUNK_SAMPLES - samplesRead) ?: -1
                        if (read > 0) {
                            samplesRead += read
                        } else {
                            break
                        }
                    }

                    if (samplesRead < CHUNK_SAMPLES || !isRecording.get()) break

                    chunkCount++

                    // Calculate RMS & peak and normalize short to float [-1.0, 1.0] for Sherpa
                    var sumSquares = 0.0
                    var localPeak = 0.0f
                    for (i in 0 until CHUNK_SAMPLES) {
                        val norm = shortBuffer[i].toFloat() / 32768.0f
                        floatBuffer[i] = norm
                        sumSquares += (norm * norm)
                        val a = abs(norm)
                        if (a > localPeak) localPeak = a
                    }
                    val rms = sqrt(sumSquares / CHUNK_SAMPLES).toFloat()
                    totalRmsSum += rms
                    if (localPeak > peakRms) peakRms = localPeak

                    _currentRms.value = rms
                    _currentPeak.value = localPeak

                    // Feed normalized audio chunk to Sherpa KWS
                    var stepConfidence = 0.0f
                    localStream?.let { stm ->
                        stm.acceptWaveform(floatBuffer, SAMPLE_RATE)
                        synchronized(spotterLock) {
                            while (spotter?.isReady(stm) == true) {
                                spotter?.decode(stm)
                            }
                            val res = spotter?.getResult(stm)
                            if (!res?.keyword.isNullOrBlank()) {
                                stepConfidence = 1.0f
                            }
                        }
                    }

                    _lastConfidence.value = stepConfidence
                    confidenceTrace.add(stepConfidence)

                    val elapsed = System.currentTimeMillis() - startTime
                    _elapsedRecordingMs.value = elapsed
                    if (elapsed >= prompt.targetDurationMs) {
                        break
                    }
                }
            } finally {
                localStream?.release()
                releaseAudioRecord()
                isRecording.set(false)
            }

            // Build non-sensitive sample summary
            val durationMs = System.currentTimeMillis() - startTime
            val avgRms = if (chunkCount > 0) (totalRmsSum / chunkCount).toFloat() else 0.0f
            val maxConf = confidenceTrace.maxOrNull() ?: 0.0f
            val meanConf = if (confidenceTrace.isNotEmpty()) confidenceTrace.sum() / confidenceTrace.size else 0.0f
            val dist = CalibrationEvaluator.calculateDistribution(confidenceTrace)
            val hitsAtDef = CalibrationEvaluator.maxConsecutiveHits(confidenceTrace, CalibrationEvaluator.DEFAULT_THRESHOLD)

            val estimatedSnr = if (avgRms > 0.001f) {
                20.0f * log10(avgRms / 0.005f).coerceAtLeast(0.0f)
            } else {
                0.0f
            }

            val summary = CalibrationSampleSummary(
                sampleId = "sample_${UUID.randomUUID().toString().take(8)}",
                sampleType = prompt.sampleType,
                durationMs = durationMs,
                pcmChunkCount = chunkCount,
                averageRms = avgRms,
                peakRms = peakRms,
                estimatedSnrDb = estimatedSnr,
                maxConfidence = maxConf,
                meanConfidence = meanConf,
                confidenceDistribution = dist,
                confidenceTrace = confidenceTrace,
                consecutiveHitsAtDefault = hitsAtDef
            )

            collectedSummaries.add(summary)
            currentStepIdx++

            scope.launch(Dispatchers.Main) {
                onStepCompleted(summary)
                if (currentStepIdx < promptList.size) {
                    _sessionState.value = CalibrationSessionState.PROMPT_READY
                } else {
                    _sessionState.value = CalibrationSessionState.EVALUATING_RESULTS
                }
            }
        }
    }

    /**
     * Stop active recording prematurely if desired.
     */
    fun stopRecordingStep() {
        isRecording.set(false)
    }

    /**
     * Completes calibration session, computes recommendation, and builds CalibrationProfile.
     */
    fun generateProfile(userId: String, deviceId: String): CalibrationProfile {
        val rec = CalibrationEvaluator.recommendThreshold(collectedSummaries)
        val posCount = collectedSummaries.count { it.sampleType == CalibrationSampleType.POSITIVE_WAKE }
        val negCount = collectedSummaries.count { it.sampleType != CalibrationSampleType.POSITIVE_WAKE }

        val profile = CalibrationProfile(
            profileId = "profile_${userId}_${deviceId}_${System.currentTimeMillis()}",
            userId = userId,
            deviceId = deviceId,
            createdAt = System.currentTimeMillis(),
            updatedAt = System.currentTimeMillis(),
            positiveSampleCount = posCount,
            negativeSampleCount = negCount,
            recommendation = rec,
            sampleSummaries = collectedSummaries.toList(),
            isCustomThresholdActive = rec.isReliable
        )

        _sessionState.value = CalibrationSessionState.COMPLETED
        return profile
    }

    fun getCollectedSummaries(): List<CalibrationSampleSummary> = collectedSummaries.toList()

    fun cancelSession() {
        isRecording.set(false)
        recordingJob?.cancel()
        releaseAudioRecord()
        collectedSummaries.clear()
        _elapsedRecordingMs.value = 0L
        _currentRms.value = 0f
        _currentPeak.value = 0f
        _lastConfidence.value = 0f
        _sessionState.value = CalibrationSessionState.IDLE
    }

    private fun releaseAudioRecord() {
        try {
            audioRecord?.stop()
            audioRecord?.release()
            audioRecord = null
        } catch (_: Exception) {}
    }

    fun destroy() {
        cancelSession()
        synchronized(spotterLock) {
            spotter?.release()
            spotter = null
        }
        Log.i(tag, "CalibrationEngine destroyed and native spotter released.")
    }
}
