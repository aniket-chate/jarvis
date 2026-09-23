# JARVIS First-50 Functional Capability Inventory

**Baseline**: Capabilities 1–50 Frozen Baseline  
**Total Documented Capabilities**: 50  
**Hardcoding Status**: 100% Passed AST Audit (0 hardcoded identities / 0 fixture leaks)  

---

## Capability 01_natural_language: Natural Language & Conversation

- **Domain**: `chat`
- **Purpose**: Handles multilingual natural conversation, greetings, follow-ups, and style adaptation.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.llm.ollama_local`
- **Registered Providers**: `provider.llm.ollama_local`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `DEDUCTIVE_COHERENCE`
- **Supported Operations** (4):
  - `chat.conversation`
  - `chat.greeting`
  - `chat.clarification`
  - `chat.multilingual`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_01_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering chat operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 02_cognitive_reasoning: Cognitive Reasoning

- **Domain**: `cognitive`
- **Purpose**: Performs inference, deduction, decomposition, contradiction detection, and hypothesis generation.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.cognitive.reasoning_engine`
- **Registered Providers**: `provider.cognitive.reasoning_engine`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `LOGICAL_CONSISTENCY`
- **Supported Operations** (4):
  - `reasoning.infer`
  - `reasoning.deduce`
  - `reasoning.decompose`
  - `reasoning.contradiction_check`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_02_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering cognitive operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 03_world_model: World Model

- **Domain**: `cognitive`
- **Purpose**: Maintains physical reality ground truth across windows, browser tabs, files, git, and processes.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.cognitive.world_model`
- **Registered Providers**: `provider.cognitive.world_model`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `EMPIRICAL_OBSERVATION`
- **Supported Operations** (5):
  - `world.probe_window`
  - `world.probe_browser`
  - `world.probe_file`
  - `world.probe_git`
  - `world.probe_process`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_03_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering cognitive operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 04_context_intelligence: Context Intelligence

- **Domain**: `cognitive`
- **Purpose**: Resolves pronouns ('it', 'that tab', 'that file') and binds working memory across turns.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.cognitive.context_engine`
- **Registered Providers**: `provider.cognitive.context_engine`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `GROUNDED_STATE_MATCH`
- **Supported Operations** (3):
  - `context.resolve_pronoun`
  - `context.get_active_referent`
  - `context.update_state`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_04_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering cognitive operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 05_meta_cognition: Meta-Cognition

- **Domain**: `cognitive`
- **Purpose**: Evaluates uncertainty, detects missing information, and triggers clarification before execution.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.cognitive.meta_evaluator`
- **Registered Providers**: `provider.cognitive.meta_evaluator`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `CONFIDENCE_CALIBRATION`
- **Supported Operations** (3):
  - `meta.estimate_confidence`
  - `meta.detect_uncertainty`
  - `meta.plan_adequacy`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_05_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering cognitive operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 06_memory_system: Memory System

- **Domain**: `memory`
- **Purpose**: Manages 7-tier memory and immutable episodic action ledger.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.memory.sqlite_vector`
- **Registered Providers**: `provider.memory.sqlite_vector`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `LEDGER_STATE_AUDIT`
- **Supported Operations** (4):
  - `memory.record_episodic`
  - `memory.query_episodic`
  - `memory.recall_semantic`
  - `memory.update_profile`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_06_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering memory operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 07_learning_adaptation: Learning & Adaptation

- **Domain**: `learning`
- **Purpose**: Captures user corrections, evaluates provider latency/accuracy, and adapts preference weights.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.learning.experience_store`
- **Registered Providers**: `provider.learning.experience_store`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `TELEMETRY_EXPERIENCE_MATCH`
- **Supported Operations** (3):
  - `learning.record_experience`
  - `learning.adjust_weights`
  - `learning.get_insights`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_07_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering learning operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 08_skill_acquisition: Skill Acquisition

- **Domain**: `skill`
- **Purpose**: Discovers recurring user procedures, creates sandbox tests, and promotes validated workflows.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.skill.sandbox_runner`
- **Registered Providers**: `provider.skill.sandbox_runner`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `SANDBOX_TEST_PASS`
- **Supported Operations** (4):
  - `skill.discover`
  - `skill.sandbox_test`
  - `skill.promote`
  - `skill.retire`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_08_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering skill operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 09_experience_replay: Experience Replay & Evaluation

