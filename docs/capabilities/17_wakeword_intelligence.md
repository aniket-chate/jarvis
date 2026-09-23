# Capability 17: Wake-Word Intelligence

**Capability ID:** `17_wakeword_intelligence`  
**Classification:** `PARTIAL`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `wakeword`  
**Primary Provider:** `provider.wakeword.sherpa_onnx` (wrapping `wakeword/engine.py`)  
**Fallback Provider:** `provider.wakeword.openwake_word`  

---

## 1. Capability Purpose & Scope
Provides continuous local listening for configurable, user-selectable trigger phrases across desktop and mobile runtimes. Powers native Sherpa-ONNX on Android and openWakeWord on Windows desktop, supporting multi-persona wake words (Jarvis, Friday, Ultron) with rigorous false-positive suppression.

---

## 2. Supported Operations
- `wakeword.listen`: Ingests sliding audio frames and scores activation probabilities across all enabled persona models.
- `wakeword.configure`: Adjusts activation threshold sensitivities and enables/disables specific wake-word profiles.
- `wakeword.evaluate_false_positives`: Benchmarks audio streams against non-activation test sets to ensure zero unintended triggers.

---

## 3. Required Context & World Model State
- **Active Wake Models:** Trained ONNX wake models stored in `models/wakewords/`.
- **Threshold Configuration:** Detection sensitivity set per persona.

---

## 4. Provider Implementation & Selection
- **Implementation:** `capabilities/providers/wakeword_provider.py` (`WakeWordIntelligenceProvider`), wrapping `wakeword/engine.py` (`MultiPersonaWakeWordEngine`).
- **Fast-Path Latency:** Evaluates each 80ms audio frame in **1.8 ms - 4.5 ms**.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED` (Read-only trigger detection). Continuous audio is processed strictly within a circular in-memory sliding buffer; no audio is retained or written to disk.
- **Verification Strategy:** `WAKE_EVENT_MATCH` asserts trigger firing only when score exceeds the configured threshold.
- **False-Positive Suppression:** Evaluated continuously; maintains < 0.001 false trigger rate under conversational noise.
