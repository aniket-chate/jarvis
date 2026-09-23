# JARVIS Long-Term Cognitive Architecture Specification

**Document Version:** 4.0-COGNITIVE-RUNTIME  
**Architect:** Aniket & Antigravity IDE  
**Status:** Approved for Phased Architecture Implementation  

---

## 1. System Architecture

```
                          JARVIS
                             │
            ┌────────────────┴────────────────┐
            │                                 │
      EXPERIENCE                       AUTONOMOUS RUNTIME
       INTERFACES                         / AGENCY
            │                                 │
            └───────────────┬─────────────────┘
                            ▼
                     PERCEPTION FABRIC
                            │
                            ▼
                       EVENT FABRIC
                            │
                            ▼
                     COGNITIVE CORE
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
       MEMORY         CAPABILITY          LEARNING
                          INTELLIGENCE
                              │
                              ▼
                       POLICY / SAFETY
                              │
                              ▼
                          EXECUTION
                              │
                              ▼
                           ACTIONS
                              │
                              ▼
                     OBSERVATION /
                       VERIFICATION
                              │
                              ▼
                       WORLD CHANGES
                              │
                              ▼
                         OBSERVATION
                              │
                              └──────────► EVENT FABRIC
```

### Cognitive Core Structure
```
Cognitive Core
│
├── Understanding
├── World Model
├── Reasoning
├── Goal Management
└── Planning
```

---

## 2. Primary Design Principle

JARVIS is **NOT**:
$$\text{User Message} \longrightarrow \text{Classifier} \longrightarrow \text{Fixed Agent} \longrightarrow \text{Tool} \longrightarrow \text{Response}$$

JARVIS **IS**:
$$\begin{aligned}
\text{Perception} &\longrightarrow \text{Event} \longrightarrow \text{Understanding} \longrightarrow \text{World Model} \longrightarrow \text{Reasoning} \\
&\longrightarrow \text{Goal} \longrightarrow \text{Planning} \longrightarrow \text{Capability Selection} \longrightarrow \text{Policy/Safety} \\
&\longrightarrow \text{Execution} \longrightarrow \text{Action} \longrightarrow \text{World Change} \longrightarrow \text{Observation} \\
&\longrightarrow \text{Verification} \longrightarrow \text{Memory/Learning} \longrightarrow \text{Event Fabric} \longrightarrow \text{Continued Cognition}
\end{aligned}$$

---

## 3. Subsystem Specifications

### 1. Experience Interfaces
Boundary converting external modalities (Voice UI, Web UI, Desktop HUD, Mobile, external APIs) into normalized `PerceptionEvent` objects and streaming outgoing responses. Zero business logic inside interfaces.

### 2. Autonomous Runtime / Agency
First-class subsystem operating independently of immediate user prompts. Supports scheduled goals, environmental triggers, background condition monitoring, and proactive workflows. All autonomous behavior generates goals processed through the exact same Cognitive Core, Policy, Execution, and Verification pipeline.

### 3. Perception Fabric
Normalizes raw multi-sensory inputs (Speech, Vision, OCR, Desktop Window, Browser State, System Telemetry, Application Events, Network Events) into typed `PerceptionEvent` payloads.

### 4. Event Fabric
The nervous system of JARVIS. Strong correlation across `event_id`, `request_id`, `parent_event_id`, `timestamp`, `priority`, and `cancellation_token`. Decoupled from FIFO message queues.

### 5. Cognitive Core
- **Understanding:** Resolves user intent, entities, references, ambiguity, constraints, urgency, and pronoun bindings.
- **World Model:** Real-time queryable representation of User, Devices, Applications, Windows, Browser Tabs, URLs, Files, Processes, and Environment with Just-In-Time (JIT) reality probes.
- **Reasoning:** Derives logical deductions, analyzes constraints, and evaluates trade-offs.
- **Goal Management:** Manages hierarchical goals, subgoals, priorities, dependencies, and completion criteria.
- **Planning:** Generates dependency DAG plans with branching, retries, timeouts, and fallback strategies.

### 6. Memory System (7 Explicit Tiers)
1. **Working Memory:** Active conversation and immediate cognitive state.
2. **Episodic Memory:** Immutable action ledger of verified physical events, outcomes, and decisions.
3. **Semantic Memory:** Stable knowledge base, facts, and embeddings.
4. **Procedural Memory:** Executable operational skill recipes and tool contracts.
5. **User Memory:** Persistent Aniket profile, habits, relationships, preferences.
6. **World Knowledge:** External and general knowledge retrieval (Tavily, Wikipedia).
7. **Experience Memory:** Reinforcement learning Q-tables and learned heuristic rules.

### 7. Capability Intelligence (`CAPABILITY -> PROVIDERS`)
Decouples intent from specific agents. Capabilities (e.g. `browser.navigate`, `file.read`, `code.execute`) are resolved dynamically to the best available Provider based on context, reliability, latency, and permissions.

### 8. Model Routing Abstraction
Pluggable model provider interface (Fast Reactive, Reasoning, Coding, Vision, Local, Cloud) allowing seamless replacement of models without modifying the Cognitive Core.

### 9. Policy & Safety Kernel
Mandatory system invariant. Evaluates risk, permissions, Two-Gate user confirmation (60s TTL), path traversal defense, and arbitrary shell allowlisting before any action can fire.

### 10. Execution Kernel
Durable workflow engine managing async execution, parallelism, deadline budgets, retries, cancellation tokens, pause/resume, and checkpointing.

### 11. Action Fabric
Domain action executors (OS, Chrome CDP 9222, Filesystem, Git, Code Sandbox, Comms) receiving structured parameters from the Execution Kernel.

### 12. Observation & Verification
Validates physical ground truth ("Did the world actually change?") by comparing expected state against actual state via CDP `/json/list`, `Path.exists()`, Git HEAD, and Win32 window coordinates.

### 13. Experience & Learning
Decoupled feedback pipeline: Outcome -> Experience -> Evaluation -> Policy Improvement, closing the loop back into the World Model and Memory.