- **Domain**: `learning`
- **Purpose**: Replays historical execution trajectories against locked evaluation suites to detect regressions.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.learning.replay_runner`
- **Registered Providers**: `provider.learning.replay_runner`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `REGRESSION_RESULT_MATCH`
- **Supported Operations** (3):
  - `replay.run_trajectory`
  - `replay.evaluate_regression`
  - `replay.benchmark_providers`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_09_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering learning operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 10_knowledge_management: Knowledge Management

- **Domain**: `knowledge`
- **Purpose**: Ingests, indexes, deduplicates, and manages personal structured and unstructured knowledge.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.knowledge.rag_store`
- **Registered Providers**: `provider.knowledge.rag_store`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `DOCUMENT_INDEX_VERIFICATION`
- **Supported Operations** (5):
  - `knowledge.ingest`
  - `knowledge.index`
  - `knowledge.query`
  - `knowledge.audit_freshness`
  - `knowledge.delete`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_10_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering knowledge operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 11_vision: Vision

- **Domain**: `vision`
- **Purpose**: Understands images, screen UI elements, and performs visual state comparison.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.vision.moondream`
- **Registered Providers**: `provider.vision.ocr`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `VISUAL_DIFF_ANALYSIS`
- **Supported Operations** (3):
  - `vision.analyze_image`
  - `vision.screen_inspect`
  - `vision.visual_diff`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_11_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering vision operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 12_ocr_documents: OCR & Document Intelligence

- **Domain**: `vision`
- **Purpose**: Extracts text, forms, tables, and key-values from scanned documents, images, and PDFs.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.vision.native_win_ocr`
- **Registered Providers**: `provider.vision.ocr`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `TEXT_EXTRACTION_MATCH`
- **Supported Operations** (3):
  - `vision.ocr`
  - `vision.scan_document`
  - `vision.extract_table`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_12_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering vision operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 13_audio_perception: Audio Perception

- **Domain**: `perception`
- **Purpose**: Captures microphone audio, performs local ASR transcription, and detects barge-in.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.audio.whisper_local`
- **Registered Providers**: `provider.audio.whisper_local`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `AUDIO_STREAM_CONFIRMATION`
- **Supported Operations** (4):
  - `audio.capture`
  - `audio.transcribe`
  - `audio.detect_speech`
  - `audio.barge_in`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_13_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering perception operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 14_environmental_perception: Environmental Perception

- **Domain**: `perception`
- **Purpose**: Perceives connected peripherals, active OS processes, and network latency status.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.os.win32`
- **Registered Providers**: `provider.os.win32`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `WIN32_API`
- **Supported Operations** (3):
  - `env.probe_hardware`
  - `env.probe_network`
  - `env.probe_processes`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_14_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering perception operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 15_multimodal_understanding: Multimodal Understanding

- **Domain**: `perception`
- **Purpose**: Fuses vision, audio, screen, and text streams, resolving inter-modality discrepancies.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.multimodal.fused_engine`
- **Registered Providers**: `provider.multimodal.fused_engine`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `FUSION_COHERENCE`
- **Supported Operations** (2):
  - `multimodal.fuse`
  - `multimodal.resolve_conflict`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_15_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering perception operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 16_voice_intelligence: Voice Intelligence

- **Domain**: `voice`
- **Purpose**: Performs neural neural text-to-speech synthesis and streaming Piper audio.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.voice.piper_local`
- **Registered Providers**: `provider.voice.piper_local`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `AUDIO_BUFFER_VERIFICATION`
- **Supported Operations** (3):
  - `voice.synthesize`
  - `voice.stream`
  - `voice.select_profile`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_16_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering voice operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 17_wakeword_intelligence: Wake-Word Intelligence

- **Domain**: `wakeword`
- **Purpose**: Listens for configurable trigger phrases on Windows and Android Sherpa-ONNX.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.wakeword.sherpa_onnx`
- **Registered Providers**: `provider.wakeword.sherpa_onnx`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `WAKE_EVENT_MATCH`
- **Supported Operations** (3):
  - `wakeword.listen`
  - `wakeword.configure`
  - `wakeword.evaluate_false_positives`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_17_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering wakeword operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 18_persona_social: Persona & Social Interaction

- **Domain**: `system`
- **Purpose**: Manages persistent personality (Jarvis, Friday, Ultron) and conversational tone.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.llm.persona_manager`
- **Registered Providers**: `provider.llm.persona_manager`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `PERSONA_STATE_ASSERTION`
- **Supported Operations** (3):
  - `system.switch_persona`
  - `system.set_tone`
  - `system.get_persona`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_18_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering system operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 19_emotion_social: Emotion & Social Context

