# JARVIS Architectural Rethink & Modernization Blueprint

**Document Version:** 2.0-FINAL  
**Status:** Saved & Finalized for Architecture Review (Planning Phase)  
**Authors:** Aniket (Lead / System Architect) & Antigravity IDE  
**Source Evidence:** 50-Exchange Live Real-Environment Test Suite (September 14, 2026)

---

## 1. Executive Summary & Problem Formulation

During the 50-Exchange Live End-to-End Stress Test executed across Real Google Chrome (CDP Port 9222), Ollama (Port 11434), and the FastAPI Gateway (Port 8000), JARVIS achieved:
- **PASS:** 23 / 50 (46.0%)
- **PARTIAL:** 6 / 50 (12.0%)
- **FAIL:** 21 / 50 (42.0%)

### Empirical Root Causes Uncovered:
1. **Asynchronous FIFO Queue Desynchronization (The Primary Bottleneck):**  
   Long-running browser automation actions (60–75s) blocked the WebSocket stream without per-request correlation. Subsequent user queries received delayed output from earlier turns (e.g., Turn 08's YouTube search leaked into Turn 09, Turn 09's media pause leaked into Turn 19's local file search).
2. **Brittle Keyword-First & Regex Routing:**  
   Monolithic `planner.py` regexes evaluated keywords without semantic understanding. Harmless reminders (*"set a reminder in 90 seconds to check on this test"*) were intercepted by shell safety as arbitrary scripts; factorial code generation was intercepted as RAM telemetry; pronoun execution (*"run it with 5"*) was intercepted by the application launcher attempting to open an executable named `"It"`.
3. **Context & Working Memory Void:**  
   Pronouns (*"it"*, *"that"*, *"that tab"*) lacked an active Context State Machine. Code context was lost between turns (Turn 33 reviewed Python division; Turn 34 hallucinated quadratic equations for $b=0$). Persona state (*"Friday"*) reset to *"Jarvis"* on LLM inference boundaries.
4. **Episodic Amnesia:**  
   No structured action ledger recorded physical tool outcomes. When asked in Turn 49 *"what did we actually do in this conversation?"*, JARVIS hallucinated that zero actions had been taken, forgetting YouTube playback, Git status checks, file operations, and notification triage.

---

## 2. Architectural Comparison: Actual vs. Target 8-Layer

| Architectural Dimension | Actual Legacy JARVIS Architecture | Proposed 8-Layer Modernized Architecture | Superiority & Trade-off Assessment |
| :--- | :--- | :--- | :--- |
| **1. Session & Message Correlation** | Loose WebSocket FIFO queue. Messages lack persistent `request_id` correlation envelopes. Late tool outputs bleed into future turns. | **Layer 1 (Session Gateway):** Strict `request_id`, `session_id`, and `client_timestamp` envelopes. Decoupled async responses. | **Proposed is vastly superior.** Prevents the catastrophic desync observed in Turns 08–19 where YouTube results answered file search queries. |
| **2. Routing & Intent Classification** | Monolithic regex & substring matching in `planner.py` (500+ lines of `if 'reminder' in query:`). | **Layer 3 (Intent Arbitrator):** Semantic meaning classified first into typed `StructuredIntent` before keyword checks. | **Proposed is vastly superior.** Eliminates keyword collisions (e.g., "check on this test" routing to developer agent instead of scheduler). |
| **3. Working Short-Term Memory** | Stateless per-turn LLM history. Pronouns ("it", "that tab") fail. Persona ("Friday") resets across tool calls. | **Layer 2 (Context Manager):** Explicit active context: active window, CDP tab, code artifact, last file, active persona. | **Proposed is vastly superior.** Maintains persistent persona, allows pronoun resolution, and passes active code snippets to follow-ups. |
| **4. Safety & Policy Gate** | Regex-based keyword blocking ("dangerous words") in `guardrails.py` run on raw text. | **Layer 4 (Safety / Policy Gate):** Evaluates typed `StructuredIntent`. Formal Two-Gate token system for dangerous actions. | **Proposed is vastly superior.** Prevents false positives (e.g. blocking harmless math or reminders) while securing actual OS risks. |
| **5. Agent Dispatch** | Tight coupling between planner, executor, and agent modules. Dispatch logic scattered. | **Layer 5 (Agent Router):** Decoupled registry. Clean mapping from `StructuredIntent.domain` to isolated agent instances. | **Proposed is superior.** Modular, maintainable, allows independent testing and mocking of individual agent domains. |
| **6. Task Execution & Concurrency** | Blocking sequential execution. Tools run inline, delaying speech synthesis and locking WebSocket stream. | **Layer 6 (Execution Manager):** Task lifecycle tracking, per-domain deadline budgets (DOM: 25s, LLM: 35s), cooperative cancel. | **Proposed is superior.** User can interrupt stuck tasks; avoids server lockups when Chrome DOM elements take long to locate. |
| **7. Physical Verification** | Simple heuristic or string return checks. Often claims success without checking OS reality. | **Layer 7 (Empirical Verification):** Active ground truth check: checks CDP tab list, `Path.exists()`, git HEAD, window rects. | **Proposed is vastly superior.** Guarantees physical state truth. Returns explicit `PHYSICALLY_UNVERIFIED` if effect didn't occur. |
| **8. Response & Audio Dispatch** | Speech synthesis (Piper TTS) chunks sent synchronously before tool response payload is acknowledged. | **Layer 8 (Response Dispatch):** Immediate tool outcome dispatch to UI, concurrent background audio streaming to client. | **Proposed is vastly superior.** Dramatically cuts perceived user latency from 45s down to sub-second UI feedback. |
| **9. Historical Session Memory** | Unstructured chat history. LLM hallucinates past actions when asked for a summary. | **Persistent State (Episodic Action Ledger):** Structured append-only event ledger recording physical tools and outcomes. | **Proposed is vastly superior.** Solves Turn 49 amnesia. Enables 100% truthful session summaries and auditing. |

### Verdict:
The **Proposed 8-Layer Architecture** is objectively better for a production-grade multimodal assistant. It eliminates the 4 major failure classes identified in empirical testing while maintaining local execution on Windows 11 without cloud dependencies.

---

## 3. End-to-End Dataflow Diagram

```
                             ┌──────────────────────────────────────┐
                             │              USER CLIENT             │
                             │  (WebSocket / HUD / Audio Stream)    │
                             └──────────────────┬───────────────────┘
                                                │
                                    Inbound WebSocket Packet
                     {request_id, session_id, text, audio, timestamp}
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. SESSION GATEWAY (server/app.py)                                                                     │
│    • Envelopes request with unique request_id & cancellation token                                     │
│    • Tracks active in-flight requests per session                                                      │
│    • Discards/diverts stale responses from cancelled/abandoned turns                                   │
└───────────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                                │
                               Enriched Request Envelope
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. CONTEXT MANAGER (orchestrator/context_manager.py)                                                   │
│    • Maintains Live Working State:                                                                     │
│        - active_persona: "Friday" (sticky across session)                                              │
│        - active_window: {"title": "Chrome", "hwnd": 1234}                                              │
│        - active_browser: {"tab_id": 5, "url": "...", "media_playing": true}                            │
│        - last_code: {"snippet": "def factorial...", "language": "python"}                             │
│        - last_file: Path("d:/assignment/JARVIS/README.md")                                            │
│        - pending_confirmation: Optional[Transaction]                                                  │
│    • Resolves Pronouns & References ("it", "that tab", "run it with 5") -> Bound Entities              │
└───────────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                                │
                                Utterance + Resolved Context
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. INTENT ARBITRATOR (orchestrator/intent_arbitrator.py)                                               │
│    • Evaluates Meaning FIRST (Semantic Domain & Action Classification)                                 │
│    • Replaces brittle keyword substrings                                                               │
│    • Generates Typed StructuredIntent:                                                                 │
│        {domain: "scheduler", action: "set_reminder", args: {time_sec: 90, msg: "check test"}}         │
└───────────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                                │
                                         StructuredIntent
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. SAFETY & POLICY GATE (orchestrator/guardrails.py)                                                   │
│    • Policy checks on Typed Intent (not raw keywords):                                                 │
│        - Path traversal prevention                                                                     │
│        - Dangerous command interception                                                                │
│        - Two-Gate authorization token for destructive/communication actions                            │
│    • If confirmation required -> stages Transaction in ContextManager, prompts User                   │
└───────────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                                │
                                      Authorized Intent
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 5. AGENT ROUTER (orchestrator/router.py)                                                               │
│    • Dispatches strictly by domain:                                                                    │
│        ├─► Browser Automation Agent (CDP Port 9222)                                                    │
│        ├─► Scheduler Agent (APScheduler Background Triggers)                                           │
│        ├─► Developer Task Agent (Git commands, Python sandbox)                                         │
│        ├─► File & Document Agent (Safe filesystem operations)                                          │
│        ├─► Vision & OCR Agent (Moondream local vision model)                                           │
│        ├─► System Control Agent (Volume, window snapping, telemetry)                                   │
│        └─► Core LLM Agent (Ollama Qwen2.5-3B conversation)                                             │
└───────────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                                │
                                          Execution Plan
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 6. EXECUTION MANAGER (orchestrator/executor.py)                                                        │
│    • Allocates task_id linked to request_id                                                            │
│    • Enforces Deadline Budgets (Browser: 25s, Telemetry: 3s, LLM: 35s)                                 │
│    • Cooperative Cancellation (aborts underlying async tasks if user interrupts)                       │
│    • Retries transient CDP network errors                                                              │
└───────────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                                │
                                           Raw Outcome
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 7. EMPIRICAL VERIFICATION (orchestrator/verifier.py)                                                   │
│    • Validates physical ground truth:                                                                  │
│        - CDP: queries target tab list to verify close / navigation                                     │
│        - Filesystem: Path.exists() and byte size verification                                          │
│        - Git: executes git rev-parse to confirm current branch                                         │
│        - Window: verifies GetWindowRect coordinates after snapping                                     │
│    • Emits Verified Status: [SUCCESS | PARTIAL | PHYSICALLY_UNVERIFIED | FAILED]                       │
└───────────────────────────────────────┬───────────────────────────────┬────────────────────────────────┘
                                        │                               │
                      Physical Event Record             Verified Result Payload
                                        │                               │
                                        ▼                               ▼
    ┌───────────────────────────────────────────────┐   ┌────────────────────────────────────────────────┐
    │ PERSISTENT STATE: EPISODIC ACTION LEDGER      │   │ 8. RESPONSE DISPATCH (server/app.py)           │
    │ (memory/episodic_ledger.py)                   │   │    • Emits immediate tool response to UI       │
    │ • Appends immutable event:                    │   │    • Streams Piper neural TTS audio in parallel│
    │   {timestamp, request_id, action, result}     │   │    • Dispatches strictly to matching request_id│
    │ • Supplies 100% truthful session recall       │   │    • Updates Live Screen HUD indicators        │
    │   for queries like "what did we do?"          │   └───────────────────────┬────────────────────────┘
    └───────────────────────────────────────────────┘                           │
                                                                                ▼
                                                                ┌───────────────────────────────┐
                                                                │          USER CLIENT          │
                                                                │  (Zero Desync / Real Feedback)│
                                                                └───────────────────────────────┘
```

---

## 4. Subsystem Specification & Precise Contracts

### Layer 1: Session Gateway
- **Target File:** `server/app.py`
- **Envelope Specification:**
  ```python
  @dataclass
  class GatewayRequest:
      request_id: str
      session_id: str
      timestamp: float
      content: str
      cancellation_token: asyncio.Event

  @dataclass
  class GatewayResponse:
      request_id: str
      session_id: str
      status: str  # "success" | "partial" | "failed" | "cancelled"
      payload: Dict[str, Any]
      latency_ms: float
  ```
- **Concurrency & Cancellation Policy:**
  - When a new turn starts for an active session, if an existing non-background task is still executing and timed out or superseded, the gateway triggers its `cancellation_token`.
  - Any late responses arriving after cancellation are written directly to the `EpisodicLedger` as background completions, never delivered to the client as answers to new queries.

### Layer 2: Context Manager
- **Target File:** `orchestrator/context_manager.py`
- **State Dataclass:**
  ```python
  @dataclass
  class ActiveContext:
      session_id: str
      active_persona: str = "Jarvis"  # Sticky: persists across LLM boundaries
      active_window: Optional[Dict[str, Any]] = None
      active_browser: Optional[Dict[str, Any]] = None  # {url, tab_id, title, media_state}
      last_code: Optional[Dict[str, str]] = None  # {snippet, language}
      last_file: Optional[str] = None
      pending_confirmation: Optional[Dict[str, Any]] = None
      recent_actions: List[Dict[str, Any]] = field(default_factory=list)
  ```
- **Pronoun Resolution Contract:**
  - If utterance contains `"it"`, `"that"`, or `"this"`, the resolver examines `last_code` (if verb is code-related), `last_file` (if verb is file-related), or `active_browser` (if verb is browser-related).
  - Example: `"run it with 5"` -> Binds `"it"` to `last_code.snippet` with argument `5`.

### Layer 3: Semantic Intent Arbitrator
- **Target File:** `orchestrator/intent_arbitrator.py`
- **Intent Structure:**
  ```python
  @dataclass
  class StructuredIntent:
      domain: str            # "browser" | "file" | "git" | "scheduler" | "code" | "system" | "chat"
      action: str            # "play_media" | "pause_media" | "close_tab" | "set_reminder" | "explain_code"
      parameters: Dict[str, Any]
      confidence: float
      requires_confirmation: bool
      target_entity: Optional[str] = None
  ```
- **Collision Elimination Rules:**
  - Any request specifying relative/absolute time (`"in 90 seconds"`, `"at 5pm"`) with intent to notify is strictly classified under domain `scheduler`.
  - Factorial, math algorithms, or code generation requests are classified under domain `code` or `chat`, never intercepted by system resource telemetry (`RAM`).

### Layer 4: Safety & Policy Gate
- **Target File:** `orchestrator/guardrails.py`
- **Contract:**
  - Evaluates `StructuredIntent.domain` and `StructuredIntent.action`.
  - Two-Gate Authorization: Destructive actions (`delete_file`, `send_external_message`, `terminate_process`) require a pre-allocated confirmation token.
  - If token is missing, the gate intercepts execution, stages the action in `ContextManager.pending_confirmation`, and prompts the user for verbal confirmation.
  - Confirmation token automatically expires after 60 seconds of inactivity.

### Layer 5: Agent Router & Decoupled Dispatch
- **Target File:** `orchestrator/router.py`
- **Contract:**
  - Zero hardcoded logic. Pure mapping table from `domain` to registered agent instances.
  - Passes both `StructuredIntent` and `ActiveContext` to the designated agent.

### Layer 6: Execution Manager
- **Target File:** `orchestrator/executor.py`
- **Contract:**
  - Wraps agent calls in `asyncio.wait_for` with domain-specific deadline budgets:
    - Browser DOM navigation: 25.0 seconds.
    - System telemetry: 3.0 seconds.
    - Local LLM inference: 35.0 seconds.
    - File I/O: 5.0 seconds.
  - Gracefully catches timeouts, attempts clean resource release, and emits a structured timeout report.

### Layer 7: Empirical Verification
- **Target File:** `orchestrator/verifier.py`
- **Contract:**
  - Queries physical reality after agent finishes:
    - Browser tab close: Queries Chrome CDP `/json/list` to confirm tab ID no longer exists.
    - File creation: Verifies `os.path.exists()` and file size > 0 bytes.
    - Git branch: Checks output of `git rev-parse --abbrev-ref HEAD`.
    - Window snap: Calls Windows `GetWindowRect` to confirm desktop coordinates match target quadrant.

### Layer 8: Response Dispatch
- **Target File:** `server/app.py`
- **Contract:**
  - Immediately dispatches the JSON tool result to the WebSocket client matching `request_id`.
  - Spawns background task for Piper neural TTS audio chunking so audio streaming does not block the WebSocket command queue.

### Persistent State: Episodic Action Ledger
- **Target File:** `memory/episodic_ledger.py`
- **Schema:**
  ```python
  @dataclass
  class EpisodicEvent:
      timestamp: float
      request_id: str
      persona: str
      domain: str
      action: str
      target: str
      status: str
      summary: str
  ```
- **Truth Grounding Contract:**
  - When the user asks session recall questions (*"what did we do in this conversation?"*, Turn 49), the query is answered by summarizing the `EpisodicLedger` events rather than ungrounded LLM inference.

---

## 5. Comprehensive Mapping of 50-Turn Test Failures to the 8 Layers

| Turn # | Prompt | Baseline Outcome | Root Cause | Modernized 8-Layer Resolution |
| :---: | :--- | :---: | :--- | :--- |
| **08** | "play some lofi music on youtube" | FAIL | Browser tool hung in DOM wait; locked WS queue | **Layer 6 (Deadline Budget)** + **Layer 8 (Immediate UI dispatch)** |
| **09** | "pause the video" | FAIL | Received delayed search response from Turn 08 | **Layer 1 (Request ID Correlation)** + **Layer 2 (Active Browser State)** |
| **10** | "resume playback" | FAIL | Received delayed Turn 08 payload | **Layer 1 (Queue Sanitization)** + **Layer 3 (Semantic Intent)** |
| **11** | "mute the video" | FAIL | Keyword collision with system volume | **Layer 3 (Domain: Browser Media)** |
| **12** | "close that tab" | FAIL | Received delayed YouTube search; pronoun "that tab" unresolved | **Layer 2 (Pronoun Resolution to active_browser.tab_id)** + **Layer 7 (CDP tab list verification)** |
| **13** | "search instagram for photography" | FAIL | CDP socket lockup | **Layer 6 (Executor CDP timeout guard)** |
| **14** | "scroll down a bit" | FAIL | No active tab tracked | **Layer 2 (Active Browser Context)** |
| **18** | "snap this window to the left half of my screen" | FAIL | Snap command sent to non-existent window handle | **Layer 2 (Active Window Detection via Win32 API)** + **Layer 7 (GetWindowRect verification)** |
| **19** | "search for files with extension .md in this directory" | FAIL | Delayed Turn 09 media pause output flushed as answer | **Layer 1 (Strict Request Envelope)**: Discards late responses from earlier turns |
| **20** | "read the first 10 lines of the README.md" | FAIL | Path resolution relative to incorrect directory | **Layer 2 (last_file context)** + **Layer 4 (Safe path validator)** |
| **21** | "show git status for this repository" | FAIL | Shell safety false positive | **Layer 3 (Domain: Git)** routes to Developer Task Agent with safe git allowlist |
| **22** | "create a temporary test branch named temp-test-branch" | FAIL | Shell safety false positive | **Layer 4 (Git branch creation allowed under developer policy)** |
| **23** | "switch back to the main or master branch" | FAIL | Pronoun "back" and branch check failed | **Layer 2 (Tracks previous branch)** + **Layer 7 (Verifies HEAD branch via rev-parse)** |
| **24** | "delete that temporary branch" | FAIL | "that temporary branch" unresolved | **Layer 2 (Resolves to "temp-test-branch")** |
| **27** | "set a reminder in 90 seconds to check on this test" | FAIL | "check" & "test" intercepted by Developer Agent as script | **Layer 3 (Intent Arbitrator detects time constraint -> routes to Scheduler)** |
| **32** | "write a quick python function to calculate the factorial of a number" | FAIL | Keyword "number" collided with RAM telemetry regex | **Layer 3 (Semantic Intent: code_generation, routes to Core LLM)** |
| **33** | "explain how it handles zero and negative numbers" | FAIL | "it" unresolved; generated unrelated quadratic equation | **Layer 2 (Binds "it" to last_code.snippet)** |
| **34** | "run it with 5" | FAIL | Application launcher tried to launch an executable named "It" | **Layer 2 (Binds "it" to Python function) -> executes in safe Python sandbox** |
| **35** | "review the following code for bugs... division" | FAIL | LLM context overflow | **Layer 2 (Clean context frame passing)** |
| **49** | "what did we actually do in this conversation? give me a quick summary of real actions" | FAIL | Complete amnesia; LLM claimed zero actions taken | **Persistent State (Episodic Action Ledger)**: Queries verified event records for 100% truthful summary |
| **50** | "switch back to Friday persona and say goodbye" | FAIL | Persona had already reset to Jarvis on Turn 15 | **Layer 2 (Session-sticky active_persona)** retains Friday and synthesizes female TTS |

---

## 6. Implementation Phasing & Readiness Criteria

When the planning review is finalized and the user approves starting code execution, implementation will follow this structured, 6-phase sequence:

### Phase 1: Gateway & Queue Sanitization (`server/app.py`)
- Wire `request_id` correlation envelopes on inbound WebSocket connections.
- Implement decoupled response dispatch: emit JSON tool responses immediately to UI, stream Piper neural TTS audio concurrently.
- Flush and isolate abandoned request buffers.

### Phase 2: Working Context Manager (`orchestrator/context_manager.py`)
- Activate `ContextManager` singleton tracking active persona, active window, active browser tab, last code snippet, and last file path.
- Implement `resolve_pronouns` rules.

### Phase 3: Semantic Intent Arbitrator (`orchestrator/intent_arbitrator.py`)
- Deploy semantic domain/action classifier.
- Route relative time requests ("in 90s") strictly to `scheduler`.
- Route code requests strictly to `core_llm`.

### Phase 4: Execution & Verification Hardening (`orchestrator/executor.py` & `verifier.py`)
- Enforce domain deadline budgets.
- Add CDP tab verification, `Path.exists()`, and `git rev-parse` empirical checks.

### Phase 5: Episodic Action Ledger (`memory/episodic_ledger.py`)
- Implement append-only event logging for all verified physical actions.
- Hook into Turn 49 / session summary queries to provide 100% truthful reports.

### Phase 6: Live 50-Exchange Re-Verification
- Execute `tests/run_50_exchange_live_test.py` across Real Chrome (Port 9222) and Ollama (Port 11434).
- Target acceptance: **>= 45 / 50 PASS (>= 90%)** with zero queue desynchronizations.

---
*All planning is saved, finalized, and documented. Standing by for user instruction before beginning code execution.*
