# JARVIS Hierarchical Classification Engine Specification

## 1. Architectural Role & Invariants
The **Hierarchical Classification Engine** is responsible exclusively for:
1. **Semantic Understanding**: Decomposing natural language utterances into domain and capability candidates.
2. **Top-K Candidate Generation**: Producing confidence-scored candidate capabilities.
3. **Ambiguity & Unknown Intent Detection**: Recognizing out-of-distribution queries or queries lacking critical parameters.

### Critical Invariant: Strict Separation of Concerns
```
User Request
     ↓
Hierarchical Classifier   → Responsibility: UNDERSTAND & CANDIDATE-GENERATE
     ↓
Candidate Capabilities (Top-K)
     ↓
World Model / Context / Memory / Capability Metadata
     ↓
Contextual Reranker       → Responsibility: CONTEXTUAL DISAMBIGUATION & RERANKING
     ↓
Planner Engine            → Responsibility: DECIDE EXECUTION STRATEGY & TASK DAG
     ↓
Policy Kernel (Safety)    → Responsibility: DECIDE WHETHER ACTION IS ALLOWED
     ↓
Execution Kernel          → Responsibility: DISPATCH TO PROVIDERS & RECORD ACTIONS
     ↓
Verification Kernel       → Responsibility: DETERMINE WHETHER IT ACTUALLY WORKED
```
- The Classifier **MUST NEVER** directly trigger side effects or execute capabilities.
- The Planner **MUST NEVER** bypass the Policy Kernel.
- The Verification Kernel **MUST NEVER** accept self-reported provider success.

---

## 2. Two-Stage Hierarchical Classification Pipeline

### Stage 1: Domain Classification
Given input text $x$, Stage 1 maps $x$ into one of the 8 canonical JARVIS capability domains:
1. `PERCEPTION_MULTIMODAL` (Capabilities 1–4, 30)
2. `MEMORY_COGNITION` (Capabilities 5–10)
3. `DESKTOP_OS_CONTROL` (Capabilities 11–17, 33–35)
4. `PRODUCTIVITY_COMMUNICATION` (Capabilities 18–21)
5. `SMART_HOME_IOT_PHYSICAL` (Capabilities 22, 45)
6. `MOBILE_ANDROID` (Capabilities 23–29)
7. `RESEARCH_KNOWLEDGE_ANALYTICS` (Capabilities 31–32, 36–38, 46–47)
8. `AGENCY_GOVERNANCE_EVOLUTION` (Capabilities 39–44, 48–50)

### Stage 2: Fine-Grained Capability Classification
Within the top predicted domains, Stage 2 scores all candidate capabilities $c \in \{1, \dots, 50\}$.
Output is a structured candidate distribution:
```json
{
  "domain": "DESKTOP_OS_CONTROL",
  "domain_confidence": 0.942,
  "candidates": [
    {"capability_id": "21_desktop_os", "score": 0.915, "operation": "os.volume_control"},
    {"capability_id": "11_desktop_os", "score": 0.420, "operation": "os.window_management"}
  ],
  "confidence": 0.915,
  "unknown": false,
  "requires_context": false,
  "requires_clarification": false
}
```

---

## 3. Ambiguity & Unknown Detection Strategy

1. **Unknown Detection Threshold**:
   - If $\max_c P(c \mid x) < \tau_{\text{unknown}}$ (configurable default: $0.45$), the classifier sets `unknown: true`.
   - The Cognitive Core routes `unknown: true` to a graceful fallback: natural language conversational clarification or web research search, rather than guessing a destructive tool.

2. **Ambiguity & Disambiguation Threshold**:
   - If the margin between top-1 and top-2 candidates is small:
     $P(\text{top-1}) - P(\text{top-2}) < \Delta_{\text{ambiguity}}$ (configurable default: $0.15$),
     the classifier marks `requires_context: true` or `requires_clarification: true`.
   - The Contextual Reranker uses the `WorldModel` (active window, foreground app) and recent `UnifiedMemory` referents to break the tie.

---

## 4. Multi-Intent Decomposition Strategy

When a user request contains compound imperatives connected by conjunctions ("and", "then", "after that", "also"):
1. Utterance segmentation splits into clauses.
2. Each clause is classified independently through the Hierarchical Classifier.
3. If multiple capabilities are generated with high confidence, the system yields a multi-intent DAG:
   - Example: *"Check disk space and then summarize error log"*
     - Clause 1: `25_shell_sysadmin` (`shell.allowlisted_diagnostics`)
     - Clause 2: `35_knowledge_synthesis` (`knowledge_synthesis.summarize`)
   - Planner constructs a 2-step execution plan linked by dependency data-flow.

---

## 5. Model Architecture & Operational Requirements

- **Model Engine**: TF-IDF + Calibrated Linear Support Vector Classifier (SGDClassifier) / Logistic Regression with Platt scaling.
- **Latency Target**: Sub-5ms CPU inference.
- **Zero Heavy Cloud Dependency**: Fully operational offline without internet connection or external API tokens.
- **Provider Replaceability**: Pluggable `BaseClassifier` interface allowing seamless upgrade to local ONNX transformer embeddings or quantized sentence-transformers without altering downstream routing logic.