- **Domain**: `perception`
- **Purpose**: Analyzes urgency, emotional tone, and selects empathetic response styles.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.perception.sentiment`
- **Registered Providers**: `provider.perception.sentiment`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `SENTIMENT_CLASSIFICATION_CHECK`
- **Supported Operations** (2):
  - `emotion.analyze_sentiment`
  - `emotion.detect_urgency`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_19_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering perception operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 20_accessibility: Accessibility

- **Domain**: `system`
- **Purpose**: Provides high-contrast HUD modes, voice navigation alternatives, and screen-reader payloads.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.ui.accessible_payload`
- **Registered Providers**: `provider.ui.accessible_payload`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `PAYLOAD_SCHEMA_VALIDATION`
- **Supported Operations** (2):
  - `accessibility.format_payload`
  - `accessibility.toggle_high_contrast`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_20_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering system operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 21_desktop_os: Desktop / OS Control

- **Domain**: `os`
- **Purpose**: Controls Win32 window geometry, snaps windows, adjusts volume, and captures telemetry.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.os.win32`
- **Registered Providers**: `provider.os.win32`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `WIN32_API_GETWINDOWRECT`
- **Supported Operations** (4):
  - `os.window_management`
  - `os.telemetry`
  - `os.volume_control`
  - `os.process_control`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_21_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering os operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 22_file_storage: File & Storage Intelligence

- **Domain**: `file`
- **Purpose**: Performs scoped filesystem operations (create, move, read, write, hash, delete, archive).
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.file.scoped`
- **Registered Providers**: `provider.file.scoped`
- **Safety Classification**: `DESTRUCTIVE`
- **Verification Strategy**: `PHYSICAL_PATH_EXISTS_AND_HASH`
- **Supported Operations** (9):
  - `file.read`
  - `file.create`
  - `file.search`
  - `file.delete`
  - `file.move`
  - `file.rename`
  - `file.list`
  - `file.compress`
  - `file.extract`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_22_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering file operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 23_browser_intelligence: Browser Intelligence

- **Domain**: `browser`
- **Purpose**: Automates Google Chrome via CDP (port 9222): tab navigation, media playback, DOM interaction.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.browser.chrome_cdp`
- **Registered Providers**: `provider.browser.chrome_cdp`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `CHROME_CDP_TAB_LIST_AND_DOM`
- **Supported Operations** (7):
  - `browser.playback`
  - `browser.media_control`
  - `browser.tab_control`
  - `browser.navigate`
  - `browser.search`
  - `browser.dom_click`
  - `browser.dom_type`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_23_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering browser operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 24_application_intelligence: Application Intelligence

- **Domain**: `os`
- **Purpose**: Discovers, launches, focuses, and inspects native Windows desktop applications.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.app.win32_launcher`
- **Registered Providers**: `provider.app.win32_launcher`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `PROCESS_PID_AND_HWND_EXISTS`
- **Supported Operations** (4):
  - `app.launch`
  - `app.focus`
  - `app.inspect_state`
  - `app.close`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_24_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering os operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 25_shell_sysadmin: Shell & System Administration

- **Domain**: `shell`
- **Purpose**: Executes strictly allowlisted diagnostic commands under zero-arbitrary-shell policy.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.dev.allowlisted_cli`
- **Registered Providers**: `provider.dev.allowlisted_cli`
- **Safety Classification**: `PRIVILEGED`
- **Verification Strategy**: `POLICY_AND_RETURNCODE`
- **Supported Operations** (3):
  - `shell.allowlisted_diagnostics`
  - `shell.network_status`
  - `shell.service_status`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_25_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering shell operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 26_software_engineering: Software Engineering

- **Domain**: `code`
- **Purpose**: Generates code, reviews AST, executes unit tests, and detects bugs in isolated sandboxes.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.dev.git_code`
- **Registered Providers**: `provider.dev.git_code`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `AST_SANDBOX_RETURNCODE`
- **Supported Operations** (4):
  - `code.generation`
  - `code.sandbox_execution`
  - `code.review`
  - `code.dependency_analysis`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_26_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering code operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 27_dev_environment: Development Environment Management

