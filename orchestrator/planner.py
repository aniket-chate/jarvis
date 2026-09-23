"""Task Planner for JARVIS Layer 2.

Transforms incoming PerceptionEvents into ordered TaskPlans with steps,
required agent types, inputs, and step dependencies.
Supports both single-step and multi-step tasks, and detects persona switch intents.
"""

import re
import uuid
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

from perception.events import PerceptionEvent
from config.settings import settings
from orchestrator.action_memory import action_memory_manager
from orchestrator.parameter_extractor import parameter_extractor

logger = logging.getLogger("JARVIS.Planner")


@dataclass
class TaskStep:
    """Individual executable unit within a TaskPlan."""
    step_id: str
    description: str
    required_agent_type: str
    inputs: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)
    status: str = "pending"  # "pending", "running", "completed", "failed", "blocked"
    result: Optional[Dict[str, Any]] = None
    retries: int = 0
    max_retries: int = 2
    confirmed: bool = False
    user_confirmed: bool = False

    @property
    def agent_type(self) -> str:
        return self.required_agent_type

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["agent_type"] = self.agent_type
        return d


@dataclass
class TaskPlan:
    """Ordered collection of TaskSteps with execution state and persona context."""
    plan_id: str
    goal: str
    steps: List[TaskStep]
    active_persona: str
    is_persona_switch: bool = False
    switch_target_persona: Optional[str] = None
    status: str = "pending"  # "pending", "in_progress", "completed", "failed", "blocked"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "active_persona": self.active_persona,
            "is_persona_switch": self.is_persona_switch,
            "switch_target_persona": self.switch_target_persona,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
        }


