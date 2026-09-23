# JARVIS 50-Capability Test Matrix

**Document Version:** 1.0-MASTER  
**Test Standard:** Minimum 10 Test Cases per Capability (Happy-path, Ambiguous, Failure, Fallback, Concurrency, Verification, Safety, Recovery, Context, Regression)  
**System Architect:** Aniket & Antigravity IDE  

---

## 1. Test Architecture & Coverage Framework

Every capability must have coverage across all 10 architectural verification dimensions:

1. **Happy Path:** Standard well-formed input and expected output.
2. **Ambiguous Input:** Incomplete query, pronoun ambiguity, missing arguments.
3. **Failure Handling:** Invalid parameters, offline application, syntax errors.
4. **Provider Fallback:** Primary provider fails; secondary provider seamlessly assumes execution.
5. **Concurrency:** Overlapping independent execution without state mixing.
6. **Physical Verification:** Observation kernel confirms ground-truth world mutation.
7. **Safety Invariant:** Policy evaluation, Two-Gate token checks, shell denial.
8. **Recovery & Checkpoint:** Workflow interruption and clean state resumption.
9. **Context Resolution:** Grounded pronoun ("it", "that tab") state resolution.
10. **Regression Invariant:** Automated regression validation in master suite.

---

## 2. Capability Test Coverage Mapping (All 50 Domains)