- **Domain**: `dev`
- **Purpose**: Inspects Python virtual environments, installed packages, and build configurations.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.dev.venv_manager`
- **Registered Providers**: `provider.dev.venv_manager`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `PACKAGE_METADATA_PROBE`
- **Supported Operations** (3):
  - `dev.inspect_venv`
  - `dev.audit_packages`
  - `dev.check_build_system`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_27_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering dev operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 28_git_version_control: Git & Version Control

- **Domain**: `git`
- **Purpose**: Manages Git repositories: status, branches, checkout, commit, diff, stash, and merge conflicts.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.dev.git_code`
- **Registered Providers**: `provider.dev.git_code`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `GIT_REV_PARSE_HEAD`
- **Supported Operations** (5):
  - `git.branch_management`
  - `git.status`
  - `git.diff`
  - `git.commit`
  - `git.stash`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_28_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering git operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 29_devops_deployment: DevOps & Deployment

- **Domain**: `devops`
- **Purpose**: Automates build triggers, health checks, staging tests, and rollback actions.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.devops.script_runner`
- **Registered Providers**: `provider.devops.script_runner`
- **Safety Classification**: `PRIVILEGED`
- **Verification Strategy**: `HTTP_200_HEALTH_PROBE`
- **Supported Operations** (3):
  - `devops.run_build`
  - `devops.health_check`
  - `devops.trigger_rollback`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_29_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering devops operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 30_database_backend: Database & Backend Intelligence

- **Domain**: `database`
- **Purpose**: Inspects database schemas, runs safe readonly analytical queries, and tests migrations.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.db.sqlite_local`
- **Registered Providers**: `provider.db.sqlite_local`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `SQLITE_SCHEMA_AND_ROW_CHECK`
- **Supported Operations** (3):
  - `db.inspect_schema`
  - `db.run_readonly_query`
  - `db.validate_migration`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_30_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering database operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 31_web_research: Web Research

- **Domain**: `search`
- **Purpose**: Plans web research, extracts multiple sources, ranks credibility, and provides citations.
- **Status**: `EXTERNAL_DEPENDENCY`
- **Primary Provider**: `provider.web.search_fetch`
- **Registered Providers**: `provider.web.search_fetch`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `HTTP_RESPONSE_AND_CITATION_MATCH`
- **Supported Operations** (3):
  - `search.web`
  - `web.fetch`
  - `search.synthesize_citations`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_31_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering search operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 32_realtime_information: Real-Time Information

- **Domain**: `info`
- **Purpose**: Fetches live weather, market feeds, and news with mandatory freshness timestamping.
- **Status**: `EXTERNAL_DEPENDENCY`
- **Primary Provider**: `provider.info.realtime_feeds`
- **Registered Providers**: `provider.info.realtime_feeds`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `TIMESTAMP_FRESHNESS_CHECK`
- **Supported Operations** (3):
  - `info.get_weather`
  - `info.get_news`
  - `info.verify_freshness`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_32_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering info operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 33_personal_search: Personal Search

- **Domain**: `search`
- **Purpose**: Performs semantic vector and full-text searches across local notes, memories, and files.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.search.personal_vector`
- **Registered Providers**: `provider.search.personal_vector`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `RESULT_SET_GROUNDING`
- **Supported Operations** (4):
  - `search.personal_vector`
  - `search.file_content`
  - `search.interaction_history`
  - `search.multi_source`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_33_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering search operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 34_information_verification: Information Verification

- **Domain**: `verification`
- **Purpose**: Audits factual assertions against observed physical reality, rejecting lying providers.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.verification.information`
- **Registered Providers**: `provider.verification.information`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `PHYSICAL_REALITY_OBSERVATION`
- **Supported Operations** (3):
  - `verification.observe_reality`
  - `verification.cross_reference_claims`
  - `verification.information`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_34_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering verification operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 35_knowledge_synthesis: Knowledge Synthesis

