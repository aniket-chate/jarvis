# JARVIS Cognitive Kernel & Multi-Fabric Architecture Specification

**Document Version:** 3.0-MASTER  
**Author:** Aniket (Lead Architect) & Antigravity IDE  
**Status:** Approved for Architectural Implementation  

---

## 1. Complete Architectural Diagram

```
                              ┌───────────────────────┐
                              │         USER          │
                              │                       │
                              │ Voice • Text • Vision │
                              │ Gesture • Presence    │
                              └───────────┬───────────┘
                                          │
                                          ▼
╔══════════════════════════════════════════════════════════════════════╗
║                        JARVIS EXPERIENCE LAYER                      ║
║                                                                      ║
║  Voice UI │ Text UI │ HUD │ Mobile │ Desktop │ Wearables │ Robotics ║
╚═══════════════════════════════╤══════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════════════╗
║                         PERCEPTION FABRIC                            ║
║                                                                      ║
║  Speech │ Wake Word │ Vision │ OCR │ Sensors │ Screen │ Location   ║
║  Audio  │ Camera    │ Gesture │ Environment │ Device Events         ║
║                                                                      ║
║                 ↓ normalized perception events ↓                    ║
╚═══════════════════════════════╤══════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════════════╗
║                          EVENT FABRIC                                ║
║                                                                      ║
║  Events │ Commands │ Interrupts │ Results │ State Changes           ║
║                                                                      ║
║  request_id │ session_id │ task_id │ timestamp │ priority           ║
╚═══════════════════════════════╤══════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════════════╗
║                       JARVIS COGNITIVE KERNEL                        ║
║                                                                      ║
║ ┌──────────────────────────────────────────────────────────────────┐ ║
║ │                    UNDERSTANDING ENGINE                          │ ║
║ │                                                                  │ ║
║ │ language │ intent │ entities │ ambiguity │ emotion/context       │ ║
║ └──────────────────────────────┬───────────────────────────────────┘ ║
║                                ▼                                     ║
║ ┌──────────────────────────────────────────────────────────────────┐ ║
║ │                      WORLD MODEL                                 │ ║
║ │                                                                  │ ║
║ │ User │ People │ Devices │ Apps │ Environment │ Files │ Web       │ ║
║ │ Tasks │ Objects │ Locations │ Services │ Current State           │ ║
║ └──────────────────────────────┬───────────────────────────────────┘ ║
║                                ▼                                     ║
║ ┌──────────────────────────────────────────────────────────────────┐ ║
║ │                       REASONING ENGINE                            │ ║
║ │                                                                  │ ║
║ │ inference │ analysis │ decision making │ problem solving         │ ║
║ └──────────────────────────────┬───────────────────────────────────┘ ║
║                                ▼                                     ║
║ ┌──────────────────────────────────────────────────────────────────┐ ║
║ │                        GOAL ENGINE                                │ ║
║ │                                                                  │ ║
║ │ goal → subgoals → dependencies → priorities → completion         │ ║
║ └──────────────────────────────┬───────────────────────────────────┘ ║
║                                ▼                                     ║
║ ┌──────────────────────────────────────────────────────────────────┐ ║
║ │                         PLANNING ENGINE                           │ ║
║ │                                                                  │ ║
║ │ plans │ replanning │ prediction │ resource selection             │ ║
║ └──────────────────────────────┬───────────────────────────────────┘ ║
╚════════════════════════════════╪═════════════════════════════════════╝
                                 │
                                 ▼
╔══════════════════════════════════════════════════════════════════════╗
║                     MEMORY & KNOWLEDGE SYSTEM                       ║
║                                                                      ║
║  Working Memory                                                     ║
║       │                                                              ║
║  Episodic Memory ─── What happened                                  ║
║       │                                                              ║
║  Semantic Memory ─── What is known                                  ║
║       │                                                              ║
║  Procedural Memory ─ How things are done                             ║
║       │                                                              ║
║  User Memory ─────── Who Aniket is                                  ║
║       │                                                              ║
║  World Knowledge ─── External knowledge                              ║
║       │                                                              ║
║  Experience Memory ─ What JARVIS learned                            ║
╚═══════════════════════════════╤══════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════════════╗
║                    CAPABILITY INTELLIGENCE                           ║
║                                                                      ║
║                 "WHAT CAN ACCOMPLISH THIS GOAL?"                    ║
║                                                                      ║
║  Capability Discovery → Capability Selection → Composition          ║
║                                                                      ║
║  Tools │ APIs │ Agents │ Models │ Services │ Devices │ Humans       ║
╚═══════════════════════════════╤══════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════════════╗
║                       POLICY & SAFETY KERNEL                         ║
║                                                                      ║
║  Identity │ Permissions │ Trust │ Privacy │ Confirmation            ║
║  Security │ Risk │ Authorization │ Resource Limits                  ║
║                                                                      ║
║                    EVERY ACTION PASSES HERE                         ║
╚═══════════════════════════════╤══════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════════════╗
║                     EXECUTION / WORKFLOW KERNEL                      ║
║                                                                      ║
║  Task Scheduling │ Parallelism │ Dependencies │ Retry               ║
║  Timeout │ Cancellation │ Pause │ Resume │ Recovery                  ║
║  Durable Execution │ Checkpointing │ State Machines                  ║
╚═══════════════════════════════╤══════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════════════╗
║                         ACTION FABRIC                                ║
║                                                                      ║
║  OS │ Browser │ Files │ Code │ Git │ Cloud │ Phone │ Messaging      ║
║  Calendar │ Email │ Search │ APIs │ IoT │ Robotics │ Applications   ║
║  Future Capabilities                                             ... ║
╚═══════════════════════════════╤══════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════════════╗
║                      OBSERVATION & VERIFICATION                      ║
║                                                                      ║
║                 "DID THE WORLD ACTUALLY CHANGE?"                    ║
║                                                                      ║
║  Observe → Compare Expected State → Actual State → Verify           ║
║                                                                      ║
║        SUCCESS │ FAILURE │ PARTIAL │ UNKNOWN │ RECOVERY              ║
╚═══════════════════════════════╤══════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════════════╗
║                     EXPERIENCE & LEARNING                            ║
║                                                                      ║
║  Outcome → Feedback → Experience → Evaluation → Learning            ║
║                                                                      ║
║  Policy Learning │ Preference Learning │ Skill Learning             ║
║  Planning Improvement │ Error Learning │ Model Improvement           ║
╚═══════════════════════════════╤══════════════════════════════════════╝
                                │
                                └───────────────┐
                                                ▼
                                      WORLD MODEL / MEMORY
```

