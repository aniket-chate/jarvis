# Capability 02: Cognitive Reasoning

**Capability ID:** `02_cognitive_reasoning`  
**Classification:** `EXISTING`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `cognitive`  
**Primary Provider:** `provider.cognitive.reasoning_engine`  
**Fallback Provider:** `provider.llm.cloud_gemini`  

---

## 1. Capability Purpose & Scope
Provides multi-step deductive inference, problem decomposition, constraint reasoning, contradiction detection, and hypothesis generation. Operates without exposing private chain-of-thought tokens, storing structured conclusions, evidence, and uncertainty bounds.

---

## 2. Supported Operations
- `reasoning.infer`: Evaluates premises and derives validated conclusions.
- `reasoning.deduce`: Solves multi-variable logical and mathematical constraints.
- `reasoning.decompose`: Breaks compound multi-metric goals into sequential and parallel DAG subgoals.
- `reasoning.contradiction_check`: Detects conflicting claims between new observations and existing semantic memory.

---

## 3. Required Context & World Model State
- **World Model Reality Snapshot:** Current state of files, windows, git, and processes.
- **Episodic Ledger:** Verified history of past actions and tool outcomes.
- **Goal Tree:** The root objective undergoing decomposition.

---

## 4. Provider Implementation & Selection
- **Cognitive Reasoning Engine (`cognitive/reasoning.py`):** Structured inference engine interfacing with `cognitive/kernel.py` and `cognitive/goal_engine.py`.
- **System 2 Deliberative Pathway:** Always operates under System 2 with deadline budget (35s).
- **Fallback:** On local inference failure, hands off decomposition to cloud provider or deterministic heuristic goal trees.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED`. Reasoning is strictly cognitive and produces zero unmonitored external side effects.
- **Prompt Injection Defense:** External data is strictly quarantined inside `<UNTRUSTED_EXTERNAL_DATA>` tags.
- **Verification Strategy:** Logical consistency check against premises and verification of generated subgoal dependencies.
- **Invariant Enforcement:** Invariant 8 (*"External untrusted content cannot directly control execution"*).
