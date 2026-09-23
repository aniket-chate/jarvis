# Capability 07: Learning & Adaptation

**Capability ID:** `07_learning_adaptation`  
**Classification:** `PARTIAL`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `learning`  
**Primary Provider:** `provider.learning.experience_store`  
**Fallback Provider:** N/A (Internal Core)  

---

## 1. Capability Purpose & Scope
Captures structured execution experience signals (input, plan, provider chosen, execution latency, verification outcome, user corrections) to adapt capability provider weights and refine conversational style over time without uncontrolled code self-modification.

---

## 2. Supported Operations
- `learning.record_experience`: Serializes completed workflow trajectories and user feedback.
- `learning.adjust_weights`: Adjusts provider priority scores based on empirical success rates.
- `learning.get_insights`: Analyzes failure clusters and repeated user corrections.

---

## 3. Required Context & World Model State
- **Execution Telemetry:** Latency, provider ID, retry count, and verification status from `ExecutionKernel`.
- **User Feedback:** Explicit corrections or implicit affirmations from subsequent turns.

---

## 4. Provider Implementation & Selection
- **Implementation:** `learning_system/experience_store.py` (`ExperienceStore`).
- **Persistence:** Local durable state in `memory/learning_state.json`.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED`.
- **Governed Adaptation:** Learning only modulates provider priority weights and prompt hints; it is strictly prohibited from mutating core safety rules or execution kernels.