- **Domain**: `cognitive`
- **Purpose**: Combines personal memory, research, and multimodal data into structured briefs with provenance.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.knowledge.synthesis`
- **Registered Providers**: `provider.knowledge.synthesis`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `CITATION_PROVENANCE_CHECK`
- **Supported Operations** (3):
  - `synthesis.combine_sources`
  - `synthesis.generate_brief`
  - `synthesis.synthesize`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_35_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering cognitive operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 36_device_mesh: Device Mesh

- **Domain**: `mesh`
- **Purpose**: Discovers, authenticates, monitors, and routes commands across trusted devices in the user mesh.
- **Status**: `HARDWARE_DEPENDENT`
- **Primary Provider**: `provider.mesh.device_mesh`
- **Registered Providers**: `provider.mesh.device_mesh`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `DEVICE_HANDSHAKE_PING`
- **Supported Operations** (9):
  - `mesh.discover_peers`
  - `mesh.register_device`
  - `mesh.get_device_status`
  - `mesh.route_to_device`
  - `mesh.sync_state`
  - `mesh.device_heartbeat`
  - `mesh.revoke_device`
  - `mesh.select_device`
  - `mesh.set_device_trust`
- **Hardware Requirements**: LAN / Wi-Fi Mesh devices / Smart IoT devices
- **Automated Test Suite**: `tests/test_capability_36_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering mesh operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 37_communication: Communication

- **Domain**: `comm`
- **Purpose**: Performs dynamic contact lookup, draft-first message creation, and two-gate verified dispatch.
- **Status**: `EXTERNAL_DEPENDENCY`
- **Primary Provider**: `provider.comm.communication_hub`
- **Registered Providers**: `provider.comm.communication_hub`
- **Safety Classification**: `EXTERNAL_COMMUNICATION`
- **Verification Strategy**: `OUTBOX_SENT_MESSAGE_VERIFICATION`
- **Supported Operations** (10):
  - `comm.lookup_contact`
  - `comm.register_contact`
  - `comm.draft_email`
  - `comm.send_email`
  - `comm.draft_message`
  - `comm.send_message`
  - `comm.send_whatsapp`
  - `comm.notify_user`
  - `comm.get_history`
  - `comm.verify_delivery`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_37_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering comm operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 38_calendar_scheduling: Calendar & Scheduling

- **Domain**: `scheduler`
- **Purpose**: Manages calendar event lifecycles, timezone-aware queries, conflict detection, and in-app alarms.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.calendar.scheduler`
- **Registered Providers**: `provider.calendar.scheduler, provider.scheduler.apscheduler`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `APSCHEDULER_JOB_EXISTS`
- **Supported Operations** (9):
  - `calendar.create_event`
  - `calendar.get_events`
  - `calendar.modify_event`
  - `calendar.delete_event`
  - `calendar.check_conflicts`
  - `calendar.get_availability`
  - `scheduler.alarm`
  - `scheduler.reminder`
  - `scheduler.interval`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_38_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering scheduler operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 39_personal_productivity: Personal Productivity

- **Domain**: `productivity`
- **Purpose**: Manages personal task queues, triages notifications, and tracks focus routines.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.productivity.local_task`
- **Registered Providers**: `provider.productivity.local_task`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `TASK_PERSISTENCE_AUDIT`
- **Supported Operations** (13):
  - `productivity.create_task`
  - `productivity.add_task`
  - `productivity.get_tasks`
  - `productivity.list_tasks`
  - `productivity.update_task`
  - `productivity.complete_task`
  - `productivity.cancel_task`
  - `productivity.delete_task`
  - `productivity.check_dependencies`
  - `productivity.start_focus_session`
  - `productivity.create_note`
  - `productivity.get_notes`
  - `productivity.triage_notifications`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_39_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering productivity operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 40_travel_navigation: Travel & Navigation

- **Domain**: `travel`
- **Purpose**: Calculates transit routes, travel timing, and organizes trip itineraries.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.travel.transit_maps`
- **Registered Providers**: `provider.travel.transit_maps`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `ROUTE_COHERENCE_CHECK`
- **Supported Operations** (6):
  - `travel.plan_route`
  - `travel.estimate_timing`
  - `travel.build_itinerary`
  - `travel.resolve_location`
  - `travel.search_places`
  - `travel.compare_routes`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_40_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering travel operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 41_autonomous_agency: Autonomous Agency

- **Domain**: `autonomy`
- **Purpose**: Executes background condition watchers, scheduled goals, and proactive environmental actions.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.autonomy.agency_runtime`
- **Registered Providers**: `provider.autonomy.agency_runtime`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `FULL_COGNITIVE_PIPELINE_RECORD`
- **Supported Operations** (8):
  - `autonomy.register_rule`
  - `autonomy.evaluate_triggers`
  - `autonomy.execute_goal`
  - `autonomy.pause_goal`
  - `autonomy.resume_goal`
  - `autonomy.cancel_goal`
  - `autonomy.get_goal_status`
  - `autonomy.recover_goals`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_41_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering autonomy operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 42_workflow_automation: Workflow Automation

