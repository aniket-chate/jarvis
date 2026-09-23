"""JARVIS 50-Capability Central Contract Registry.

Defines the explicit machine-readable contracts for all 50 capability domains in accordance with
the frozen JARVIS Capability Roadmap v1.
"""

from typing import Dict, List, Optional
from capabilities.contracts.schema import CapabilityContract, SafetyClassification


class ContractRegistry50:
    """Central repository storing formal contracts for all 50 capability domains."""

    def __init__(self):
        self._contracts: Dict[str, CapabilityContract] = {}
        self._contracts_by_operation: Dict[str, CapabilityContract] = {}
        self._build_contracts()

    def _register(self, contract: CapabilityContract):
        self._contracts[contract.capability_id] = contract
        for op in contract.supported_operations:
            self._contracts_by_operation[op] = contract

    def get_contract(self, capability_id: str) -> Optional[CapabilityContract]:
        res = self._contracts.get(capability_id)
        if res is None and capability_id == "44_smart_home_iot":
            return self._contracts.get("44_smarthome_iot")
        return res

    def get_contract_for_operation(self, operation: str) -> Optional[CapabilityContract]:
        return self._contracts_by_operation.get(operation)

    def list_all_contracts(self) -> List[CapabilityContract]:
        return list(self._contracts.values())

    def _build_contracts(self):
        # -------------------------------------------------------------
        # Tier 1: Foundational Cognition & Security (1-7, 34, 48)
        # -------------------------------------------------------------
        self._register(CapabilityContract(
            capability_id="01_natural_language",
            name="Natural Language & Conversation",
            domain="chat",
            purpose="Handles multilingual natural conversation, greetings, follow-ups, and style adaptation.",
            supported_operations=["chat.conversation", "chat.greeting", "chat.clarification", "chat.multilingual"],
            primary_provider_id="provider.llm.ollama_local",
            fallback_provider_id="provider.llm.cloud_gemini",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="DEDUCTIVE_COHERENCE",
            timeout_sec=30.0,
        ))

        self._register(CapabilityContract(
            capability_id="02_cognitive_reasoning",
            name="Cognitive Reasoning",
            domain="cognitive",
            purpose="Performs inference, deduction, decomposition, contradiction detection, and hypothesis generation.",
            supported_operations=["reasoning.infer", "reasoning.deduce", "reasoning.decompose", "reasoning.contradiction_check"],
            primary_provider_id="provider.cognitive.reasoning_engine",
            fallback_provider_id="provider.llm.cloud_gemini",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="LOGICAL_CONSISTENCY",
            timeout_sec=35.0,
        ))

        self._register(CapabilityContract(
            capability_id="03_world_model",
            name="World Model",
            domain="cognitive",
            purpose="Maintains physical reality ground truth across windows, browser tabs, files, git, and processes.",
            supported_operations=["world.probe_window", "world.probe_browser", "world.probe_file", "world.probe_git", "world.probe_process"],
            primary_provider_id="provider.cognitive.world_model",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="EMPIRICAL_OBSERVATION",
            timeout_sec=5.0,
        ))

        self._register(CapabilityContract(
            capability_id="04_context_intelligence",
            name="Context Intelligence",
            domain="cognitive",
            purpose="Resolves pronouns ('it', 'that tab', 'that file') and binds working memory across turns.",
            supported_operations=["context.resolve_pronoun", "context.get_active_referent", "context.update_state"],
            primary_provider_id="provider.cognitive.context_engine",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="GROUNDED_STATE_MATCH",
            timeout_sec=2.0,
        ))

        self._register(CapabilityContract(
            capability_id="05_meta_cognition",
            name="Meta-Cognition",
            domain="cognitive",
            purpose="Evaluates uncertainty, detects missing information, and triggers clarification before execution.",
            supported_operations=["meta.estimate_confidence", "meta.detect_uncertainty", "meta.plan_adequacy"],
            primary_provider_id="provider.cognitive.meta_evaluator",
            fallback_provider_id="provider.cognitive.reasoning_engine",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="CONFIDENCE_CALIBRATION",
            timeout_sec=5.0,
        ))

        self._register(CapabilityContract(
            capability_id="06_memory_system",
            name="Memory System",
            domain="memory",
            purpose="Manages 7-tier memory and immutable episodic action ledger.",
            supported_operations=["memory.record_episodic", "memory.query_episodic", "memory.recall_semantic", "memory.update_profile"],
            primary_provider_id="provider.memory.sqlite_vector",
            fallback_provider_id="provider.memory.in_memory",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="LEDGER_STATE_AUDIT",
            timeout_sec=5.0,
        ))

        self._register(CapabilityContract(
            capability_id="07_learning_adaptation",
            name="Learning & Adaptation",
            domain="learning",
            purpose="Captures user corrections, evaluates provider latency/accuracy, and adapts preference weights.",
            supported_operations=["learning.record_experience", "learning.adjust_weights", "learning.get_insights"],
            primary_provider_id="provider.learning.experience_store",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="TELEMETRY_EXPERIENCE_MATCH",
            timeout_sec=5.0,
        ))

        self._register(CapabilityContract(
            capability_id="08_skill_acquisition",
            name="Skill Acquisition",
            domain="skill",
            purpose="Discovers recurring user procedures, creates sandbox tests, and promotes validated workflows.",
            supported_operations=["skill.discover", "skill.sandbox_test", "skill.promote", "skill.retire"],
            primary_provider_id="provider.skill.sandbox_runner",
            safety_classification=SafetyClassification.MODIFYING,
            verification_strategy="SANDBOX_TEST_PASS",
            timeout_sec=30.0,
        ))

        self._register(CapabilityContract(
            capability_id="09_experience_replay",
            name="Experience Replay & Evaluation",
            domain="learning",
            purpose="Replays historical execution trajectories against locked evaluation suites to detect regressions.",
            supported_operations=["replay.run_trajectory", "replay.evaluate_regression", "replay.benchmark_providers"],
            primary_provider_id="provider.learning.replay_runner",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="REGRESSION_RESULT_MATCH",
            timeout_sec=60.0,
        ))

        self._register(CapabilityContract(
            capability_id="10_knowledge_management",
            name="Knowledge Management",
            domain="knowledge",
            purpose="Ingests, indexes, deduplicates, and manages personal structured and unstructured knowledge.",
            supported_operations=["knowledge.ingest", "knowledge.index", "knowledge.query", "knowledge.audit_freshness", "knowledge.delete"],
            primary_provider_id="provider.knowledge.rag_store",
            fallback_provider_id="provider.file.scoped",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="DOCUMENT_INDEX_VERIFICATION",
            timeout_sec=15.0,
        ))

        # -------------------------------------------------------------
        # Tier 2: Perception Fabric (11-15, 17)
        # -------------------------------------------------------------
        self._register(CapabilityContract(
            capability_id="11_vision",
            name="Vision",
            domain="vision",
            purpose="Understands images, screen UI elements, and performs visual state comparison.",
            supported_operations=["vision.analyze_image", "vision.screen_inspect", "vision.visual_diff"],
            primary_provider_id="provider.vision.moondream",
            fallback_provider_id="provider.vision.cloud_gemini",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="VISUAL_DIFF_ANALYSIS",
            timeout_sec=20.0,
        ))

        self._register(CapabilityContract(
            capability_id="12_ocr_documents",
            name="OCR & Document Intelligence",
            domain="vision",
            purpose="Extracts text, forms, tables, and key-values from scanned documents, images, and PDFs.",
            supported_operations=["vision.ocr", "vision.scan_document", "vision.extract_table"],
            primary_provider_id="provider.vision.native_win_ocr",
            fallback_provider_id="provider.vision.tesseract",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="TEXT_EXTRACTION_MATCH",
            timeout_sec=15.0,
        ))

        self._register(CapabilityContract(
            capability_id="13_audio_perception",
            name="Audio Perception",
            domain="perception",
            purpose="Captures microphone audio, performs local ASR transcription, and detects barge-in.",
            supported_operations=["audio.capture", "audio.transcribe", "audio.detect_speech", "audio.barge_in"],
            primary_provider_id="provider.audio.whisper_local",
            fallback_provider_id="provider.audio.android_mic",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="AUDIO_STREAM_CONFIRMATION",
            timeout_sec=10.0,
        ))

        self._register(CapabilityContract(
            capability_id="14_environmental_perception",
            name="Environmental Perception",
            domain="perception",
            purpose="Perceives connected peripherals, active OS processes, and network latency status.",
            supported_operations=["env.probe_hardware", "env.probe_network", "env.probe_processes"],
            primary_provider_id="provider.os.win32",
            fallback_provider_id="provider.os.psutil",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="WIN32_API",
            timeout_sec=5.0,
        ))

        self._register(CapabilityContract(
            capability_id="15_multimodal_understanding",
            name="Multimodal Understanding",
            domain="perception",
            purpose="Fuses vision, audio, screen, and text streams, resolving inter-modality discrepancies.",
            supported_operations=["multimodal.fuse", "multimodal.resolve_conflict"],
            primary_provider_id="provider.multimodal.fused_engine",
            fallback_provider_id="provider.llm.cloud_gemini",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="FUSION_COHERENCE",
            timeout_sec=25.0,
        ))

        self._register(CapabilityContract(
            capability_id="16_voice_intelligence",
            name="Voice Intelligence",
            domain="voice",
            purpose="Performs neural neural text-to-speech synthesis and streaming Piper audio.",
            supported_operations=["voice.synthesize", "voice.stream", "voice.select_profile"],
            primary_provider_id="provider.voice.piper_local",
            fallback_provider_id="provider.voice.android_tts",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="AUDIO_BUFFER_VERIFICATION",
            timeout_sec=10.0,
        ))

        self._register(CapabilityContract(
            capability_id="17_wakeword_intelligence",
            name="Wake-Word Intelligence",
            domain="wakeword",
            purpose="Listens for configurable trigger phrases on Windows and Android Sherpa-ONNX.",
            supported_operations=["wakeword.listen", "wakeword.configure", "wakeword.evaluate_false_positives"],
            primary_provider_id="provider.wakeword.sherpa_onnx",
            fallback_provider_id="provider.wakeword.openwake_word",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="WAKE_EVENT_MATCH",
            timeout_sec=5.0,
        ))

        # -------------------------------------------------------------
        # Tier 3: Interaction & Social Fabric (18-20)
        # -------------------------------------------------------------
        self._register(CapabilityContract(
            capability_id="18_persona_social",
            name="Persona & Social Interaction",
            domain="system",
            purpose="Manages persistent personality (Jarvis, Friday, Ultron) and conversational tone.",
            supported_operations=["system.switch_persona", "system.set_tone", "system.get_persona"],
            primary_provider_id="provider.llm.persona_manager",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="PERSONA_STATE_ASSERTION",
            timeout_sec=2.0,
        ))

        self._register(CapabilityContract(
            capability_id="19_emotion_social",
            name="Emotion & Social Context",
            domain="perception",
            purpose="Analyzes urgency, emotional tone, and selects empathetic response styles.",
            supported_operations=["emotion.analyze_sentiment", "emotion.detect_urgency"],
            primary_provider_id="provider.perception.sentiment",
            fallback_provider_id="provider.llm.ollama_local",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="SENTIMENT_CLASSIFICATION_CHECK",
            timeout_sec=5.0,
        ))

        self._register(CapabilityContract(
            capability_id="20_accessibility",
            name="Accessibility",
            domain="system",
            purpose="Provides high-contrast HUD modes, voice navigation alternatives, and screen-reader payloads.",
            supported_operations=["accessibility.format_payload", "accessibility.toggle_high_contrast"],
            primary_provider_id="provider.ui.accessible_payload",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="PAYLOAD_SCHEMA_VALIDATION",
            timeout_sec=2.0,
        ))

        # -------------------------------------------------------------
        # Tier 4: Computer Control & Engineering (21-28)
        # -------------------------------------------------------------
        self._register(CapabilityContract(
            capability_id="21_desktop_os",
            name="Desktop / OS Control",
            domain="os",
            purpose="Controls Win32 window geometry, snaps windows, adjusts volume, and captures telemetry.",
            supported_operations=["os.window_management", "os.telemetry", "os.volume_control", "os.process_control"],
            primary_provider_id="provider.os.win32",
            fallback_provider_id="provider.os.pyautogui",
            safety_classification=SafetyClassification.MODIFYING,
            verification_strategy="WIN32_API_GETWINDOWRECT",
            timeout_sec=10.0,
        ))

        self._register(CapabilityContract(
            capability_id="22_file_storage",
            name="File & Storage Intelligence",
            domain="file",
            purpose="Performs scoped filesystem operations (create, move, read, write, hash, delete, archive).",
            supported_operations=["file.read", "file.create", "file.search", "file.delete", "file.move", "file.rename", "file.list", "file.compress", "file.extract"],
            primary_provider_id="provider.file.scoped",
            fallback_provider_id="provider.file.python_shutil",
            safety_classification=SafetyClassification.DESTRUCTIVE,
            requires_two_gate_confirmation=True,
            verification_strategy="PHYSICAL_PATH_EXISTS_AND_HASH",
            timeout_sec=15.0,
        ))

        self._register(CapabilityContract(
            capability_id="23_browser_intelligence",
            name="Browser Intelligence",
            domain="browser",
            purpose="Automates Google Chrome via CDP (port 9222): tab navigation, media playback, DOM interaction.",
            supported_operations=["browser.playback", "browser.media_control", "browser.tab_control", "browser.navigate", "browser.search", "browser.dom_click", "browser.dom_type"],
            primary_provider_id="provider.browser.chrome_cdp",
            fallback_provider_id="provider.browser.playwright",
            safety_classification=SafetyClassification.MODIFYING,
            verification_strategy="CHROME_CDP_TAB_LIST_AND_DOM",
            timeout_sec=25.0,
        ))

        self._register(CapabilityContract(
            capability_id="24_application_intelligence",
            name="Application Intelligence",
            domain="os",
            purpose="Discovers, launches, focuses, and inspects native Windows desktop applications.",
            supported_operations=["app.launch", "app.focus", "app.inspect_state", "app.close"],
            primary_provider_id="provider.app.win32_launcher",
            fallback_provider_id="provider.os.win32",
            safety_classification=SafetyClassification.MODIFYING,
            verification_strategy="PROCESS_PID_AND_HWND_EXISTS",
            timeout_sec=15.0,
        ))

        self._register(CapabilityContract(
            capability_id="25_shell_sysadmin",
            name="Shell & System Administration",
            domain="shell",
            purpose="Executes strictly allowlisted diagnostic commands under zero-arbitrary-shell policy.",
            supported_operations=["shell.allowlisted_diagnostics", "shell.network_status", "shell.service_status"],
            primary_provider_id="provider.dev.allowlisted_cli",
            safety_classification=SafetyClassification.PRIVILEGED,
            verification_strategy="POLICY_AND_RETURNCODE",
            timeout_sec=15.0,
        ))

        self._register(CapabilityContract(
            capability_id="26_software_engineering",
            name="Software Engineering",
            domain="code",
            purpose="Generates code, reviews AST, executes unit tests, and detects bugs in isolated sandboxes.",
            supported_operations=["code.generation", "code.sandbox_execution", "code.review", "code.dependency_analysis"],
            primary_provider_id="provider.dev.git_code",
            fallback_provider_id="provider.llm.cloud_gemini",
            safety_classification=SafetyClassification.MODIFYING,
            verification_strategy="AST_SANDBOX_RETURNCODE",
            timeout_sec=30.0,
        ))

        self._register(CapabilityContract(
            capability_id="27_dev_environment",
            name="Development Environment Management",
            domain="dev",
            purpose="Inspects Python virtual environments, installed packages, and build configurations.",
            supported_operations=["dev.inspect_venv", "dev.audit_packages", "dev.check_build_system"],
            primary_provider_id="provider.dev.venv_manager",
            fallback_provider_id="provider.dev.git_code",
            safety_classification=SafetyClassification.MODIFYING,
            verification_strategy="PACKAGE_METADATA_PROBE",
            timeout_sec=15.0,
        ))

        self._register(CapabilityContract(
            capability_id="28_git_version_control",
            name="Git & Version Control",
            domain="git",
            purpose="Manages Git repositories: status, branches, checkout, commit, diff, stash, and merge conflicts.",
            supported_operations=["git.branch_management", "git.status", "git.diff", "git.commit", "git.stash"],
            primary_provider_id="provider.dev.git_code",
            fallback_provider_id="provider.dev.git_cli",
            safety_classification=SafetyClassification.MODIFYING,
            verification_strategy="GIT_REV_PARSE_HEAD",
            timeout_sec=15.0,
        ))

        # -------------------------------------------------------------
        # Tier 5: Information & Knowledge (29-33, 35)
        # -------------------------------------------------------------
        self._register(CapabilityContract(
            capability_id="29_devops_deployment",
            name="DevOps & Deployment",
            domain="devops",
            purpose="Automates build triggers, health checks, staging tests, and rollback actions.",
            supported_operations=["devops.run_build", "devops.health_check", "devops.trigger_rollback"],
            primary_provider_id="provider.devops.script_runner",
            fallback_provider_id="provider.dev.git_code",
            safety_classification=SafetyClassification.PRIVILEGED,
            requires_two_gate_confirmation=True,
            verification_strategy="HTTP_200_HEALTH_PROBE",
            timeout_sec=45.0,
        ))

        self._register(CapabilityContract(
            capability_id="30_database_backend",
            name="Database & Backend Intelligence",
            domain="database",
            purpose="Inspects database schemas, runs safe readonly analytical queries, and tests migrations.",
            supported_operations=["db.inspect_schema", "db.run_readonly_query", "db.validate_migration"],
            primary_provider_id="provider.db.sqlite_local",
            fallback_provider_id="provider.db.schema_inspector",
            safety_classification=SafetyClassification.MODIFYING,
            verification_strategy="SQLITE_SCHEMA_AND_ROW_CHECK",
            timeout_sec=15.0,
        ))

        self._register(CapabilityContract(
            capability_id="31_web_research",
            name="Web Research",
            domain="search",
            purpose="Plans web research, extracts multiple sources, ranks credibility, and provides citations.",
            supported_operations=["search.web", "web.fetch", "search.synthesize_citations"],
            primary_provider_id="provider.web.search_fetch",
            fallback_provider_id="provider.web.tavily_api",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="HTTP_RESPONSE_AND_CITATION_MATCH",
            timeout_sec=20.0,
        ))

        self._register(CapabilityContract(
            capability_id="32_realtime_information",
            name="Real-Time Information",
            domain="info",
            purpose="Fetches live weather, market feeds, and news with mandatory freshness timestamping.",
            supported_operations=["info.get_weather", "info.get_news", "info.verify_freshness"],
            primary_provider_id="provider.info.realtime_feeds",
            fallback_provider_id="provider.web.search_fetch",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="TIMESTAMP_FRESHNESS_CHECK",
            timeout_sec=10.0,
        ))

        self._register(CapabilityContract(
            capability_id="33_personal_search",
            name="Personal Search",
            domain="search",
            purpose="Performs semantic vector and full-text searches across local notes, memories, and files.",
            supported_operations=["search.personal_vector", "search.file_content", "search.interaction_history", "search.multi_source"],
            primary_provider_id="provider.search.personal_vector",
            fallback_provider_id="provider.file.scoped",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="RESULT_SET_GROUNDING",
            timeout_sec=10.0,
        ))

        self._register(CapabilityContract(
            capability_id="34_information_verification",
            name="Information Verification",
            domain="verification",
            purpose="Audits factual assertions against observed physical reality, rejecting lying providers.",
            supported_operations=["verification.observe_reality", "verification.cross_reference_claims", "verification.information"],
            primary_provider_id="provider.verification.information",
            fallback_provider_id="provider.verification.verifier",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="PHYSICAL_REALITY_OBSERVATION",
            timeout_sec=5.0,
        ))

        self._register(CapabilityContract(
            capability_id="35_knowledge_synthesis",
            name="Knowledge Synthesis",
            domain="cognitive",
            purpose="Combines personal memory, research, and multimodal data into structured briefs with provenance.",
            supported_operations=["synthesis.combine_sources", "synthesis.generate_brief", "synthesis.synthesize"],
            primary_provider_id="provider.knowledge.synthesis",
            fallback_provider_id="provider.cognitive.synthesizer",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="CITATION_PROVENANCE_CHECK",
            timeout_sec=25.0,
        ))

        # -------------------------------------------------------------
        # Tier 6: Automation, Agency & Productivity (36-43)
        # -------------------------------------------------------------
        self._register(CapabilityContract(
            capability_id="36_device_mesh",
            name="Device Mesh",
            domain="mesh",
            purpose="Discovers, authenticates, monitors, and routes commands across trusted devices in the user mesh.",
            supported_operations=[
                "mesh.discover_peers",
                "mesh.register_device",
                "mesh.get_device_status",
                "mesh.route_to_device",
                "mesh.sync_state",
                "mesh.device_heartbeat",
                "mesh.revoke_device",
                "mesh.select_device",
                "mesh.set_device_trust",
            ],
            primary_provider_id="provider.mesh.device_mesh",
            fallback_provider_id="provider.mesh.local_lan",
            safety_classification=SafetyClassification.MODIFYING,
            verification_strategy="DEVICE_HANDSHAKE_PING",
            timeout_sec=15.0,
        ))

        self._register(CapabilityContract(
            capability_id="37_communication",
            name="Communication",
            domain="comm",
            purpose="Performs dynamic contact lookup, draft-first message creation, and two-gate verified dispatch.",
            supported_operations=[
                "comm.lookup_contact",
                "comm.register_contact",
                "comm.draft_email",
                "comm.send_email",
                "comm.draft_message",
                "comm.send_message",
                "comm.send_whatsapp",
                "comm.notify_user",
                "comm.get_history",
                "comm.verify_delivery",
            ],
            primary_provider_id="provider.comm.communication_hub",
            fallback_provider_id="provider.comm.google_gmail",
            safety_classification=SafetyClassification.EXTERNAL_COMMUNICATION,
            requires_two_gate_confirmation=True,
            verification_strategy="OUTBOX_SENT_MESSAGE_VERIFICATION",
            timeout_sec=20.0,
        ))

        self._register(CapabilityContract(
            capability_id="38_calendar_scheduling",
            name="Calendar & Scheduling",
            domain="scheduler",
            purpose="Manages calendar event lifecycles, timezone-aware queries, conflict detection, and in-app alarms.",
            supported_operations=[
                "calendar.create_event",
                "calendar.get_events",
                "calendar.modify_event",
                "calendar.delete_event",
                "calendar.check_conflicts",
                "calendar.get_availability",
                "scheduler.alarm",
                "scheduler.reminder",
                "scheduler.interval",
            ],
            primary_provider_id="provider.calendar.scheduler",
            fallback_provider_id="provider.scheduler.apscheduler",
            safety_classification=SafetyClassification.MODIFYING,
            verification_strategy="APSCHEDULER_JOB_EXISTS",
            timeout_sec=10.0,
        ))

        self._register(CapabilityContract(
            capability_id="39_personal_productivity",
            name="Personal Productivity",
            domain="productivity",
            purpose="Manages personal task queues, triages notifications, and tracks focus routines.",
            supported_operations=[
                "productivity.create_task",
                "productivity.add_task",
                "productivity.get_tasks",
                "productivity.list_tasks",
                "productivity.update_task",
                "productivity.complete_task",
                "productivity.cancel_task",
                "productivity.delete_task",
                "productivity.check_dependencies",
                "productivity.start_focus_session",
                "productivity.create_note",
                "productivity.get_notes",
                "productivity.triage_notifications",
            ],
            primary_provider_id="provider.productivity.local_task",
            fallback_provider_id="provider.productivity.in_memory",
            safety_classification=SafetyClassification.MODIFYING,
            verification_strategy="TASK_PERSISTENCE_AUDIT",
            timeout_sec=10.0,
        ))

        self._register(CapabilityContract(
            capability_id="40_travel_navigation",
            name="Travel & Navigation",
            domain="travel",
            purpose="Calculates transit routes, travel timing, and organizes trip itineraries.",
            supported_operations=[
                "travel.plan_route",
                "travel.estimate_timing",
                "travel.build_itinerary",
                "travel.resolve_location",
                "travel.search_places",
                "travel.compare_routes",
            ],
            primary_provider_id="provider.travel.transit_maps",
            fallback_provider_id="provider.travel.mock_osm",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="ROUTE_COHERENCE_CHECK",
            timeout_sec=15.0,
        ))

        self._register(CapabilityContract(
            capability_id="41_autonomous_agency",
            name="Autonomous Agency",
            domain="autonomy",
            purpose="Executes background condition watchers, scheduled goals, and proactive environmental actions.",
            supported_operations=[
                "autonomy.register_rule",
                "autonomy.evaluate_triggers",
                "autonomy.execute_goal",
                "autonomy.pause_goal",
                "autonomy.resume_goal",
                "autonomy.cancel_goal",
                "autonomy.get_goal_status",
                "autonomy.recover_goals",
            ],
            primary_provider_id="provider.autonomy.agency_runtime",
            fallback_provider_id="provider.autonomy.local_watcher",
            safety_classification=SafetyClassification.MODIFYING,
            verification_strategy="FULL_COGNITIVE_PIPELINE_RECORD",
            timeout_sec=30.0,
        ))

        self._register(CapabilityContract(
            capability_id="42_workflow_automation",
            name="Workflow Automation",
            domain="workflow",
            purpose="Executes multi-step DAG workflows with checkpointing, pause/resume, branching, and crash recovery.",
            supported_operations=[
                "workflow.execute_dag",
                "workflow.define",
                "workflow.pause",
                "workflow.resume",
                "workflow.cancel",
                "workflow.get_status",
                "workflow.persist_checkpoint",
                "workflow.resume_checkpoint",
                "workflow.approve_gate",
                "workflow.compensate",
                "workflow.history",
            ],
            primary_provider_id="provider.workflow.runtime_kernel",
            fallback_provider_id="provider.workflow.dag_engine",
            safety_classification=SafetyClassification.MODIFYING,
            checkpoint_required=True,
            verification_strategy="DISK_CHECKPOINT_VERIFICATION",
            timeout_sec=60.0,
        ))

        self._register(CapabilityContract(
            capability_id="43_monitoring_alerts",
            name="Monitoring & Alerts",
            domain="monitor",
            purpose="Monitors system metrics, file events, and emits deduplicated alert notifications.",
            supported_operations=[
                "monitor.watch_condition",
                "monitor.create_rule",
                "monitor.evaluate_metrics",
                "monitor.emit_alert",
                "monitor.deduplicate",
                "monitor.acknowledge_alert",
                "monitor.resolve_alert",
                "monitor.get_alerts",
                "monitor.pause",
                "monitor.resume",
                "monitor.detect_stale",
                "monitor.escalate_alert",
            ],
            primary_provider_id="provider.monitor.event_alerts",
            fallback_provider_id="provider.monitor.threshold_poll",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="ALERT_EVENT_LOG_VERIFICATION",
            timeout_sec=10.0,
        ))

        # -------------------------------------------------------------
        # Tier 7: Advanced & Specialized Integrations (44-50)
        # -------------------------------------------------------------
        self._register(CapabilityContract(
            capability_id="44_smarthome_iot",
            name="Smart Home / IoT",
            domain="iot",
            purpose="Controls lights, thermostats, sensors, switches, media cast targets via generic IoT provider abstraction.",
            supported_operations=[
                "iot.control_device",
                "iot.query_state",
                "iot.cast_media",
                "iot.discover_devices",
                "iot.verify_state",
                "iot.group_devices",
                "iot.subscribe_events",
                "iot.set_availability",
            ],
            primary_provider_id="provider.iot.smart_mesh",
            fallback_provider_id="provider.iot.home_assistant",
            safety_classification=SafetyClassification.PHYSICAL,
            requires_two_gate_confirmation=True,
            verification_strategy="HOME_ASSISTANT_API_STATE",
            timeout_sec=15.0,
        ))

        self._register(CapabilityContract(
            capability_id="45_robotics_interface",
            name="Physical / Robotics Interface",
            domain="robotics",
            purpose="Interacts with physical actuators and robotic interfaces under strict physical safety interlocks.",
            supported_operations=[
                "robotics.execute_trajectory",
                "robotics.emergency_stop",
                "robotics.read_telemetry",
                "robotics.discover_devices",
                "robotics.get_capabilities",
                "robotics.read_sensor",
                "robotics.execute_command",
                "robotics.observe_state",
                "robotics.verify_state",
                "robotics.reset_emergency_stop",
                "robotics.set_authorization",
                "robotics.set_trust",
                "robotics.get_status",
                "robotics.register_device",
                "robotics.remove_device",
            ],
            primary_provider_id="provider.robotics.physical_interface",
            fallback_provider_id="provider.robotics.mock_interlock",
            safety_classification=SafetyClassification.PHYSICAL,
            requires_two_gate_confirmation=True,
            verification_strategy="PHYSICAL_INTERLOCK_VERIFICATION",
            timeout_sec=5.0,
        ))

        self._register(CapabilityContract(
            capability_id="46_data_science",
            name="Data Science & Analytics",
            domain="analytics",
            purpose="Loads tabular datasets, computes statistics, detects anomalies, and generates plots in sandbox.",
            supported_operations=[
                "analytics.compute_stats",
                "analytics.generate_plot",
                "analytics.detect_anomalies",
                "analytics.load_dataset",
                "analytics.discover_schema",
                "analytics.profile_data",
                "analytics.quality_check",
                "analytics.aggregate_group",
                "analytics.filter_sort",
                "analytics.correlation_analysis",
                "analytics.distribution_analysis",
                "analytics.transform_data",
                "analytics.generate_visualization",
                "analytics.explain_results",
            ],
            primary_provider_id="provider.analytics.data_science_engine",
            fallback_provider_id="provider.analytics.python_sandbox",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="DATAFRAME_AND_IMAGE_VERIFICATION",
            timeout_sec=30.0,
        ))

        self._register(CapabilityContract(
            capability_id="47_simulation_prediction",
            name="Simulation & Prediction",
            domain="simulation",
            purpose="Performs what-if scenario simulations and sensitivity analyses with confidence bounds.",
            supported_operations=[
                "simulation.run_what_if",
                "simulation.sensitivity_analysis",
                "simulation.define_scenario",
                "simulation.run_simulation",
                "simulation.predict",
                "simulation.forecast",
                "simulation.validate_model",
                "simulation.compare_scenarios",
                "simulation.get_provenance",
            ],
            primary_provider_id="provider.simulation.prediction_engine",
            fallback_provider_id="provider.sim.monte_carlo",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="SIMULATION_OUTPUT_BOUNDS_CHECK",
            timeout_sec=30.0,
        ))

        self._register(CapabilityContract(
            capability_id="48_security_identity",
            name="Security & Identity",
            domain="security",
            purpose="Validates user identity, manages trust and authentication, enforces PolicyKernel rules, verifies Two-Gate tokens, and masks secrets.",
            supported_operations=[
                "security.evaluate_policy",
                "security.verify_token",
                "security.mask_credentials",
                "security.register_identity",
                "security.authenticate",
                "security.authorize",
                "security.evaluate_trust",
                "security.revoke_trust",
                "security.register_device",
                "security.authenticate_device",
                "security.redact_secrets",
                "security.create_audit_event",
                "security.query_audit_events",
                "security.create_session",
                "security.validate_session",
                "security.revoke_session",
                "security.rotate_credentials",
                "security.quarantine_prompt",
            ],
            primary_provider_id="provider.security.identity_manager",
            fallback_provider_id="provider.safety.policy_kernel",
            safety_classification=SafetyClassification.PRIVILEGED,
            verification_strategy="POLICY_EVALUATION_ASSERTION",
            timeout_sec=5.0,
        ))

        self._register(CapabilityContract(
            capability_id="49_self_diagnostics",
            name="Verification & Self-Diagnostics",
            domain="diagnostics",
            purpose="Runs live health checks, verifies provider responsiveness, probes subsystems, and runs regression self-tests.",
            supported_operations=[
                "diagnostics.health_check",
                "diagnostics.audit_providers",
                "diagnostics.run_self_test",
                "diagnostics.run_probe",
                "diagnostics.verify_subsystem",
                "diagnostics.collect_evidence",
                "diagnostics.diagnose",
                "diagnostics.get_status",
                "diagnostics.verify_memory",
                "diagnostics.verify_world_model",
                "diagnostics.verify_autonomy",
                "diagnostics.verify_security",
                "diagnostics.verify_providers",
                "diagnostics.get_diagnostic_report",
            ],
            primary_provider_id="provider.diag.system_audit",
            fallback_provider_id="provider.verification.verifier",
            safety_classification=SafetyClassification.READ_ONLY,
            verification_strategy="SELF_TEST_RESULT_ASSERTION",
            timeout_sec=60.0,
        ))

        self._register(CapabilityContract(
            capability_id="50_capability_evolution",
            name="Capability Evolution",
            domain="evolution",
            purpose="Detects execution gaps, benchmarks provider versions, manages sandboxed improvement proposals, and tracks progression with rollback.",
            supported_operations=[
                "evolution.detect_gaps",
                "evolution.benchmark_provider",
                "evolution.record_progression",
                "evolution.create_proposal",
                "evolution.validate_proposal",
                "evolution.sandbox_proposal",
                "evolution.evaluate_proposal",
                "evolution.submit_for_approval",
                "evolution.record_human_approval",
                "evolution.release_version",
                "evolution.rollback_version",
                "evolution.get_version_history",
                "evolution.get_proposal",
                "evolution.list_proposals",
            ],
            primary_provider_id="provider.evolution.gap_analyzer",
            safety_classification=SafetyClassification.MODIFYING,
            verification_strategy="REGISTRY_UPDATE_AUDIT",
            timeout_sec=15.0,
        ))


contract_registry_50 = ContractRegistry50()