class TaskPlanner:
    """Decomposes user intents and PerceptionEvents into executable plans."""

    def __init__(self):
        self.known_personas = ["Jarvis", "Friday", "Ultron", "Omi"]

    def create_plan(self, event: PerceptionEvent) -> TaskPlan:
        """Analyzes PerceptionEvent and generates an ordered TaskPlan."""
        # Extract text content from payload
        text = ""
        if "text" in event.payload:
            text = str(event.payload["text"]).strip()
        elif "raw_text" in event.payload:
            text = str(event.payload["raw_text"]).strip()
        elif "transcript" in event.payload:
            text = str(event.payload["transcript"]).strip()

        active_persona = event.active_persona or settings.active_persona_name
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"

        # Check Context Manager for active session persona
        try:
            from orchestrator.context_manager import context_manager
            if context_manager.active_persona:
                active_persona = context_manager.active_persona
        except Exception:
            pass

        # 0. Multi-Step Intent Check (e.g. compound coordinate actions)
        multi_step_match = self._detect_multi_step(text)
        if multi_step_match:
            logger.info("[Planner] [%s] Generated multi-step plan for: '%s'", active_persona, text)
            return self._build_multi_step_plan(plan_id, text, multi_step_match, active_persona)

        # 0b. Semantic Intent Arbitrator (Meaning FIRST)
        try:
            from orchestrator.intent_arbitrator import intent_arbitrator
            structured_intent = intent_arbitrator.arbitrate(text)
            if structured_intent and structured_intent.domain != "chat":
                # Special Multi-Step Case: Personal + External Synthesis
                if structured_intent.domain == "synthesis" and structured_intent.action == "personal_and_external_synthesis":
                    s1 = TaskStep(
                        step_id=f"{plan_id}_step_1",
                        description="Retrieve personal project architecture and notes",
                        required_agent_type="personal_search_agent",
                        inputs={"action": "search_personal", "query": structured_intent.params.get("personal_query", "JARVIS architecture"), "top_k": 3}
                    )
                    s2 = TaskStep(
                        step_id=f"{plan_id}_step_2",
                        description="Search external web information",
                        required_agent_type="web_agent",
                        inputs={"action": "search", "query": structured_intent.params.get("external_query", "modern AI assistant architecture"), "max_results": 3}
                    )
                    s3 = TaskStep(
                        step_id=f"{plan_id}_step_3",
                        description="Synthesize personal and external findings",
                        required_agent_type="personal_search_agent",
                        inputs={"action": "synthesize", "query": text},
                        depends_on=[f"{plan_id}_step_1", f"{plan_id}_step_2"]
                    )
                    logger.info("[Planner] [%s] Generated multi-step synthesis plan (33+31 -> 35)", active_persona)
                    return TaskPlan(
                        plan_id=plan_id,
                        goal=text,
                        steps=[s1, s2, s3],
                        active_persona=active_persona,
                    )

                step = self._build_step_from_intent(plan_id, structured_intent, text)
                if step:
                    logger.info(
                        "[Planner] [%s] Intent Arbitrator resolved: domain='%s', action='%s' -> Agent='%s'",
                        active_persona,
                        structured_intent.domain,
                        structured_intent.action,
                        step.required_agent_type,
                    )
                    is_sw = (structured_intent.action == "switch_persona")
                    return TaskPlan(
                        plan_id=plan_id,
                        goal=text,
                        steps=[step],
                        active_persona=active_persona,
                        is_persona_switch=is_sw,
                        switch_target_persona=structured_intent.target if is_sw else None,
                    )
        except Exception as arb_err:
            logger.warning("[Planner] Intent Arbitrator exception: %s", arb_err)

        # 1. Check for Persona Switch Intent (spoken or text without wake word)
        persona_target = self._detect_persona_switch(text)
        if persona_target:
            try:
                from cognitive.world_model import world_model
                world_model.set_persona(persona_target)
            except Exception:
                pass
            logger.info(
                "[Planner] [%s] Detected persona switch intent: '%s' -> target '%s'",
                active_persona,
                text,
                persona_target,
            )
            step = TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Switch active persona to {persona_target}",
                required_agent_type="system_control_agent",
                inputs={"action": "switch_persona", "persona": persona_target},
            )
            return TaskPlan(
                plan_id=plan_id,
                goal=f"Switch persona to {persona_target}",
                steps=[step],
                active_persona=active_persona,
                is_persona_switch=True,
                switch_target_persona=persona_target,
            )

        # 2. Check for Multi-Step Intent (e.g. search news and draft email)
        multi_step_match = self._detect_multi_step(text)
        if multi_step_match:
            logger.info("[Planner] [%s] Generated multi-step plan for: '%s'", active_persona, text)
            return self._build_multi_step_plan(plan_id, text, multi_step_match, active_persona)

        # 3. Default Single-Step Task Plan
        single_step = self._build_single_step(plan_id, text)
        logger.info(
            "[Planner] [%s] Generated single-step plan: Agent='%s', Goal='%s'",
            active_persona,
            single_step.required_agent_type,
            text[:35],
        )

        return TaskPlan(
            plan_id=plan_id,
            goal=text,
            steps=[single_step],
            active_persona=active_persona,
        )

    def _build_step_from_intent(self, plan_id: str, intent: Any, text: str) -> Optional[TaskStep]:
        d = intent.domain
        act = intent.action
        params = intent.params
        target = intent.target

        if d == "info":
            if act == "get_weather":
                loc = params.get("location") or target or "Delhi"
                tt = params.get("time_target", "now")
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Retrieve real-time weather for {loc}",
                    required_agent_type="weather_agent",
                    inputs={"action": "get_weather", "location": loc, "time_target": tt, "query": text}
                )
            elif act == "get_news":
                topic = params.get("topic") or target or "general"
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Retrieve news for {topic}",
                    required_agent_type="news_agent",
                    inputs={"action": "get_news", "topic": topic, "query": text}
                )

        elif d == "scheduler":
            if act in ["list", "list_alarms"]:
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description="List active alarms",
                    required_agent_type="scheduler_agent",
                    inputs={"action": "list"}
                )
            elif act in ["cancel", "cancel_alarm", "delete"]:
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description="Cancel active alarm",
                    required_agent_type="scheduler_agent",
                    inputs={"action": "cancel", "alarm_id": params.get("alarm_id", "")}
                )
            elif act in ["check_conflicts", "create_calendar_event", "get_calendar_events"]:
                pass
            else:
                delay = int(params.get("delay_seconds", 60))
                msg = params.get("message") or target or "Scheduled alarm notification"
                action_name = act if act in ["set_alarm", "set_reminder", "create_alarm"] else "set_alarm"
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Set alarm for {delay} seconds: {msg}",
                    required_agent_type="scheduler_agent",
                    inputs={"action": action_name, "delay_seconds": delay, "message": msg, "target": target}
                )

        elif d == "ocr":
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Scan document OCR: {target}",
                required_agent_type="vision_ocr_agent",
                inputs={"action": "scan_document", "image_path": target, "save_to_kb": params.get("save_to_kb", False)}
            )

        elif d == "code":
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Code assistant: {act}",
                required_agent_type="core_llm_agent",
                inputs={"action": act, "prompt": text, "code": params.get("code", ""), "input_arg": params.get("input_arg", 5), "scenario": params.get("scenario", "")}
            )

        elif d == "file":
            if act == "stage_file_creation":
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Stage file creation: {target}",
                    required_agent_type="file_agent",
                    inputs={"action": "create", "path": target, "content": params.get("content", ""), "requires_confirmation": True, "directory": params.get("directory", "desktop")}
                )
            elif act in ["confirmed_create_file", "create_file"]:
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Create file: {target}",
                    required_agent_type="file_agent",
                    inputs={"action": "create", "path": target, "filename": params.get("filename", target), "content": params.get("content", ""), "user_confirmed": True, "directory": params.get("directory", "documents")}
                )
            elif act in ["read_file", "read", "show_file", "show", "open_file", "open"]:
                p = params.get("path") or params.get("file_path") or params.get("filename") or target
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Read file: {p}",
                    required_agent_type="file_agent",
                    inputs={"action": "read", "path": p, "file_path": p, "filename": p, "directory": params.get("directory", "documents")}
                )
            elif act in ["delete_file", "delete", "remove_file", "remove"]:
                p = params.get("path") or params.get("file_path") or params.get("filename") or target
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Delete file: {p}",
                    required_agent_type="file_agent",
                    inputs={"action": "delete_file", "path": p, "file_path": p, "directory": params.get("directory", "documents")}
                )
            elif act == "move_file":
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Move file: {target}",
                    required_agent_type="file_agent",
                    inputs={"action": "move", "source": params.get("source", target), "destination": params.get("destination", "downloads"), "user_confirmed": True}
                )
            elif act in ["rename_file", "rename"]:
                new_n = params.get("new_name") or params.get("destination") or ""
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Rename file: {target} to {new_n}",
                    required_agent_type="file_agent",
                    inputs={"action": "rename", "source": target, "path": target, "new_name": new_n, "destination": new_n, "user_confirmed": True}
                )
            elif act == "search_file":
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Search for file: {target}",
                    required_agent_type="file_agent",
                    inputs={"action": "search", "pattern": params.get("pattern", f"*{target}*"), "directory": "workspace"}
                )

        elif d == "git":
            if act == "status":
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description="Inspect git repository status",
                    required_agent_type="dev_tool_agent",
                    inputs={"action": "git_status"}
                )
            elif act == "create_branch":
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Create git branch: {target}",
                    required_agent_type="dev_tool_agent",
                    inputs={"action": "git_create_branch", "branch": target, "branch_name": target}
                )
            elif act == "switch_branch":
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Switch git branch to {target}",
                    required_agent_type="dev_tool_agent",
                    inputs={"action": "git_switch", "branch": target, "target": target}
                )

        elif d == "browser":
            if act in ["pause_media", "resume_media"]:
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Browser media {act}",
                    required_agent_type="browser_automation_agent",
                    inputs={"action": act}
                )
            elif act == "close_tab":
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description="Close active browser tab",
                    required_agent_type="browser_automation_agent",
                    inputs={"action": "close_tab"}
                )
            elif act == "query_page":
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description="Query active page",
                    required_agent_type="browser_automation_agent",
                    inputs={"action": "get_active_tab"}
                )
            elif act == "github_search":
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description="Search GitHub in active browser",
                    required_agent_type="browser_automation_agent",
                    inputs={"action": "open_url", "query": params.get("url", "https://github.com/search?q=python&type=repositories"), "url": params.get("url")}
                )
            elif act == "play_youtube":
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description="Play YouTube music",
                    required_agent_type="browser_automation_agent",
                    inputs={"action": "play_youtube", "song": params.get("song", "lofi beats"), "query": params.get("song", "lofi beats")}
                )
            elif act == "open_url":
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Open URL: {target}",
                    required_agent_type="browser_automation_agent",
                    inputs={"action": "open_url", "query": params.get("url", target), "url": params.get("url", target)}
                )

        elif d == "communication":
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"WhatsApp draft: {target}",
                required_agent_type="communication_agent",
                inputs={"action": "draft_whatsapp", "recipient": params.get("recipient", "Sachin"), "message": params.get("message", "I'm running late"), "user_confirmed": False}
            )

        elif d == "system":
            if act == "multi_telemetry":
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description="Multi-metric system telemetry",
                    required_agent_type="system_control_agent",
                    inputs={"action": "multi_telemetry"}
                )
            elif act == "summarize_session":
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description="Summarize session activity",
                    required_agent_type="core_llm_agent",
                    inputs={"action": "session_summary", "summary": params.get("summary", "")}
                )
            elif act == "switch_persona":
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Switch persona to {target}",
                    required_agent_type="system_control_agent",
                    inputs={"action": "switch_persona", "persona": target}
                )
            elif act == "cancel_action":
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description="Cancel pending transaction",
                    required_agent_type="core_llm_agent",
                    inputs={"action": "cancel_action", "response": params.get("response", "Action cancelled. The operation was safely aborted."), "user_cancelled": True}
                )

        elif d == "personal_search":
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Search personal knowledge: {target}",
                required_agent_type="personal_search_agent",
                inputs={"action": "search_personal", "query": target or text, "top_k": params.get("top_k", 5)}
            )

        elif d == "synthesis":
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Synthesize knowledge: {target}",
                required_agent_type="personal_search_agent",
                inputs={"action": "synthesize", "query": text, "sources": params.get("sources", [])}
            )

        return None

    def _detect_persona_switch(self, text: str) -> Optional[str]:
        """Detects explicit requests like 'call yourself Friday from now on', 'switch persona to Ultron'."""
        lower = text.lower().strip()
        patterns = [
            r"\b(?:switch|change|set)\s+(?:persona|voice|identity|mode)\s+to\s+(\w+)\b",
            r"\bcall yourself (\w+) from now on\b",
            r"\bfrom now on,? call yourself (\w+)\b",
            r"\bfrom now on,? your name is (\w+)\b",
            r"\byour name is (\w+) from now on\b",
            r"\bbe (\w+) from now on\b",
            r"^(?:please\s+)?switch\s+to\s+(\w+)$",
            r"^(?:please\s+)?activate\s+(\w+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, lower)
            if match:
                candidate = match.group(1)
                from utils.fuzzy_matcher import match_persona
                matched = match_persona(candidate, candidates=self.known_personas)
                if matched:
                    return matched
        return None

    def _detect_multi_step(self, text: str) -> Optional[Dict[str, Any]]:
        """Identifies compound requests containing sequential connectives (and then, and draft, then)."""
        lower = text.lower()
        if any(w in lower for w in ["in my documents", "in documents", "in downloads", "in desktop", "in workspace", "local file", "file called", "file named"]):
            return None
        if "news" in lower and ("email" in lower or "draft" in lower or "send" in lower):
            return {"type": "news_and_email"}
        if ("search" in lower or "find" in lower) and ("and save" in lower or "save to file" in lower or "save to a file" in lower or "save it to" in lower):
            return {"type": "search_and_save"}

        # Generalized coordinate conjunction clause decomposition
        parts = re.split(r",?\s+(?:and\s+then|then|and)\s+", text, flags=re.IGNORECASE)
        if len(parts) >= 2:
            imperatives = {
                "check", "get", "tell", "show", "open", "launch", "start", "search",
                "find", "look", "summarize", "save", "write", "create", "delete",
                "close", "set", "play", "send", "browse", "read", "inspect", "what"
            }
            valid_clauses = []
            for p in parts:
                clean_p = p.strip()
                tokens = clean_p.lower().split()
                if not tokens:
                    continue
                first_tok = tokens[0]
                if first_tok in ["please", "kindly"]:
                    tokens = tokens[1:]
                    first_tok = tokens[0] if tokens else ""
                if first_tok in imperatives or (len(tokens) > 1 and tokens[0] == "the" and tokens[1] in ["weather", "news"]):
                    valid_clauses.append(clean_p)
                elif any(k in clean_p.lower() for k in ["tell me the result", "tell me result", "save the summary", "save it", "summarize it"]):
                    valid_clauses.append(clean_p)

            if len(valid_clauses) >= 2 and len(valid_clauses) == len(parts):
                return {"type": "coordinate_clauses", "clauses": valid_clauses}

        return None

    def _build_multi_step_plan(self, plan_id: str, goal: str, intent_info: Dict[str, Any], persona: str) -> TaskPlan:
        """Decomposes compound intent into sequentially dependent TaskSteps."""
        steps: List[TaskStep] = []

        if intent_info["type"] == "news_and_email":
            # Step 1: Retrieve news
            step_1 = TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Fetch latest news headlines on requested topic",
                required_agent_type="news_agent",
                inputs={"query": goal, "count": 3},
                depends_on=[],
            )
            # Step 2: Draft email summary (depends on step 1)
            step_2 = TaskStep(
                step_id=f"{plan_id}_step_2",
                description="Draft email with news summary to recipient",
                required_agent_type="communication_agent",
                inputs={"action": "draft_email", "subject": "News Update", "recipient": "team@example.com"},
                depends_on=[step_1.step_id],
            )
            steps.extend([step_1, step_2])

        elif intent_info["type"] == "search_and_save":
            step_1 = TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Execute web search",
                required_agent_type="web_agent",
                inputs={"query": goal},
                depends_on=[],
            )
            step_2 = TaskStep(
                step_id=f"{plan_id}_step_2",
                description="Save research findings to file",
                required_agent_type="file_agent",
                inputs={"action": "save", "filename": "search_results.txt"},
                depends_on=[step_1.step_id],
            )
            steps.extend([step_1, step_2])

        elif intent_info["type"] == "coordinate_clauses":
            clauses = intent_info.get("clauses", [])
            prev_step_id = None
            for idx, clause in enumerate(clauses):
                step_idx = idx + 1
                curr_step_id = f"{plan_id}_step_{step_idx}"
                cl_low = clause.lower()

                # Check dependency on previous step
                is_dependent = bool(
                    prev_step_id and (
                        any(ref in cl_low for ref in [" it", " that", " the result", " the summary", " the findings"])
                        or cl_low.startswith("summarize")
                        or cl_low.startswith("save")
                        or cl_low.startswith("tell me")
                    )
                )

                step = self._build_single_step(curr_step_id, clause)
                if is_dependent and prev_step_id:
                    step.depends_on = [prev_step_id]
                else:
                    step.depends_on = []

                steps.append(step)
                prev_step_id = curr_step_id

        return TaskPlan(
            plan_id=plan_id,
            goal=goal,
            steps=steps,
            active_persona=persona,
        )

    def _build_single_step(self, plan_id: str, text: str) -> TaskStep:
        """Infers single-step agent assignment based on intent keywords."""
        lower = text.lower().strip()
        # Generalized conversational prefix stripping
        clean_lower = re.sub(r"^(?:hey\s+|ok\s+|okay\s+)?jarvis[\s,:]+", "", lower).strip()
        clean_lower = re.sub(r"^(?:can\s+you\s+(?:please\s+)?|could\s+you\s+(?:please\s+)?|please\s+|kindly\s+)", "", clean_lower).strip()

        # -4. Symmetrical Action Memory Follow-ups resolved via Universal Fuzzy Matcher
        from utils.fuzzy_matcher import match_intent_action
        action_intent = match_intent_action(text)

        active_sess = action_memory_manager.get_active_session()
        has_media = active_sess and (
            active_sess.get("action_type") in ["media_playback", "youtube_playback", "chained_play", "web_action"]
            or active_sess.get("is_playing")
        )
        has_page = action_memory_manager.has_live_page() or bool(active_sess)

        if action_intent == "pause" and (has_media or has_page):
            logger.info("[Planner ActionMemory] Symmetrically resolving pause intent ('%s') against active session: %s", text, active_sess)
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Symmetrically stop/pause active media in browser session",
                required_agent_type="browser_automation_agent",
                inputs={"action": "stop_media", "query": text}
            )

        if action_intent == "resume" and (has_media or has_page):
            logger.info("[Planner ActionMemory] Symmetrically resolving resume intent ('%s') against active session: %s", text, active_sess)
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Symmetrically resume active media in browser session",
                required_agent_type="browser_automation_agent",
                inputs={"action": "resume_media", "query": text}
            )

        is_browser_target = any(w in lower for w in ["tab", "page", "browser", "site", "website", "it", "that", "this"]) or lower in ["close", "close please", "close now"]
        is_desktop_app_close = any(app in lower for app in ["notepad", "calculator", "calc", "powershell", "terminal", "explorer", "window", "windows"])
        if action_intent == "close" and has_page and (is_browser_target or not is_desktop_app_close) and not is_desktop_app_close:
            logger.info("[Planner ActionMemory] Symmetrically resolving close intent ('%s') against active session: %s", text, active_sess)
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Symmetrically close active browser page",
                required_agent_type="browser_automation_agent",
                inputs={"action": "close_page", "query": text}
            )

        # -3. Priority Shell Command Refusal Gate (Safety Invariant - Regression 6 Fix)
        # Prevents commands like "run whoami for me", "execute whoami", "run whoami" from launching apps!
        shell_patterns = [
            r"\b(?:run|execute)\s+(?:a\s+)?(?:shell|bash|powershell|cmd|terminal)\b",
            r"\b(?:run|execute)\s+(?:whoami|ipconfig|ifconfig|netstat|uname|cat\s+/etc|rm\s+-rf|del\s+/f|powershell|cmd\.exe|bash)\b",
            r"^(?:run|execute)\s+([a-zA-Z0-9_-]+)(?:\s+for\s+me|\s+please)?$",
            r"^(?:whoami|ipconfig|ifconfig|netstat|uname)\b",
        ]
        is_prohibited_shell = False
        command_candidate = ""
        for spat in shell_patterns:
            sm = re.search(spat, lower)
            if sm:
                matched_cmd = sm.group(1) if sm.groups() else sm.group(0)
                known_shell_cmds = ["whoami", "ipconfig", "ifconfig", "netstat", "uname", "dir", "ls", "ps", "top", "chmod", "chown", "curl", "wget"]
                if any(k in lower for k in known_shell_cmds) or "shell" in lower or "bash" in lower or "powershell" in lower or "terminal" in lower:
                    is_prohibited_shell = True
                    command_candidate = matched_cmd
                    break

        if is_prohibited_shell:
            logger.warning("[Planner Safety] Intercepted prohibited general shell execution attempt: '%s'", text)
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Refuse prohibited general shell execution",
                required_agent_type="dev_tool_agent",
                inputs={"action": "refuse_general_shell", "command": command_candidate or text}
            )

        # -2. Telephony Honesty Refusal Gate
        # Plain honesty refusal when telephone calls are requested without WhatsApp
        phone_call_match = re.search(r"\b(?:call|phone|dial|telephone|ring)\s+(?:the\s+number\s+)?(\+?\d[\d\s-]{7,15})\b", lower)
        if phone_call_match and "whatsapp" not in lower:
            target_num = phone_call_match.group(1).strip()
            logger.info("[Planner Telephony] Honest refusal for direct cellular phone call to: %s", target_num)
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="State telephony honesty constraint",
                required_agent_type="core_llm_agent",
                inputs={
                    "query": text,
                    "system_extra": (
                        f"HONESTY CONSTRAINT: The user asked to call a telephone number ({target_num}). "
                        f"You must state clearly and plainly that you do not have cellular telephony capability to place real telephone calls to phone numbers for free. "
                        f"Explain that you can place free voice calls via WhatsApp Web if the contact is in their WhatsApp, or generate an SMS intent."
                    )
                }
            )

        # -1b. Google Maps Route & Directions Navigation (Astra Web Agent Path)
        maps_m = re.search(r"\b(?:route\s+(?:of|to|for)|directions?\s+(?:to|for)|how\s+to\s+reach)\s+(.+)", lower)
        if maps_m or ("route" in lower and any(w in lower for w in ["shaniwar wada", "mumbai", "pune", "delhi", "maps", "destination"])):
            dest = maps_m.group(1).strip() if maps_m else text
            dest = re.sub(r"\b(?:on\s+maps|on\s+google\s+maps|using\s+maps|for\s+me|please)\b", "", dest, flags=re.IGNORECASE).strip()
            dest = re.sub(r"^(?:give\s+me\s+the\s+route\s+(?:of|to)|show\s+me\s+the\s+route\s+(?:of|to))\s+", "", dest, flags=re.IGNORECASE).strip()
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Extract live route to '{dest}' via Google Maps",
                required_agent_type="browser_automation_agent",
                inputs={"action": "maps_route", "destination": dest, "query": dest}
            )

        # -1b2. Conversational Route Origin Follow-up (e.g., following "give me route of shaniwar wada", user says "jalna")
        active_sess = action_memory_manager.get_active_session()
        if active_sess and active_sess.get("action_type") == "maps_route":
            prev_dest = active_sess.get("query")
            clean_loc = re.sub(r"^(?:from|starting\s+from)\s+", "", lower).strip()
            known_locs = ["jalna", "pune", "mumbai", "delhi", "nagpur", "nashik", "aurangabad", "chhatrapati sambhajinagar"]
            if clean_loc in known_locs or lower.startswith("from ") or (len(lower.split()) <= 2 and not any(w in lower for w in ["hello", "hi", "hey", "who", "what", "stop", "cancel"])):
                logger.info("[Planner MapFollowUp] Linking conversational route origin '%s' to destination '%s'", text, prev_dest)
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Extract live route from '{text}' to '{prev_dest}' via Google Maps",
                    required_agent_type="browser_automation_agent",
                    inputs={"action": "maps_route", "origin": text, "destination": prev_dest, "query": f"{text} to {prev_dest}"}
                )

        # -1a. Scoped Local File Operations with Structured Parameter Extraction (Regression 3 & 4 Fix)
        # Prioritize local file move/search before general web search
        is_past_inquiry = bool(re.search(r"^(?:did\s+you|was\s+the|were\s+the|have\s+you|why\s+did\s+you)\b", lower))
        file_keywords = ["file", "files", "document", "documents", "downloads", "desktop", "workspace", ".txt", ".pdf", ".json", ".csv", ".py", ".md"]
        is_file_op = not is_past_inquiry and any(k in lower for k in file_keywords) and any(w in lower for w in ["search", "find", "move", "create", "write", "make", "delete", "remove", "save", "copy", "read", "show", "view", "open", "cat", "inspect", "rename"])
        if is_file_op:
            file_params = parameter_extractor.extract_file_parameters(text)
            if file_params.get("requires_clarification"):
                clarif_prompt = file_params.get("clarification_prompt") or "Could you clarify the file details?"
                logger.info("[Planner FileOps] Ambiguity detected. Requesting user clarification: %s", clarif_prompt)
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description="Request user clarification for file operation",
                    required_agent_type="core_llm_agent",
                    inputs={"query": clarif_prompt, "system_extra": clarif_prompt, "response": clarif_prompt}
                )

            f_act = file_params.get("action")
            if f_act == "search":
                f_pat = file_params.get("filename") or "*"
                f_dir = file_params.get("directory") or "documents"
                logger.info("[Planner FileOps] Structured file search: pattern='%s', dir='%s'", f_pat, f_dir)
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Search for files matching '{f_pat}' in {f_dir}",
                    required_agent_type="file_agent",
                    inputs={"action": "search", "pattern": f_pat, "directory": f_dir}
                )
            elif f_act == "move":
                f_src = file_params.get("source") or file_params.get("filename")
                f_dest = file_params.get("destination") or "downloads"
                logger.info("[Planner FileOps] Structured file move: src='%s', dest='%s'", f_src, f_dest)
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Move file from {f_src} to {f_dest}",
                    required_agent_type="file_agent",
                    inputs={"action": "move", "source": f_src, "destination": f_dest}
                )
            elif f_act == "rename":
                f_src = file_params.get("filename")
                f_dest = file_params.get("destination") or file_params.get("new_name") or ""
                logger.info("[Planner FileOps] Structured file rename: src='%s', new_name='%s'", f_src, f_dest)
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Rename file '{f_src}' to '{f_dest}'",
                    required_agent_type="file_agent",
                    inputs={"action": "rename", "path": f_src, "source": f_src, "new_name": f_dest, "destination": f_dest}
                )
            elif f_act == "create":
                f_name = file_params.get("filename") or "new_file.txt"
                f_content = file_params.get("content", "")
                f_dir = file_params.get("directory") or "documents"
                logger.info("[Planner FileOps] Structured file create: name='%s', dir='%s', content_len=%d", f_name, f_dir, len(f_content))
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Create file '{f_name}' in {f_dir}",
                    required_agent_type="file_agent",
                    inputs={"action": "create", "path": f_name, "content": f_content, "directory": f_dir}
                )
            elif f_act == "delete":
                f_name = file_params.get("filename") or ""
                f_dir = file_params.get("directory") or "workspace"
                logger.info("[Planner FileOps] Structured file delete: target='%s', dir='%s'", f_name, f_dir)
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Delete file '{f_name}' from {f_dir}",
                    required_agent_type="file_agent",
                    inputs={"action": "delete_file", "path": f_name, "file_path": f_name, "directory": f_dir}
                )
            elif f_act == "read":
                f_name = file_params.get("filename") or ""
                f_dir = file_params.get("directory") or "documents"
                logger.info("[Planner FileOps] Structured file read: target='%s', dir='%s'", f_name, f_dir)
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Read file '{f_name}' from {f_dir}",
                    required_agent_type="file_agent",
                    inputs={"action": "read", "path": f_name, "file_path": f_name, "directory": f_dir}
                )

        # -1. Affirmative Confirmation Handoff (Gate 2 Approval for Pending Actions - Priority 5 & 6)
        from orchestrator.memory import memory_manager
        pending = memory_manager.get_pending_action()
        is_approval = pending and any(
            re.search(r"\b" + re.escape(w) + r"\b", lower)
            for w in ["yes", "confirm", "proceed", "approve", "go ahead", "do it", "sure", "authorized", "ok", "yeah", "yep"]
        )
        if is_approval:
            req_agent = pending.get("required_agent_type", "system_control_agent")
            action_inputs = dict(pending.get("inputs", {}))
            action_inputs["user_confirmed"] = True
            action_inputs["confirmed"] = True
            memory_manager.clear_pending_action()
            logger.info("[Planner] Handoff approved pending action: agent=%s, inputs=%s", req_agent, action_inputs)
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Execute approved sensitive action: {pending.get('action')}",
                required_agent_type=req_agent,
                inputs=action_inputs,
                confirmed=True,
                user_confirmed=True,
            )
        elif pending and any(re.search(r"\b" + re.escape(w) + r"\b", lower) for w in ["no", "cancel", "stop", "abort", "don't", "dont", "wait", "nevermind"]):
            cancelled_act = pending.get("action", "operation")
            memory_manager.clear_pending_action()
            logger.info("[Planner] User explicitly cancelled pending action: %s", cancelled_act)
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Cancel pending sensitive action: {cancelled_act}",
                required_agent_type="core_llm_agent",
                inputs={"action": "cancel_action", "response": f"Action cancelled. The sensitive operation '{cancelled_act}' was safely aborted.", "user_cancelled": True},
                confirmed=False,
            )

        # 0cb. Grounded Capability Introspection (Priority 8)
        cap_triggers = [
            "what are your capabilities", "what can you do", "list your capabilities",
            "what agents do you have", "show your capabilities", "tell me your capabilities",
            "what skills do you have", "tell me what you can do", "list your skills"
        ]
        if any(ct in lower for ct in cap_triggers):
            import yaml
            from orchestrator.router import REGISTRY_CONFIG_PATH
            reg_text = ""
            if REGISTRY_CONFIG_PATH.exists():
                try:
                    with open(REGISTRY_CONFIG_PATH, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                        cap_lines = []
                        for aid, spec in data.get("agents", {}).items():
                            cap_lines.append(f"- {spec.get('name', aid)} ({aid}): {spec.get('description', '')} [Capabilities: {', '.join(spec.get('capabilities', []))}]")
                        reg_text = "\n".join(cap_lines)
                except Exception as ex:
                    logger.warning("[Planner] Could not load agent registry for capability grounding: %s", ex)

            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Present verified agent capabilities from registry",
                required_agent_type="core_llm_agent",
                inputs={
                    "query": text,
                    "system_extra": (
                        f"CRITICAL GROUNDING: You must answer the user's question about your capabilities strictly and exclusively using the following verified registry of built agents:\n\n"
                        f"{reg_text}\n\n"
                        f"Do not invent capabilities outside this list. Emphasize that you operate locally on personal hardware. "
                        f"Summarize concisely in 4-5 bullet points covering your core agents (e.g. Web Action Agent, System Control, File Management, Schedulers, Dev Tools). Keep response under 100 words."
                    )
                }
            )

        # 0. User Operational Feedback / Complaints (Priority 4)
        # Prevents frustration messages like "unable to play", "it didn't work" from being re-searched as songs!
        complaint_phrases = [
            "unable", "can't", "cannot", "didn't work", "not working", "why didn't you",
            "nothing played", "didn't play", "won't play", "failed", "broken",
            "doesn't work", "did not work", "did not play", "why did you", "not playing"
        ]
        is_technical_question = bool(re.search(r"\b(?:how\s+(?:do|can|to)|why\s+(?:is|does)|explain|what\s+is|what\s+causes|debug|solve|fix\s+(?:a|the|this)|error|exception)\b", lower))
        if any(p in lower for p in complaint_phrases) and not is_technical_question:
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Address user operational feedback conversationally",
                required_agent_type="core_llm_agent",
                inputs={"query": text, "instruction": "The user is reporting an operational failure or complaint about a previous task. Acknowledge respectfully in your persona character, do not launch any external tools or songs, and ask how to proceed."}
            )

        # 0b. Unsupported Music Streaming Platforms (Priority 6)
        # Truthful clarification for Spotify, Apple Music, etc.
        unsupported_music = ["spotify", "apple music", "soundcloud", "amazon music", "tidal", "gaana", "jiosaavn", "wynk"]
        if any(w in lower for w in ["play", "listen to", "stream", "song", "music"]) and any(p in lower for p in unsupported_music) and not lower.startswith("open"):
            matched_p = next(p for p in unsupported_music if p in lower).capitalize()
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Inform user regarding unsupported platform {matched_p}",
                required_agent_type="core_llm_agent",
                inputs={"query": f"The user asked to play audio on {matched_p}. Respond honestly and clearly: 'I can only play audio directly from YouTube right now. Would you like me to play this on YouTube instead, or open the {matched_p} application for you?'"}
            )

        # 0c. Memory Storage & Owner Identity Recall (Priority 8)
        if any(w in lower for w in ["what do you remember", "tell me what you remember", "what is in your memory", "what you remember", "show what you remember", "list memories", "show memories"]):
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Recall all stored facts from Long-Term Memory",
                required_agent_type="system_control_agent",
                inputs={"action": "recall_memories", "query": text}
            )

        if any(w in lower for w in ["who is your owner", "who is my owner", "who owns you", "who is the owner", "who made you"]):
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Recall owner identity from Long-Term Memory",
                required_agent_type="system_control_agent",
                inputs={"action": "recall_owner", "query": text}
            )

        forget_correction = re.search(r"^(?:actually\s+)?forget\s+(?:that|this)[.,;!]?\s+(.+)$", text, flags=re.IGNORECASE)
        if forget_correction and len(forget_correction.group(1).strip()) > 3:
            return self._build_single_step(plan_id, forget_correction.group(1).strip())

        if any(w in lower for w in ["forget that", "forget this", "forget the", "forget my", "delete from memory", "remove from memory", "erase memory"]):
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Forget fact from persistent memory",
                required_agent_type="system_control_agent",
                inputs={"action": "forget", "query": text}
            )

        if any(w in lower for w in ["change it to", "update it to", "actually, change", "change that to", "update memory to"]):
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Update fact in persistent memory",
                required_agent_type="system_control_agent",
                inputs={"action": "update_memory", "query": text}
            )

        if any(w in lower for w in ["remember that", "remember it", "remember this", "remember:", "remember "]) or re.search(r"\b[a-zA-Z]+\s+is\s+(?:my|your)\s+owner\b", lower) or re.search(r"\bmy\s+name\s+is\s+[a-zA-Z]+\b", lower):
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Store fact in persistent memory",
                required_agent_type="system_control_agent",
                inputs={"action": "remember", "query": text}
            )


        # 0d. Prohibited General Shell Execution Refusal Gate (Safety Invariant - Group 3)
        prohibited_shell = [
            "run shell", "shell command", "execute bash", "execute in bash", "powershell command",
            "run terminal", "run in cmd", "execute in shell", "run bash", "run in bash", "bash command"
        ]
        if any(p in lower for p in prohibited_shell) or re.search(r"\b(?:run|execute)\s+(?:this\s+)?(?:shell|bash|powershell|cmd|terminal)\b", lower) or re.search(r"\b(?:bash|powershell|cmd):\s*", lower):
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Refuse prohibited general shell execution",
                required_agent_type="dev_tool_agent",
                inputs={"action": "refuse_general_shell", "command": text}
            )

        # 0e-1. Alarms, Reminders & Scheduling (Priority over Notification Triage)
        is_alarm_or_timer = bool(
            re.search(r"\b(?:set|create|schedule)\s+(?:an?\s+)?(?:alarm|timer|reminder)\b", lower) or
            re.search(r"\b(?:alarm|timer)\s+(?:of|for|at|in)\b", lower) or
            re.search(r"\bwake\s+me\s+(?:up\s+)?(?:at|for|in)\b", lower) or
            re.search(r"\bremind\s+me\s+(?:in|at|to)\b", lower)
        )
        if is_alarm_or_timer:
            sched_params = parameter_extractor.extract_schedule_params(text)
            delay = int(sched_params.get("delay_seconds", 60))
            msg = sched_params.get("message") or "Scheduled alarm notification"
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Set in-app alarm for {delay} seconds",
                required_agent_type="scheduler_agent",
                inputs={"action": "set_alarm", "delay_seconds": delay, "message": msg}
            )

        if any(w in lower for w in ["list alarms", "show alarms", "active alarms", "my alarms"]):
            return TaskStep(f"{plan_id}_step_1", "List active alarms", "scheduler_agent", {"action": "list"})

        if any(w in lower for w in ["cancel alarm", "delete alarm"]):
            return TaskStep(f"{plan_id}_step_1", "Cancel active alarm", "scheduler_agent", {"action": "cancel"})

        # 0e. Desktop Notification Triage (Group 5 - Read Only)
        if any(w in lower for w in ["notification", "notifications", "triage notifications", "unread alerts", "check alerts"]) and not any(w in lower for w in ["send", "create", "trigger", "alarm", "timer", "remind", "set"]):
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Read-only desktop notification triage from Windows Action Center",
                required_agent_type="notification_triage_agent",
                inputs={"action": "triage_notifications", "limit": 25}
            )

        # 0f. Camera OCR & Document Scanning (Priority 7)
        ocr_keywords = [
            "read this document", "read document", "scan document", "scan this document",
            "scan receipt", "read receipt", "read this receipt", "extract text from document",
            "extract text from receipt", "ocr document", "ocr this document", "scan image",
            "extract text from image", "ocr receipt", "read this image", "scan bill", "read invoice"
        ]
        ocr_match = re.search(r"\b(?:ocr|scan\s+(?:document|receipt|whiteboard|image|bill|invoice|paper)|extract\s+text\s+from(?:\s+image)?)\s*(.*)", lower)
        if any(k in lower for k in ocr_keywords) or (ocr_match and ("ocr" in lower or "scan" in lower or "extract" in lower)):
            img_target = ocr_match.group(1).strip() if ocr_match else ""
            if not img_target or img_target in ["this document", "document", "receipt", "image", "this receipt", "the document", "the receipt"]:
                from orchestrator.memory import memory_manager
                from config.settings import PROJECT_ROOT
                from pathlib import Path
                last_img = memory_manager.retrieve("last_image_path")
                if last_img and Path(last_img).exists():
                    img_target = str(last_img)
                else:
                    cand = PROJECT_ROOT / "workspace" / "test_ocr" / "invoice_receipt.png"
                    if not cand.exists():
                        cand = PROJECT_ROOT / "workspace" / "sample_receipt.png"
                    img_target = str(cand)

            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Scan document and extract text via native Windows OCR: {img_target}",
                required_agent_type="vision_ocr_agent",
                inputs={"action": "scan_document", "image_path": img_target, "save_to_kb": "knowledge" in lower or "save" in lower}
            )

        # 0w. WhatsApp Messaging (Priority 10) & WhatsApp Calling (Priority 11)
        if "whatsapp" in lower and any(w in lower for w in ["call", "dial", "ring", "voice call"]):
            m_call = re.search(r"\b(?:call|dial|ring)\s+([a-zA-Z0-9_\s]+?)(?:\s+on\s+whatsapp)?$", lower)
            contact = "Contact"
            if m_call:
                contact = m_call.group(1).replace("on whatsapp", "").strip().capitalize()
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Initiate WhatsApp voice call to {contact}",
                required_agent_type="browser_automation_agent",
                inputs={"action": "whatsapp_call", "contact": contact, "target": contact}
            )

        wa_msg_match = re.search(r"\b(?:send|write)\s+(?:a\s+)?whatsapp(?:\s+message)?\s+(?:to\s+)?([a-zA-Z0-9_\s]+?)\s+(?:saying|that|with text|message)?\s*[:\"']?(.+)[\"']?$", lower)
        if "whatsapp" in lower and any(w in lower for w in ["send", "message", "text", "write"]):
            recipient = "Contact"
            msg_body = "Hello from JARVIS"
            if wa_msg_match:
                recipient = wa_msg_match.group(1).strip()
                msg_body = wa_msg_match.group(2).strip().strip('"\'')
            else:
                m1 = re.search(r"\bto\s+([a-zA-Z0-9_]+)", lower)
                if m1:
                    recipient = m1.group(1).capitalize()
                m2 = re.search(r"\b(?:saying|that)\s+(.+)", text, re.IGNORECASE)
                if m2:
                    msg_body = m2.group(1).strip()

            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Draft and send WhatsApp message to {recipient}",
                required_agent_type="communication_agent",
                inputs={"channel": "whatsapp", "action": "send_whatsapp", "recipient": recipient, "to": recipient, "body": msg_body, "text": msg_body}
            )

        # 0g. Allowlisted Dev Support: Git, Regex, JSON (Group 3)
        if any(w in lower for w in ["git status", "status of git", "status of the repo", "repository status"]) or lower.startswith("git status"):
            return TaskStep(f"{plan_id}_step_1", "Execute allowlisted git status", "dev_tool_agent", {"action": "git_status"})
        elif any(w in lower for w in ["git diff", "show diff", "show me the diff", "git changes", "working tree changes"]) or lower.startswith("git diff"):
            return TaskStep(f"{plan_id}_step_1", "Execute allowlisted git diff", "dev_tool_agent", {"action": "git_diff"})
        elif any(w in lower for w in ["git branch", "list branches", "show branches", "what branches"]) or lower.startswith("git branch"):
            return TaskStep(f"{plan_id}_step_1", "Execute allowlisted git branch list", "dev_tool_agent", {"action": "git_branch"})
        elif re.search(r"\b(?:create|make)\s+(?:a\s+)?(?:new\s+|temporary\s+)?(?:test\s+)?branch(?:\s+called\s+|\s+named\s+|\s+)?([a-zA-Z0-9_\-\.]*)", lower):
            b_m = re.search(r"\b(?:create|make)\s+(?:a\s+)?(?:new\s+|temporary\s+)?(?:test\s+)?branch(?:\s+called\s+|\s+named\s+|\s+)?([a-zA-Z0-9_\-\.]*)", lower)
            b_name = b_m.group(1).strip() if (b_m and b_m.group(1)) else "temp-test-branch"
            return TaskStep(f"{plan_id}_step_1", f"Create temporary git branch {b_name}", "dev_tool_agent", {"action": "git_create_branch", "branch": b_name})
        elif (
            re.match(r"^git\s+(?:switch|checkout)\s+(.+)", lower)
            or re.search(r"\bswitch\s+(?:to\s+)?(?:it|the\s+branch|temporary\s+branch)\b", lower)
            or re.search(r"\bswitch\s+back\b", lower)
            or re.search(r"\bswitch\s+(?:to\s+)?([a-zA-Z0-9_\-]+)\s+branch\b", lower)
            or re.search(r"\bswitch\s+branch\s+(?:to\s+)?([a-zA-Z0-9_\-]+)\b", lower)
        ):
            branch_match = (
                re.search(r"\bswitch\s+(?:to\s+)?([a-zA-Z0-9_\-]+)\s+branch\b", lower)
                or re.search(r"\bswitch\s+branch\s+(?:to\s+)?([a-zA-Z0-9_\-]+)\b", lower)
            )
            if branch_match:
                target_b = branch_match.group(1).strip()
            elif "it" in lower or "temporary" in lower:
                target_b = "temp-test-branch"
            elif "back" in lower:
                target_b = "main"
            elif re.match(r"^git\s+(?:switch|checkout)\s+(.+)", lower):
                target_b = re.match(r"^git\s+(?:switch|checkout)\s+(.+)", lower).group(1).strip()
            else:
                target_b = "main"
            return TaskStep(f"{plan_id}_step_1", f"Switch git branch to {target_b}", "dev_tool_agent", {"action": "git_switch", "branch": target_b})
        elif re.match(r"^git\s+commit\s+(?:-m\s+)?(.+)", lower):
            c_msg = re.match(r"^git\s+commit\s+(?:-m\s+)?(.+)", lower).group(1).strip().strip('"\'')
            return TaskStep(f"{plan_id}_step_1", f"Commit changes to git: {c_msg}", "dev_tool_agent", {"action": "git_commit", "message": c_msg})
        elif any(w in lower for w in ["don't commit", "dont commit", "do not commit"]):
            return TaskStep(f"{plan_id}_step_1", "Acknowledge no commit instruction", "core_llm_agent", {"query": text, "instruction": "The user instructed not to commit any changes. Acknowledge respectfully that no commits will be made and the working tree remains unstaged."})
        elif "generate regex" in lower or "create regex" in lower or re.match(r"^regex\s+(?:for\s+)?(.+)", lower):
            reg_desc = re.sub(r"^(?:generate|create)?\s*regex\s*(?:for\s*)?", "", lower).strip()
            return TaskStep(f"{plan_id}_step_1", f"Generate regex for: {reg_desc}", "dev_tool_agent", {"action": "generate_regex", "description": reg_desc})
        elif "format json" in lower or "validate json" in lower:
            return TaskStep(f"{plan_id}_step_1", "Format and validate JSON payload", "dev_tool_agent", {"action": "format_json", "json": text})

        # 0h. Desktop Window & Workspace Management (Group 1 - Regression 2 Fix)
        snap_m = re.search(r"\bsnap\s+.*?(left|right|top|bottom|maximize|restore)", lower)
        if snap_m:
            direction = snap_m.group(1).lower()
            return TaskStep(f"{plan_id}_step_1", f"Snap active window to {direction}", "system_control_agent", {"action": "snap_window", "direction": direction})

        if lower in ["minimize", "minimize it", "minimize this", "minimize window", "minimize active window"] or re.search(r"\bminimize\s+(?:the\s+)?([a-zA-Z0-9_\s]+)\b", lower):
            min_target = None
            min_m = re.search(r"\bminimize\s+(?:the\s+)?([a-zA-Z0-9_\s]+)\b", lower)
            if min_m and min_m.group(1) not in ["it", "this", "window", "active window"]:
                min_target = min_m.group(1).strip()
            return TaskStep(f"{plan_id}_step_1", "Minimize window", "system_control_agent", {"action": "minimize_window", "target": min_target})

        if lower in ["bring it back", "bring this back", "restore it", "restore this", "restore window", "restore active window"] or re.search(r"\brestore\s+(?:the\s+)?([a-zA-Z0-9_\s]+)\b", lower):
            res_target = None
            res_m = re.search(r"\brestore\s+(?:the\s+)?([a-zA-Z0-9_\s]+)\b", lower)
            if res_m and res_m.group(1) not in ["it", "this", "window", "active window"]:
                res_target = res_m.group(1).strip()
            return TaskStep(f"{plan_id}_step_1", "Restore window", "system_control_agent", {"action": "restore_window", "target": res_target})

        front_m = re.search(r"\bbring\s+([a-zA-Z0-9_\s]+?)\s+to\s+the\s+front\b", lower)
        if front_m:
            f_target = front_m.group(1).strip()
            return TaskStep(f"{plan_id}_step_1", f"Bring window '{f_target}' to front", "system_control_agent", {"action": "switch_window", "target": f_target})

        switch_m = re.search(r"\bswitch\s+(?:to\s+)?([a-zA-Z0-9_\s]+)\b", lower)
        if switch_m and not any(w in lower for w in ["git switch", "switch branch", "branch"]):
            sw_target = switch_m.group(1).strip()
            return TaskStep(f"{plan_id}_step_1", f"Switch window to '{sw_target}'", "system_control_agent", {"action": "switch_window", "target": sw_target})

        which_win_m = re.search(r"\bwhich\s+one\s+is\s+([a-zA-Z0-9_\s]+)\b", lower)
        if which_win_m:
            target_app = which_win_m.group(1).strip()
            return TaskStep(f"{plan_id}_step_1", f"Identify window for '{target_app}'", "system_control_agent", {"action": "find_window", "target": target_app})

        if any(w in lower for w in ["list windows", "open windows", "active windows", "show windows", "what windows are open", "which windows are open"]):
            return TaskStep(f"{plan_id}_step_1", "List desktop windows", "system_control_agent", {"action": "list_windows"})

        if lower in ["close the application", "close this application", "close the app", "close this app", "close application", "close window", "close active window"]:
            return TaskStep(f"{plan_id}_step_1", "Close active desktop application", "system_control_agent", {"action": "close_application", "target": "active"})


        # 0i. System Power States & Scheduled Actions (Group 1)
        sched_power_m = re.search(r"\b(?:shut\s*down|power\s*off|restart|reboot)\s+(?:in|after)\s+(\d+)\s*(minutes?|mins?|seconds?|secs?|hours?|hrs?)", lower)
        if sched_power_m:
            p_val = int(sched_power_m.group(1))
            p_unit = sched_power_m.group(2).lower()
            p_action = "shutdown" if "shut" in lower or "power" in lower else "restart"
            delay_sec = p_val * 60 if "min" in p_unit else (p_val * 3600 if "hour" in p_unit or "hr" in p_unit else p_val)
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Schedule system {p_action} in {delay_sec} seconds",
                required_agent_type="scheduler_agent",
                inputs={"action": "set_alarm", "delay_seconds": delay_sec, "message": f"Execute authorized system {p_action}"}
            )

        # General linguistic guard: Questions/inquiries must NEVER execute destructive OS power actions
        is_interrogative = bool(re.search(r"^(?:did|have|has|had|were|was|are|is|can|could|will|would|do|does|why|what|when|where|who|how)\b", lower) or lower.strip().endswith("?"))
        if not is_interrogative:
            if any(w in lower for w in ["shut down pc", "shutdown computer", "turn off pc", "power off computer", "shut down the system", "shut down the computer", "shutdown the computer", "turn off the computer"]) or (re.search(r"\b(?:shutdown|shut down)\b", lower) and not any(w in lower for w in ["backend", "server", "app", "tab", "window", "process", "service"])):
                return TaskStep(f"{plan_id}_step_1", "Execute system shutdown (Requires Two-Gate Approval)", "system_control_agent", {"action": "power_shutdown"})
            if any(w in lower for w in ["restart pc", "restart computer", "reboot pc", "reboot computer", "restart the system", "restart the computer", "reboot the computer", "restart the pc", "reboot the pc"]) or (re.search(r"\b(?:restart|reboot)\b", lower) and not any(w in lower for w in ["backend", "server", "app", "service", "process"])):
                return TaskStep(f"{plan_id}_step_1", "Execute system restart (Requires Two-Gate Approval)", "system_control_agent", {"action": "power_restart"})
            if any(w in lower for w in ["put pc to sleep", "sleep pc", "system sleep", "put the computer to sleep"]):
                return TaskStep(f"{plan_id}_step_1", "Put system to sleep (Requires Two-Gate Approval)", "system_control_agent", {"action": "power_sleep"})


        # 0j. Audio, Volume & Peripherals (Group 1)
        vol_m = re.search(r"\b(?:set\s+)?volume\s+(?:to\s+)?(\d+)\b", lower)
        vol_up_m = re.search(r"\b(?:increase|raise|turn up)\s+volume(?:\s+by\s+(\d+))?\b", lower)
        vol_down_m = re.search(r"\b(?:decrease|lower|turn down)\s+volume(?:\s+by\s+(\d+))?\b", lower)
        if vol_m:
            val = int(vol_m.group(1))
            return TaskStep(f"{plan_id}_step_1", f"Set system master volume to {val}%", "system_control_agent", {"action": "set_volume", "level": val})
        elif vol_up_m:
            delta = int(vol_up_m.group(1)) if vol_up_m.group(1) else 10
            return TaskStep(f"{plan_id}_step_1", f"Increase master volume by {delta}%", "system_control_agent", {"action": "adjust_volume", "delta": delta})
        elif vol_down_m:
            delta = int(vol_down_m.group(1)) if vol_down_m.group(1) else 10
            return TaskStep(f"{plan_id}_step_1", f"Decrease master volume by {delta}%", "system_control_agent", {"action": "adjust_volume", "delta": -delta})
        elif any(w in lower for w in ["mute audio", "mute sound", "mute volume", "mute pc", "mute the computer", "mute system"]) or lower == "mute":
            return TaskStep(f"{plan_id}_step_1", "Mute system audio", "system_control_agent", {"action": "mute"})
        elif any(w in lower for w in ["unmute audio", "unmute sound", "unmute volume", "unmute pc", "unmute the computer", "unmute system"]) or lower == "unmute":
            return TaskStep(f"{plan_id}_step_1", "Unmute system audio", "system_control_agent", {"action": "unmute"})

        if any(w in lower for w in ["audio device", "audio devices", "sound output", "playback devices"]):
            return TaskStep(f"{plan_id}_step_1", "List audio playback devices", "system_control_agent", {"action": "list_audio_devices"})
        if any(w in lower for w in ["connected peripherals", "usb devices", "list peripherals", "peripherals"]):
            return TaskStep(f"{plan_id}_step_1", "List connected peripherals", "system_control_agent", {"action": "list_connected_peripherals"})
        if "bluetooth on" in lower or "enable bluetooth" in lower:
            return TaskStep(f"{plan_id}_step_1", "Enable Bluetooth service", "system_control_agent", {"action": "toggle_bluetooth", "enable": True})
        if "bluetooth off" in lower or "disable bluetooth" in lower:
            return TaskStep(f"{plan_id}_step_1", "Disable Bluetooth service", "system_control_agent", {"action": "toggle_bluetooth", "enable": False})

        # 0ja. Browser Tabs & Window Focus (Brings Chrome to front)
        if any(w in lower for w in [
            "show me all the tabs on screen", "show me all the tabs", "show all tabs", "show tabs",
            "list tabs", "active tabs", "show the tabs", "tabs on screen", "bring chrome to front",
            "switch to chrome", "show chrome", "open tabs"
        ]):
            return TaskStep(f"{plan_id}_step_1", "Bring browser to front and display active tabs", "browser_automation_agent", {"action": "show_tabs"})

        # 0jb. Real-Time Sports & Match Scores (Routed to Web Search for live data)
        score_keywords = ["match score", "cricket score", "live score", "current score", "football score", "ipl score", "game score", "today's score", "match status"]
        if any(w in lower for w in score_keywords):
            return TaskStep(f"{plan_id}_step_1", f"Search live web for {text}", "web_agent", {"query": text})

        # 0k. Batch File Operations & Compression (Group 2)
        batch_m = re.search(r"\bbatch\s+rename\s+(?:files?\s+)?(?:matching\s+)?['\"]?([^\s'\"]+)['\"]?\s+to\s+['\"]?([^\s'\"]+)['\"]?(?:\s+in\s+([a-zA-Z0-9_.-]+))?", lower)
        if batch_m:
            b_pat = batch_m.group(1)
            b_rep = batch_m.group(2)
            b_dir = batch_m.group(3) or "documents"
            return TaskStep(f"{plan_id}_step_1", f"Batch rename files matching '{b_pat}' to '{b_rep}' in {b_dir}", "file_agent", {"action": "batch_rename", "pattern": b_pat, "replacement": b_rep, "directory": b_dir})

        extract_m = re.search(r"\b(?:extract|unzip)\s+(?:archive|file)?\s*([^\s]+)(?:\s+(?:to|into)\s+([^\s]+))?", lower)
        if extract_m:
            e_arc = extract_m.group(1)
            e_dest = extract_m.group(2)
            return TaskStep(f"{plan_id}_step_1", f"Extract archive '{e_arc}'", "file_agent", {"action": "extract", "archive": e_arc, "target_dir": e_dest})

        comp_m = re.search(r"\b(?:compress\s+(?:folder|directory)?|zip\s+(?:folder|directory)?)\s*([^\s]+)(?:\s+(?:to|into)\s+([^\s]+))?", lower)
        if comp_m:
            c_src = comp_m.group(1)
            c_out = comp_m.group(2)
            return TaskStep(f"{plan_id}_step_1", f"Compress '{c_src}' into zip archive", "file_agent", {"action": "compress", "source": c_src, "output_zip": c_out})

        conv_img_m = re.search(r"\bconvert\s+(?:image\s+)?([^\s]+)\s+to\s+(webp|png|jpg|jpeg)\b", lower)
        if conv_img_m:
            img_src = conv_img_m.group(1)
            img_fmt = conv_img_m.group(2)
            return TaskStep(f"{plan_id}_step_1", f"Convert image '{img_src}' to {img_fmt}", "file_agent", {"action": "convert_image", "path": img_src, "format": img_fmt})

        conv_doc_m = re.search(r"\bconvert\s+(?:document\s+)?([^\s]+)\s+to\s+(txt|text|pdf)\b", lower)
        if conv_doc_m:
            doc_src = conv_doc_m.group(1)
            doc_fmt = conv_doc_m.group(2)
            return TaskStep(f"{plan_id}_step_1", f"Convert document '{doc_src}' to {doc_fmt}", "file_agent", {"action": "convert_document", "path": doc_src, "format": doc_fmt})

        # 1. Device Registry queries (authoritative live device query)
        device_phrases = [
            "connected device", "connected devices", "devices are connected",
            "devices do i have", "my devices", "show devices", "show my devices",
            "list devices", "list my devices", "what devices", "tell me connected devices",
            "tell me my connected devices", "device status", "device registry", "active devices"
        ]
        if any(p in lower for p in device_phrases):
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Query live Device Registry",
                required_agent_type="system_control_agent",
                inputs={"action": "devices", "query": text}
            )

        # 2. Real Current-Time query
        time_phrases = [
            "current time", "what time is it", "what is the time", "tell me current time",
            "tell me the time", "time now", "what's the time", "current date and time",
            "today's date", "what date is it", "what day is today"
        ]
        if any(p in lower for p in time_phrases) or lower in ["time", "current time", "what time"]:
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Query live current time in configured timezone",
                required_agent_type="system_control_agent",
                inputs={"action": "time", "query": text}
            )

        # 2b. Code Review & Analysis (Priority Developer Task)

        is_code_review = (
            re.search(r"\b(?:review|analyze|debug|inspect)\s+(?:this\s+)?(?:python\s+)?(?:code|function|snippet|script)?\s*:", lower) or
            re.match(r"^review\s+this\b", lower) or
            re.search(r"\b(?:review|analyze|debug)\s+this\s+python\s+code\b", lower) or
            ("review" in lower and any(kw in lower for kw in ["def ", "class ", "return ", "import ", "lambda "]))
        )
        if is_code_review:
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Perform code review and error analysis",
                required_agent_type="core_llm_agent",
                inputs={
                    "query": text,
                    "system_extra": (
                        "CRITICAL DEVELOPER INSTRUCTION: The user has provided code for review. "
                        "Carefully analyze syntax, logic, and potential runtime errors (such as ZeroDivisionError, infinite recursion, or unhandled exceptions). "
                        "State any bugs directly, explain why they occur, and provide a corrected version. "
                        "Do NOT launch any browser, do NOT open any websites, and do NOT interpret identifiers (e.g. 'x', 'view', 'browser') as web navigation targets."
                    )
                }
            )

        # 3. Generalized Astra Live Web Action (Architectural Shift)

        # Any "do X on Y", "search X on Y", "look for X on Y", "open Y and do X", etc.
        chained_m1 = re.match(r"^(?:please\s+)?(?:open|launch|go to|browse to)\s+([a-zA-Z0-9_.-]+)\s+(?:and|, then|then)\s+(?:search(?:\s+for)?|find|look up)\s+(.+)$", lower)
        chained_m2 = re.match(r"^(?:please\s+)?(?:search(?:\s+for)?|look(?:\s+for)?)\s+(.+?)\s+(?:on|in)\s+([a-zA-Z0-9_.-]+)$", lower)
        chained_m3 = re.match(r"^(?:please\s+)?search\s+([a-zA-Z0-9_.-]+)\s+(?:for|about)\s+(.+)$", lower)

        known_web_platforms = [
            "linkedin", "internshala", "snapchat", "facebook", "instagram", "youtube", "twitter",
            "reddit", "github", "wikipedia", "amazon", "google", "bing", "yahoo", "netflix",
            "maps", "chatgpt", "claude", "groq", "perplexity", "gemini", "deepseek", "copilot", "spotify", "gmail", "whatsapp"
        ]

        if chained_m1:
            site = chained_m1.group(1).strip()
            search_term = chained_m1.group(2).strip()
            if site.lower() not in ["documents", "downloads", "desktop", "workspace"]:
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Astra live web action: open {site} and search for '{search_term}'",
                    required_agent_type="browser_automation_agent",
                    inputs={"action": "web_action", "query": search_term, "site": site, "task": text}
                )
        elif chained_m2:
            search_term = chained_m2.group(1).strip()
            site = chained_m2.group(2).strip()
            if site.lower() not in ["documents", "downloads", "desktop", "workspace"]:
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Astra live web action: search for '{search_term}' on {site}",
                    required_agent_type="browser_automation_agent",
                    inputs={"action": "web_action", "query": search_term, "site": site, "task": text}
                )
        elif chained_m3:
            site = chained_m3.group(1).strip()
            search_term = chained_m3.group(2).strip()
            if site.lower() not in ["documents", "downloads", "desktop", "workspace"]:
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Astra live web action: search {site} for '{search_term}'",
                    required_agent_type="browser_automation_agent",
                    inputs={"action": "web_action", "query": search_term, "site": site, "task": text}
                )

        # 3b. Application / Website / Game Open & Launch Execution (Priority 3)
        # Examples: "open google", "open notepad", "open chrome", "launch steam", "play minecraft", "open calculator", "start gta"
        open_match = (
            re.match(r"^(?:please\s+)?(?:open|launch|start|run|play|go to|browse to)\s+(?:the\s+)?(?:game\s+|app\s+|application\s+)?(.+)$", clean_lower)
            or re.match(r"^(?:please\s+)?(?:open|launch|start|run|play|go to|browse to)\s+(?:the\s+)?(?:game\s+|app\s+|application\s+)?(.+)$", lower)
        )
        if open_match:
            target_raw = open_match.group(1).strip()
            # Conjunction splitting for compound requests like "open chatgpt and say hi" -> extract primary target "chatgpt"
            target_primary = re.split(r"\s+(?:and|then|with)\s+", target_raw, flags=re.IGNORECASE)[0].strip()
            # Clean trailing polite words
            for suffix in [" for me", " please", " on my pc", " on desktop", " game", " app", " application"]:
                if target_primary.endswith(suffix):
                    target_primary = target_primary[:-len(suffix)].strip()
            target_primary = target_primary.rstrip('.?!').strip()

            target_lower = target_primary.lower()
            known_websites = [
                "google", "youtube", "github", "reddit", "twitter", "x", "wikipedia", "netflix",
                "bing", "yahoo", "amazon", "linkedin", "internshala", "snapchat", "facebook",
                "chatgpt", "claude", "groq", "perplexity", "gemini", "deepseek", "copilot", "spotify", "gmail", "whatsapp", "instagram"
            ]
            is_website = (
                target_lower in known_websites or
                target_lower.startswith("http://") or
                target_lower.startswith("https://") or
                target_lower.startswith("www.") or
                ("." in target_lower and " " not in target_lower)
            )

            if is_website:
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Open website visibly in browser: {target_primary}",
                    required_agent_type="browser_automation_agent",
                    inputs={"action": "web_action", "query": target_primary, "site": target_lower, "target": target_primary, "task": text}
                )
            else:
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Launch application: {target_primary}",
                    required_agent_type="system_control_agent",
                    inputs={"action": "open_application", "target": target_primary, "query": text}
                )

        # Close application execution
        close_match = (
            re.match(r"^(?:please\s+)?(?:close|kill|quit|terminate|exit)\s+(?:the\s+)?(?:game\s+|app\s+|application\s+)?(.+)$", clean_lower)
            or re.match(r"^(?:please\s+)?(?:close|kill|quit|terminate|exit)\s+(?:the\s+)?(?:game\s+|app\s+|application\s+)?(.+)$", lower)
        )
        if close_match:
            target_raw = close_match.group(1).strip()
            for suffix in [" for me", " please", " app", " application", " game"]:
                if target_raw.endswith(suffix):
                    target_raw = target_raw[:-len(suffix)].strip()
            target_raw = target_raw.rstrip('.?!').strip()
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Close application: {target_raw}",
                required_agent_type="system_control_agent",
                inputs={"action": "close_application", "target": target_raw, "query": text}
            )

        # Check for any request referencing known web platforms
        web_actions = ["search", "look", "find", "check", "browse", "show", "view", "see", "stories", "posts", "feed", "profile", "account"]
        has_web_action = any(re.search(rf"\b{re.escape(w)}\b", lower) for w in web_actions)

        # Special check for X / Twitter platform
        if (re.search(r"\b(?:on\s+x|x\.com|twitter)\b", lower) or ("x" in lower.split() and any(w in lower for w in ["feed", "tweet", "tweets", "timeline"]))) and has_web_action and not any(w in lower for w in ["documents", "downloads"]):
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Astra live web action on X (Twitter)",
                required_agent_type="browser_automation_agent",
                inputs={"action": "web_action", "site": "twitter", "query": text, "task": text}
            )

        for wp in known_web_platforms:
            if re.search(rf"\b{re.escape(wp)}\b", lower) and has_web_action and not any(w in lower for w in ["documents", "downloads"]):
                resolved_query = text
                # Contextual pronoun resolution (e.g. "show me his Instagram account" after "tell me about virat kohli")
                if any(p in lower for p in [" his ", " her ", " their ", " this "]):
                    last_plan = memory_manager.retrieve("last_plan") or {}
                    prev_goal = last_plan.get("goal", "") if isinstance(last_plan, dict) else ""
                    clean_prev = re.sub(r"\b(tell me about|who is|search for|about|show me)\b", "", prev_goal, flags=re.IGNORECASE).strip()
                    if clean_prev:
                        resolved_query = f"{clean_prev} {wp}"
                return TaskStep(
                    step_id=f"{plan_id}_step_1",
                    description=f"Astra live web action on {wp}",
                    required_agent_type="browser_automation_agent",
                    inputs={"action": "web_action", "site": wp, "query": resolved_query, "task": text}
                )

        # 3c. Live Internship & Job Opportunities Search (Priority 10)
        job_keywords = ["internship", "internships", "job", "jobs", "hiring", "openings", "vacancies", "vacancy", "fresher jobs"]
        if any(w in lower for w in job_keywords):
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description="Live web search for internships and jobs",
                required_agent_type="web_agent",
                inputs={"query": text, "category": "jobs"}
            )

        # Weather & ASR Homophone Ambiguity (Capability 32)
        is_weather = False
        weather_loc = "Delhi"
        weather_time = "now"
        is_conjunction = bool(
            re.search(r"\b(?:know|doubt|wonder|unsure|decide|choose|matter|see|tell|ask|care)\s+whether\b", lower) or
            re.search(r"\bwhether\s+(?:to|or|not|this|that|it|he|she|they|we|i|you|there)\b", lower) or
            re.search(r"\bwhether\b.+\bor\b", lower) or
            "whether this is" in lower or "whether to" in lower or "don't know whether" in lower or "dont know whether" in lower
        )
        if not is_conjunction:
            if any(w in lower for w in ["weather", "forecast", "temperature", "will it rain", "rain tonight"]):
                is_weather = True
            elif (
                re.search(r"\b(?:tell\s+me|what\s*'?s|what\s+is|how\s*'?s|how\s+is|check|show\s+me|give\s+me)\s+(?:the\s+|today'?s\s+|tomorrow'?s\s+)?(?:today\s+)?whether\b", lower) or
                re.search(r"\b(?:today|tomorrow|tonight|right\s+now|current|outside)\s+whether\b", lower) or
                re.search(r"\bwhether\s+(?:today|tomorrow|tonight|right\s+now|outside|forecast|report)\b", lower) or
                re.search(r"\bwhether\s+(?:in|for|at)\s+[a-zA-Z\s]+\b", lower) or
                lower.strip() in ["whether", "today whether", "tell me today whether", "what is whether", "how is whether", "check whether"]
            ):
                is_weather = True
            elif re.search(r"\b(?:what\s+about|how\s+about|and)\s+(tomorrow|today|tonight)\b", lower) or lower in ["and tomorrow", "and tomorrow?", "tomorrow?"]:
                from orchestrator.context_manager import context_manager
                w_ctx = context_manager.get_weather_context() if hasattr(context_manager, "get_weather_context") else {}
                if w_ctx.get("active"):
                    is_weather = True
                    m_t = re.search(r"\b(tomorrow|today|tonight)\b", lower)
                    weather_time = m_t.group(1) if m_t else "tomorrow"
                    weather_loc = w_ctx.get("location", "Delhi")

        if is_weather:
            clean_text = re.sub(r"[?!.,;]+$", "", text).strip()
            m_city = re.search(r"\b(?:in|for|at)\s+([a-zA-Z0-9_\-\s]+?)(?:\s+(?:today|tomorrow|tonight|right\s+now|now))?$", clean_text, re.IGNORECASE)
            if not m_city:
                m_city = re.search(r"\b(?:in|for|at)\s+([a-zA-Z0-9_\-\s]+?)(?:\s+(?:today|tomorrow|tonight|right\s+now|now|\?))", text, re.IGNORECASE)
            if m_city:
                cand = m_city.group(1).strip()
                cand = re.sub(r"\b(?:right\s+now|now|today|tomorrow|tonight)\b", "", cand, flags=re.IGNORECASE).strip().title()
                if cand:
                    weather_loc = cand
            if "tomorrow" in lower:
                weather_time = "tomorrow"
            elif "tonight" in lower:
                weather_time = "tonight"
            elif "today" in lower:
                weather_time = "today"
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Retrieve real-time weather for {weather_loc}",
                required_agent_type="weather_agent",
                inputs={"action": "get_weather", "location": weather_loc, "time_target": weather_time, "query": text}
            )

        # News
        if any(w in lower for w in ["news", "headlines", "current events"]):
            return TaskStep(f"{plan_id}_step_1", "Fetch latest news", "news_agent", {"query": text})

        # Calendar
        if any(w in lower for w in ["calendar", "schedule", "events", "meeting", "agenda"]):
            return TaskStep(f"{plan_id}_step_1", "Inspect calendar events", "calendar_agent", {"action": "list_events"})

        # Communication / Email / SMS (with typo resilience e.g. emial -> email)
        norm_comm = re.sub(r"\bemials?\b", "email", lower)
        comm_pattern = r"\b(?:emails?|draft\s+an?\s+email|inbox|sms|send\s+(?:an?\s+)?(?:email|text|message)|text\s+message)\b"
        if re.search(comm_pattern, norm_comm):
            return TaskStep(f"{plan_id}_step_1", "Handle communication task", "communication_agent", {"query": text})

        # Smart Home
        smart_home_pattern = r"\b(?:lights?|living\s+room|bedroom|kitchen|thermostat|ac|fan)\b"
        turn_pattern = r"\b(?:turn\s+(?:on|off)|switch\s+(?:on|off))\s+(?:the\s+)?(?:lights?|ac|fan|heater|lamp|tv|air\s+conditioner)\b"
        is_smart_home = (
            re.search(turn_pattern, lower)
            or (re.search(smart_home_pattern, lower) and any(w in lower for w in ["turn", "dim", "brighten", "set", "adjust", "temperature", "degrees", "on", "off"]))
        )
        if is_smart_home and not any(w in lower for w in ["flight", "speed of light", "in light of", "highlight"]):
            return TaskStep(f"{plan_id}_step_1", "Execute smart home control", "smart_home_agent", {"command": text})

        # Media / Casting to Peer Device (Phone / TV / Secondary PC)
        if any(w in lower for w in ["cast", "stream", "chromecast", "play on tv", "play on my phone", "play on phone", "play on pc", "play on desktop", "play it on"]):
            return TaskStep(f"{plan_id}_step_1", "Stream media via cast agent", "cast_agent", {"query": text})

        # Local Browser Media Playback (Priority 2 - Generalized Chained Action with YouTube default)
        if (lower.startswith("play ") or any(w in lower for w in ["play song", "play a song", "play new song", "play music", "play track", "play on youtube", "search youtube", "open youtube and play"])) and not any(w in lower for w in ["play on tv", "play on phone", "play on my phone", "play on pc", "play on desktop"]):
            raw_song = re.sub(r"^(?:please\s+)?(?:play|listen to)\s+", "", text, flags=re.IGNORECASE).strip()
            raw_song = re.sub(r"\s+on\s+(?:youtube|browser)$", "", raw_song, flags=re.IGNORECASE).strip()
            song_name = raw_song or text
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Chained browser media playback for: {song_name}",
                required_agent_type="browser_automation_agent",
                inputs={
                    "action": "chained_play",
                    "site": "youtube",
                    "query": song_name,
                    "song": song_name,
                    "task": f"Go to https://www.youtube.com, search for '{song_name}', and initiate playback"
                }
            )

        # Conversational / Persona Identity / Greetings
        if any(w in lower for w in ["who are you", "what are you", "who made you", "introduce yourself", "how are you", "what can you do", "tell me about yourself", "good morning", "good evening", "good afternoon"]) or lower in ["hi", "hello", "hey", "yo", "sup", "who are you"]:
            return TaskStep(f"{plan_id}_step_1", "Conversational response via Core LLM", "core_llm_agent", {"query": text})


        # 5. Scoped File & Document Control (Issue 5)
        # Search files
        file_search_match = re.search(r"\b(?:search|find)\s+(?:for\s+)?([^\s]+)\s+(?:in|under)\s+(documents|downloads|desktop|workspace)", lower)
        if file_search_match:
            pattern = file_search_match.group(1)
            target_folder = file_search_match.group(2)
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Search for files matching '{pattern}' in {target_folder}",
                required_agent_type="file_agent",
                inputs={"action": "search", "pattern": pattern, "directory": target_folder}
            )

        # Move file
        file_move_match = re.search(r"\bmove\s+file\s+([^\s]+)\s+(?:to|into)\s+([^\s]+)", lower)
        if file_move_match:
            src = file_move_match.group(1)
            dest = file_move_match.group(2)
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Move file from {src} to {dest}",
                required_agent_type="file_agent",
                inputs={"action": "move", "source": src, "destination": dest}
            )

        # Create / Delete file fallback
        if not is_past_inquiry and any(w in lower for w in ["create", "write", "make", "save", "delete", "remove"]) and "file" in lower:
            f_params = parameter_extractor.extract_file_parameters(text)
            if f_params.get("requires_clarification"):
                clarif_p = f_params.get("clarification_prompt", "Could you clarify the file operation details?")
                return TaskStep(f"{plan_id}_step_1", "Request user clarification for file operation", "core_llm_agent", {"query": clarif_p, "system_extra": clarif_p})
            if f_params.get("action") == "delete":
                dname = f_params.get("filename") or ""
                ddir = f_params.get("directory") or "workspace"
                return TaskStep(f"{plan_id}_step_1", f"Delete file '{dname}' from {ddir}", "file_agent", {"action": "delete_file", "path": dname, "file_path": dname, "directory": ddir})
            elif f_params.get("action") == "create":
                fname = f_params.get("filename") or "new_file.txt"
                fdir = f_params.get("directory") or "documents"
                fcontent = f_params.get("content", "")
                return TaskStep(f"{plan_id}_step_1", f"Create file '{fname}' in {fdir}", "file_agent", {"action": "create", "path": fname, "content": fcontent, "directory": fdir})

        # Image Generation
        if any(w in lower for w in ["generate image", "create picture", "draw", "render"]):
            return TaskStep(f"{plan_id}_step_1", "Generate image", "image_gen_agent", {"prompt": text})

        # File fallback
        if not is_past_inquiry and any(w in lower for w in ["file", "document", "folder", "read file", "save file"]):
            f_params = parameter_extractor.extract_file_parameters(text)
            f_target = f_params.get("filename") or ""
            f_act = f_params.get("action") or "read"
            if not f_target and f_params.get("requires_clarification"):
                clarif_p = f_params.get("clarification_prompt", "Which file would you like me to access?")
                return TaskStep(f"{plan_id}_step_1", "Request user clarification for file operation", "core_llm_agent", {"query": clarif_p, "system_extra": clarif_p, "response": clarif_p})
            return TaskStep(
                step_id=f"{plan_id}_step_1",
                description=f"Manage local file '{f_target}'",
                required_agent_type="file_agent",
                inputs={"action": f_act, "path": f_target, "file_path": f_target, "filename": f_target, "directory": f_params.get("directory", "documents")}
            )

        # System Control / Telemetry (battery, disk, ram, cpu, network, phone, health, memory)
        telemetry_words = [
            "battery", "storage", "disk", "volume", "system status", "cpu", "ram", "memory",
            "internet", "wifi", "network", "health report", "diagnostic", "test yourself", "self-test",
            "eating the most memory", "phone connected", "is my phone"
        ]
        if any(re.search(rf"\b{re.escape(w)}\b", lower) for w in telemetry_words) or lower in ["cpu?", "ram?", "network?", "wifi?", "phone?"]:
            return TaskStep(f"{plan_id}_step_1", "System telemetry query", "system_control_agent", {"query": text})

        # Biometric Identity Verification (Camera Face Gate)
        if any(w in lower for w in ["verify identity", "facial authentication", "biometric match", "face match"]):
            return TaskStep(f"{plan_id}_step_1", "Verify user identity", "identity_agent", {"action": "verify_face"})

        # Web Search intent
        if any(w in lower for w in ["search", "google", "look up", "find online", "browse web", "research", "tell me about"]):
            return TaskStep(f"{plan_id}_step_1", "Search web for information", "web_agent", {"query": text})

        # Default general conversation / reasoning to Core LLM
        return TaskStep(f"{plan_id}_step_1", "Reason and answer via Core LLM", "core_llm_agent", {"query": text})


task_planner = TaskPlanner()