- **Domain**: `workflow`
- **Purpose**: Executes multi-step DAG workflows with checkpointing, pause/resume, branching, and crash recovery.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.workflow.runtime_kernel`
- **Registered Providers**: `provider.workflow.runtime_kernel`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `DISK_CHECKPOINT_VERIFICATION`
- **Supported Operations** (11):
  - `workflow.execute_dag`
  - `workflow.define`
  - `workflow.pause`
  - `workflow.resume`
  - `workflow.cancel`
  - `workflow.get_status`
  - `workflow.persist_checkpoint`
  - `workflow.resume_checkpoint`
  - `workflow.approve_gate`
  - `workflow.compensate`
  - `workflow.history`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_42_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering workflow operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 43_monitoring_alerts: Monitoring & Alerts

- **Domain**: `monitor`
- **Purpose**: Monitors system metrics, file events, and emits deduplicated alert notifications.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.monitor.event_alerts`
- **Registered Providers**: `provider.monitor.event_alerts`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `ALERT_EVENT_LOG_VERIFICATION`
- **Supported Operations** (12):
  - `monitor.watch_condition`
  - `monitor.create_rule`
  - `monitor.evaluate_metrics`
  - `monitor.emit_alert`
  - `monitor.deduplicate`
  - `monitor.acknowledge_alert`
  - `monitor.resolve_alert`
  - `monitor.get_alerts`
  - `monitor.pause`
  - `monitor.resume`
  - `monitor.detect_stale`
  - `monitor.escalate_alert`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_43_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering monitor operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 44_smarthome_iot: Smart Home / IoT

- **Domain**: `iot`
- **Purpose**: Controls lights, thermostats, sensors, switches, media cast targets via generic IoT provider abstraction.
- **Status**: `HARDWARE_DEPENDENT`
- **Primary Provider**: `provider.iot.smart_mesh`
- **Registered Providers**: `provider.iot.smart_mesh`
- **Safety Classification**: `PHYSICAL`
- **Verification Strategy**: `HOME_ASSISTANT_API_STATE`
- **Supported Operations** (8):
  - `iot.control_device`
  - `iot.query_state`
  - `iot.cast_media`
  - `iot.discover_devices`
  - `iot.verify_state`
  - `iot.group_devices`
  - `iot.subscribe_events`
  - `iot.set_availability`
- **Hardware Requirements**: LAN / Wi-Fi Mesh devices / Smart IoT devices
- **Automated Test Suite**: `tests/test_capability_44_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering iot operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 45_robotics_interface: Physical / Robotics Interface

- **Domain**: `robotics`
- **Purpose**: Interacts with physical actuators and robotic interfaces under strict physical safety interlocks.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.robotics.physical_interface`
- **Registered Providers**: `provider.robotics.physical_interface`
- **Safety Classification**: `PHYSICAL`
- **Verification Strategy**: `PHYSICAL_INTERLOCK_VERIFICATION`
- **Supported Operations** (15):
  - `robotics.execute_trajectory`
  - `robotics.emergency_stop`
  - `robotics.read_telemetry`
  - `robotics.discover_devices`
  - `robotics.get_capabilities`
  - `robotics.read_sensor`
  - `robotics.execute_command`
  - `robotics.observe_state`
  - `robotics.verify_state`
  - `robotics.reset_emergency_stop`
  - `robotics.set_authorization`
  - `robotics.set_trust`
  - `robotics.get_status`
  - `robotics.register_device`
  - `robotics.remove_device`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_45_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering robotics operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 46_data_science: Data Science & Analytics

