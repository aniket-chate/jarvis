package com.jarvis.client.voice.kws

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
import com.jarvis.client.voice.JarvisVoiceService
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
import java.io.FileWriter
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.abs
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.sqrt

/**
 * 5-Sample Guided Custom Wake-Word Enrollment Engine.
 *
 * Collects natural pronunciation repetitions, performs rigorous acoustic quality analysis
 * (energy, SNR, speech presence, clipping), calculates data-driven calibrated hyperparameters,
 * and builds a validated draft WakeWordProfile.
 *
 * Privacy & Safety Contract:
 * - Raw microphone audio exists strictly in transient RAM buffers and is immediately discarded.
 * - Zero raw audio is persisted to disk or sent across the network.
 * - Enrollment does NOT modify or automatically activate the active production wake-word profile.
 * - Guarantees clean restoration of background voice standby upon completion, cancel, or error.
 */
class WakeWordEnrollmentEngine(
    private val context: Context,
    private val userId: String = "default_user",
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.Default + Job())
) {

    private val tag = "WakeWordEnrollmentEngine"

    private val _enrollmentState = MutableStateFlow(EnrollmentState.IDLE)
    val enrollmentState: StateFlow<EnrollmentState> = _enrollmentState.asStateFlow()

    private val _currentRms = MutableStateFlow(0f)
    val currentRms: StateFlow<Float> = _currentRms.asStateFlow()

    private val _currentPeak = MutableStateFlow(0f)
    val currentPeak: StateFlow<Float> = _currentPeak.asStateFlow()

    private val _elapsedRecordingMs = MutableStateFlow(0L)
    val elapsedRecordingMs: StateFlow<Long> = _elapsedRecordingMs.asStateFlow()

    private val isRecording = AtomicBoolean(false)
    private var recordingJob: Job? = null
    private var audioRecord: AudioRecord? = null

    val tokenizer = SherpaBpeTokenizer(context)

    // Optional isolated Sherpa spotter for spotter telemetry evaluation
    private var spotter: KeywordSpotter? = null
    private val spotterLock = Any()

    private var activePhrase: String = ""
    private var activeNormalizedPhrase: String = ""
    private var activeTokenizedPhrase: String = ""

    private val collectedSamples = mutableListOf<EnrollmentSampleResult>()
    private var stepPrompts: List<EnrollmentStep> = emptyList()
    private var currentStepIdx = 0
    private var finalEnrollmentResult: WakeWordEnrollmentResult? = null

    companion object {
        const val SAMPLE_RATE = 16000
        const val CHUNK_SAMPLES = 1280 // 80ms at 16kHz
        const val DEFAULT_STEP_DURATION_MS = 3500L

        const val ASSET_ENCODER = "models/kws/encoder-epoch-12-avg-2-chunk-16-left-64.onnx"
        const val ASSET_DECODER = "models/kws/decoder-epoch-12-avg-2-chunk-16-left-64.onnx"
        const val ASSET_JOINER = "models/kws/joiner-epoch-12-avg-2-chunk-16-left-64.onnx"
        const val ASSET_TOKENS = "models/kws/tokens.txt"

        /**
         * Generates standard 5-step natural variation prompts for the given wake phrase.
         */
        fun createDefaultPrompts(phrase: String): List<EnrollmentStep> {
            val clean = phrase.trim().ifBlank { "Hey Jarvis" }
            return listOf(
                EnrollmentStep(
                    stepIndex = 1,
                    totalSteps = 5,
                    title = "Normal Utterance (1/5)",
                    promptInstruction = "Say '$clean' at your normal speaking volume.",
                    speakingStyle = "NORMAL",
                    targetDurationMs = DEFAULT_STEP_DURATION_MS
                ),
                EnrollmentStep(
                    stepIndex = 2,
                    totalSteps = 5,
                    title = "Soft Utterance (2/5)",
                    promptInstruction = "Say '$clean' slightly softly / quietly.",
                    speakingStyle = "SOFT",
                    targetDurationMs = DEFAULT_STEP_DURATION_MS
                ),
                EnrollmentStep(
                    stepIndex = 3,
                    totalSteps = 5,
                    title = "Distance Utterance (3/5)",
                    promptInstruction = "Hold phone slightly further away and say '$clean'.",
                    speakingStyle = "DISTANCE",
                    targetDurationMs = DEFAULT_STEP_DURATION_MS
                ),
                EnrollmentStep(
                    stepIndex = 4,
                    totalSteps = 5,
                    title = "Fast Utterance (4/5)",
                    promptInstruction = "Say '$clean' quickly / conversationally.",
                    speakingStyle = "FAST",
                    targetDurationMs = DEFAULT_STEP_DURATION_MS
                ),
                EnrollmentStep(
                    stepIndex = 5,
                    totalSteps = 5,
                    title = "Natural Utterance (5/5)",
                    promptInstruction = "Say '$clean' clearly as you naturally would.",
                    speakingStyle = "NATURAL",
                    targetDurationMs = DEFAULT_STEP_DURATION_MS
                )
            )
        }
    }

    /**
     * Pre-validates user-specified wake phrase for character validity and BPE tokenizability.
     */
    fun validatePhrase(phrase: String): PhraseValidationResult {
        val trimmed = phrase.trim()
        if (trimmed.isBlank()) {
            return PhraseValidationResult(
                isValid = false,
                normalizedPhrase = "",
                tokenizedKeyword = "",
                errorMessage = "Wake phrase cannot be empty."
            )
        }

        if (trimmed.length < 3) {
            return PhraseValidationResult(
                isValid = false,
                normalizedPhrase = "",
                tokenizedKeyword = "",
                errorMessage = "Wake phrase must be at least 3 characters long."
            )
        }

        if (trimmed.length > 32) {
            return PhraseValidationResult(
                isValid = false,
                normalizedPhrase = "",
                tokenizedKeyword = "",
                errorMessage = "Wake phrase cannot exceed 32 characters."
            )
        }

        // Allow English letters, numbers, spaces, and hyphens
        val validPattern = Regex("""^[a-zA-Z0-9\s\-']+$""")
        if (!validPattern.matches(trimmed)) {
            return PhraseValidationResult(
                isValid = false,
                normalizedPhrase = "",
                tokenizedKeyword = "",
                errorMessage = "Phrase contains invalid characters. Use English letters, numbers, or spaces."
            )
        }

        val normalized = trimmed.replace(Regex("""\s+"""), " ").uppercase()

        // Tokenize using SentencePiece BPE tokenizer
        val tokenized = tokenizer.tokenizeToKeywordLine(normalized)
        if (tokenized.isBlank()) {
            return PhraseValidationResult(
                isValid = false,
                normalizedPhrase = normalized,
                tokenizedKeyword = "",
                errorMessage = "Phrase could not be tokenized by acoustic model vocabulary."
            )
        }

        return PhraseValidationResult(
            isValid = true,
            normalizedPhrase = normalized,
            tokenizedKeyword = tokenized
        )
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
                Log.d(tag, "Extracted KWS asset for enrollment: $fileName (${outFile.length()} bytes)")
            } catch (e: Exception) {
                Log.e(tag, "Failed to copy KWS asset: $assetName", e)
            }
        }
        return outFile
    }

    private fun getTempKeywordsFile(): File {
        val tempDir = File(context.filesDir, "temp_enrollment")
        if (!tempDir.exists()) tempDir.mkdirs()
        return File(tempDir, "enrollment_keywords.txt")
    }

    private fun cleanupTempKeywordsFile() {
        try {
            val tempDir = File(context.filesDir, "temp_enrollment")
            if (tempDir.exists()) {
                tempDir.deleteRecursively()
            }
        } catch (_: Exception) {}
    }

    private fun initIsolatedSpotter(tokenizedKeyword: String): Boolean {
        synchronized(spotterLock) {
            spotter?.release()
            spotter = null

            return try {
                val tempKwFile = getTempKeywordsFile()
                FileWriter(tempKwFile).use { writer ->
                    writer.write("$tokenizedKeyword\n")
                }

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
                    keywordsFile = tempKwFile.absolutePath,
                    keywordsScore = 1.0f,
                    keywordsThreshold = 0.35f,
                    numTrailingBlanks = 1
                )

                spotter = KeywordSpotter(assetManager = null, config = kwsConfig)
                Log.i(tag, "Isolated Sherpa KeywordSpotter initialized for enrollment telemetry of '$tokenizedKeyword'")
                true
            } catch (t: Throwable) {
                Log.w(tag, "Optional enrollment KeywordSpotter could not be initialized: ${t.message}")
                true // Non-blocking: enrollment quality relies on audio analysis
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
     * Initiates a guided enrollment session for a custom wake phrase.
     */
    fun startEnrollment(phrase: String, customPrompts: List<EnrollmentStep>? = null): Boolean {
        if (!hasPermission()) {
            Log.w(tag, "Cannot start enrollment: RECORD_AUDIO permission missing.")
            _enrollmentState.value = EnrollmentState.FAILED
            return false
        }

        val validation = validatePhrase(phrase)
        if (!validation.isValid) {
            Log.w(tag, "Enrollment validation rejected phrase: ${validation.errorMessage}")
            _enrollmentState.value = EnrollmentState.FAILED
            return false
        }

        this.activePhrase = phrase.trim()
        this.activeNormalizedPhrase = validation.normalizedPhrase
        this.activeTokenizedPhrase = validation.tokenizedKeyword

        // Pause standby voice service to safely release microphone
        JarvisVoiceService.pauseStandby(context)

        initIsolatedSpotter(activeTokenizedPhrase)

        collectedSamples.clear()
        stepPrompts = customPrompts ?: createDefaultPrompts(activePhrase)
        currentStepIdx = 0
        finalEnrollmentResult = null

        _enrollmentState.value = EnrollmentState.PREPARING
        return true
    }

    fun getCurrentStep(): EnrollmentStep? {
        return if (currentStepIdx < stepPrompts.size) stepPrompts[currentStepIdx] else null
    }

    /**
     * Records and evaluates the current enrollment step prompt.
     */
    fun startRecordingStep(onStepCompleted: (EnrollmentSampleResult) -> Unit) {
        val step = getCurrentStep() ?: return
        if (isRecording.getAndSet(true)) return

        _enrollmentState.value = EnrollmentState.RECORDING

        recordingJob = scope.launch(Dispatchers.IO) {
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
                Log.e(tag, "AudioRecord init failed for enrollment step.")
                _enrollmentState.value = EnrollmentState.FAILED
                isRecording.set(false)
                JarvisVoiceService.resumeStandby(context)
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

            val localStream: OnlineStream? = synchronized(spotterLock) {
                spotter?.createStream()
            }

            val confidenceTrace = mutableListOf<Float>()
            val chunkRmsList = mutableListOf<Float>()
            var peakRms = 0.0f
            var chunkCount = 0
            var clippingChunks = 0
            var keywordDetected = false
            var keywordScore = 0.0f
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

                    // Calculate RMS & peak, convert to normalized float
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
                    chunkRmsList.add(rms)
                    if (localPeak > peakRms) peakRms = localPeak
                    if (localPeak >= 0.99f) clippingChunks++

                    _currentRms.value = rms
                    _currentPeak.value = localPeak

                    // Feed audio chunk to Sherpa KWS for telemetry
                    var stepConfidence = 0.0f
                    localStream?.let { stm ->
                        stm.acceptWaveform(floatBuffer, SAMPLE_RATE)
                        synchronized(spotterLock) {
                            while (spotter?.isReady(stm) == true) {
                                spotter?.decode(stm)
                            }
                            val res = spotter?.getResult(stm)
                            if (!res?.keyword.isNullOrBlank()) {
                                keywordDetected = true
                                stepConfidence = 1.0f
                                keywordScore = 1.0f
                            }
                        }
                    }

                    confidenceTrace.add(stepConfidence)

                    val elapsed = System.currentTimeMillis() - startTime
                    _elapsedRecordingMs.value = elapsed
                    if (elapsed >= step.targetDurationMs) {
                        break
                    }
                }
            } finally {
                localStream?.release()
                releaseAudioRecord()
                isRecording.set(false)
            }

            val durationMs = System.currentTimeMillis() - startTime
            val totalPcmFrames = chunkCount * CHUNK_SAMPLES
            val sampleCount = totalPcmFrames

            val minRms = chunkRmsList.minOrNull() ?: 0.0f
            val maxRms = chunkRmsList.maxOrNull() ?: 0.0f
            val totalAvgRms = if (chunkRmsList.isNotEmpty()) chunkRmsList.average().toFloat() else 0.0f

            // 1. Noise Floor Estimation:
            // In a 3.5-second recording, speech takes 0.4s to 1.2s.
            // The lowest 30% of energy chunks accurately measure quiescent background noise,
            // independent of when the user spoke in the window.
            val sortedRms = chunkRmsList.sorted()
            val noiseFrameCount = max(1, (sortedRms.size * 0.30f).toInt())
            val noiseFloor = if (sortedRms.isNotEmpty()) {
                sortedRms.take(noiseFrameCount).average().toFloat().coerceIn(0.0001f, 0.05f)
            } else 0.001f

            // 2. Dynamic Speech Threshold & Speech Segment Extraction:
            // Adapts to device microphone gain (e.g. Vivo V29).
            val dynamicSpeechThreshold = (noiseFloor * 1.8f).coerceAtLeast(0.0008f)
            val speechChunks = chunkRmsList.filter { it >= dynamicSpeechThreshold }

            val speechRms = if (speechChunks.isNotEmpty()) {
                speechChunks.average().toFloat()
            } else {
                val topCount = max(1, (sortedRms.size * 0.25f).toInt())
                if (sortedRms.isNotEmpty()) sortedRms.takeLast(topCount).average().toFloat() else totalAvgRms
            }

            val speechFrameCount = speechChunks.size
            val speechDurationMs = speechFrameCount * (CHUNK_SAMPLES * 1000L / SAMPLE_RATE)

            // 3. SNR Calculation:
            val snrDb = if (speechRms > noiseFloor) {
                (20.0f * log10(speechRms / noiseFloor)).coerceIn(0.0f, 40.0f)
            } else {
                0.0f
            }

            // 4. Speech Presence Detection:
            // Speech is confirmed present if sustained frames exceed threshold or speech energy is elevated above noise floor
            val hasSpeech = (speechFrameCount >= 2 && speechRms >= dynamicSpeechThreshold) ||
                    (speechRms >= (noiseFloor * 1.5f) && speechRms >= 0.0010f && peakRms >= 0.008f)

            val isClipping = (peakRms >= 0.99f) || (clippingChunks > 0)

            // 5. Rigorous Audio Quality Classification:
            val qualityClassification = when {
                durationMs < 800L -> "TOO_SHORT"
                isClipping -> "CLIPPING"
                !hasSpeech || speechRms < 0.0010f -> "TOO_QUIET"
                snrDb < 3.0f && noiseFloor > 0.02f -> "HIGH_NOISE"
                snrDb >= 6.0f && speechRms >= 0.0020f -> "GOOD"
                else -> "ACCEPTABLE"
            }

            val isValid = (qualityClassification == "GOOD" || qualityClassification == "ACCEPTABLE")
            val validationStatus = when (qualityClassification) {
                "GOOD" -> "GOOD_AUDIO"
                "ACCEPTABLE" -> "ACCEPTABLE_AUDIO"
                "TOO_QUIET" -> "TOO_QUIET"
                "CLIPPING" -> "CLIPPING"
                "HIGH_NOISE" -> "HIGH_NOISE"
                "TOO_SHORT" -> "TOO_SHORT"
                else -> qualityClassification
            }

            Log.i(
                tag,
                "Sample ${step.stepIndex} diagnostics: frames=$totalPcmFrames, minRms=$minRms, maxRms=$maxRms, " +
                        "avgRms=$totalAvgRms, noiseFloor=$noiseFloor, speechRms=$speechRms, speechFrames=$speechFrameCount " +
                        "(${speechDurationMs}ms), speechThreshold=$dynamicSpeechThreshold, snr=${String.format(java.util.Locale.US, "%.1f", snrDb)}dB, " +
                        "clipping=$clippingChunks, hasSpeech=$hasSpeech, quality=$qualityClassification, valid=$isValid"
            )

            val metrics = EnrollmentAcousticMetrics(
                totalPcmFrames = totalPcmFrames,
                sampleCount = sampleCount,
                minRms = minRms,
                maxRms = maxRms,
                averageRms = totalAvgRms,
                peakRms = peakRms,
                noiseFloorRms = noiseFloor,
                speechRms = speechRms,
                speechFrameCount = speechFrameCount,
                speechDurationMs = speechDurationMs,
                speechThreshold = dynamicSpeechThreshold,
                clippingCount = clippingChunks,
                estimatedSnrDb = snrDb,
                durationMs = durationMs,
                pcmChunkCount = chunkCount,
                hasSpeechPresence = hasSpeech,
                isClipping = isClipping,
                qualityClassification = qualityClassification,
                keywordScore = keywordScore,
                isKeywordDetected = keywordDetected,
                confidenceTrace = confidenceTrace,
                validationStatus = validationStatus
            )

            val sampleResult = EnrollmentSampleResult(
                stepIndex = step.stepIndex,
                sampleId = "enr_sample_${UUID.randomUUID().toString().take(8)}",
                speakingStyle = step.speakingStyle,
                metrics = metrics,
                isValid = isValid
            )

            collectedSamples.add(sampleResult)
            currentStepIdx++

            scope.launch(Dispatchers.Main) {
                onStepCompleted(sampleResult)
                if (currentStepIdx < stepPrompts.size) {
                    _enrollmentState.value = EnrollmentState.SAMPLE_COMPLETE
                } else {
                    _enrollmentState.value = EnrollmentState.COMPLETED
                    finalEnrollmentResult = evaluateEnrollmentResult()
                    JarvisVoiceService.resumeStandby(context)
                }
            }
        }
    }

    fun stopRecordingStep() {
        isRecording.set(false)
    }

    /**
     * Computes the aggregated enrollment result with calibrated hyperparameters.
     * Separates audio quality validation from uncalibrated KWS detection.
     */
    fun evaluateEnrollmentResult(): WakeWordEnrollmentResult {
        val total = stepPrompts.size
        val validAudioSamples = collectedSamples.count { it.isValid }
        val detectedSamples = collectedSamples.count { it.metrics.isKeywordDetected }

        val avgRms = if (collectedSamples.isNotEmpty()) {
            collectedSamples.map { it.metrics.averageRms }.sum() / collectedSamples.size
        } else 0f

        val avgPeak = if (collectedSamples.isNotEmpty()) {
            collectedSamples.map { it.metrics.peakRms }.sum() / collectedSamples.size
        } else 0f

        val avgNoise = if (collectedSamples.isNotEmpty()) {
            collectedSamples.map { it.metrics.noiseFloorRms }.sum() / collectedSamples.size
        } else 0f

        val avgSpeechRms = if (collectedSamples.isNotEmpty()) {
            collectedSamples.map { it.metrics.speechRms }.sum() / collectedSamples.size
        } else 0f

        val avgSnr = if (collectedSamples.isNotEmpty()) {
            collectedSamples.map { it.metrics.estimatedSnrDb }.sum() / collectedSamples.size
        } else 0f

        val avgScore = if (collectedSamples.isNotEmpty()) {
            collectedSamples.map { it.metrics.keywordScore }.sum() / collectedSamples.size
        } else 0f

        val allConfs = collectedSamples.flatMap { it.metrics.confidenceTrace }
        val minConf = allConfs.minOrNull() ?: 0f
        val maxConf = allConfs.maxOrNull() ?: 0f

        // Token count adaptation: single words like "Computer", "Friday" use ~0.32; multi-word use ~0.36
        val tokenCount = activeTokenizedPhrase.split(" ").filter { it.isNotBlank() }.size
        val baseThreshold = if (tokenCount <= 4) 0.32f else 0.36f
        val energyAdjustment = when {
            avgSpeechRms < 0.005f -> -0.03f // softer speech -> lower threshold slightly
            avgSpeechRms > 0.040f -> +0.03f // loud speech -> raise threshold slightly
            else -> 0.0f
        }
        val recommendedThreshold = (baseThreshold + energyAdjustment).coerceIn(0.28f, 0.45f)
        val recommendedScore = 1.0f
        val recommendedTrailingBlanks = if (collectedSamples.any { it.speakingStyle == "FAST" }) 2 else 1

        // Strict 5/5 valid speech sample requirement for reliable activation
        val isReliable = (validAudioSamples == total && total >= 5)
        val reliabilityReason = when {
            validAudioSamples < 3 -> "Audio quality insufficient: only $validAudioSamples of $total samples had clear speech."
            validAudioSamples < total -> "Enrollment incomplete: $validAudioSamples of $total samples valid. Exactly $total valid samples required."
            else -> "High-quality enrollment: $validAudioSamples/$total speech samples validated (${String.format(java.util.Locale.US, "%.1f", avgSnr)}dB SNR). Ready to activate."
        }

        val result = WakeWordEnrollmentResult(
            userId = userId,
            phrase = activePhrase,
            normalizedPhrase = activeNormalizedPhrase,
            tokenizedPhrase = activeTokenizedPhrase,
            totalSamples = total,
            validAudioSamples = validAudioSamples,
            successfulSamples = validAudioSamples,
            detectedSamples = detectedSamples,
            averageRms = avgRms,
            averagePeak = avgPeak,
            averageNoiseFloor = avgNoise,
            averageSpeechRms = avgSpeechRms,
            averageSnrDb = avgSnr,
            averageKeywordScore = avgScore,
            minConfidence = minConf,
            maxConfidence = maxConf,
            recommendedKeywordsThreshold = recommendedThreshold,
            recommendedKeywordsScore = recommendedScore,
            recommendedNumTrailingBlanks = recommendedTrailingBlanks,
            isReliable = isReliable,
            reliabilityReason = reliabilityReason,
            sampleResults = collectedSamples.toList()
        )

        this.finalEnrollmentResult = result
        return result
    }

    fun getEnrollmentResult(): WakeWordEnrollmentResult? = finalEnrollmentResult

    fun getCollectedSamples(): List<EnrollmentSampleResult> = collectedSamples.toList()

    /**
     * Cancels the enrollment session, discards transient samples, and restores standby.
     */
    fun cancelEnrollment() {
        isRecording.set(false)
        recordingJob?.cancel()
        releaseAudioRecord()
        cleanupTempKeywordsFile()
        collectedSamples.clear()
        _elapsedRecordingMs.value = 0L
        _currentRms.value = 0f
        _currentPeak.value = 0f
        _enrollmentState.value = EnrollmentState.CANCELLED

        // Guarantee production microphone standby is restored
        JarvisVoiceService.resumeStandby(context)
    }

    private fun releaseAudioRecord() {
        try {
            audioRecord?.stop()
        } catch (_: Exception) {}
        try {
            audioRecord?.release()
        } catch (_: Exception) {}
        audioRecord = null
    }
}
