# JARVIS 50-Capability Provider Matrix

**Document Version:** 1.0-MASTER  
**Architecture Principle:** Replaceable Providers Behind Standardized Interfaces  
**System Architect:** Aniket & Antigravity IDE  

---

## 1. Provider Architectural Abstraction

In accordance with **Invariant 4** (*"No provider is allowed to dictate Cognitive Core architecture"*), every external technology, vendor API, OS subsystem, and local model sits behind the `BaseCapabilityProvider` abstract interface:

```python
class BaseCapabilityProvider(ABC):
    @property
    def provider_id(self) -> str: ...
    @property
    def supported_capabilities(self) -> List[str]: ...
    def is_available(self) -> bool: ...
    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult: ...
```

---

## 2. Complete 50-Capability Provider Mapping

| ID | Capability Domain | Primary Provider (`provider_id`) | Fallback Provider (`provider_id`) | Underlying Asset / Reused Module | Device Target | Provider Status |
| :---: | :--- | :--- | :--- | :--- | :--- | :---: |
| **01** | **Natural Language** | `provider.llm.ollama_local` | `provider.llm.cloud_gemini` | `cognitive/understanding.py`, `llm/ollama_client.py` | Windows Local | **Active** |
| **02** | **Cognitive Reasoning** | `provider.cognitive.reasoning_engine` | `provider.llm.cloud_gemini` | `cognitive/reasoning.py`, `cognitive/kernel.py` | Windows Local | **Active** |
| **03** | **World Model** | `provider.cognitive.world_model` | N/A (Internal Core) | `cognitive/world_model.py` | Windows Local | **Active** |
| **04** | **Context Intelligence** | `provider.cognitive.context_engine` | N/A (Internal Core) | `cognitive/understanding.py` | Windows Local | **Active** |
| **05** | **Meta-Cognition** | `provider.cognitive.meta_evaluator` | `provider.cognitive.reasoning_engine`| `cognitive/understanding.py`, `verification/verifier.py` | Windows Local | **Scaffolding** |
| **06** | **Memory System** | `provider.memory.sqlite_vector` | `provider.memory.in_memory` | `memory/system.py`, `agents/semantic_rag.py` | Windows Local | **Active** |
| **07** | **Learning & Adaptation** | `provider.learning.experience_store`| N/A (Internal Core) | `learning_system/experience_store.py` | Windows Local | **Active** |
| **08** | **Skill Acquisition** | `provider.skill.sandbox_runner` | N/A (Internal Core) | `skills/`, `cognitive/planning_engine.py` | Windows Local | **Scaffolding** |
| **09** | **Experience Replay** | `provider.learning.replay_runner` | N/A (Internal Core) | `tests/run_all_audits.py`, `memory/` | Windows Local | **Scaffolding** |
| **10** | **Knowledge Management**| `provider.knowledge.rag_store` | `provider.file.scoped` | `agents/personal_knowledge_base.py`, `about_me_ingest.py`| Windows Local | **Active (Verified E2E)** |
| **11** | **Vision** | `provider.vision.moondream` | `provider.vision.cloud_gemini` | `agents/vision_agent.py`, `capabilities/providers/vision_provider.py` | Windows Local | **Active** |
| **12** | **OCR & Documents** | `provider.vision.native_win_ocr` | `provider.vision.tesseract` | `agents/vision_ocr_agent.py` | Windows Local | **Active** |
| **13** | **Audio Perception** | `provider.audio.whisper_local` | `provider.audio.android_mic` | `voice/asr.py`, `perception/channels/voice_input.py` | Windows / Android | **Active** |
| **14** | **Environmental Perception**| `provider.os.win32` | `provider.os.psutil` | `cognitive/world_model.py`, `capabilities/providers/os_provider.py` | Windows Local | **Active** |
| **15** | **Multimodal Understanding**| `provider.multimodal.fused_engine`| `provider.llm.cloud_gemini` | `perception/processing/context_awareness.py` | Windows Local | **Scaffolding** |
| **16** | **Voice Intelligence** | `provider.voice.piper_local` | `provider.voice.android_tts` | `voice/tts_piper.py`, `client/android/` | Windows / Android | **Active** |
| **17** | **Wake-Word Intelligence**| `provider.wakeword.sherpa_onnx` | `provider.wakeword.openwake_word`| `wakeword/engine.py`, `client/android/` | Android / Windows | **Active** |
| **18** | **Persona & Social** | `provider.llm.persona_manager` | N/A (Internal Core) | `llm/personas.py`, `cognitive/world_model.py` | Windows Local | **Active** |
| **19** | **Emotion & Context** | `provider.perception.sentiment` | `provider.llm.ollama_local` | `perception/processing/context_awareness.py` | Windows Local | **Scaffolding** |
| **20** | **Accessibility** | `provider.ui.accessible_payload`| `provider.voice.piper_local` | UI Event formatters, Screen reader adapters | Windows / Mobile | **Scaffolding** |
| **21** | **Desktop / OS Control** | `provider.os.win32` | `provider.os.pyautogui` | `agents/system_control_agent.py`, `os_provider.py` | Windows Local | **Active** |
| **22** | **File & Storage** | `provider.file.scoped` | `provider.file.python_shutil` | `agents/file_document_agent.py`, `file_provider.py` | Windows Local | **Active** |
| **23** | **Browser Intelligence** | `provider.browser.chrome_cdp` | `provider.browser.playwright` | `agents/browser_automation_agent.py`, `browser_provider.py` | Windows Local | **Active** |
| **24** | **Application Intelligence**| `provider.app.win32_launcher` | `provider.os.win32` | `agents/system_control_agent.py` | Windows Local | **Active** |
| **25** | **Shell & Sysadmin** | `provider.dev.allowlisted_cli` | N/A (Strict Safety) | `safety/policy_kernel.py`, `developer_provider.py` | Windows Local | **Active** |
| **26** | **Software Engineering** | `provider.dev.git_code` | `provider.llm.cloud_gemini` | `agents/dev_tool_agent.py`, `developer_provider.py` | Windows Local | **Active** |
| **27** | **Dev Environment** | `provider.dev.venv_manager` | `provider.dev.git_code` | `agents/dev_tool_agent.py` | Windows Local | **Scaffolding** |
| **28** | **Git & Version Control** | `provider.dev.git_code` | `provider.dev.git_cli` | `agents/dev_tool_agent.py`, `developer_provider.py` | Windows Local | **Active** |
| **29** | **DevOps & Deployment** | `provider.devops.script_runner` | `provider.dev.git_code` | `tests/` infrastructure, `server/app.py` | Windows Local | **Scaffolding** |
| **30** | **Database Intelligence**| `provider.db.sqlite_local` | `provider.db.schema_inspector`| `memory/` SQLite persistence modules | Windows Local | **Scaffolding** |
| **31** | **Web Research** | `provider.web.search_fetch` | `provider.web.tavily_api` | `agents/web_agent.py`, `skills/tavily_search.py` | Windows / Cloud | **Active (Verified E2E)** |
| **32** | **Real-Time Information** | `provider.info.realtime_feeds` | `provider.web.search_fetch` | `agents/weather_agent.py`, `agents/news_agent.py` | Windows / Cloud | **Active (Verified E2E)** |
| **33** | **Personal Search** | `provider.search.personal_vector`| `provider.file.scoped` | `agents/personal_knowledge_base.py`, `semantic_rag.py` | Windows Local | **Active** |
| **34** | **Information Verification**| `provider.verification.verifier`| N/A (Internal Core) | `verification/verifier.py` | Windows Local | **Active** |
| **35** | **Knowledge Synthesis** | `provider.cognitive.synthesizer`| `provider.llm.cloud_gemini` | `cognitive/reasoning.py`, `agents/semantic_rag.py` | Windows Local | **Active** |
| **36** | **Device Mesh** | `provider.mesh.tailscale_rpc` | `provider.mesh.local_lan` | `client/android/`, `docs/tailscale_remote_access.md` | Windows / Android | **Scaffolding** |
| **37** | **Communication** | `provider.comm.google_gmail` | `provider.comm.whatsapp_cdp` | `agents/communication_agent.py`, `skills/google_gmail.py`| Windows / Cloud | **Active** |
| **38** | **Calendar & Scheduling** | `provider.scheduler.apscheduler`| `provider.calendar.google` | `agents/calendar_agent.py`, `skills/google_calendar.py` | Windows / Cloud | **Active** |
| **39** | **Personal Productivity** | `provider.productivity.local_task`| `provider.memory.sqlite_vector`| `agents/notification_triage_agent.py`, `workspace/` | Windows Local | **Scaffolding** |
| **40** | **Travel & Navigation** | `provider.travel.transit_maps` | `provider.web.search_fetch` | Web search routing, external navigation APIs | Windows / Mobile | **New** |
| **41** | **Autonomous Agency** | `provider.autonomy.agency_runtime`| N/A (Internal Core) | `autonomous_runtime/agency.py` | Windows Local | **Active** |
| **42** | **Workflow Automation** | `provider.workflow.runtime_kernel`| N/A (Internal Core) | `execution/runtime.py` | Windows Local | **Active** |
| **43** | **Monitoring & Alerts** | `provider.monitor.threshold_poll`| `provider.autonomy.agency_runtime`| `autonomous_runtime/agency.py`, `observability/` | Windows Local | **Scaffolding** |
| **44** | **Smart Home / IoT** | `provider.iot.home_assistant` | `provider.iot.cast_media` | `agents/smart_home_agent.py`, `skills/home_assistant.py`| LAN / IoT | **Active** |
| **45** | **Physical / Robotics** | `provider.robotics.mock_interlock`| N/A (Strict Safety) | `perception/channels/sensor_input.py` | Hardware LAN | **Scaffolding** |
| **46** | **Data Science & Analytics**| `provider.analytics.python_sandbox`| `provider.dev.git_code` | `capabilities/providers/developer_provider.py` | Windows Local | **Scaffolding** |
| **47** | **Simulation & Prediction**| `provider.sim.monte_carlo` | `provider.cognitive.reasoning_engine`| `cognitive/reasoning.py` | Windows Local | **Scaffolding** |
| **48** | **Security & Identity** | `provider.safety.policy_kernel` | N/A (Internal Core) | `safety/policy_kernel.py`, `agents/identity_agent.py` | Windows Local | **Active** |
| **49** | **Verification & Diagnostics**| `provider.diag.system_audit` | `provider.verification.verifier`| `verification/verifier.py`, `tests/run_all_audits.py` | Windows Local | **Active** |
| **50** | **Capability Evolution** | `provider.evolution.gap_analyzer`| N/A (Internal Core) | `capabilities/intelligence.py`, `learning_system/` | Windows Local | **Scaffolding** |

---

## 3. Dynamic Hot-Swapping & Telemetry Recording

Every provider selection and fallback event is recorded in the execution trace:
```json
{
  "request_id": "req_1789458291",
  "capability": "search.web",
  "attempted_providers": [
    {"provider_id": "provider.web.search_fetch", "status": "TIMEOUT", "latency_ms": 5000},
    {"provider_id": "provider.web.tavily_api", "status": "SUCCESS", "latency_ms": 340}
  ],
  "fallback_used": true,
  "selected_provider": "provider.web.tavily_api"
}
```
Cognitive Core code remains 100% agnostic to whether Tavily, DuckDuckGo, or local files answer the query.
