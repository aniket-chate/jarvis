# Capability 20: Accessibility

**Capability ID:** `20_accessibility`  
**Classification:** `FOUNDATION`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `system`  
**Primary Provider:** `provider.ui.accessible_payload`  
**Fallback Provider:** `provider.ui.standard`  

---

## 1. Capability Purpose & Scope
Provides accessible multi-modal interaction formats: transforms dense visual, tabular, and nested telemetry payloads into linear, descriptive text optimized for screen readers, and controls high-contrast HUD themes for visual accessibility.

---

## 2. Supported Operations
- `accessibility.format_payload`: Converts nested dictionaries, arrays, and metrics into clean, human-readable sentences formatted for screen readers (`aria-live: polite`).
- `accessibility.toggle_high_contrast`: Toggles high-contrast HUD visual mode and simplified text layout.

---

## 3. Required Context & World Model State
- **Raw Telemetry / Data Structure:** Arbitrary structured payload from execution or perception.
- **Client Display Mode:** Current high-contrast theme state.

---

## 4. Provider Implementation & Selection
- **Implementation:** `capabilities/providers/accessibility_provider.py` (`AccessibilityProvider`).
- **Fast-Path Latency:** Evaluates in **< 1.0 ms**.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED` (Read-only UI formatting and theme selection).
- **Verification Strategy:** `PAYLOAD_SCHEMA_VALIDATION` ensures formatted strings maintain 100% key-value fidelity with the underlying structured data without loss of diagnostic precision.
