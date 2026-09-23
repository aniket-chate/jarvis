# JARVIS Real Capability Verification Test Matrix (Capabilities 1–50)

## Overview
This document specifies the end-to-end real functional verification scenarios for all 50 JARVIS capabilities.
In accordance with the frozen Capability Roadmap v1, every test adheres to the mandatory verification lifecycle:
```
USER REQUEST 
  ↓ 
UNDERSTANDING (Intent & Entity Parsing)
  ↓ 
CAPABILITY SELECTION (Contract Registry)
  ↓ 
PROVIDER SELECTION & DISPATCH
  ↓ 
EXECUTION (Action Dispatch)
  ↓ 
REAL / OBSERVED RESULT (State Query)
  ↓ 
VERIFICATION (Physical / Ground-Truth Check)
  ↓ 
USER-FACING RESULT
```
Self-reported success is strictly rejected: all side-effecting operations require independent world-state observation (file system presence, database rows, memory recall, or kinematic state).

---

## Capabilities 1–50 End-to-End Verification Matrix

| ID | Capability Name | User Request Scenario | Understanding & Intent | Provider | Real World State Observed & Verified | Result |
|---|---|---|---|---|---|---|
| **01** | Natural Language & Conversation | *"Explain quantum superposition in simple terms."* | Intent: `chat.conversation`, topic: `quantum` | `OllamaLLMProvider` | Generated response contains explanation of superposition and wave-particle duality. Coherence verified. | PASS |
| **02** | Cognitive Reasoning | *"If all servers in us-east are down, can we route to eu-west?"* | Intent: `reasoning.deduce`, facts: `failover policy` | `CognitiveReasoningEngine` | Logical deduction result confirms routing availability under active constraints. Non-empty reasoning tree verified. | PASS |
| **03** | World Model Reality | *"What window is currently in the foreground?"* | Intent: `world.probe_window` | `WorldModelProvider` | Queries Win32 OS window list; verifies non-empty title, process name, and PID. Reality verified. | PASS |
| **04** | Context Intelligence | *"What was the file we discussed three turns ago?"* | Intent: `context.resolve_pronoun`, referent: `file` | `ContextEngine` | Resolved referent matches the stored file object in context history. | PASS |
| **05** | Meta-Cognition | *"Delete the entire production cluster right now."* | Intent: `meta.plan_adequacy`, risk: `critical` | `MetaEvaluator` | Detects critical risk, calculates high uncertainty/destructive impact, flags mandatory confirmation. | PASS |
| **06** | 7-Tier Memory System | *"Remember that my primary server IP is 192.168.1.100."* | Intent: `memory.record_episodic` | `UnifiedMemory` | Writes to SQLite episodic table; independently queries DB to verify stored key-value record exists. | PASS |
| **07** | Learning & Adaptation | *"I prefer short concise answers when writing code."* | Intent: `learning.update_profile`, pref: `brevity` | `LearningAdapter` | Updates user preference profile in persistent store; verifies profile reload returns brevity preference. | PASS |
| **08** | Skill Acquisition | *"Register new command macro for git status and diff."* | Intent: `skill.register_macro` | `SkillRegistry` | Macro registered in dynamic skill table; verified callable with expected execution signature. | PASS |
| **09** | Experience Replay | *"Replay the error log from the previous deployment."* | Intent: `learning.replay_episode` | `ExperienceReplay` | Retrieves execution trace from SQLite historical logs; verifies chronological step ordering. | PASS |
| **10** | Knowledge Management | *"Ingest system architecture summary into knowledge base."* | Intent: `knowledge.ingest_document` | `KnowledgeEngine` | Embeds text and indexes into vector store; verifies query returns matching semantic chunk. | PASS |
| **11** | Vision & Screen Inspection | *"Inspect the current screen layout."* | Intent: `vision.screen_inspect` | `VisionProvider` | Captures screen buffer via MSS/Pillow; verifies image dimensions (width, height > 0) and non-empty byte buffer. | PASS |
| **12** | OCR & Document Reading | *"Read the text in the error screenshot."* | Intent: `vision.ocr`, target: `image buffer` | `VisionProvider` | OCR parses image buffer; verifies extracted string matches ground-truth test text. | PASS |
| **13** | Audio Perception & VAD | *"Listen for voice command in background audio."* | Intent: `audio.detect_speech` | `AudioProvider` | Processes audio float array; verifies silence detected on zero-array and speech detected on signal. | PASS |
| **14** | Environmental Perception | *"Check CPU and memory load of this machine."* | Intent: `env.probe_hardware` | `EnvironmentProvider` | Queries psutil/OS hardware counters; verifies CPU % in [0, 100] and RAM % in [0, 100]. | PASS |
| **15** | Multimodal Understanding | *"Combine image and audio stream to determine presence."* | Intent: `multimodal.fuse_streams` | `MultimodalProvider` | Fuses visual bounding box and audio energy into joint presence event. State verified. | PASS |
| **16** | Voice Intelligence & TTS | *"Speak notification: Backup completed."* | Intent: `voice.synthesize_speech` | `VoiceProvider` | Generates speech waveform buffer; verifies audio samples generated with non-zero duration. | PASS |
| **17** | Wake Word Intelligence | *"Listen for wake word 'Jarvis'."* | Intent: `wakeword.evaluate_stream` | `WakeWordProvider` | Processes audio frame; verifies score calculated against 0.75 threshold. | PASS |
| **18** | Persona & Social Dynamics | *"Switch persona tone to formal and concise."* | Intent: `persona.update_style` | `PersonaProvider` | Updates active persona config; verifies settings.active_persona reflects new configuration. | PASS |
| **19** | Emotion & Tone Perception | *"Analyze tone of incoming email: 'Urgent fix needed immediately!'."* | Intent: `emotion.analyze_sentiment` | `EmotionProvider` | Analyzes text sentiment; verifies urgency=HIGH and emotional valence detected accurately. | PASS |
| **20** | Accessibility & UI Control | *"Enable high-contrast mode for screen reader."* | Intent: `accessibility.set_mode` | `AccessibilityProvider` | Sets accessibility profile flags; verifies active screen narration state updated. | PASS |
| **21** | Desktop OS Control | *"Mute system volume temporarily."* | Intent: `os.volume_control`, target: `mute` | `DesktopControlProvider` | Executes Win32/pycaw audio endpoint call; verifies master mute state confirmed. | PASS |
| **22** | File & Storage Management | *"Create a test configuration file at data/test_audit.json."* | Intent: `file.create`, path: `data/test_audit.json` | `FileStorageProvider` | Writes file to disk; independently reads file using `os.path.exists` and verifies contents match. | PASS |
| **23** | Browser Intelligence | *"Open browser and navigate to internal status endpoint."* | Intent: `browser.navigate`, url: `http://127.0.0.1:8765/` | `BrowserProvider` | Launches headless/playwright session; verifies URL loaded and DOM root element exists. | PASS |
| **24** | Application Intelligence | *"Focus or launch notepad.exe."* | Intent: `app.launch_or_focus`, name: `notepad` | `AppIntelligenceProvider` | Checks process tree via win32/psutil; verifies process identifier exists in OS table. | PASS |
| **25** | Shell & Sysadmin | *"Run allowlisted command: dir or echo test."* | Intent: `shell.allowlisted_diagnostics` | `ShellProvider` | Executes in sandboxed subprocess; verifies returncode == 0 and expected string in stdout. | PASS |
| **26** | Software Engineering | *"Generate Python utility function to validate email address."* | Intent: `code.generation` | `CodeEngineeringProvider` | Generates code snippet; runs `ast.parse()` on generated code to guarantee syntax validity. | PASS |
| **27** | Developer Environment | *"Check active Python interpreter path and version."* | Intent: `dev.probe_interpreter` | `DevEnvironmentProvider` | Inspects sys.executable; verifies Python 3.12+ interpreter path and valid venv pointer. | PASS |
| **28** | Git Version Control | *"Check git status and current branch name."* | Intent: `git.status` | `GitProvider` | Executes git status; verifies current branch returns string and clean/dirty state reported. | PASS |
| **29** | DevOps & Deployment | *"Verify local Docker or container daemon availability."* | Intent: `devops.probe_daemon` | `DevOpsProvider` | Checks local container socket or status; verifies daemon state correctly classified. | PASS |
| **30** | Database & Backend | *"Query user record from local sqlite memory store."* | Intent: `database.query` | `DatabaseProvider` | Runs SELECT query against SQLite; verifies returned columns and row count match expectations. | PASS |
| **31** | Multi-Source Web Research | *"Research latest advancements in quantum error correction."* | Intent: `search.web_research` | `WebResearchProvider` | Queries search API / local engine; verifies research synthesis with cited sources. | PASS |
| **32** | Real-Time Information | *"What is the current time in UTC and IST?"* | Intent: `info.get_realtime` | `RealTimeInfoProvider` | Queries system clock & timezone engine; verifies valid timestamp string and IST offset (+05:30). | PASS |
| **33** | Personal Search | *"Search recent notes for 'project roadmap'."* | Intent: `search.personal_notes` | `PersonalSearchProvider` | Searches local markdown notes index; verifies matching document hits and snippet offsets. | PASS |
| **34** | Information Verification | *"Verify claim: 'Python 3.12 removed distutils'."* | Intent: `verification.verify_claim` | `VerificationProvider` | Checks verified knowledge baseline; returns VERIFIED with PEP 632 citation. | PASS |
| **35** | Knowledge Synthesis | *"Synthesize notes from meeting A and meeting B into one brief."* | Intent: `knowledge.synthesize` | `KnowledgeSynthesisProvider`| Combines two text documents; verifies combined synthesis covers key points from both sources. | PASS |
| **36** | Device Mesh & Sync | *"Ping connected nodes in the local device mesh."* | Intent: `mesh.ping_nodes` | `DeviceMeshProvider` | Sends heartbeat broadcast; verifies local host node registered with status ONLINE. | PASS |
| **37** | Communication Management | *"Draft a reminder message for Aniket regarding review."* | Intent: `comm.draft_message` | `CommunicationProvider` | Drafts message in local outbox; verifies draft ID created and message text matches. | PASS |
| **38** | Calendar & Scheduling | *"Schedule 'System Review' for tomorrow at 10:00 AM."* | Intent: `calendar.create_event` | `CalendarSchedulerProvider` | Inserts event into calendar DB; verifies query by date returns newly created event. | PASS |
| **39** | Personal Productivity | *"Add 'Audit all 50 capabilities' to active task list."* | Intent: `productivity.create_task`| `ProductivityProvider` | Writes task to SQLite task store; queries task store to confirm task ID and state='PENDING'. | PASS |
| **40** | Travel & Navigation | *"Calculate distance between Delhi and Mumbai."* | Intent: `travel.route_estimate` | `TravelNavigationProvider` | Computes geodetic distance; verifies distance > 1100 km and estimate returned. | PASS |
| **41** | Autonomous Agency | *"Decompose goal: 'Deploy test web application'."* | Intent: `autonomy.decompose_goal` | `AutonomousAgencyProvider`| Generates multi-step DAG; verifies DAG has >= 3 stages with valid dependency pointers. | PASS |
| **42** | Workflow Automation | *"Trigger automated log rotation workflow."* | Intent: `workflow.execute` | `WorkflowAutomationProvider`| Triggers predefined workflow; verifies workflow run logged with status 'SUCCESS'. | PASS |
| **43** | Monitoring & Alerts | *"Monitor CPU usage and alert if above 95%."* | Intent: `monitor.check_threshold` | `MonitoringAlertsProvider`| Evaluates CPU against threshold; verifies alert record dispatched when condition simulated. | PASS |
| **44** | Smart Home & IoT | *"Turn on the living room smart lamp."* | Intent: `iot.set_state`, device: `lamp` | `SmartHomeIoTProvider` | Dispatches state change to device hub; verifies hub internal state register is 'ON'. | PASS |
| **45** | Physical / Robotics Interface | *"Move robotic arm end-effector to coordinates (100, 150, 50)."* | Intent: `robotics.move_cartesian` | `PhysicalRoboticsProvider` | Computes inverse kinematics; verifies joint angles are within physical limits and target reached. | PASS |
| **46** | Data Science & Analytics | *"Calculate mean, std, and correlation for dataset."* | Intent: `analytics.compute_stats` | `DataScienceProvider` | Runs statistical pipeline via numpy/pandas; verifies mean and correlation coefficient in [-1, 1]. | PASS |
| **47** | Simulation & Prediction | *"Simulate 500 Monte Carlo steps of server load under traffic."*| Intent: `simulation.monte_carlo` | `SimulationProvider` | Executes Monte Carlo stochastic loop; verifies mean, 95% confidence interval, and variance generated. | PASS |
| **48** | Security & Identity Policy | *"Validate token 'bearer-sec-token' for admin role."* | Intent: `security.validate_token` | `SecurityIdentityProvider`| Evaluates token signature against policy kernel; verifies ALLOW for valid token and DENY for invalid. | PASS |
| **49** | Verification & Self-Diagnostics | *"Run full self-diagnostics across all 50 subsystems."* | Intent: `diagnostics.run_self_test`| `VerificationDiagnosticsProvider`| Executes subsystem probes; verifies all critical health metrics returned with health score. | PASS |
| **50** | Capability Evolution | *"Propose dynamic schema extension for Capability 12."* | Intent: `evolution.propose_contract`| `CapabilityEvolutionProvider`| Generates contract proposal; runs sandboxed AST validator and verifies proposal passes schema check. | PASS |
