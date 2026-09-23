# Capability 13: Audio Perception

**Capability ID:** `13_audio_perception`  
**Classification:** `PARTIAL`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `perception`  
**Primary Provider:** `provider.audio.whisper_local` (wrapping `voice/asr.py` & CPU Whisper)  
**Fallback Provider:** `provider.audio.android_mic`  

---

## 1. Capability Purpose & Scope
Captures host microphone audio and Android client streaming buffers, performs local CPU Whisper speech recognition (with Marathi, English, and code-switching language hints), executes Voice Activity Detection (VAD) distinguishing speech from ambient noise, and detects user barge-in interruptions in real time.

---

## 2. Supported Operations
- `audio.capture`: Ingests raw audio frames from system microphone or mobile client.
- `audio.transcribe`: Transcribes PCM audio buffers using local CPU Whisper with configurable language hints (English, Marathi `mr`).
- `audio.detect_speech`: VAD analysis assessing RMS energy against speech thresholds.
- `audio.barge_in`: Detects user speech energy while the assistant is actively speaking to immediately abort TTS playback.

---

## 3. Required Context & World Model State
- **Audio Device State:** Host microphone connectivity and input channel gain.
- **Synthesizer State:** `tts_active` flag indicating whether assistant speech is playing.

---

## 4. Provider Implementation & Selection
- **Implementation:** `capabilities/providers/audio_provider.py` (`AudioPerceptionProvider`), wrapping `voice/asr.py` (`ASREngine`).
- **Fast-Path Latency:** VAD and barge-in evaluate in **< 5 ms**; local Whisper transcription completes in **150 ms - 350 ms**.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED` (Read-only audio perception). Audio buffers are processed purely in-memory; raw audio is never sent to external third-party cloud APIs.
- **Verification Strategy:** `AUDIO_STREAM_CONFIRMATION` verifies RMS floor, silence suppression, and language confidence.
- **Edge Cases Handled:** Silence floor suppression, microphone disconnects, overlapping speech, Marathi-English code switching.
