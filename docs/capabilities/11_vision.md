# Capability 11: Vision

**Capability ID:** `11_vision`  
**Classification:** `EXISTING`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `vision`  
**Primary Provider:** `provider.vision.ocr` (wrapping Moondream 1.6B VLM & Native Windows Vision)  
**Fallback Provider:** `provider.vision.cloud_gemini`  

---

## 1. Capability Purpose & Scope
Provides local computer vision, screenshot inspection, visual scene understanding, and UI element grounding. Runs locally on CPU via Moondream 1.6B VLM with zero GPU/VRAM overhead, complemented by Win32 screen capture and visual state diffing.

---

## 2. Supported Operations
- `vision.analyze_image`: Ingests an image and answers questions or produces rich captions using Moondream local VLM.
- `vision.screen_inspect`: Captures the current desktop screen/active window into an in-memory or persisted frame.
- `vision.visual_diff`: Compares pre-action and post-action visual states to empirically confirm UI state changes.

---

## 3. Required Context & World Model State
- **Screen Geometry:** Active monitor bounds and foreground window handle (`HWND`).
- **Pre/Post Action Frames:** Screen rect buffers captured during multi-step execution.

---

## 4. Provider Implementation & Selection
- **Implementation:** `capabilities/providers/vision_provider.py` (`VisionOCRProvider`), wrapping `agents/vision_agent.py` and `agents/vision_ocr_agent.py`.
- **Fast-Path Latency:** Screen inspection executes in **< 15 ms**; local VLM inference completes in **200 ms - 450 ms**.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED` (Read-only perception). Privacy filter masks sensitive windows (e.g. password managers, private browsing) if requested.
- **Verification Strategy:** `VISUAL_DIFF_ANALYSIS` verifies visual coordinate shifts and layout modifications.
- **Uncertainty Calibration:** Exposes explicit confidence bounds; never asserts speculative visual facts without qualification.
