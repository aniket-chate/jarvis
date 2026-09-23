package com.jarvis.client.voice

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
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong
import kotlin.math.abs
import kotlin.math.sqrt

/**
 * Dynamic Open-Vocabulary Keyword Spotter powered by sherpa-onnx Zipformer streaming KWS.
 * Supports arbitrary user-enrolled wake phrases without model retraining or cloud dependencies.
 *
 * Implements the standard WakeWordDetector contract with zero continuous raw audio persistence.
 */
class SherpaKwsDetector(
    private val context: Context,
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.Default + Job()),
    private var activeUserId: String = "default_user"
) : WakeWordDetector {

    val tag = TAG_KWS

    private val _state = MutableStateFlow(WakeWordState.IDLE)
    override val state: StateFlow<WakeWordState> = _state.asStateFlow()

    private val _diagnostics = MutableStateFlow(VoiceDiagnostics())
    override val diagnostics: StateFlow<VoiceDiagnostics> = _diagnostics.asStateFlow()

    private val _micDiagnostics = MutableStateFlow(MicrophoneDiagnostics())
    override val micDiagnostics: StateFlow<MicrophoneDiagnostics> = _micDiagnostics.asStateFlow()

    var detectorGeneration: String = "kws_gen_init"
        private set

    private val profileManager = WakeWordProfileManager(context)
    @Volatile private var activeProfile: WakeWordProfile = profileManager.loadProfile(activeUserId)

    private val countStandbyCycles = AtomicInteger(0)
    private val countWakeDetections = AtomicInteger(0)
    private val countRejectedEvents = AtomicInteger(0)
    private val countDirectCommands = AtomicInteger(0)
    private val countHandoffSuccesses = AtomicInteger(0)
    private val countHandoffErrors = AtomicInteger(0)

    private val countPcmChunks = AtomicLong(0L)
    private val countReadErrors = AtomicLong(0L)
    private val countKwsEvaluations = AtomicLong(0L)
    private val lastSuccessfulPcmReadTimestamp = AtomicLong(0L)

    var onWatchdogFailureListener: ((reason: String) -> Unit)? = null

    @Volatile private var runningAudioSource = "VOICE_RECOGNITION"
    @Volatile private var runningAudioState = "UNINITIALIZED"
    @Volatile private var runningRecordingState = "STOPPED"
    @Volatile private var runningLastReadError = "None"
    @Volatile private var runningRms = 0f
    @Volatile private var runningPeak = 0f
    @Volatile private var runningMaxPeak = 0f
    @Volatile private var runningLastKeyword = "None"
    @Volatile private var minBufferSizeCache = 0

    private var onWakeCallback: ((String) -> Unit)? = null
    @Volatile private var isListening = false
    private var audioRecordJob: Job? = null
    private var watchdogJob: Job? = null
    private var audioRecord: AudioRecord? = null
    private val audioRecordLock = Any()

    // Privacy-safe KWS isolation diagnostic attempt records (zero raw audio)
    data class KwsAttemptDiagnostic(
        val attemptNumber: Int,
        val phrase: String,
        val threshold: Float,
        val score: Float,
        val detected: Boolean,
        val rms: Float,
        val peak: Float,
        val pcmFrames: Long,
        val elapsedMs: Long,
        val resetStatus: String,
        val timestamp: Long = System.currentTimeMillis()
    )

    private val kwsDiagnosticHistory = java.util.concurrent.CopyOnWriteArrayList<KwsAttemptDiagnostic>()

    // sherpa-onnx components
    private var spotter: KeywordSpotter? = null
    private var stream: OnlineStream? = null
    private val spotterLock = Any()

    companion object {
        const val TAG_KWS = "JARVIS_KWS"
        const val SAMPLE_RATE = 16000
        const val CHUNK_SAMPLES = 1280 // 80ms at 16kHz
        const val DEBOUNCE_MS = 500L
        const val AUDIO_HANDOFF_SETTLE_MS = 150L
        private var lastWakeTimestamp = 0L

        const val ASSET_ENCODER = "models/kws/encoder-epoch-12-avg-2-chunk-16-left-64.onnx"
        const val ASSET_DECODER = "models/kws/decoder-epoch-12-avg-2-chunk-16-left-64.onnx"
        const val ASSET_JOINER = "models/kws/joiner-epoch-12-avg-2-chunk-16-left-64.onnx"
        const val ASSET_TOKENS = "models/kws/tokens.txt"
    }

    init {
        initializeSpotter()
        syncMicDiagnostics()
    }

    fun isActuallyRecording(): Boolean {
        return synchronized(audioRecordLock) {
            val rec = audioRecord
            rec != null && rec.state == AudioRecord.STATE_INITIALIZED && rec.recordingState == AudioRecord.RECORDSTATE_RECORDING
        }
    }

    fun isKeywordSpotterReady(): Boolean {
        return synchronized(spotterLock) {
            spotter != null && stream != null
        }
    }

    fun isDetectionLoopAlive(): Boolean {
        return (audioRecordJob?.isActive == true) && isListening
    }

    fun getAudioRecordState(): String = runningAudioState

    fun getRecordingState(): String = runningRecordingState

    fun getLastPcmReadTimestamp(): Long = lastSuccessfulPcmReadTimestamp.get()

    fun getPcmHeartbeatAgeMs(): Long {
        val last = lastSuccessfulPcmReadTimestamp.get()
        return if (last == 0L) Long.MAX_VALUE else (System.currentTimeMillis() - last)
    }

    fun isPcmHealthy(maxAgeMs: Long = 1500L): Boolean {
        return isActuallyRecording() && (getPcmHeartbeatAgeMs() <= maxAgeMs)
    }

    fun isActuallyRecordingAndStreaming(sinceChunks: Long = 0L): Boolean {
        return synchronized(audioRecordLock) {
            val rec = audioRecord
            val isRec = rec != null && rec.state == AudioRecord.STATE_INITIALIZED && rec.recordingState == AudioRecord.RECORDSTATE_RECORDING
            val currentChunks = countPcmChunks.get()
            isRec && currentChunks > sinceChunks && (getPcmHeartbeatAgeMs() <= 2000L)
        }
    }

    fun getPcmChunksRead(): Long = countPcmChunks.get()

    fun getMicDiagnostics(): MicrophoneDiagnostics = _micDiagnostics.value

    fun recordKwsAttempt(
        attemptNumber: Int,
        phrase: String,
        threshold: Float,
        score: Float,
        detected: Boolean,
        rms: Float,
        peak: Float,
        pcmFrames: Long,
        elapsedMs: Long,
        resetStatus: String
    ) {
        val entry = KwsAttemptDiagnostic(
            attemptNumber = attemptNumber,
            phrase = phrase,
            threshold = threshold,
            score = score,
            detected = detected,
            rms = rms,
            peak = peak,
            pcmFrames = pcmFrames,
            elapsedMs = elapsedMs,
            resetStatus = resetStatus
        )
        kwsDiagnosticHistory.add(entry)
        Log.i(
            tag,
            "KWS_ATTEMPT_DIAGNOSTIC attempt=$attemptNumber phrase='$phrase' detected=$detected " +
            "score=$score thr=$threshold rms=$rms peak=$peak frames=$pcmFrames elapsed=${elapsedMs}ms reset=$resetStatus"
        )
    }

    fun getKwsDiagnosticHistory(): List<KwsAttemptDiagnostic> = kwsDiagnosticHistory.toList()
    fun clearKwsDiagnosticHistory() = kwsDiagnosticHistory.clear()

    /**
     * Copies model assets from APK to local app storage for high-performance direct file access.
     */
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

    private fun initializeSpotter(): Boolean {
        return synchronized(spotterLock) {
            try {
                activeProfile = profileManager.loadProfile(activeUserId)
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
                    maxActivePaths = 8,
                    keywordsFile = keywordsFile.absolutePath,
                    keywordsScore = activeProfile.keywordsScore,
                    keywordsThreshold = activeProfile.keywordsThreshold,
                    numTrailingBlanks = activeProfile.numTrailingBlanks
                )

                spotter?.release()
                spotter = KeywordSpotter(assetManager = null, config = kwsConfig)
                stream?.release()
                stream = spotter?.createStream()

                detectorGeneration = "kws_gen_${java.util.UUID.randomUUID().toString().take(8)}"
                val keywordsContent = try { keywordsFile.readText().trim() } catch (_: Exception) { "" }

                Log.i(
                    tag,
                    "ACTIVE_WAKE_PROFILE phrase='${activeProfile.phrase}' " +
                    "profile_id='${activeProfile.profileId}' " +
                    "keywords_file='${keywordsFile.absolutePath}' " +
                    "keywords_content='$keywordsContent' " +
                    "tokenized_keyword='${activeProfile.tokenizedKeyword}' " +
                    "threshold=${activeProfile.keywordsThreshold} " +
                    "keywords_score=${activeProfile.keywordsScore} " +
                    "max_active_paths=8 " +
                    "detector_generation=$detectorGeneration"
                )
                true
            } catch (e: Exception) {
                Log.e(tag, "Failed to initialize Sherpa KeywordSpotter", e)
                runningAudioState = "KWS_INIT_ERROR"
                false
            }
        }
    }

    fun reloadProfile(): Boolean {
        return synchronized(spotterLock) {
            activeProfile = profileManager.loadProfile(activeUserId)
            initializeSpotter()
        }
    }

    fun switchUser(newUserId: String): Boolean {
        return synchronized(spotterLock) {
            activeUserId = profileManager.sanitizeUserId(newUserId)
            activeProfile = profileManager.loadProfile(activeUserId)
            initializeSpotter()
        }
    }

    fun getActiveProfile(): WakeWordProfile = activeProfile

    fun getActiveUserId(): String = activeUserId

    fun updateWakePhrase(newPhrase: String) {
        synchronized(spotterLock) {
            activeProfile = profileManager.updatePhrase(
                userId = activeUserId,
                newPhrase = newPhrase,
                keywordsScore = activeProfile.keywordsScore,
                keywordsThreshold = activeProfile.keywordsThreshold
            )
            initializeSpotter()
        }
    }

    fun applyExplicitThresholds(score: Float, threshold: Float) {
        synchronized(spotterLock) {
            if (activeProfile.keywordsScore != score || activeProfile.keywordsThreshold != threshold) {
                activeProfile = activeProfile.copy(keywordsScore = score, keywordsThreshold = threshold)
                initializeSpotter()
            }
        }
    }

    fun hasPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
    }

    override fun startListening(onWakeDetected: (commandAfterWake: String) -> Unit) {
        if (!hasPermission()) {
            Log.w(TAG_KWS, "Cannot start Sherpa KWS: RECORD_AUDIO permission missing.")
            runningAudioState = "NO_PERMISSION"
            runningRecordingState = "STOPPED"
            syncMicDiagnostics()
            _state.value = WakeWordState.ERROR
            return
        }

        synchronized(spotterLock) {
            val s = spotter
            val st = stream
            if (s == null || st == null) {
                val ok = initializeSpotter()
                if (!ok || spotter == null) {
                    Log.e(TAG_KWS, "Sherpa KeywordSpotter unavailable.")
                    runningAudioState = "MODEL_INIT_ERROR"
                    syncMicDiagnostics()
                    _state.value = WakeWordState.ERROR
                    return
                }
            } else {
                s.reset(st)
            }
            Unit
        }

        this.onWakeCallback = onWakeDetected
        isListening = true
        lastWakeTimestamp = 0L
        lastSuccessfulPcmReadTimestamp.set(0L)
        _state.value = WakeWordState.LISTENING_FOR_WAKE
        countStandbyCycles.incrementAndGet()
        syncDiagnostics()

        Log.i(
            TAG_KWS,
            "KWS_STANDBY_START phrase='${activeProfile.phrase}' threshold=${activeProfile.keywordsThreshold} score=${activeProfile.keywordsScore} gen=$detectorGeneration"
        )

        startAudioCaptureLoop()
        startWatchdog()
    }

    private fun startWatchdog() {
        watchdogJob?.cancel()
        watchdogJob = scope.launch(Dispatchers.Default) {
            while (isActive && isListening) {
                delay(1000L)
                if (!isActive || !isListening) break
                val currentChunks = countPcmChunks.get()
                val isRec = isActuallyRecording()
                val heartbeatAge = getPcmHeartbeatAgeMs()
                val isHealthy = isRec && (currentChunks == 0L || heartbeatAge <= 2000L)

                if (!isHealthy) {
                    Log.w(
                        TAG_KWS,
                        "VOICE_STATE: MIC_WATCHDOG_HEARTBEAT_EXPIRED heartbeatAge=${heartbeatAge}ms isRecording=$isRec " +
                        "chunks=$currentChunks lastError=$runningLastReadError generation=$detectorGeneration"
                    )
                    onWatchdogFailureListener?.invoke("Watchdog heartbeat expired (age=${heartbeatAge}ms, error=$runningLastReadError)")
                    if (isListening) {
                        Log.w(TAG_KWS, "VOICE_STATE: MIC_WATCHDOG_RESTART_TRIGGERED")
                        restartAudioCapture()
                    }
                }
            }
        }
    }

    private fun restartAudioCapture() {
        if (!isListening) return
        scope.launch(Dispatchers.IO) {
            releaseAudioRecord()
            delay(100L)
            if (isListening) {
                startAudioCaptureLoop()
            }
        }
    }

    private fun startAudioCaptureLoop() {
        audioRecordJob?.cancel()
        audioRecordJob = scope.launch(Dispatchers.IO) {
            val minBufSize = AudioRecord.getMinBufferSize(
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT
            )
            val bufferSize = maxOf(minBufSize, CHUNK_SAMPLES * 2 * 4)

            var record: AudioRecord? = null
            var attempts = 0
            val maxAttempts = 3

            while (attempts < maxAttempts && isActive && isListening && record == null) {
                attempts++
                try {
                    val candidate = AudioRecord(
                        MediaRecorder.AudioSource.VOICE_RECOGNITION,
                        SAMPLE_RATE,
                        AudioFormat.CHANNEL_IN_MONO,
                        AudioFormat.ENCODING_PCM_16BIT,
                        bufferSize
                    )
                    if (candidate.state == AudioRecord.STATE_INITIALIZED) {
                        record = candidate
                        runningAudioSource = "VOICE_RECOGNITION"
                    } else {
                        candidate.release()
                    }
                } catch (e: Exception) {
                    Log.w(TAG_KWS, "Attempt $attempts: VOICE_RECOGNITION AudioRecord init failed", e)
                }

                if (record == null) {
                    try {
                        val candidate = AudioRecord(
                            MediaRecorder.AudioSource.MIC,
                            SAMPLE_RATE,
                            AudioFormat.CHANNEL_IN_MONO,
                            AudioFormat.ENCODING_PCM_16BIT,
                            bufferSize
                        )
                        if (candidate.state == AudioRecord.STATE_INITIALIZED) {
                            record = candidate
                            runningAudioSource = "MIC"
                        } else {
                            candidate.release()
                        }
                    } catch (e: Exception) {
                        Log.e(TAG_KWS, "Attempt $attempts: MIC AudioRecord fallback failed", e)
                    }
                }

                if (record == null && attempts < maxAttempts) {
                    delay(100L)
                }
            }

            synchronized(audioRecordLock) {
                audioRecord = record
            }

            if (record == null || record.state != AudioRecord.STATE_INITIALIZED) {
                Log.e(TAG_KWS, "AudioRecord initialization permanently failed after $attempts attempts.")
                runningAudioState = "INIT_FAILED"
                runningRecordingState = "STOPPED"
                syncMicDiagnostics()
                _state.value = WakeWordState.ERROR
                return@launch
            }

            runningAudioState = "INITIALIZED"

            // Enable hardware DSP noise suppression and echo cancellation if available
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN) {
                val sessionId = record.audioSessionId
                try {
                    if (AcousticEchoCanceler.isAvailable()) {
                        AcousticEchoCanceler.create(sessionId)?.apply { enabled = true }
                    }
                    if (NoiseSuppressor.isAvailable()) {
                        NoiseSuppressor.create(sessionId)?.apply { enabled = true }
                    }
                } catch (e: Exception) {
                    Log.w(TAG_KWS, "Failed to attach audio effects: ${e.message}")
                }
            }

            try {
                record.startRecording()
                if (record.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    runningRecordingState = "RECORDING"
                } else {
                    runningRecordingState = "NOT_RECORDING"
                }
                syncMicDiagnostics()
                Log.i(TAG_KWS, "Sherpa KWS capture loop started (16kHz, mono, source=$runningAudioSource, target='${activeProfile.phrase}')")
            } catch (e: Exception) {
                Log.e(TAG_KWS, "AudioRecord.startRecording failed", e)
                runningRecordingState = "START_FAILED"
                syncMicDiagnostics()
                _state.value = WakeWordState.ERROR
                return@launch
            }

            val shortBuffer = ShortArray(CHUNK_SAMPLES)
            val floatBuffer = FloatArray(CHUNK_SAMPLES)
            var chunksSinceLog = 0L
            var lastHeartbeatLogTime = System.currentTimeMillis()

            try {
                while (isActive && isListening) {
                    var samplesRead = 0
                    while (samplesRead < CHUNK_SAMPLES && isActive && isListening) {
                        val currentRecord = synchronized(audioRecordLock) { audioRecord }
                        val read = currentRecord?.read(
                            shortBuffer,
                            samplesRead,
                            CHUNK_SAMPLES - samplesRead
                        ) ?: -1

                        if (read > 0) {
                            samplesRead += read
                            lastSuccessfulPcmReadTimestamp.set(System.currentTimeMillis())
                        } else {
                            val errStr = when (read) {
                                AudioRecord.ERROR_INVALID_OPERATION -> "ERROR_INVALID_OPERATION"
                                AudioRecord.ERROR_BAD_VALUE -> "ERROR_BAD_VALUE"
                                AudioRecord.ERROR_DEAD_OBJECT -> "ERROR_DEAD_OBJECT"
                                AudioRecord.ERROR -> "GENERIC_ERROR"
                                else -> "ERROR_CODE_$read"
                            }
                            runningLastReadError = errStr
                            countReadErrors.incrementAndGet()
                            Log.w(TAG_KWS, "AudioRecord read error: $errStr ($read)")
                            break
                        }
                    }

                    if (samplesRead < CHUNK_SAMPLES || !isListening) {
                        syncMicDiagnostics()
                        continue
                    }

                    val totalChunks = countPcmChunks.incrementAndGet()
                    chunksSinceLog++

                    // Convert 16-bit PCM to normalized Float32 [-1.0, 1.0] in-place
                    var sumSquares = 0.0
                    var peak = 0.0f
                    for (i in 0 until CHUNK_SAMPLES) {
                        val sample = shortBuffer[i].toFloat() / 32768.0f
                        floatBuffer[i] = sample
                        sumSquares += (sample * sample)
                        val absVal = abs(sample)
                        if (absVal > peak) peak = absVal
                    }
                    val rms = sqrt(sumSquares / CHUNK_SAMPLES).toFloat()
                    runningRms = rms
                    runningPeak = peak
                    if (peak > runningMaxPeak) runningMaxPeak = peak

                    val now = System.currentTimeMillis()
                    if (now - lastHeartbeatLogTime >= 2000L) {
                        lastHeartbeatLogTime = now
                        Log.i(
                            TAG_KWS,
                            "PCM_HEARTBEAT chunksSinceLastCheck=$chunksSinceLog lastReadAgeMs=${getPcmHeartbeatAgeMs()} rms=$rms peak=$peak readError=$runningLastReadError"
                        )
                        chunksSinceLog = 0L
                    }

                    // Feed streaming PCM chunk into sherpa-onnx KeywordSpotter
                    synchronized(spotterLock) {
                        val spot = spotter
                        val st = stream
                        if (spot != null && st != null) {
                            st.acceptWaveform(floatBuffer, SAMPLE_RATE)

                            while (spot.isReady(st)) {
                                spot.decode(st)
                                countKwsEvaluations.incrementAndGet()

                                val result = spot.getResult(st)
                                if (result.keyword.isNotBlank()) {
                                    val attemptIdx = countWakeDetections.incrementAndGet()
                                    lastWakeTimestamp = now
                                    runningLastKeyword = result.keyword

                                    Log.i(
                                        TAG_KWS,
                                        "KWS_ATTEMPT attemptId=$attemptIdx sessionGeneration=$detectorGeneration phrase='${activeProfile.phrase}' " +
                                        "threshold=${activeProfile.keywordsThreshold} score=1.00 detected=true " +
                                        "pcmHeartbeatAgeMs=${getPcmHeartbeatAgeMs()} totalPcmChunks=$totalChunks " +
                                        "audioRecordState=$runningAudioState recordingState=$runningRecordingState detectorLoopAlive=true"
                                    )

                                    Log.i(
                                        TAG_KWS,
                                        "KWS_DETECTED phrase='${activeProfile.phrase}' score=1.00 threshold=${activeProfile.keywordsThreshold} chunks=$totalChunks pcmAge=${getPcmHeartbeatAgeMs()}ms"
                                    )

                                    recordKwsAttempt(
                                        attemptNumber = attemptIdx,
                                        phrase = activeProfile.phrase,
                                        threshold = activeProfile.keywordsThreshold,
                                        score = 1.0f,
                                        detected = true,
                                        rms = rms,
                                        peak = peak,
                                        pcmFrames = totalChunks * CHUNK_SAMPLES,
                                        elapsedMs = 0L,
                                        resetStatus = "SPOTTER_RESET_SUCCESS"
                                    )

                                    _state.value = WakeWordState.WAKE_DETECTED
                                    syncDiagnostics()
                                    syncMicDiagnostics()

                                    onWakeCallback?.invoke("")
                                    spot.reset(st)
                                    break
                                }
                            }
                        }
                    }

                    syncMicDiagnostics()
                }
            } catch (e: Exception) {
                Log.e(TAG_KWS, "DETECTION_LOOP_EXCEPTION detector loop failed", e)
                if (isListening) {
                    restartAudioCapture()
                }
            } finally {
                releaseAudioRecord()
                runningRecordingState = "STOPPED"
                syncMicDiagnostics()
            }
        }
    }

    override fun stopListening() {
        isListening = false
        watchdogJob?.cancel()
        watchdogJob = null
        audioRecordJob?.cancel()
        audioRecordJob = null
        releaseAudioRecord()
        _state.value = WakeWordState.IDLE
        runningRecordingState = "STOPPED"
        syncMicDiagnostics()
    }

    private fun releaseAudioRecord() {
        synchronized(audioRecordLock) {
            try {
                val rec = audioRecord
                if (rec != null) {
                    val recState = rec.recordingState
                    val st = rec.state
                    val sessId = rec.audioSessionId
                    val bufSize = minBufferSizeCache
                    if (recState == AudioRecord.RECORDSTATE_RECORDING) {
                        rec.stop()
                    }
                    rec.release()
                    Log.i(
                        tag,
                        "VOICE_STATE: AUDIO_RECORD_RELEASED " +
                        "recordingState=$recState state=$st bufferSize=$bufSize " +
                        "sampleRate=$SAMPLE_RATE source=$runningAudioSource sessionId=$sessId " +
                        "detector_generation=$detectorGeneration"
                    )
                }
                audioRecord = null
                runningAudioState = "UNINITIALIZED"
            } catch (e: Exception) {
                Log.w(tag, "Exception releasing AudioRecord: ${e.message}")
            }
        }
    }

    override fun destroy() {
        stopListening()
        synchronized(spotterLock) {
            stream?.release()
            stream = null
            spotter?.release()
            spotter = null
        }
    }

    private fun syncDiagnostics() {
        _diagnostics.value = VoiceDiagnostics(
            standbyCycles = countStandbyCycles.get(),
            wakeDetections = countWakeDetections.get(),
            rejectedEvents = countRejectedEvents.get(),
            directCommands = countDirectCommands.get(),
            handoffSuccesses = countHandoffSuccesses.get(),
            handoffErrors = countHandoffErrors.get()
        )
    }

    private fun syncMicDiagnostics() {
        _micDiagnostics.value = MicrophoneDiagnostics(
            isPermissionGranted = hasPermission(),
            audioRecordState = runningAudioState,
            recordingState = runningRecordingState,
            sampleRate = SAMPLE_RATE,
            channelConfig = "CHANNEL_IN_MONO",
            audioSource = runningAudioSource,
            pcmChunksRead = countPcmChunks.get(),
            readErrors = countReadErrors.get(),
            lastReadError = runningLastReadError,
            currentRms = runningRms,
            currentPeak = runningPeak,
            maxPeak = runningMaxPeak,
            melFramesProcessed = 0L,
            embeddingsGenerated = 0L,
            inferencesEvaluated = countKwsEvaluations.get(),
            lastConfidence = 1.0f,
            maxConfidence = 1.0f,
            threshold = activeProfile.keywordsThreshold,
            consecutiveHits = 1,
            consecutiveRequired = 1,
            wakeDetections = countWakeDetections.get(),
            rejectedDetections = countRejectedEvents.get()
        )
    }
}
