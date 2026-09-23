"""JARVIS Planning Engine (Cognitive Core - Stage 5).

Converts GoalTrees into executable, verifiable cognitive plans.
Steps specify required capabilities rather than hard-coded agents.
"""

from dataclasses import dataclass, field
import logging
import time
from typing import Any, Dict, List, Optional
from cognitive.goal_engine import GoalTree, SubGoal

logger = logging.getLogger("JARVIS.Cognitive.PlanningEngine")


@dataclass
class PlanStep:
    step_id: str
    description: str
    required_capability: str     # e.g. "browser.playback", "os.snap_window", "scheduler.set_alarm"
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout_sec: float = 30.0
    verification_rule: str = "auto"
    retry_count: int = 2
    status: str = "PENDING"      # PENDING, RUNNING, COMPLETED, FAILED, BLOCKED
    result: Optional[Any] = None


@dataclass
class CognitivePlan:
    plan_id: str
    root_goal: str
    steps: List[PlanStep] = field(default_factory=list)
    is_fast_path: bool = True
    social_context: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)
    status: str = "PENDING"


class PlanningEngine:
    """Synthesizes capability-driven execution plans with verification contracts."""

    def __init__(self):
        # Maps semantic actions to abstract capability strings
        self._action_capability_map = {
            "play_youtube": "browser.playback",
            "pause_media": "browser.media_control",
            "resume_media": "browser.media_control",
            "close_tab": "browser.tab_control",
            "snap_window": "os.window_management",
            "multi_telemetry": "os.telemetry",
            "set_reminder": "scheduler.alarm",
            "create_branch": "git.branch_management",
            "switch_branch": "git.branch_management",
            "git_status": "git.status",
            "generate_code": "code.generation",
            "execute_code": "code.sandbox_execution",
            "session_summary": "memory.session_recall",
            "search_web": "search.web",
            "web_fetch": "web.fetch",
            "synthesize_citations": "search.synthesize_citations",
            "research_and_compare": "search.web",
            "read_file": "file.read",
            "create_file": "file.create",
            "search_files": "file.search",
            "delete_file": "file.delete",
            "move_file": "file.move",
            "rename_file": "file.rename",
            "scan_document": "vision.ocr",
            "navigate": "browser.navigate",
            "search": "browser.search",
            "inspect_page": "browser.inspect",
            "navigate_back": "browser.navigate",
            "execute_shell": "shell.execute",
            "destructive_operation": "system.destructive",
            "send_message": "communication.send",
            "switch_persona": "system.switch_persona",
            "ingest_knowledge": "knowledge.ingest",
            "query_knowledge": "knowledge.query",
            "audit_knowledge": "knowledge.audit_freshness",
            "delete_knowledge": "knowledge.delete",
            "index_knowledge": "knowledge.index",
            "get_weather": "info.get_weather",
            "get_news": "info.get_news",
            "verify_freshness": "info.verify_freshness",
            "weather_and_news": "info.get_weather",
            "search_personal": "search.personal_vector",
            "search_personal_vector": "search.personal_vector",
            "search_files": "search.file_content",
            "search_file_content": "search.file_content",
            "search_interactions": "search.interaction_history",
            "search_multi_source": "search.multi_source",
            "verify_information": "verification.information",
            "cross_reference_claims": "verification.cross_reference_claims",
            "observe_reality": "verification.observe_reality",
            "synthesize_knowledge": "synthesis.combine_sources",
            "combine_sources": "synthesis.combine_sources",
            "generate_brief": "synthesis.generate_brief",
            "personal_and_external_synthesis": "search.personal_vector",
            # Capability 36 — Device Mesh
            "discover_peers": "mesh.discover_peers",
            "register_device": "mesh.register_device",
            "get_device_status": "mesh.get_device_status",
            "route_to_device": "mesh.route_to_device",
            "sync_state": "mesh.sync_state",
            "select_device": "mesh.select_device",
            "revoke_device": "mesh.revoke_device",
            # Capability 37 — Communication
            "lookup_contact": "comm.lookup_contact",
            "draft_email": "comm.draft_email",
            "send_email": "comm.send_email",
            "draft_message": "comm.draft_message",
            "send_message": "comm.send_message",
            "draft_whatsapp": "comm.draft_message",
            "send_whatsapp": "comm.send_whatsapp",
            "notify_user": "comm.notify_user",
            # Capability 38 — Calendar & Scheduling
            "create_calendar_event": "calendar.create_event",
            "get_calendar_events": "calendar.get_events",
            "modify_calendar_event": "calendar.modify_event",
            "delete_calendar_event": "calendar.delete_event",
            "check_conflicts": "calendar.check_conflicts",
            "get_availability": "calendar.get_availability",
            "calendar_mesh_notify": "calendar.get_events",
        }

    def generate_plan(
        self,
        goal_tree: GoalTree,
        is_fast_path: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ) -> CognitivePlan:
        plan_id = f"plan_{int(time.time()*1000)}"
        social_ctx = context.get("social_context") if context else None
        plan = CognitivePlan(
            plan_id=plan_id,
            root_goal=goal_tree.root_goal,
            is_fast_path=is_fast_path,
            social_context=social_ctx,
        )

        is_urgent = bool(social_ctx and social_ctx.get("is_urgent"))

        for idx, subgoal in enumerate(goal_tree.subgoals):
            # Decompose multi-intent research comparison into distinct pipeline steps
            if subgoal.action == "research_and_compare":
                topic_a = subgoal.parameters.get("topic_a", "")
                topic_b = subgoal.parameters.get("topic_b", "")
                comp_query = subgoal.parameters.get("query", f"{topic_a} vs {topic_b}")
                s1 = PlanStep(
                    step_id=f"{plan_id}_s1",
                    description=f"Search web for {topic_a}",
                    required_capability="search.web",
                    parameters={"query": topic_a, "max_results": 3},
                    timeout_sec=20.0,
                    verification_rule="verify_effect",
                )
                s2 = PlanStep(
                    step_id=f"{plan_id}_s2",
                    description=f"Search web for {topic_b}",
                    required_capability="search.web",
                    parameters={"query": topic_b, "max_results": 3},
                    timeout_sec=20.0,
                    verification_rule="verify_effect",
                )
                s3 = PlanStep(
                    step_id=f"{plan_id}_s3",
                    description=f"Synthesize citations comparing {topic_a} and {topic_b}",
                    required_capability="search.synthesize_citations",
                    parameters={"query": comp_query},
                    timeout_sec=15.0,
                    verification_rule="verify_effect",
                )
                plan.steps.extend([s1, s2, s3])
                continue

            # Decompose multi-intent personal + external synthesis DAG (33 -> 31 -> 34 -> 35)
            if subgoal.action == "personal_and_external_synthesis":
                p_topic = subgoal.parameters.get("personal_query") or subgoal.parameters.get("topic") or subgoal.parameters.get("query", "")
                ext_topic = subgoal.parameters.get("external_query") or subgoal.parameters.get("query", p_topic)
                s1 = PlanStep(
                    step_id=f"{plan_id}_s1",
                    description=f"Retrieve personal knowledge for '{p_topic}'",
                    required_capability="search.personal_vector",
                    parameters={"query": p_topic, "top_k": 3},
                    timeout_sec=10.0,
                    verification_rule="verify_effect",
                )
                s2 = PlanStep(
                    step_id=f"{plan_id}_s2",
                    description=f"Search external web for '{ext_topic}'",
                    required_capability="search.web",
                    parameters={"query": ext_topic, "max_results": 3},
                    timeout_sec=15.0,
                    verification_rule="verify_effect",
                )
                s3 = PlanStep(
                    step_id=f"{plan_id}_s3",
                    description="Verify retrieved evidence across sources",
                    required_capability="verification.information",
                    parameters={"claim": f"Comparison between personal notes on '{p_topic}' and external '{ext_topic}'"},
                    timeout_sec=10.0,
                    verification_rule="verify_effect",
                )
                s4 = PlanStep(
                    step_id=f"{plan_id}_s4",
                    description="Synthesize personal and external evidence into brief",
                    required_capability="synthesis.combine_sources",
                    parameters={"query": f"Comparison of personal {p_topic} with external {ext_topic}"},
                    timeout_sec=20.0,
                    verification_rule="verify_effect",
                )
                plan.steps.extend([s1, s2, s3, s4])
                continue

            # Decompose multi-intent weather and news into distinct plan steps
            if subgoal.action == "weather_and_news":
                loc = subgoal.parameters.get("location", "Delhi")
                topic = subgoal.parameters.get("topic", "technology")
                s1 = PlanStep(
                    step_id=f"{plan_id}_s1",
                    description=f"Fetch live weather for {loc}",
                    required_capability="info.get_weather",
                    parameters={"location": loc, "time_target": subgoal.parameters.get("time_target", "today")},
                    timeout_sec=10.0,
                    verification_rule="verify_effect",
                )
                s2 = PlanStep(
                    step_id=f"{plan_id}_s2",
                    description=f"Fetch latest news for {topic}",
                    required_capability="info.get_news",
                    parameters={"topic": topic, "time_filter": subgoal.parameters.get("time_filter", "latest"), "count": 5},
                    timeout_sec=10.0,
                    verification_rule="verify_effect",
                )
                plan.steps.extend([s1, s2])
                continue

            # Decompose cross-capability composite DAG (Calendar -> Device Mesh -> Communication -> Verification)
            if subgoal.action == "calendar_mesh_notify":
                s1 = PlanStep(
                    step_id=f"{plan_id}_s1",
                    description="Retrieve upcoming calendar events",
                    required_capability="calendar.get_events",
                    parameters={"limit": 5},
                    timeout_sec=10.0,
                    verification_rule="verify_effect",
                )
                s2 = PlanStep(
                    step_id=f"{plan_id}_s2",
                    description="Select reachable trusted device with notifications capability",
                    required_capability="mesh.select_device",
                    parameters={"required_capability": "notifications"},
                    timeout_sec=10.0,
                    verification_rule="verify_effect",
                )
                s3 = PlanStep(
                    step_id=f"{plan_id}_s3",
                    description="Dispatch notification of calendar schedule to selected device",
                    required_capability="comm.notify_user",
                    parameters={"title": "Calendar Alert", "message": "Upcoming events synchronized."},
                    timeout_sec=15.0,
                    verification_rule="verify_effect",
                )
                s4 = PlanStep(
                    step_id=f"{plan_id}_s4",
                    description="Verify execution and delivery reality",
                    required_capability="verification.observe_reality",
                    parameters={"claim": "Calendar schedule notified on mesh device"},
                    timeout_sec=10.0,
                    verification_rule="verify_effect",
                )
                plan.steps.extend([s1, s2, s3, s4])
                continue

            cap = self._action_capability_map.get(subgoal.action, f"{subgoal.domain}.{subgoal.action}")
            base_timeout = 10.0 if "os." in cap or "scheduler." in cap else 35.0
            timeout = max(5.0, base_timeout * 0.7) if is_urgent else base_timeout

            step = PlanStep(
                step_id=f"{plan_id}_s{idx+1}",
                description=subgoal.description,
                required_capability=cap,
                parameters=subgoal.parameters,
                timeout_sec=timeout,
                verification_rule="verify_effect",
            )
            plan.steps.append(step)

        logger.info(
            "[PlanningEngine] Generated plan '%s' with %d step(s) (cap='%s', urgent=%s)",
            plan_id,
            len(plan.steps),
            plan.steps[0].required_capability if plan.steps else "none",
            is_urgent,
        )
        return plan

    def replan_on_failure(self, failed_step: PlanStep, reason: str) -> Optional[CognitivePlan]:
        """Creates an alternative recovery plan when a step fails verification."""
        logger.warning("[PlanningEngine] Replanning for failed step '%s': %s", failed_step.step_id, reason)
        recovery_id = f"replan_{int(time.time()*1000)}"
        retry_step = PlanStep(
            step_id=f"{recovery_id}_retry",
            description=f"Retry {failed_step.description}",
            required_capability=failed_step.required_capability,
            parameters=failed_step.parameters,
            timeout_sec=failed_step.timeout_sec * 1.5,
            retry_count=failed_step.retry_count - 1,
        )
        return CognitivePlan(plan_id=recovery_id, root_goal="Recovery", steps=[retry_step], is_fast_path=True)


planning_engine = PlanningEngine()
