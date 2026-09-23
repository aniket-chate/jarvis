# Capability 12: OCR & Document Intelligence

**Capability ID:** `12_ocr_documents`  
**Classification:** `EXISTING`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `vision`  
**Primary Provider:** `provider.vision.ocr` (wrapping `winsdk.windows.media.ocr.OcrEngine`)  
**Fallback Provider:** `provider.vision.tesseract`  

---

## 1. Capability Purpose & Scope
Extracts printed, handwritten, scanned, and photographed text, tables, and key-value pairs from documents, receipts, whiteboard photos, and screen regions using native Windows 10/11 offline OCR (`winsdk.windows.media.ocr.OcrEngine`). Requires zero external cloud calls.

---

## 2. Supported Operations
- `vision.ocr`: Extracts linear and multi-line text from images and screenshots with calibrated confidence.
- `vision.scan_document`: Analyzes scanned documents, receipts, and forms, optionally committing extracted text to the Personal Knowledge Base.
- `vision.extract_table`: Identifies tabular structures, columns, and rows from document images.

---

## 3. Required Context & World Model State
- **Document Source:** File path or byte buffer of scanned image.
- **Language Profile:** Native Windows OCR language dictionary (e.g. `en-US`, `mr-IN`).

---

## 4. Provider Implementation & Selection
- **Implementation:** `capabilities/providers/vision_provider.py` (`VisionOCRProvider`), wrapping `agents/vision_ocr_agent.py`.
- **Fast-Path Latency:** Native Windows OCR executes in **40 ms - 120 ms**.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED` (Read-only perception).
- **Verification Strategy:** `TEXT_EXTRACTION_MATCH` verifies character counts and line counts.
- **Uncertainty Calibration:** When confidence < 0.60, outputs probabilistic phrasing ("I may have read this as '...'") to avoid hallucinating false certainty.