- **Domain**: `analytics`
- **Purpose**: Loads tabular datasets, computes statistics, detects anomalies, and generates plots in sandbox.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.analytics.data_science_engine`
- **Registered Providers**: `provider.analytics.data_science_engine`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `DATAFRAME_AND_IMAGE_VERIFICATION`
- **Supported Operations** (14):
  - `analytics.compute_stats`
  - `analytics.generate_plot`
  - `analytics.detect_anomalies`
  - `analytics.load_dataset`
  - `analytics.discover_schema`
  - `analytics.profile_data`
  - `analytics.quality_check`
  - `analytics.aggregate_group`
  - `analytics.filter_sort`
  - `analytics.correlation_analysis`
  - `analytics.distribution_analysis`
  - `analytics.transform_data`
  - `analytics.generate_visualization`
  - `analytics.explain_results`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_46_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering analytics operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 47_simulation_prediction: Simulation & Prediction

- **Domain**: `simulation`
- **Purpose**: Performs what-if scenario simulations and sensitivity analyses with confidence bounds.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.simulation.prediction_engine`
- **Registered Providers**: `provider.simulation.prediction_engine`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `SIMULATION_OUTPUT_BOUNDS_CHECK`
- **Supported Operations** (9):
  - `simulation.run_what_if`
  - `simulation.sensitivity_analysis`
  - `simulation.define_scenario`
  - `simulation.run_simulation`
  - `simulation.predict`
  - `simulation.forecast`
  - `simulation.validate_model`
  - `simulation.compare_scenarios`
  - `simulation.get_provenance`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_47_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering simulation operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 48_security_identity: Security & Identity

- **Domain**: `security`
- **Purpose**: Validates user identity, manages trust and authentication, enforces PolicyKernel rules, verifies Two-Gate tokens, and masks secrets.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.security.identity_manager`
- **Registered Providers**: `provider.security.identity_manager`
- **Safety Classification**: `PRIVILEGED`
- **Verification Strategy**: `POLICY_EVALUATION_ASSERTION`
- **Supported Operations** (18):
  - `security.evaluate_policy`
  - `security.verify_token`
  - `security.mask_credentials`
  - `security.register_identity`
  - `security.authenticate`
  - `security.authorize`
  - `security.evaluate_trust`
  - `security.revoke_trust`
  - `security.register_device`
  - `security.authenticate_device`
  - `security.redact_secrets`
  - `security.create_audit_event`
  - `security.query_audit_events`
  - `security.create_session`
  - `security.validate_session`
  - `security.revoke_session`
  - `security.rotate_credentials`
  - `security.quarantine_prompt`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_48_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering security operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 49_self_diagnostics: Verification & Self-Diagnostics

- **Domain**: `diagnostics`
- **Purpose**: Runs live health checks, verifies provider responsiveness, probes subsystems, and runs regression self-tests.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.diag.system_audit`
- **Registered Providers**: `provider.diag.system_audit`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `SELF_TEST_RESULT_ASSERTION`
- **Supported Operations** (14):
  - `diagnostics.health_check`
  - `diagnostics.audit_providers`
  - `diagnostics.run_self_test`
  - `diagnostics.run_probe`
  - `diagnostics.verify_subsystem`
  - `diagnostics.collect_evidence`
  - `diagnostics.diagnose`
  - `diagnostics.get_status`
  - `diagnostics.verify_memory`
  - `diagnostics.verify_world_model`
  - `diagnostics.verify_autonomy`
  - `diagnostics.verify_security`
  - `diagnostics.verify_providers`
  - `diagnostics.get_diagnostic_report`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_49_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering diagnostics operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

## Capability 50_capability_evolution: Capability Evolution

- **Domain**: `evolution`
- **Purpose**: Detects execution gaps, benchmarks provider versions, manages sandboxed improvement proposals, and tracks progression with rollback.
- **Status**: `IMPLEMENTED`
- **Primary Provider**: `provider.evolution.gap_analyzer`
- **Registered Providers**: `provider.evolution.gap_analyzer`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `REGISTRY_UPDATE_AUDIT`
- **Supported Operations** (14):
  - `evolution.detect_gaps`
  - `evolution.benchmark_provider`
  - `evolution.record_progression`
  - `evolution.create_proposal`
  - `evolution.validate_proposal`
  - `evolution.sandbox_proposal`
  - `evolution.evaluate_proposal`
  - `evolution.submit_for_approval`
  - `evolution.record_human_approval`
  - `evolution.release_version`
  - `evolution.rollback_version`
  - `evolution.get_version_history`
  - `evolution.get_proposal`
  - `evolution.list_proposals`
- **Hardware Requirements**: None (Software-only)
- **Automated Test Suite**: `tests/test_capability_50_*.py`
- **Real-World Test Procedure**: Dispatch natural language command triggering evolution operation, verify side effect and state transition.
- **Anti-Hardcoding Audit**: `CLEAN (0 hardcoded identities / 0 fixture leaks)`

---

