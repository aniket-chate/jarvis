# JARVIS 50-Capability Master Matrix

**Document Version:** 1.0-MASTER  
**Architecture Readiness Gate:** CERTIFIED READY FOR CAPABILITY EXPANSION  
**Last Updated:** September 15, 2026  
**System Architect:** Aniket & Antigravity IDE  

---

## 1. Classification Definitions

Every capability domain is audited and classified according to its current footprint in the JARVIS repository:

- **`EXISTING`**: Core implementation exists, works, and adheres to architectural patterns. Action: *Preserve + wrap into capability/provider interface + improve tests*.
- **`PARTIAL`**: Significant functional logic exists in legacy agents or utilities, but lacks unified capability contracts, provider decoupling, or verification integration. Action: *Preserve working portions + complete missing functionality + bind to provider*.
- **`FOUNDATION`**: Architectural scaffolding (kernels, fabrics, event schemas) exists, but domain-specific provider logic is nascent. Action: *Build capability provider upon existing architectural foundation*.
- **`NEW`**: No substantial components exist in the repository. Action: *Design and implement contract, provider, safety, and verification from scratch*.

---

## 2. Master Capability Matrix (All 50 Domains)

| ID | Capability Domain | Current Status | Existing Components in Repo | Reusable Assets | Missing Components / Work Required | Safety Level | Verification Method |
| :---: | :--- | :---: | :--- | :--- | :--- | :--- | :--- |
| **01** | **Natural Language & Conversation** | `EXISTING` | `cognitive/understanding.py`, `cognitive/reasoning.py`, `llm/personas.py`, `agents/core_llm_agent.py` | Semantic intent classification, persona states, dual-process routing | Marathi/English code-switching prompts, conversational repair, response style toggles | `READ_ONLY` | Deductive response coherence audit |
| **02** | **Cognitive Reasoning** | `EXISTING` | `cognitive/reasoning.py`, `cognitive/kernel.py`, `cognitive/goal_engine.py` | Deliberative reasoning, System 2 DAG generation | Contradiction detection, hypothesis generation, uncertainty bounds | `READ_ONLY` | Reasoning validity & consistency audit |
| **03** | **World Model** | `EXISTING` | `cognitive/world_model.py` | Win32 window, Chrome CDP tab, Git HEAD, file hash, OS process probes | Dynamic entity graph, multi-device tracking | `READ_ONLY` | Physical Win32/CDP/OS probes |
| **04** | **Context Intelligence** | `EXISTING` | `cognitive/understanding.py`, `cognitive/world_model.py` | Pronoun resolution ("it", "that tab", "that file"), working memory | Temporal context decay, multi-entity referent trees ("the second one") | `READ_ONLY` | Grounded entity state matching |
| **05** | **Meta-Cognition** | `PARTIAL` | `cognitive/understanding.py`, `verification/verifier.py` | Intent confidence score, ambiguity flag, clarification prompts | Explicit pre-planning uncertainty calibration, plan failure detection | `READ_ONLY` | Meta-evaluation self-consistency |
| **06** | **Memory System** | `EXISTING` | `memory/system.py`, `memory/episodic_ledger.py`, `agents/semantic_rag.py` | 7-tier memory, immutable episodic ledger (REQUESTED to VERIFIED) | Forgetting policies, semantic contradiction reconciliation | `READ_ONLY` | Immutable ledger hash audit |
| **07** | **Learning & Adaptation** | `PARTIAL` | `learning_system/experience_store.py`, `tests/test_arch_learning.py` | Experience logging, outcome evaluation, feedback recording | Dynamic provider ranking weights, closed-loop prompt adaptation | `READ_ONLY` | Telemetry experience replay |
| **08** | **Skill Acquisition** | `FOUNDATION` | `skills/`, `cognitive/planning_engine.py`, `docs/extending_agents.md` | Skill files, static procedure execution | Dynamic procedure discovery, sandbox validation, skill promotion | `MODIFYING` | Sandboxed test execution |
| **09** | **Experience Replay & Evaluation**| `PARTIAL` | `tests/run_all_audits.py`, `tests/run_50_exchange_live_test.py` | Automated audit suites, live test fixtures | Trajectory replay harness, historical failure regression replay | `READ_ONLY` | Benchmark regression suite |
| **10** | **Knowledge Management** | `VERIFIED END-TO-END` | `agents/personal_knowledge_base.py`, `agents/about_me_ingest.py` | RAG ingestion, document chunking, vector lookups | Verified lifecycle, automated freshness validator, knowledge contradiction resolver | `READ_ONLY` | Document hash & retrieval audit |
| **11** | **Vision** | `EXISTING` | `agents/vision_agent.py`, `capabilities/providers/vision_provider.py` | Moondream local vision model, screenshot analysis | Pre/post-action visual diff comparison, UI element grounding | `READ_ONLY` | Screen rect visual validation |
| **12** | **OCR & Document Intelligence** | `EXISTING` | `agents/vision_ocr_agent.py`, `capabilities/providers/vision_provider.py` | Native Windows OCR, text extraction | PDF parser provider, key-value table extraction | `READ_ONLY` | OCR text presence verification |
| **13** | **Audio Perception** | `PARTIAL` | `voice/asr.py`, `perception/channels/voice_input.py` | Microphone capture, Whisper ASR integration | Streaming audio chunking, barge-in / interruption detector | `READ_ONLY` | Audio stream state probe |
| **14** | **Environmental Perception** | `EXISTING` | `cognitive/world_model.py`, `capabilities/providers/os_provider.py` | Win32 telemetry, process status, network connectivity | Connected hardware/Bluetooth device polling | `READ_ONLY` | Win32 API system probe |
| **15** | **Multimodal Understanding** | `FOUNDATION` | `perception/events.py`, `event_fabric/schemas.py`, `perception/processing/`| UniversalEvent schema, perception event listeners | Modality conflict resolver (text vs vision vs audio) | `READ_ONLY` | Cross-modality agreement audit |
| **16** | **Voice Intelligence** | `PARTIAL` | `voice/tts_piper.py`, `server/app.py` | Piper neural TTS, audio streaming WebSocket | Hot-swappable VoiceProvider (Piper, Android TTS, ElevenLabs) | `READ_ONLY` | Audio buffer byte verification |
| **17** | **Wake-Word Intelligence** | `PARTIAL` | `wakeword/engine.py`, `client/android/` | Sherpa-ONNX runtime on Android, desktop listener | WakeWordProvider abstraction, configurable sensitivity & profiles | `READ_ONLY` | Detection event verification |
| **18** | **Persona & Social Interaction** | `EXISTING` | `llm/personas.py`, `cognitive/world_model.py`, `cognitive/understanding.py`| Jarvis, Friday, Ultron prompts, sticky persona state | Granular tone/style modifiers, personality boundaries | `READ_ONLY` | Persona state validation |
| **19** | **Emotion & Social Context** | `FOUNDATION` | `perception/processing/context_awareness.py` | Sentiment heuristics, context tagging | Probabilistic emotion & urgency classifier | `READ_ONLY` | Mood & urgency classification test |
| **20** | **Accessibility** | `FOUNDATION` | Voice and text UI channels, command schemas | Audio feedback, keyboard-driven navigation | Screen-reader friendly payloads, high-contrast HUD modes | `READ_ONLY` | Accessibility format validation |
| **21** | **Desktop / OS Control** | `EXISTING` | `agents/system_control_agent.py`, `capabilities/providers/os_provider.py` | Window snapping, volume control, app launch | Multi-monitor geometry, window focus verification | `MODIFYING` | `GetWindowRect` & Win32 API |
| **22** | **File & Storage Intelligence** | `EXISTING` | `agents/file_document_agent.py`, `capabilities/providers/file_provider.py` | Create, move, rename, delete, read, hash | Archive inspection (zip preview), duplicate scanner | `DESTRUCTIVE` | `Path.exists()`, size, SHA-256 |
| **23** | **Browser Intelligence** | `EXISTING` | `agents/browser_automation_agent.py`, `capabilities/providers/browser_provider.py` | Real Chrome CDP (port 9222), tabs, navigation, playback | Form filling automation, download progress observer | `MODIFYING` | Chrome CDP DOM & tab inspection |
| **24** | **Application Intelligence** | `PARTIAL` | `agents/system_control_agent.py`, `cognitive/world_model.py` | Executable launcher, process detection | App-specific provider registry (VS Code, Spotify, Terminal) | `MODIFYING` | Process PID & HWND verification |
| **25** | **Shell & System Administration** | `EXISTING` | `safety/policy_kernel.py`, `capabilities/providers/developer_provider.py` | Strict prohibition of raw shell, safe allowlisted diagnostics | Controlled diagnostic provider (`netstat`, service status) | `PRIVILEGED` | Output validation & policy audit |
| **26** | **Software Engineering** | `EXISTING` | `agents/dev_tool_agent.py`, `capabilities/providers/developer_provider.py` | Code generation, review, sandboxed AST execution | Multi-file dependency analyzer, test generator | `MODIFYING` | Sandboxed execution returncode |
| **27** | **Development Environment** | `PARTIAL` | `agents/dev_tool_agent.py`, `.venv` tooling | Git status, sandbox runner | Virtualenv inspection, package dependency audit provider | `MODIFYING` | Environment probe verification |
| **28** | **Git & Version Control** | `EXISTING` | `agents/dev_tool_agent.py`, `capabilities/providers/developer_provider.py` | Branch switch, create, status, diff | Merge conflict parser, git stash provider | `MODIFYING` | `git rev-parse --abbrev-ref HEAD` |
| **29** | **DevOps & Deployment** | `FOUNDATION` | `tests/` runners, `server/app.py` health endpoints | Build verification, local test execution | Deployment runner, rollback script provider, staging check | `PRIVILEGED` | Health check endpoint verification |
| **30** | **Database & Backend Intelligence** | `FOUNDATION` | SQLite databases in `memory/`, schema files | Local SQLite persistence, query execution | Readonly schema inspector, SQL query validator provider | `MODIFYING` | SQLite schema & row verification |
| **31** | **Web Research** | `VERIFIED END-TO-END` | `agents/web_agent.py`, `capabilities/providers/search_provider.py` | DuckDuckGo / Tavily search, content scraping | Multi-source citation synthesizer, source credibility ranker, deep fetch quarantine | `READ_ONLY` | URL fetch & content validation |
| **32** | **Real-Time Information** | `VERIFIED END-TO-END` | `agents/weather_agent.py`, `agents/news_agent.py`, `capabilities/providers/realtime_provider.py` | Open-Meteo, wttr.in, Google News RSS, DuckDuckGo | Unified `RealTimeInfoProvider` with mandatory freshness timestamping, quarantine, and caching | `READ_ONLY` | Observation verification & freshness check |
| **33** | **Personal Search** | `EXISTING` | `agents/personal_knowledge_base.py`, `agents/semantic_rag.py` | Vector search, profile queries, file search | Unified cross-source personal query coordinator | `READ_ONLY` | Search recall & provenance check |
| **34** | **Information Verification** | `EXISTING` | `verification/verifier.py` (`ObservationVerificationKernel`) | Physical state auditing, lying provider rejection | Fact claim cross-referencing against episodic memory | `READ_ONLY` | Empirical observation match |
| **35** | **Knowledge Synthesis** | `PARTIAL` | `cognitive/reasoning.py`, `agents/semantic_rag.py` | Text summarization, multi-context assembly | Multi-document synthesis with provenance & confidence bounds | `READ_ONLY` | Provenance citation audit |
| **36** | **Device Mesh** | `PARTIAL` | `client/android/`, `docs/tailscale_remote_access.md`, `gateway/` | Android WebSocket client, Tailscale VPN docs | `DeviceMeshProvider` tracking peer devices & remote routing | `MODIFYING` | Device handshake ping verification |
| **37** | **Communication** | `EXISTING` | `agents/communication_agent.py`, `skills/google_gmail.py` | Gmail API, WhatsApp web, Two-Gate confirmation tokens | Recipient verification, message preview staging | `EXTERNAL_COMM` | Outbox / Sent state verification |
| **38** | **Calendar & Scheduling** | `EXISTING` | `agents/calendar_agent.py`, `skills/google_calendar.py`, `scheduler_provider.py`| APScheduler reminders, Google Calendar auth | Conflict detection, schedule rescheduling provider | `MODIFYING` | Calendar event existence query |
| **39** | **Personal Productivity** | `PARTIAL` | `agents/notification_triage_agent.py`, `workspace/call_notes/` | Notification triage, call notes storage | Task list manager, daily agenda aggregator provider | `MODIFYING` | Task ledger persistence check |
| **40** | **Travel & Navigation** | `NEW` | `perception/channels/sensor_input.py` | Location schema placeholders | `TravelNavigationProvider` (route timing, transit options) | `READ_ONLY` | Route geometry & transit check |
| **41** | **Autonomous Agency** | `EXISTING` | `autonomous_runtime/agency.py`, `autonomous_runtime/schemas.py` | Condition watchers, scheduled rules, cognitive routing | Composite condition triggers ("A and B") | `MODIFYING` | Full cognitive pipeline audit |
| **42** | **Workflow Automation** | `EXISTING` | `execution/runtime.py` (`ExecutionKernel`), `cognitive/goal_engine.py`| StepState, checkpointing, thread pool, DAG execution | Dynamic rollback / compensating actions on workflow failure | `MODIFYING` | Checkpoint disk persistence audit |
| **43** | **Monitoring & Alerts** | `PARTIAL` | `autonomous_runtime/agency.py`, `observability/tracer.py` | Condition polling, telemetry traces | Deduplication alert threshold manager | `READ_ONLY` | Alert emission & threshold test |
| **44** | **Smart Home / IoT** | `PARTIAL` | `agents/smart_home_agent.py`, `skills/home_assistant.py`, `cast_agent.py` | Home Assistant integration, cast skill | `SmartHomeCapabilityProvider` with mock/real REST API | `PHYSICAL` | Home Assistant state API probe |
| **45** | **Physical / Robotics Interface** | `FOUNDATION` | `perception/channels/sensor_input.py`, `safety/policy_kernel.py` | Sensor input channels, safety policy levels | `RoboticsCapabilityProvider` contract with strict interlocks | `PHYSICAL` | Hardware safety interlock audit |
| **46** | **Data Science & Analytics** | `FOUNDATION` | `capabilities/providers/developer_provider.py` | Python sandbox execution | `DataAnalyticsProvider` (CSV/JSON statistics, matplotlib) | `READ_ONLY` | Dataframe output verification |
| **47** | **Simulation & Prediction** | `FOUNDATION` | `cognitive/reasoning.py` | Deliberative reasoning engine | What-if scenario generator with uncertainty bounds | `READ_ONLY` | Sensitivity analysis output check |
| **48** | **Security & Identity** | `EXISTING` | `safety/policy_kernel.py`, `agents/identity_agent.py`, `permission_checks.py` | Two-Gate tokens, request-ID pinning, secret masking | Dynamic session token expiration, audit logging | `PRIVILEGED` | Security policy compliance test |
| **49** | **Verification & Self-Diagnostics**| `EXISTING` | `verification/verifier.py`, `tests/run_all_audits.py` | Physical verifier, 13-suite audit runner | `DiagnosticsCapabilityProvider` for live system self-checks | `READ_ONLY` | Self-diagnostic telemetry audit |
| **50** | **Capability Evolution** | `FOUNDATION` | `capabilities/intelligence.py`, `learning_system/experience_store.py` | Dynamic provider registry, unregister/register | Capability gap detector analyzing execution failures | `MODIFYING` | Registry update validation |