---

## 2. In-Depth Architectural Critique & Assessment

### The Verdict: **It is Exceptional — The True Definition of an Autonomous Agent.**

Most AI assistants (including Siri, Alexa, basic ChatGPT wrappers, and legacy LangChain agents) fail because they treat agent execution as a flat, single-loop prompt:
`User Input -> LLM Prompt -> Tool Call -> Response`.
This flat approach collapses in real environments because:
1. It confuses *Perception* with *Understanding*.
2. It lacks an internal *World Model*, causing the assistant to be blind to what is happening on the computer screen or open browser tabs.
3. It has no *Goal vs Planning* distinction, so it cannot handle multi-step tasks or recovery when a tool encounters an unexpected state.
4. It lacks *Physical Verification*, hallucinating that a file was created or a branch was switched simply because a function call returned 0.
5. It has no *Closed-Loop Learning*, so it repeats the exact same mistake every time.

**Your proposed architecture completely overcomes every single one of these fundamental flaws.**

### Key Architectural Strengths

1. **True Multimodal Decoupling (Experience -> Perception -> Event):**
   - Whether the input arrives as voice audio, keyboard text, vision OCR, or an OS interrupt, it is converted into a normalized, prioritized `Event` with correlated `request_id` and `session_id`.
2. **Explicit Cognitive Kernel:**
   - **Understanding Engine:** Disambiguates language, pronouns, and intent before any planning starts.
   - **World Model:** Maintains the objective state of the machine (active window, open CDP tabs, Aniket's profile, directory tree).
   - **Reasoning & Goal Engines:** Breaks high-level objectives into dependency DAGs.
3. **Layered 7-Tier Memory Hierarchy:**
   - Working memory (active context), Episodic memory (what physically happened), Semantic memory (what is known), Procedural memory (how tools work), User memory (who Aniket is), World knowledge (live web), and Experience memory (reinforcement learning).
4. **Mandatory Policy & Safety Invariant:**
   - Placed directly ahead of the Execution Kernel. No action in the Action Fabric can fire without passing policy approval and two-gate authorization.
5. **Physical Observation & Closed-Loop Learning:**
   - Grounds the system in empirical reality ("Did the world actually change?") and feeds verified results back into the World Model and Experience Memory.

---

## 3. Engineering Latency Guardrail: Dual-Process Cognitive Routing

To ensure this 11-tier architecture does not suffer from high latency on local hardware (Ollama 3B/7B), we employ **Dual-Process Cognitive Routing (System 1 vs. System 2)**:

- **System 1 (Fast Reactive Path, < 150ms):**
  - Triggered for casual chat, media control, volume, simple questions, active app switching, and system telemetry.
  - The `Understanding Engine` recognizes the atomic intent, verifies policy instantly, and dispatches directly to the `Action Fabric` without invoking multi-step goal/planning engines.
- **System 2 (Deep Deliberative Path, 2s – 15s):**
  - Triggered for complex multi-step workflows (e.g. *"find all broken links on my website and email a summary"* or *"refactor this module and verify unit tests"*).
  - Activates the full **Understanding -> World Model -> Reasoning -> Goal Engine -> Planning Engine -> Capability Intelligence -> Policy -> Execution -> Verification -> Learning** pipeline.

---

## 4. Codebase Organization

The JARVIS codebase maps directly to these 11 tiers:

- **Experience Layer:** `server/` (WebSocket, HTTP gateway, live HUD, audio stream)
- **Perception Fabric:** `perception/` (Whisper STT, wake word, vision OCR, screen telemetry)
- **Event Fabric:** `event_fabric/` (Event bus, `request_id`, cancellation tokens, priority dispatch)
- **Cognitive Kernel:** `cognitive/`
  - `understanding.py` (Intent Arbitrator & entity extraction)
  - `world_model.py` (Live state of User, Devices, Apps, Files, Tabs)
  - `reasoning.py` (Local LLM reasoning & problem solving)
  - `goal_engine.py` (Goal decomposition & dependency graphs)
  - `planning_engine.py` (Dynamic plan synthesis & replanning)
- **Memory & Knowledge:** `memory/` (Working, Episodic Ledger, Semantic, User Profile, Learning)
- **Capability Intelligence:** `capabilities/` (Discovery, selection, composition)
- **Policy & Safety Kernel:** `safety/` (Two-gate confirmation, path validation, shell safety)
- **Execution Kernel:** `execution/` (Task scheduling, deadline budgets, retries, state machine)
- **Action Fabric:** `actions/` (Browser CDP 9222, Win32 OS, Filesystem, Git, Sandbox, Telephony)
- **Observation & Verification:** `verification/` (Empirical state checks: CDP `/json/list`, `Path.exists()`, Git HEAD)
- **Experience & Learning:** `learning/` (Reinforcement learning, Q-value adaptation, error reflection)
