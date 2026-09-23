package com.jarvis.client.ui

import android.Manifest
import android.app.AlertDialog
import android.content.pm.PackageManager
import android.os.Bundle
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.recyclerview.widget.LinearLayoutManager
import com.jarvis.client.R
import com.jarvis.client.databinding.ActivityMainBinding
import com.jarvis.client.model.ConnectionState
import com.jarvis.client.settings.JarvisSettingsManager
import com.jarvis.client.voice.VoiceState
import kotlinx.coroutines.launch

/**
 * Main executive activity for Jarvis Android Client with dual Text & Voice interfaces.
 */
class MainActivity : AppCompatActivity() {

    private val tag = "MainActivity"
    private lateinit var binding: ActivityMainBinding
    private val viewModel: MainViewModel by viewModels()
    private val chatAdapter = ChatAdapter()

    private val requestAudioPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted: Boolean ->
        if (isGranted) {
            viewModel.startVoiceListening()
        } else {
            Toast.makeText(
                this,
                getString(R.string.permission_mic_rationale),
                Toast.LENGTH_LONG
            ).show()
        }
    }

    private val requestNotificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted: Boolean ->
        if (isGranted) {
            android.util.Log.i("MainActivity", "POST_NOTIFICATIONS permission granted by user")
        } else {
            android.util.Log.w("MainActivity", "POST_NOTIFICATIONS permission denied by user")
            Toast.makeText(
                this,
                getString(R.string.permission_notification_rationale),
                Toast.LENGTH_SHORT
            ).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupWindowInsets()
        setupRecyclerView()
        setupListeners()
        observeViewModel()
        updateHeaderLabels()
        checkAndRequestNotificationPermission()
    }

    override fun onResume() {
        super.onResume()
        viewModel.checkAndRefreshCapabilities()
    }

    private fun setupWindowInsets() {
        val initialHeaderPaddingTop = binding.headerLayout.paddingTop
        val initialInputPaddingBottom = binding.inputBarLayout.paddingBottom

        ViewCompat.setOnApplyWindowInsetsListener(binding.root) { _, insets ->
            val imeInsets = insets.getInsets(WindowInsetsCompat.Type.ime())
            val systemBarsInsets = insets.getInsets(WindowInsetsCompat.Type.systemBars())

            // Status bar top inset
            binding.headerLayout.setPadding(
                binding.headerLayout.paddingLeft,
                systemBarsInsets.top + initialHeaderPaddingTop,
                binding.headerLayout.paddingRight,
                binding.headerLayout.paddingBottom
            )

            // Bottom inset: IME keyboard when active, otherwise system navigation bar
            val bottomInset = if (imeInsets.bottom > 0) {
                imeInsets.bottom
            } else {
                systemBarsInsets.bottom
            }

            binding.inputBarLayout.setPadding(
                binding.inputBarLayout.paddingLeft,
                binding.inputBarLayout.paddingTop,
                binding.inputBarLayout.paddingRight,
                bottomInset + initialInputPaddingBottom
            )

            // Auto-scroll chat to latest message when keyboard pops up
            if (imeInsets.bottom > 0 && chatAdapter.itemCount > 0) {
                binding.recyclerViewChat.post {
                    binding.recyclerViewChat.smoothScrollToPosition(chatAdapter.itemCount - 1)
                }
            }

            insets
        }

        // Auto-scroll when message input gains focus
        binding.etMessageInput.setOnFocusChangeListener { _, hasFocus ->
            if (hasFocus && chatAdapter.itemCount > 0) {
                binding.recyclerViewChat.postDelayed({
                    binding.recyclerViewChat.smoothScrollToPosition(chatAdapter.itemCount - 1)
                }, 200)
            }
        }

        // Layout change listener for RecyclerView so messages adjust when keyboard/input size changes
        binding.recyclerViewChat.addOnLayoutChangeListener { _, _, _, _, bottom, _, _, _, oldBottom ->
            if (bottom < oldBottom && chatAdapter.itemCount > 0) {
                binding.recyclerViewChat.post {
                    binding.recyclerViewChat.smoothScrollToPosition(chatAdapter.itemCount - 1)
                }
            }
        }
    }

    private fun checkAndRequestNotificationPermission() {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(
                    this,
                    Manifest.permission.POST_NOTIFICATIONS
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                requestNotificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }

    private fun setupRecyclerView() {
        val layoutManager = LinearLayoutManager(this).apply {
            stackFromEnd = true
        }
        binding.recyclerViewChat.layoutManager = layoutManager
        binding.recyclerViewChat.adapter = chatAdapter
    }

    private fun setupListeners() {
        binding.btnSendMessage.setOnClickListener {
            sendMessage()
        }

        binding.etMessageInput.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                sendMessage()
                true
            } else {
                false
            }
        }

        binding.btnMic.setOnClickListener {
            handleMicButtonClick()
        }

        binding.btnConfirmAction.setOnClickListener {
            viewModel.confirmAction(true)
        }

        binding.btnCancelAction.setOnClickListener {
            viewModel.confirmAction(false)
        }

        binding.btnVoiceStandby.setOnClickListener {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                viewModel.toggleVoiceService(this)
            } else {
                requestAudioPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            }
        }

        binding.btnOpenSettings.setOnClickListener {
            showSettingsDialog()
        }

        binding.statusBadge.setOnClickListener {
            viewModel.sendPing()
        }
    }

    private fun handleMicButtonClick() {
        val state = viewModel.compositeVoiceState.value
        when (state) {
            VoiceState.LISTENING -> {
                viewModel.stopVoiceListening()
            }
            VoiceState.SPEAKING -> {
                viewModel.stopSpeaking()
            }
            else -> {
                if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                    viewModel.startVoiceListening()
                } else {
                    requestAudioPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                }
            }
        }
    }

    private fun sendMessage() {
        val text = binding.etMessageInput.text?.toString()?.trim() ?: ""
        if (text.isNotEmpty()) {
            viewModel.sendMessage(text)
            binding.etMessageInput.setText("")
        }
    }

    private fun observeViewModel() {
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                launch {
                    viewModel.connectionState.collect { state ->
                        updateConnectionStatusUI(state)
                    }
                }

                launch {
                    viewModel.isVoiceServiceRunning.collect { isRunning ->
                        val tintColor = if (isRunning) {
                            ContextCompat.getColor(this@MainActivity, R.color.jarvis_cyan)
                        } else {
                            ContextCompat.getColor(this@MainActivity, R.color.text_secondary)
                        }
                        binding.btnVoiceStandby.setColorFilter(tintColor)
                    }
                }

                launch {
                    viewModel.chatMessages.collect { messages ->
                        chatAdapter.submitList(messages) {
                            if (messages.isNotEmpty()) {
                                binding.recyclerViewChat.scrollToPosition(messages.size - 1)
                            }
                        }
                    }
                }

                launch {
                    viewModel.pendingConfirmation.collect { pendingMsg ->
                        if (pendingMsg != null) {
                            binding.confirmationCard.visibility = View.VISIBLE
                            binding.tvConfirmMessage.text = pendingMsg.text
                        } else {
                            binding.confirmationCard.visibility = View.GONE
                        }
                    }
                }

                launch {
                    viewModel.compositeVoiceState.collect { voiceState ->
                        updateVoiceStateUI(voiceState)
                    }
                }

                launch {
                    viewModel.partialTranscript.collect { partial ->
                        binding.tvPartialTranscript.text = partial
                    }
                }

                launch {
                    viewModel.serviceVoiceState.collect { sState ->
                        if (viewModel.isVoiceServiceRunning.value) {
                            when (sState) {
                                com.jarvis.client.voice.ServiceVoiceState.RECOVERING -> {
                                    binding.tvVoiceState.text = "Standby: RECOVERING..."
                                    binding.tvVoiceIcon.text = "🔁"
                                }
                                com.jarvis.client.voice.ServiceVoiceState.ERROR -> {
                                    binding.tvVoiceState.text = "Standby: ERROR / NOT RECORDING"
                                    binding.tvVoiceIcon.text = "⚠️"
                                }
                                com.jarvis.client.voice.ServiceVoiceState.LISTENING_CONFIRMATION -> {
                                    binding.tvVoiceState.text = "Awaiting Confirmation (Say 'Yes' or 'No')"
                                    binding.tvVoiceIcon.text = "🔴"
                                }
                                com.jarvis.client.voice.ServiceVoiceState.WAITING_CONFIRMATION -> {
                                    binding.tvVoiceState.text = "Awaiting Confirmation..."
                                    binding.tvVoiceIcon.text = "❓"
                                }
                                else -> {}
                            }
                        }
                    }
                }

                launch {
                    viewModel.micDiagnostics.collect { diag ->
                        if (viewModel.isVoiceServiceRunning.value && viewModel.serviceVoiceState.value == com.jarvis.client.voice.ServiceVoiceState.STANDBY_RECORDING) {
                            if (diag.recordingState == "RECORDING" && diag.pcmChunksRead > 0) {
                                binding.tvVoiceState.text = String.format(
                                    java.util.Locale.US,
                                    "Standby: RECORDING (RMS: %.3f | Pk: %.2f | Thr: %.2f | Chunks: %d)",
                                    diag.currentRms,
                                    diag.currentPeak,
                                    diag.threshold,
                                    diag.pcmChunksRead
                                )
                                binding.tvVoiceIcon.text = "🎙️"
                            } else if (diag.recordingState == "RECORDING") {
                                binding.tvVoiceState.text = "Standby: RECORDING (Waiting for audio...)"
                                binding.tvVoiceIcon.text = "🎙️"
                            } else {
                                binding.tvVoiceState.text = "Standby: NOT RECORDING (${diag.recordingState} / ${diag.audioRecordState})"
                                binding.tvVoiceIcon.text = "⚠️"
                            }
                        }
                    }
                }
            }
        }
    }

    private fun updateConnectionStatusUI(state: ConnectionState) {
        val (textRes, colorRes) = when (state) {
            ConnectionState.DISCONNECTED -> Pair(R.string.status_disconnected, R.color.status_red)
            ConnectionState.CONNECTING -> Pair(R.string.status_connecting, R.color.status_yellow)
            ConnectionState.CONNECTED -> Pair(R.string.status_connected, R.color.status_green)
            ConnectionState.AUTHENTICATING -> Pair(R.string.status_authenticating, R.color.status_yellow)
            ConnectionState.AUTHENTICATED -> Pair(R.string.status_authenticated, R.color.jarvis_cyan)
            ConnectionState.RECONNECTING -> Pair(R.string.status_reconnecting, R.color.status_yellow)
            ConnectionState.ERROR -> Pair(R.string.status_error, R.color.status_red)
        }

        val color = ContextCompat.getColor(this, colorRes)
        binding.tvStatusText.setText(textRes)
        binding.tvStatusText.setTextColor(color)
        binding.viewStatusDot.setBackgroundColor(color)
    }

    private fun updateVoiceStateUI(voiceState: VoiceState) {
        when (voiceState) {
            VoiceState.IDLE -> {
                binding.tvVoiceIcon.text = "🎙️"
                binding.tvVoiceState.setText(R.string.voice_idle)
                binding.tvVoiceState.setTextColor(ContextCompat.getColor(this, R.color.text_secondary))
                binding.btnMic.setColorFilter(ContextCompat.getColor(this, R.color.mic_idle))
            }
            VoiceState.LISTENING -> {
                binding.tvVoiceIcon.text = "🔴"
                binding.tvVoiceState.setText(R.string.voice_listening)
                binding.tvVoiceState.setTextColor(ContextCompat.getColor(this, R.color.mic_listening))
                binding.btnMic.setColorFilter(ContextCompat.getColor(this, R.color.mic_listening))
            }
            VoiceState.PROCESSING -> {
                binding.tvVoiceIcon.text = "⏳"
                binding.tvVoiceState.setText(R.string.voice_thinking)
                binding.tvVoiceState.setTextColor(ContextCompat.getColor(this, R.color.status_yellow))
                binding.btnMic.setColorFilter(ContextCompat.getColor(this, R.color.status_yellow))
            }
            VoiceState.SPEAKING -> {
                binding.tvVoiceIcon.text = "🔊"
                binding.tvVoiceState.setText(R.string.voice_speaking)
                binding.tvVoiceState.setTextColor(ContextCompat.getColor(this, R.color.mic_speaking))
                binding.btnMic.setColorFilter(ContextCompat.getColor(this, R.color.mic_speaking))
            }
            VoiceState.ERROR -> {
                binding.tvVoiceIcon.text = "⚠️"
                binding.tvVoiceState.setText(R.string.voice_error)
                binding.tvVoiceState.setTextColor(ContextCompat.getColor(this, R.color.status_red))
                binding.btnMic.setColorFilter(ContextCompat.getColor(this, R.color.status_red))
            }
        }
    }

    private fun updateHeaderLabels() {
        val settings = viewModel.settingsManager
        binding.tvDeviceLabel.text = "Device: ${settings.deviceName} (${settings.deviceId})"
        binding.tvBackendUrlLabel.text = settings.backendBaseUrl
    }

    private fun showSettingsDialog() {
        val settings = viewModel.settingsManager
        val dialogView = LayoutInflater.from(this).inflate(R.layout.dialog_settings, null)

        val etBackendUrl = dialogView.findViewById<EditText>(R.id.etBackendUrl)
        val etUserId = dialogView.findViewById<EditText>(R.id.etUserId)
        val etDeviceId = dialogView.findViewById<EditText>(R.id.etDeviceId)
        val etDeviceName = dialogView.findViewById<EditText>(R.id.etDeviceName)
        val etAuthToken = dialogView.findViewById<EditText>(R.id.etAuthToken)

        etBackendUrl.setText(settings.backendBaseUrl)
        etUserId.setText(settings.userId)
        etDeviceId.setText(settings.deviceId)
        etDeviceName.setText(settings.deviceName)
        etAuthToken.setText(settings.authToken)

        val tvSettingsWakeWordSummary: TextView = dialogView.findViewById(R.id.tvSettingsWakeWordSummary)
        val btnChangeWakeWord: Button = dialogView.findViewById(R.id.btnChangeWakeWord)
        val btnResetWakeWord: Button = dialogView.findViewById(R.id.btnResetWakeWord)

        fun updateWakeWordSummary() {
            val prof = viewModel.activeWakeWordProfile.value
            val profType = if (prof.isCustomEnrolled && prof.phrase != "Hey Jarvis") "Custom Active" else "Factory Default"
            tvSettingsWakeWordSummary.text = "Current Wake Word: ${prof.phrase}\nProfile: $profType\nUser: ${settings.userId}"
        }
        updateWakeWordSummary()

        btnChangeWakeWord.setOnClickListener {
            showWakeWordEnrollmentDialog {
                updateWakeWordSummary()
            }
        }

        btnResetWakeWord.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("Reset Wake Word?")
                .setMessage("Jarvis will return to the default wake word ('Hey Jarvis').")
                .setPositiveButton("Reset") { _, _ ->
                    val res = viewModel.resetWakeWordToDefault(applicationContext)
                    if (res.success) {
                        updateWakeWordSummary()
                        Toast.makeText(this, "Wake word reset to 'Hey Jarvis'.", Toast.LENGTH_SHORT).show()
                    }
                }
                .setNegativeButton("Cancel", null)
                .show()
        }

        val btnOpenFieldTestHarness: Button? = dialogView.findViewById(R.id.btnOpenFieldTestHarness)
        btnOpenFieldTestHarness?.setOnClickListener {
            showWakeWordFieldTestHarness()
        }

        val btnOpenKwsIsolationTest: Button? = dialogView.findViewById(R.id.btnOpenKwsIsolationTest)
        btnOpenKwsIsolationTest?.setOnClickListener {
            showKwsIsolationDialog()
        }

        val btnOpenSttIsolationTest: Button? = dialogView.findViewById(R.id.btnOpenSttIsolationTest)
        btnOpenSttIsolationTest?.setOnClickListener {
            showSpeechRecognizerIsolationDialog()
        }

        AlertDialog.Builder(this)
            .setView(dialogView)
            .setPositiveButton(R.string.btn_save) { _, _ ->
                val newUrl = etBackendUrl.text.toString().trim()
                val newUserId = etUserId.text.toString().trim()
                val newDeviceId = etDeviceId.text.toString().trim()
                val newDeviceName = etDeviceName.text.toString().trim()
                val newAuthToken = etAuthToken.text.toString().trim()

                viewModel.updateSettings(
                    backendUrl = newUrl.ifBlank { JarvisSettingsManager.DEFAULT_BACKEND_URL },
                    userId = newUserId.ifBlank { JarvisSettingsManager.DEFAULT_USER_ID },
                    deviceId = newDeviceId.ifBlank { JarvisSettingsManager.DEFAULT_DEVICE_ID },
                    deviceName = newDeviceName.ifBlank { JarvisSettingsManager.DEFAULT_DEVICE_NAME },
                    authToken = newAuthToken
                )
                updateHeaderLabels()
            }
            .setNegativeButton(R.string.btn_cancel, null)
            .show()
    }

    private fun showWakeWordFieldTestHarness() {
        try {
            val settings = viewModel.settingsManager
            val webView = android.webkit.WebView(this)
            webView.settings.javaScriptEnabled = true
            webView.settings.domStorageEnabled = true
            webView.settings.allowFileAccess = true

            val bridge = com.jarvis.client.voice.kws.WakeWordFieldTestBridge(
                context = applicationContext,
                userId = settings.userId,
                onReloadSpotter = {
                    com.jarvis.client.voice.JarvisVoiceService.pauseStandby(applicationContext)
                    com.jarvis.client.voice.JarvisVoiceService.resumeStandby(applicationContext)
                    true
                }
            )
            webView.addJavascriptInterface(bridge, "JarvisTestBridge")
            webView.loadUrl("file:///android_asset/wake_word_field_test.html")

            val dialog = AlertDialog.Builder(this)
                .setTitle("Wake-Word Field Test Harness")
                .setView(webView)
                .setPositiveButton("Close") { d, _ ->
                    bridge.cancelEnrollment()
                    d.dismiss()
                }
                .create()

            dialog.setOnDismissListener {
                bridge.cancelEnrollment()
                webView.destroy()
            }
            dialog.show()
        } catch (e: Exception) {
            Log.e(tag, "Failed to launch wake word field test harness", e)
            Toast.makeText(this, "Error opening field test: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun showWakeWordEnrollmentDialog(onCompleted: (() -> Unit)? = null) {
        try {
            val settings = viewModel.settingsManager
            val dialogView = LayoutInflater.from(this).inflate(R.layout.dialog_wake_word_enrollment, null)
            val dialog = AlertDialog.Builder(this).setView(dialogView).create()

            val enrollmentEngine = com.jarvis.client.voice.kws.WakeWordEnrollmentEngine(applicationContext, settings.userId)

            val cardPhraseSetup: View = dialogView.findViewById(R.id.cardPhraseSetup)
            val etWakePhraseInput: EditText = dialogView.findViewById(R.id.etWakePhraseInput)
            val tvPhraseValidationWarning: TextView = dialogView.findViewById(R.id.tvPhraseValidationWarning)
            val btnStartEnrollment: Button = dialogView.findViewById(R.id.btnStartEnrollment)

            val cardEnrollmentWizard: View = dialogView.findViewById(R.id.cardEnrollmentWizard)
            val tvStepCounter: TextView = dialogView.findViewById(R.id.tvStepCounter)
            val tvStepInstruction: TextView = dialogView.findViewById(R.id.tvStepInstruction)
            val progressBarStep: ProgressBar = dialogView.findViewById(R.id.progressBarStep)
            val tvStepStatus: TextView = dialogView.findViewById(R.id.tvStepStatus)
            val tvLiveAudioStats: TextView = dialogView.findViewById(R.id.tvLiveAudioStats)
            val btnRecordStep: Button = dialogView.findViewById(R.id.btnRecordStep)
            val btnCancelEnrollment: Button = dialogView.findViewById(R.id.btnCancelEnrollment)

            val cardEnrollmentResults: View = dialogView.findViewById(R.id.cardEnrollmentResults)
            val tvResultWakeWord: TextView = dialogView.findViewById(R.id.tvResultWakeWord)
            val tvResultSamples: TextView = dialogView.findViewById(R.id.tvResultSamples)
            val tvResultSnr: TextView = dialogView.findViewById(R.id.tvResultSnr)
            val tvResultSensitivity: TextView = dialogView.findViewById(R.id.tvResultSensitivity)
            val tvResultReliability: TextView = dialogView.findViewById(R.id.tvResultReliability)
            val btnApplyWakeWord: Button = dialogView.findViewById(R.id.btnApplyWakeWord)
            val btnTryAgain: Button = dialogView.findViewById(R.id.btnTryAgain)

            val cardActivationSuccess: View = dialogView.findViewById(R.id.cardActivationSuccess)
            val tvSuccessPhrase: TextView = dialogView.findViewById(R.id.tvSuccessPhrase)
            val btnDoneSuccess: Button = dialogView.findViewById(R.id.btnDoneSuccess)

            var stagedDraft: com.jarvis.client.voice.kws.WakeWordProfile? = null

            // Observe live RMS / peak
            lifecycleScope.launch {
                repeatOnLifecycle(androidx.lifecycle.Lifecycle.State.STARTED) {
                    launch {
                        enrollmentEngine.currentRms.collect { rms ->
                            val peak = enrollmentEngine.currentPeak.value
                            tvLiveAudioStats.text = String.format(java.util.Locale.US, "RMS: %.4f | Peak: %.4f", rms, peak)
                        }
                    }
                }
            }

            fun updateWizardStepUi() {
                val step = enrollmentEngine.getCurrentStep()
                if (step != null) {
                    tvStepCounter.text = "Sample ${step.stepIndex} of ${step.totalSteps}"
                    tvStepInstruction.text = step.promptInstruction
                    progressBarStep.progress = step.stepIndex
                    tvStepStatus.text = "Status: Ready to record sample ${step.stepIndex}"
                    btnRecordStep.isEnabled = true
                    btnRecordStep.text = "🎙️ Record Sample (${step.stepIndex}/5)"
                }
            }

            btnStartEnrollment.setOnClickListener {
                val phrase = etWakePhraseInput.text.toString().trim()
                val valRes = enrollmentEngine.validatePhrase(phrase)
                if (!valRes.isValid) {
                    tvPhraseValidationWarning.visibility = View.VISIBLE
                    tvPhraseValidationWarning.text = valRes.errorMessage ?: "Invalid wake phrase."
                    return@setOnClickListener
                }
                tvPhraseValidationWarning.visibility = View.GONE

                val started = enrollmentEngine.startEnrollment(phrase)
                if (!started) {
                    Toast.makeText(this, "Could not start enrollment. Check audio permission.", Toast.LENGTH_SHORT).show()
                    return@setOnClickListener
                }

                cardPhraseSetup.visibility = View.GONE
                cardEnrollmentWizard.visibility = View.VISIBLE
                updateWizardStepUi()
            }

            btnRecordStep.setOnClickListener {
                btnRecordStep.isEnabled = false
                tvStepStatus.text = "🎙️ Listening... Please speak naturally."
                enrollmentEngine.startRecordingStep { sampleResult ->
                    runOnUiThread {
                        val snrStr = String.format(java.util.Locale.US, "%.1f", sampleResult.metrics.estimatedSnrDb)
                        if (sampleResult.isValid) {
                            tvStepStatus.text = "✓ Sample captured: ${sampleResult.metrics.validationStatus} (SNR: ${snrStr} dB)"
                        } else {
                            tvStepStatus.text = "⚠️ Sample warning: ${sampleResult.metrics.validationStatus} (SNR: ${snrStr} dB)"
                        }

                        val nextStep = enrollmentEngine.getCurrentStep()
                        if (nextStep != null) {
                            updateWizardStepUi()
                        } else {
                            // 5 steps completed!
                            val finalResult = enrollmentEngine.evaluateEnrollmentResult()
                            stagedDraft = viewModel.wakeWordProfileManager.createDraft(finalResult)

                            cardEnrollmentWizard.visibility = View.GONE
                            cardEnrollmentResults.visibility = View.VISIBLE

                            tvResultWakeWord.text = "Wake Word: ${finalResult.phrase}"
                            tvResultSamples.text = "Speech Samples: ${finalResult.validAudioSamples} / ${finalResult.totalSamples} validated"
                            tvResultSnr.text = String.format(java.util.Locale.US, "Speech Signal-to-Noise: %.1f dB", finalResult.averageSnrDb)
                            tvResultSensitivity.text = String.format(
                                java.util.Locale.US,
                                "Recommended Sensitivity: Threshold %.2f | Score %.2f",
                                finalResult.recommendedKeywordsThreshold,
                                finalResult.recommendedKeywordsScore
                            )
                            tvResultReliability.text = "Quality: ${finalResult.reliabilityReason}"
                            btnApplyWakeWord.isEnabled = (finalResult.isReliable && finalResult.validAudioSamples == finalResult.totalSamples)
                        }
                    }
                }
            }

            btnApplyWakeWord.setOnClickListener {
                val draft = stagedDraft
                if (draft == null) {
                    Toast.makeText(this, "No valid draft to activate.", Toast.LENGTH_SHORT).show()
                    return@setOnClickListener
                }
                btnApplyWakeWord.isEnabled = false
                btnApplyWakeWord.text = "Applying..."

                val activation = viewModel.activateWakeWordProfile(draft, applicationContext)
                if (activation.success && activation.activeProfile != null) {
                    cardEnrollmentResults.visibility = View.GONE
                    cardActivationSuccess.visibility = View.VISIBLE
                    tvSuccessPhrase.text = "Your new wake word is: '${activation.activeProfile.phrase}'"
                    onCompleted?.invoke()
                } else {
                    btnApplyWakeWord.isEnabled = true
                    btnApplyWakeWord.text = "✓ Apply Wake Word"
                    Toast.makeText(this, "Activation failed: ${activation.errorMessage}", Toast.LENGTH_LONG).show()
                }
            }

            btnTryAgain.setOnClickListener {
                enrollmentEngine.cancelEnrollment()
                cardEnrollmentResults.visibility = View.GONE
                cardPhraseSetup.visibility = View.VISIBLE
            }

            btnCancelEnrollment.setOnClickListener {
                enrollmentEngine.cancelEnrollment()
                dialog.dismiss()
            }

            btnDoneSuccess.setOnClickListener {
                dialog.dismiss()
            }

            dialog.setOnDismissListener {
                enrollmentEngine.cancelEnrollment()
            }

            dialog.show()
        } catch (e: Exception) {
            Log.e(tag, "Failed to show wake word enrollment dialog", e)
            Toast.makeText(this, "Error opening wake word enrollment: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun showCalibrationDialog() {
        try {
            val settings = viewModel.settingsManager
            val storageManager = viewModel.calibrationStorageManager
            val dialogView = LayoutInflater.from(this).inflate(R.layout.dialog_calibration, null)
            val dialog = AlertDialog.Builder(this).setView(dialogView).create()

            var calibrationEngine: com.jarvis.client.voice.calibration.CalibrationEngine? = null
            fun getCalibrationEngine(): com.jarvis.client.voice.calibration.CalibrationEngine {
                if (calibrationEngine == null) {
                    calibrationEngine = com.jarvis.client.voice.calibration.CalibrationEngine(applicationContext, settings.userId)
                }
                return calibrationEngine!!
            }

            val tvCurrentProfileStatus = dialogView.findViewById<android.widget.TextView>(R.id.tvCurrentProfileStatus)
            val tvCurrentThresholdInfo = dialogView.findViewById<android.widget.TextView>(R.id.tvCurrentThresholdInfo)
            val tvSampleCountsInfo = dialogView.findViewById<android.widget.TextView>(R.id.tvSampleCountsInfo)

            val cardCalibrationWizard = dialogView.findViewById<View>(R.id.cardCalibrationWizard)
            val tvStepCounter = dialogView.findViewById<android.widget.TextView>(R.id.tvStepCounter)
            val tvStepInstruction = dialogView.findViewById<android.widget.TextView>(R.id.tvStepInstruction)
            val progressBarStep = dialogView.findViewById<android.widget.ProgressBar>(R.id.progressBarStep)
            val tvStepStatus = dialogView.findViewById<android.widget.TextView>(R.id.tvStepStatus)
            val tvLiveMaxConfidence = dialogView.findViewById<android.widget.TextView>(R.id.tvLiveMaxConfidence)
            val btnRecordStep = dialogView.findViewById<android.widget.Button>(R.id.btnRecordStep)
            val btnCancelCalibration = dialogView.findViewById<android.widget.Button>(R.id.btnCancelCalibration)

            val cardCalibrationResults = dialogView.findViewById<View>(R.id.cardCalibrationResults)
            val tvResultsPositives = dialogView.findViewById<android.widget.TextView>(R.id.tvResultsPositives)
            val tvResultsNegatives = dialogView.findViewById<android.widget.TextView>(R.id.tvResultsNegatives)
            val tvResultsRecommendation = dialogView.findViewById<android.widget.TextView>(R.id.tvResultsRecommendation)
            val tvResultsExplanation = dialogView.findViewById<android.widget.TextView>(R.id.tvResultsExplanation)

            val btnStartCalibration = dialogView.findViewById<android.widget.Button>(R.id.btnStartCalibration)
            val btnViewResults = dialogView.findViewById<android.widget.Button>(R.id.btnViewResults)
            val btnApplyCalibration = dialogView.findViewById<android.widget.Button>(R.id.btnApplyCalibration)
            val btnResetCalibration = dialogView.findViewById<android.widget.Button>(R.id.btnResetCalibration)
            val btnCloseCalibration = dialogView.findViewById<android.widget.Button>(R.id.btnCloseCalibration)

            fun displayResultsUI(profile: com.jarvis.client.voice.calibration.CalibrationProfile) {
                val summaries = profile.sampleSummaries ?: emptyList()
                val positives = summaries.filter { it.sampleType == com.jarvis.client.voice.calibration.CalibrationSampleType.POSITIVE_WAKE }
                val negatives = summaries.filter { it.sampleType != com.jarvis.client.voice.calibration.CalibrationSampleType.POSITIVE_WAKE }

                val minPosPeak = positives.mapNotNull { it.maxConfidence }.minOrNull() ?: 0f
                val avgPosPeak = if (positives.isNotEmpty()) positives.map { it.maxConfidence }.sum() / positives.size else 0f
                val lowestPosConf = positives.flatMap { it.confidenceTrace ?: emptyList() }.minOrNull() ?: 0f

                val maxNegPeak = negatives.mapNotNull { it.maxConfidence }.maxOrNull() ?: 0f
                val avgNegPeak = if (negatives.isNotEmpty()) negatives.map { it.maxConfidence }.sum() / negatives.size else 0f
                val noiseFloor = if (negatives.isNotEmpty()) negatives.map { it.averageRms }.sum() / negatives.size else 0f

                tvResultsPositives.text = String.format(
                    java.util.Locale.US,
                    "Positives (%d): Min Peak: %.3f | Avg Peak: %.3f | Lowest Conf: %.3f",
                    positives.size,
                    minPosPeak,
                    avgPosPeak,
                    lowestPosConf
                )

                tvResultsNegatives.text = String.format(
                    java.util.Locale.US,
                    "Negatives (%d): Max Peak: %.3f | Avg Peak: %.3f | Noise Floor RMS: %.4f",
                    negatives.size,
                    maxNegPeak,
                    avgNegPeak,
                    noiseFloor
                )

                val rec = profile.recommendation ?: com.jarvis.client.voice.calibration.CalibrationRecommendation()
                tvResultsRecommendation.text = String.format(
                    java.util.Locale.US,
                    "Recommended: Threshold %.2f | Hits: %d | FAR: %.1f%% | FRR: %.1f%% | Margin: %.2f | Reliable: %s",
                    rec.recommendedThreshold,
                    rec.recommendedConsecutiveHits,
                    rec.expectedFar * 100f,
                    rec.expectedFrr * 100f,
                    rec.confidenceMargin,
                    if (rec.isReliable) "YES" else "NO"
                )

                if (rec.isReliable) {
                    tvResultsExplanation.text = "If the recommended profile is reliable, applying it can make Jarvis more responsive to your speaking style while reducing false triggers from your environment."
                    tvResultsExplanation.setTextColor(ContextCompat.getColor(this, R.color.status_green))
                } else {
                    tvResultsExplanation.text = "Not enough separation between your wake-word samples and background sounds. Jarvis will keep the safe default threshold (0.32)."
                    tvResultsExplanation.setTextColor(ContextCompat.getColor(this, R.color.status_yellow))
                }
            }

            fun refreshStatusUI() {
                val savedProfile = storageManager.loadProfile(settings.userId)
                val isCustomActive = settings.isCustomThresholdEnabled && savedProfile != null && savedProfile.isCustomThresholdActive

                if (isCustomActive && savedProfile != null) {
                    tvCurrentProfileStatus.text = "Current Profile: Active (User: ${settings.userId})"
                    tvCurrentProfileStatus.setTextColor(ContextCompat.getColor(this, R.color.jarvis_cyan))
                    val recHits = savedProfile.recommendation?.recommendedConsecutiveHits ?: 3
                    tvCurrentThresholdInfo.text = String.format(
                        java.util.Locale.US,
                        "Current Threshold: %.2f | Consecutive Hits: %d",
                        settings.customWakeThreshold,
                        recHits
                    )
                    tvSampleCountsInfo.text = String.format(
                        java.util.Locale.US,
                        "Positive Samples: %d | Negative Samples: %d",
                        savedProfile.positiveSampleCount,
                        savedProfile.negativeSampleCount
                    )
                } else {
                    tvCurrentProfileStatus.text = "Current Profile: None (Default 0.32)"
                    tvCurrentProfileStatus.setTextColor(ContextCompat.getColor(this, R.color.text_secondary))
                    tvCurrentThresholdInfo.text = "Current Threshold: 0.32 | Consecutive Hits: 3"
                    if (savedProfile != null) {
                        tvSampleCountsInfo.text = String.format(
                            java.util.Locale.US,
                            "Saved Samples: %d Pos / %d Neg (Not Active)",
                            savedProfile.positiveSampleCount,
                            savedProfile.negativeSampleCount
                        )
                    } else {
                        tvSampleCountsInfo.text = "Positive Samples: 0 | Negative Samples: 0"
                    }
                }
            }

            refreshStatusUI()

            fun updateWizardPromptUI() {
                val engine = getCalibrationEngine()
                val prompt = engine.getCurrentPrompt()
                if (prompt != null) {
                    tvStepCounter.text = "Step ${prompt.stepIndex} of ${prompt.totalSteps}: ${prompt.title}"
                    tvStepInstruction.text = prompt.instruction
                    tvStepStatus.text = "Ready to record"
                    tvLiveMaxConfidence.text = "Max Conf: 0.000"
                    progressBarStep.progress = 0
                    progressBarStep.isIndeterminate = false
                    btnRecordStep.isEnabled = true
                    btnRecordStep.text = "Record Sample (3.5s)"
                }
            }

            btnStartCalibration.setOnClickListener {
                if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                    requestAudioPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                    return@setOnClickListener
                }

                com.jarvis.client.voice.JarvisVoiceService.pauseStandby(this)
                val engine = getCalibrationEngine()
                val started = engine.startSession()
                if (!started) {
                    Toast.makeText(this, "Calibration engine could not be initialized.", Toast.LENGTH_SHORT).show()
                    com.jarvis.client.voice.JarvisVoiceService.resumeStandby(this)
                    return@setOnClickListener
                }
                cardCalibrationWizard.visibility = View.VISIBLE
                cardCalibrationResults.visibility = View.GONE
                updateWizardPromptUI()
            }

            btnRecordStep.setOnClickListener {
                btnRecordStep.isEnabled = false
                val engine = getCalibrationEngine()
                val prompt = engine.getCurrentPrompt() ?: return@setOnClickListener
                tvStepStatus.text = "Listening... (${prompt.title})"
                progressBarStep.isIndeterminate = true

                engine.startRecordingStep { summary ->
                    runOnUiThread {
                        progressBarStep.isIndeterminate = false
                        tvLiveMaxConfidence.text = String.format(java.util.Locale.US, "Max Conf: %.3f", summary.maxConfidence)

                        val nextPrompt = engine.getCurrentPrompt()
                        if (nextPrompt != null) {
                            tvStepStatus.text = "Recorded step ${summary.sampleType.name}. Ready for next step."
                            updateWizardPromptUI()
                        } else {
                            tvStepStatus.text = "All 11 samples captured!"
                            cardCalibrationWizard.visibility = View.GONE
                            val profile = engine.generateProfile(settings.userId, settings.deviceId)
                            storageManager.saveProfile(profile)
                            cardCalibrationResults.visibility = View.VISIBLE
                            displayResultsUI(profile)
                            refreshStatusUI()
                            com.jarvis.client.voice.JarvisVoiceService.resumeStandby(this)
                            Toast.makeText(this, "Calibration complete! Review results below.", Toast.LENGTH_SHORT).show()
                        }
                    }
                }
            }

            btnCancelCalibration.setOnClickListener {
                calibrationEngine?.cancelSession()
                cardCalibrationWizard.visibility = View.GONE
                com.jarvis.client.voice.JarvisVoiceService.resumeStandby(this)
                refreshStatusUI()
            }

            btnViewResults.setOnClickListener {
                val savedProfile = storageManager.loadProfile(settings.userId)
                if (savedProfile != null && (savedProfile.sampleSummaries?.isNotEmpty() == true)) {
                    cardCalibrationResults.visibility = View.VISIBLE
                    displayResultsUI(savedProfile)
                } else {
                    Toast.makeText(this, "No calibration results found. Please start calibration.", Toast.LENGTH_SHORT).show()
                }
            }

            btnApplyCalibration.setOnClickListener {
                val savedProfile = storageManager.loadProfile(settings.userId)
                if (savedProfile != null && (savedProfile.sampleSummaries?.isNotEmpty() == true)) {
                    val activeProfile = savedProfile.copy(isCustomThresholdActive = true)
                    viewModel.applyCalibrationProfile(activeProfile, this)
                    refreshStatusUI()
                    cardCalibrationResults.visibility = View.VISIBLE
                    displayResultsUI(activeProfile)
                    val recThr = activeProfile.recommendation?.recommendedThreshold ?: 0.32f
                    Toast.makeText(
                        this,
                        String.format(java.util.Locale.US, "Calibrated threshold applied: %.2f", recThr),
                        Toast.LENGTH_LONG
                    ).show()
                } else {
                    Toast.makeText(this, "Please complete calibration before applying.", Toast.LENGTH_SHORT).show()
                }
            }

            btnResetCalibration.setOnClickListener {
                viewModel.disableCustomCalibration(this)
                storageManager.deleteProfile(settings.userId)
                refreshStatusUI()
                cardCalibrationResults.visibility = View.GONE
                cardCalibrationWizard.visibility = View.GONE
                Toast.makeText(this, "Calibration reset to default (Threshold: 0.32, Hits: 3)", Toast.LENGTH_SHORT).show()
            }

            btnCloseCalibration.setOnClickListener {
                dialog.dismiss()
            }

            dialog.setOnDismissListener {
                calibrationEngine?.destroy()
                calibrationEngine = null
                com.jarvis.client.voice.JarvisVoiceService.resumeStandby(this)
            }

            dialog.show()
        } catch (e: Exception) {
            Log.e(tag, "Failed to open calibration dialog: ${e.message}", e)
            Toast.makeText(this, "Unable to open calibration: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun showKwsIsolationDialog() {
        try {
            val settings = viewModel.settingsManager
            val activeProf = viewModel.activeWakeWordProfile.value

            com.jarvis.client.voice.JarvisVoiceService.pauseStandby(this)

            var detector: com.jarvis.client.voice.SherpaKwsDetector? =
                com.jarvis.client.voice.SherpaKwsDetector(applicationContext, activeUserId = settings.userId)

            var attempts = 0
            var detections = 0
            var isTestRunning = true

            val layout = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(32, 24, 32, 24)
                setBackgroundColor(ContextCompat.getColor(context, R.color.jarvis_card_bg))
            }

            val tvTitle = TextView(this).apply {
                text = "🎯 Sherpa KWS Isolation Test"
                textSize = 16f
                setTextColor(ContextCompat.getColor(context, R.color.jarvis_cyan))
                setTypeface(null, android.graphics.Typeface.BOLD)
            }
            layout.addView(tvTitle)

            val tvSubtitle = TextView(this).apply {
                text = "Tests raw Sherpa-ONNX keyword spotter on Vivo V29 without WebSocket, SpeechRecognizer, or TTS."
                textSize = 11f
                setTextColor(ContextCompat.getColor(context, R.color.text_secondary))
                setPadding(0, 4, 0, 16)
            }
            layout.addView(tvSubtitle)

            val tvActivePhrase = TextView(this).apply {
                text = "Active Phrase: '${activeProf.phrase}' (Thr: ${activeProf.keywordsThreshold})"
                textSize = 13f
                setTextColor(ContextCompat.getColor(context, R.color.text_primary))
                setTypeface(null, android.graphics.Typeface.BOLD)
            }
            layout.addView(tvActivePhrase)

            val tvLiveRms = TextView(this).apply {
                text = "Audio: Initializing..."
                textSize = 12f
                setTextColor(ContextCompat.getColor(context, R.color.text_secondary))
                setPadding(0, 4, 0, 8)
            }
            layout.addView(tvLiveRms)

            val tvCounters = TextView(this).apply {
                text = "Attempts: 0 | Detections: 0 | Rate: 0.0%"
                textSize = 14f
                setTextColor(ContextCompat.getColor(context, R.color.jarvis_cyan))
                setTypeface(null, android.graphics.Typeface.BOLD)
                setPadding(0, 4, 0, 8)
            }
            layout.addView(tvCounters)

            val tvLog = TextView(this).apply {
                text = "Status: Listening for '${activeProf.phrase}'..."
                textSize = 12f
                setTextColor(ContextCompat.getColor(context, R.color.text_primary))
                setPadding(0, 4, 0, 16)
            }
            layout.addView(tvLog)

            val btnRow = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                weightSum = 3f
            }

            val btnAddAttempt = Button(this).apply {
                text = "🎙️ +1 Attempt"
                textSize = 11f
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }

            val btnToggleTest = Button(this).apply {
                text = "⏹ Stop"
                textSize = 11f
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }

            val btnReset = Button(this).apply {
                text = "↺ Reset"
                textSize = 11f
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }

            btnRow.addView(btnAddAttempt)
            btnRow.addView(btnToggleTest)
            btnRow.addView(btnReset)
            layout.addView(btnRow)

            fun updateUi() {
                val rate = if (attempts > 0) (detections.toFloat() / attempts * 100f) else 0f
                tvCounters.text = String.format(java.util.Locale.US, "Attempts: %d | Detections: %d | Rate: %.1f%%", attempts, detections, rate)
            }

            btnAddAttempt.setOnClickListener {
                attempts++
                updateUi()
            }

            btnReset.setOnClickListener {
                attempts = 0
                detections = 0
                updateUi()
                tvLog.text = "Status: Reset. Listening for '${activeProf.phrase}'..."
            }

            val dialog = AlertDialog.Builder(this)
                .setView(layout as View)
                .setPositiveButton("Close") { d, _ -> d?.dismiss() }
                .create()

            fun startListeningOnDetector() {
                detector?.startListening {
                    runOnUiThread {
                        detections++
                        if (detections > attempts) attempts = detections
                        updateUi()
                        val timeStr = java.text.SimpleDateFormat("HH:mm:ss.SSS", java.util.Locale.US).format(java.util.Date())
                        tvLog.text = "✓ DETECTED at $timeStr (Score: 1.00)"
                    }
                }
            }

            btnToggleTest.setOnClickListener {
                if (isTestRunning) {
                    detector?.stopListening()
                    isTestRunning = false
                    btnToggleTest.text = "▶ Start"
                    tvLog.text = "Status: Paused."
                } else {
                    startListeningOnDetector()
                    isTestRunning = true
                    btnToggleTest.text = "⏹ Stop"
                    tvLog.text = "Status: Listening for '${activeProf.phrase}'..."
                }
            }

            lifecycleScope.launch {
                repeatOnLifecycle(androidx.lifecycle.Lifecycle.State.STARTED) {
                    launch {
                        detector?.micDiagnostics?.collect { mic ->
                            tvLiveRms.text = String.format(java.util.Locale.US, "Audio: %s | RMS: %.4f | Peak: %.4f", mic.recordingState, mic.currentRms, mic.currentPeak)
                        }
                    }
                }
            }

            startListeningOnDetector()

            dialog.setOnDismissListener {
                detector?.stopListening()
                detector?.destroy()
                detector = null
                com.jarvis.client.voice.JarvisVoiceService.resumeStandby(this)
            }

            dialog.show()
        } catch (e: Exception) {
            Log.e(tag, "Failed to show KWS isolation dialog", e)
            Toast.makeText(this, "Error starting KWS isolation test: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun showSpeechRecognizerIsolationDialog() {
        try {
            com.jarvis.client.voice.JarvisVoiceService.pauseStandby(this)

            val sttManager = com.jarvis.client.voice.SpeechRecognitionManager(applicationContext)

            val layout = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(32, 24, 32, 24)
                setBackgroundColor(ContextCompat.getColor(context, R.color.jarvis_card_bg))
            }

            val tvTitle = TextView(this).apply {
                text = "🎙️ SpeechRecognizer Isolation Test"
                textSize = 16f
                setTextColor(ContextCompat.getColor(context, R.color.jarvis_cyan))
                setTypeface(null, android.graphics.Typeface.BOLD)
            }
            layout.addView(tvTitle)

            val tvSubtitle = TextView(this).apply {
                text = "Tests Android SpeechRecognizer directly (e.g. 'turn on the flashlight') without wake word or WebSocket."
                textSize = 11f
                setTextColor(ContextCompat.getColor(context, R.color.text_secondary))
                setPadding(0, 4, 0, 16)
            }
            layout.addView(tvSubtitle)

            val tvState = TextView(this).apply {
                text = "State: IDLE"
                textSize = 13f
                setTextColor(ContextCompat.getColor(context, R.color.text_primary))
                setTypeface(null, android.graphics.Typeface.BOLD)
                setPadding(0, 0, 0, 8)
            }
            layout.addView(tvState)

            val tvPartial = TextView(this).apply {
                text = "Partial: (none)"
                textSize = 12f
                setTextColor(ContextCompat.getColor(context, R.color.text_secondary))
                setPadding(0, 0, 0, 8)
            }
            layout.addView(tvPartial)

            val tvResult = TextView(this).apply {
                text = "Result: (none)"
                textSize = 14f
                setTextColor(ContextCompat.getColor(context, R.color.jarvis_cyan))
                setTypeface(null, android.graphics.Typeface.BOLD)
                setPadding(0, 0, 0, 16)
            }
            layout.addView(tvResult)

            val btnStartListening = Button(this).apply {
                text = "🎙️ Tap to Speak (e.g. 'turn on flashlight')"
                textSize = 13f
                setBackgroundColor(ContextCompat.getColor(context, R.color.jarvis_bubble_bg))
                setTextColor(ContextCompat.getColor(context, R.color.jarvis_cyan))
            }
            layout.addView(btnStartListening)

            btnStartListening.setOnClickListener {
                tvPartial.text = "Partial: Listening..."
                tvResult.text = "Result: (waiting)"
                sttManager.startListening()
            }

            val dialog = AlertDialog.Builder(this)
                .setView(layout as View)
                .setPositiveButton("Close") { d, _ -> d?.dismiss() }
                .create()

            lifecycleScope.launch {
                repeatOnLifecycle(androidx.lifecycle.Lifecycle.State.STARTED) {
                    launch {
                        sttManager.voiceState.collect { vs ->
                            tvState.text = "State: ${vs.name}"
                        }
                    }
                    launch {
                        sttManager.partialResults.collect { part ->
                            tvPartial.text = "Partial: '$part'"
                        }
                    }
                    launch {
                        sttManager.transcriptionResults.collect { res ->
                            tvResult.text = "Result: '$res'"
                        }
                    }
                    launch {
                        sttManager.errorEvents.collect { err ->
                            tvResult.text = "⚠️ Error: $err"
                        }
                    }
                }
            }

            dialog.setOnDismissListener {
                sttManager.destroy()
                com.jarvis.client.voice.JarvisVoiceService.resumeStandby(this)
            }

            dialog.show()
        } catch (e: Exception) {
            Log.e(tag, "Failed to show SpeechRecognizer isolation dialog", e)
            Toast.makeText(this, "Error starting STT isolation test: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }
}
