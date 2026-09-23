# Capability 05: Meta-Cognition

**Capability ID:** `05_meta_cognition`  
**Classification:** `PARTIAL`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `cognitive`  
**Primary Provider:** `provider.cognitive.meta_evaluator`  
**Fallback Provider:** `provider.cognitive.reasoning_engine`  

---

## 1. Capability Purpose & Scope
Provides internal self-monitoring, confidence calibration, missing information detection, and plan adequacy assessment. Prevents overconfident hallucinations and stops execution when required parameters or context are missing.

---

## 2. Supported Operations
- `meta.estimate_confidence`: Calculates calibrated confidence scores (0.0 to 1.0) for intent interpretations.
- `meta.detect_uncertainty`: Identifies underspecified entity references and ambiguous requests.
- `meta.plan_adequacy`: Evaluates whether a proposed CognitivePlan satisfies all goal preconditions.

---

## 3. Required Context & World Model State
- **Understood Intent:** The candidate `CognitiveIntent` produced by the Understanding Engine.
- **Available Providers:** Registered capabilities in `CapabilityIntelligence`.

---

## 4. Provider Implementation & Selection
- **Implementation:** Integrated into `cognitive/understanding.py` and `cognitive/kernel.py`.
- **Clarification Trigger:** When confidence falls below 0.60 or `is_ambiguous=True`, the Cognitive Kernel returns an interactive clarification request without invoking side-effect execution.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED`.
- **Verification Strategy:** Confidence calibration checks against ambiguous test sets.
- **Invariant Enforcement:** Halts planning when certainty is insufficient.