| ID | Capability Domain | Primary Test Suite File | Happy / Ambiguous Test | Safety / Policy Test | Physical Verification Test | Provider Fallback Test | Status |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **01** | **Natural Language** | `tests/test_arch_cognitive_core.py` | `test_cognitive_core_pipeline` | Policy check on query | Deductive response check | Ollama -> Gemini fallback | **VERIFIED** |
| **02** | **Cognitive Reasoning** | `tests/test_arch_cognitive_core.py` | `test_system_2_deliberative` | Injection quarantine | Reasoning consistency | ReasoningEngine fallback | **VERIFIED** |
| **03** | **World Model** | `tests/audit_world_model_reality.py` | `test_reality_probes` | Read-only state check | Win32 HWND / Git HEAD | Multiple probe fallback | **VERIFIED** |
| **04** | **Context Intelligence** | `tests/audit_context_resolution.py` | `test_browser_context_tree` | Scoped context boundaries | Referent entity matching | Active referent search | **VERIFIED** |
| **05** | **Meta-Cognition** | `tests/test_arch_cognitive_core.py` | `test_uncertainty_detection` | Clarification prompt check | Confidence calibration | ReasoningEngine fallback | **VERIFIED** |
| **06** | **Memory System** | `tests/audit_episodic_recall.py` | `test_truthful_episodic_recall`| Untrusted data tagging | Immutable ledger hash | SQLite -> In-memory | **VERIFIED** |
| **07** | **Learning & Adaptation** | `tests/test_arch_learning.py` | `test_experience_logging` | Read-only telemetry | Outcome score match | Local experience store | **VERIFIED** |
| **08** | **Skill Acquisition** | `tests/test_all_50_capabilities.py` | `test_skill_sandbox_eval` | Sandboxed execution | Returncode verification | Dynamic mock sandbox | **PENDING** |
| **09** | **Experience Replay** | `tests/test_all_50_capabilities.py` | `test_trajectory_playback` | Read-only replay | Replay match assertion | Historical log parser | **PENDING** |
| **10** | **Knowledge Management** | `tests/test_capability_10_knowledge.py` | `test_knowledge_lifecycle` | Sandbox & prompt injection refusal | Document presence & index check | RAG store -> Mock provider | **VERIFIED END-TO-END** |
| **11** | **Vision** | `tests/audit_10_scenarios.py` | `test_screen_inspect` | Visual permission gate | Screen rect check | Moondream -> Gemini | **VERIFIED** |
| **12** | **OCR & Documents** | `tests/audit_10_scenarios.py` | `test_native_win_ocr` | Read-only document | OCR text presence | Win OCR -> Tesseract | **VERIFIED** |
| **13** | **Audio Perception** | `tests/test_all_50_capabilities.py` | `test_audio_stream_chunk` | Mic privacy boundary | Stream state probe | Whisper -> Android mic | **PENDING** |
| **14** | **Environmental Perception**| `tests/audit_world_model_reality.py`| `test_os_process_probe` | System permission check | Win32 API metrics | Win32 -> psutil | **VERIFIED** |
| **15** | **Multimodal Understanding**| `tests/test_all_50_capabilities.py`| `test_multimodal_fusion` | Cross-modality safety | Modality agreement audit | Fused -> Core LLM | **PENDING** |
| **16** | **Voice Intelligence** | `tests/test_all_50_capabilities.py` | `test_piper_tts_synthesis` | Output rate limits | Audio buffer byte length | Piper -> Android TTS | **PENDING** |
| **17** | **Wake-Word Intelligence**| `tests/test_all_50_capabilities.py` | `test_wakeword_detection` | False-positive check | Wake event timestamp | Sherpa-ONNX -> OpenWake | **PENDING** |
| **18** | **Persona & Social** | `tests/test_layer2.py` | `test_persona_sticky_state` | Identity boundary | Settings persona assertion | Jarvis <-> Friday | **VERIFIED** |
| **19** | **Emotion & Context** | `tests/test_all_50_capabilities.py` | `test_sentiment_analysis` | Empathy policy | Score bounds check | Rule heuristic -> LLM | **PENDING** |
| **20** | **Accessibility** | `tests/test_all_50_capabilities.py` | `test_accessible_payload` | Format compliance | Payload schema validation | Screen reader adapter | **PENDING** |
| **21** | **Desktop / OS Control** | `tests/test_arch_execution.py` | `test_snap_window_execution`| Window action policy | `GetWindowRect` | Win32 -> PyAutoGUI | **VERIFIED** |
| **22** | **File & Storage** | `tests/audit_verification.py` | `test_file_action_observation`| Two-Gate delete token | `Path.exists()` & SHA-256 | Scoped -> Shutil | **VERIFIED** |
| **23** | **Browser Intelligence** | `tests/audit_verification.py` | `test_browser_navigation` | Tab close confirmation | CDP Tab list query | Chrome CDP -> Playwright | **VERIFIED** |
| **24** | **Application Intelligence**| `tests/test_all_50_capabilities.py`| `test_app_launch_and_focus` | Executable allowlist | Process PID & HWND | Win32 launcher -> OS | **PENDING** |
| **25** | **Shell & Sysadmin** | `tests/audit_safety_invariant.py` | `test_shell_command_refusals`| **Level 3: Prohibited** | Policy refusal output | Allowlisted CLI only | **VERIFIED** |
| **26** | **Software Engineering** | `tests/audit_10_scenarios.py` | `test_code_iteration_and_fix`| Sandbox security boundary | AST returncode check | Local sandbox -> LLM | **VERIFIED** |
| **27** | **Dev Environment** | `tests/test_all_50_capabilities.py` | `test_venv_inspection` | Virtualenv scope | Metadata file check | VenvManager -> Pip CLI | **PENDING** |
| **28** | **Git & Version Control** | `tests/audit_verification.py` | `test_git_branch_switch` | Uncommitted changes check | `git rev-parse HEAD` | GitCode -> GitCLI | **VERIFIED** |
| **29** | **DevOps & Deployment** | `tests/test_all_50_capabilities.py` | `test_devops_health_probe` | Two-Gate deploy token | HTTP 200 health check | ScriptRunner -> Staging | **PENDING** |
| **30** | **Database Intelligence**| `tests/test_all_50_capabilities.py` | `test_sqlite_readonly_query` | Read-only SQL gate | Row count & schema check | SQLite -> SchemaInspector | **PENDING** |
| **31** | **Web Research** | `tests/test_capability_31_web_research.py` | `test_research_report_workflow`| Untrusted data boundary & injection quarantine | Content hash & citations verifier | SearchFetch -> Tavily/Brave/DDG | **VERIFIED END-TO-END** |
| **32** | **Real-Time Information** | `tests/test_capability_32_realtime_information.py` | `test_weather_news_freshness`| Quarantine & shell execution refusal | Observation timestamp & freshness check | LiveFeeds -> OpenMeteo/wttr | **VERIFIED END-TO-END** |
| **33** | **Personal Search** | `tests/test_about_me_rag.py` | `test_personal_kb_query` | Owner identity gate | Provenance metadata check | PersonalVector -> File | **VERIFIED** |
| **34** | **Information Verification**| `tests/audit_verification.py` | `test_lying_provider_rejection`| Untrusted claims audit | Physical reality probe | Core observation kernel | **VERIFIED** |
| **35** | **Knowledge Synthesis** | `tests/test_all_50_capabilities.py` | `test_synthesis_citation_gen`| Hallucination prevention | Citation source check | Synthesizer -> LLM | **PENDING** |
| **36** | **Device Mesh** | `tests/test_all_50_capabilities.py` | `test_device_handshake_ping` | Tailscale VPN security | Handshake response | Tailscale -> Local LAN | **PENDING** |
| **37** | **Communication** | `tests/audit_safety_invariant.py` | `test_whatsapp_email_safety` | Two-Gate token required | Outbox sent status | Gmail API -> WhatsApp CDP | **VERIFIED** |
| **38** | **Calendar & Scheduling** | `tests/audit_autonomy.py` | `test_scheduled_task_trigger` | Date boundary validation | APScheduler job registry | APScheduler -> Google Cal | **VERIFIED** |
| **39** | **Personal Productivity** | `tests/test_all_50_capabilities.py` | `test_task_crud_operations` | Data isolation | SQLite task row count | LocalTask -> SQLite | **PENDING** |
| **40** | **Travel & Navigation** | `tests/test_all_50_capabilities.py` | `test_route_plan_calculation`| Location data privacy | Route coordinates check | TransitMaps -> Search | **PENDING** |
| **41** | **Autonomous Agency** | `tests/audit_autonomy.py` | `test_file_appears_condition` | Prohibited action denial | Full cognitive pipeline | AgencyRuntime -> Rules | **VERIFIED** |
| **42** | **Workflow Automation** | `tests/audit_checkpoint_recovery.py`| `test_checkpoint_and_recovery`| Transaction bounds | Checkpoint JSON on disk | RuntimeKernel -> DAG | **VERIFIED** |
| **43** | **Monitoring & Alerts** | `tests/test_all_50_capabilities.py` | `test_metric_threshold_alert` | Deduplication policy | Alert log event record | ThresholdPoll -> Agency | **PENDING** |
| **44** | **Smart Home / IoT** | `tests/test_all_50_capabilities.py` | `test_home_assistant_switch` | Physical Two-Gate token | Home Assistant state API | HomeAssistant -> Cast | **PENDING** |
| **45** | **Physical / Robotics** | `tests/test_all_50_capabilities.py` | `test_robotics_interlock` | **Physical Safety Interlock** | Interlock engagement | MockInterlock -> Safety | **PENDING** |
| **46** | **Data Science & Analytics**| `tests/test_all_50_capabilities.py` | `test_dataframe_statistics` | Isolated memory budget | Dataframe shape & stats | PythonSandbox -> DevGit | **PENDING** |
| **47** | **Simulation & Prediction**| `tests/test_all_50_capabilities.py` | `test_what_if_simulation` | Uncertainty disclosure | Sensitivity bounds check | MonteCarlo -> Reasoning | **PENDING** |
| **48** | **Security & Identity** | `tests/audit_safety_invariant.py` | `test_confirmation_lifecycle`| Replay & TTL enforcement | Policy evaluation report | PolicyKernel -> Identity | **VERIFIED** |
| **49** | **Verification & Diagnostics**| `tests/run_all_audits.py` | `test_full_system_self_audit` | Read-only diagnostic | 13-suite 100% pass | SystemAudit -> Verifier | **VERIFIED** |
| **50** | **Capability Evolution** | `tests/test_all_50_capabilities.py` | `test_capability_gap_detector`| Schema migration policy | Registry version update | GapAnalyzer -> Registry | **PENDING** |

---

## 3. Coverage Status

- **VERIFIED in Existing Suites (28 / 50 = 56%):** Fully covered and passing 100% green in `run_all_audits.py` and foundational tests.
- **TARGET for New Integrated Suite `tests/test_all_50_capabilities.py` (22 / 50 = 44%):** Comprehensive test harness covering all newly providerized and scaffolding capabilities.