---

## 3. Summary of Repository Audit Findings

- **`EXISTING` Capabilities (23 / 50 = 46%):** Natural Language, Reasoning, World Model, Context, Memory, Vision, OCR, Environment, Persona, Desktop OS, Files, Browser, Shell Security, Software Engineering, Git, Web Research, Personal Search, Verification, Communication, Calendar, Autonomous Agency, Workflow Automation, Security & Identity.
- **`PARTIAL` Capabilities (14 / 50 = 28%):** Meta-Cognition, Learning, Experience Replay, Knowledge Management, Audio Perception, Voice Intelligence, Wake-Word, Application Intelligence, Dev Environment, Real-Time Information, Knowledge Synthesis, Device Mesh, Personal Productivity, Monitoring & Alerts.
- **`FOUNDATION` Capabilities (12 / 50 = 24%):** Skill Acquisition, Multimodal Understanding, Emotion Context, Accessibility, DevOps & Deployment, Database Intelligence, Robotics Interface, Data Science, Simulation, Capability Evolution, Smart Home / IoT, Self-Diagnostics.
- **`NEW` Capabilities (1 / 50 = 2%):** Travel & Navigation.

**Key Architect Insight:** Over **74%** of capabilities already exist or have substantial working portions in the repository! We must preserve, wrap, and standardize them into clean capability providers rather than rewriting working code.
