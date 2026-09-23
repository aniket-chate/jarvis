# Capability 16: Voice Intelligence

**Capability ID:** `16_voice_intelligence`  
**Classification:** `PARTIAL`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `voice`  
**Primary Provider:** `provider.voice.piper_local` (wrapping `voice/tts_piper.py` & Piper CPU models)  
**Fallback Provider:** `provider.voice.android_tts`  

---

## 1. Capability Purpose & Scope
Provides low-latency neural speech synthesis and streaming audio playback across distinct acoustic personas (Jarvis, Friday, Ultron, Omi). Operates 100% locally on CPU via ONNX neural models with zero VRAM footprint, with fallback audio generation for CI/test headless environments.

---

## 2. Supported Operations
- `voice.synthesize`: Synthesizes arbitrary text into in-memory PCM WAV byte buffers formatted for the active persona's voice model.
- `voice.stream`: Segments synthesized speech into low-latency chunked packets suitable for WebSocket transmission to client endpoints.
- `voice.select_profile`: Dynamically binds acoustic voice profiles (e.g. `en_GB-alan-medium`, `en_US-amy-medium`, `en_US-lessac-medium`).

---

## 3. Required Context & World Model State
- **Active Persona:** Target voice persona from `config.settings.settings`.
- **Acoustic Models:** Piper ONNX models stored under `models/piper/`.

---

## 4. Provider Implementation & Selection
- **Implementation:** `capabilities/providers/voice_provider.py` (`VoiceIntelligenceProvider`), wrapping `voice/tts_piper.py` (`PiperTTSEngine`).
- **Fast-Path Latency:** Speech synthesis completes in **60 ms - 180 ms**; streaming packetization in **< 5 ms**.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED` (Read-only voice generation).
- **Verification Strategy:** `AUDIO_BUFFER_VERIFICATION` validates RIFF WAV headers, sample rates (22,050 Hz), and non-zero byte payloads.
- **Provider Replaceability:** Fully replaceable; future providers (e.g. ElevenLabs, Android TTS) adhere to the same contract interface.
