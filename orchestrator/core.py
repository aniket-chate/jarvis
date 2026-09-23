"""Orchestrator Core for JARVIS Layer 2.

Glues all orchestration subsystems:
receive_event -> persona_switch_intent -> plan -> safety guardrails -> route -> execute -> verify -> response.
Subscribes to PerceptionEvents from Layer 1's Unified Event Bus.
"""

import logging
from typing import Dict, Any, Optional

from perception.events import PerceptionEvent, event_bus
from orchestrator.planner import task_planner, TaskPlan
from orchestrator.guardrails import safety_guardrail
from orchestrator.executor import execution_manager
from orchestrator.verifier import task_verifier
from orchestrator.memory import memory_manager
from config.settings import settings

logger = logging.getLogger("JARVIS.Orchestrator")


class OrchestratorCore:
    """Core brain of Layer 2 coordinating planning, safety, execution, and verification."""

    def __init__(self):
        self.planner = task_planner
        self.guardrail = safety_guardrail
        self.executor = execution_manager
        self.verifier = task_verifier
        self.memory = memory_manager

    def process_event(self, event: PerceptionEvent, plan: Optional[TaskPlan] = None) -> Dict[str, Any]:
        """Main end-to-end processing pipeline for an incoming PerceptionEvent."""
        active_persona = event.active_persona or settings.active_persona_name

        logger.info(
            "[Orchestrator] [%s] Processing event '%s' from source '%s'",
            active_persona,
            event.type,
            event.source,
        )

        # 1. Plan task decomposition
        if plan is None:
            plan = self.planner.create_plan(event)

        # 2. Check for Persona Switch Intent
        if plan.is_persona_switch and plan.switch_target_persona:
            new_persona = plan.switch_target_persona
            settings.set_active_persona(new_persona)
            logger.info("[Orchestrator] SYSTEM INTENT: Switched active persona to '%s'", new_persona)
            plan.status = "completed"
            summary = self._build_persona_switch_response(new_persona)
            return {
                "trace_id": plan.plan_id,
                "type": "persona_switch",
                "active_persona": new_persona,
                "status": "completed",
                "response": summary,
                "plan": plan.to_dict(),
            }

        # 3. Apply Safety Guardrails before execution
        for step in plan.steps:
            is_safe, reason = self.guardrail.evaluate_step(step, plan.active_persona)
            if not is_safe:
                step.status = "blocked"
                step.result = {"error": reason}
                plan.status = "blocked"
                verification = self.verifier.verify_and_summarize(plan, {"status": "blocked", "failed_steps": [step.step_id]})
                try:
                    from orchestrator.learning import learning_engine
                    learning_engine.record_feedback(
                        action=step.required_agent_type or "guardrail",
                        reward=-0.2,
                        context=f"policy_rejection:{reason[:50]}"
                    )
                except Exception:
                    pass
                return {
                    "trace_id": plan.plan_id,
                    "type": "guardrail_blocked",
                    "active_persona": plan.active_persona,
                    "status": "blocked",
                    "reason": reason,
                    "response": verification["summary"],
                    "plan": plan.to_dict(),
                }

        # 4. Route and execute approved plan steps
        exec_summary = self.executor.execute_plan(plan)

        # 5. Verify results against intent
        verification = self.verifier.verify_and_summarize(plan, exec_summary)

        # 6. Extract user response from verified plan results
        final_response = verification.get("response") or verification.get("summary")
        if not final_response or final_response.strip().lower() in ["done.", "action complete."]:
            # Secondary check on step result fields
            for step in plan.steps:
                res = getattr(step, "result", None)
                if res and isinstance(res, dict):
                    for k in ["response", "output", "message", "answer", "summary", "text"]:
                        v = res.get(k)
                        if isinstance(v, str) and v.strip():
                            final_response = v.strip()
                            break
                    if final_response and final_response.strip().lower() not in ["done.", "action complete."]:
                        break

        final_response = final_response or verification.get("summary", "Done.")

        # 7. Update session memory and episodic ledger with this turn
        self.memory.remember(f"last_plan_{plan.plan_id}", {
            "goal": plan.goal,
            "status": plan.status,
            "persona": plan.active_persona,
        }, persistent=False, persona=plan.active_persona)

        # Record into Episodic Action Ledger for 100% grounded session recall
        try:
            from memory.episodic_ledger import episodic_ledger
            from orchestrator.context_manager import context_manager
            req_id = getattr(event.payload, "get", lambda k, d=None: None)("request_id") or plan.plan_id
            for step in plan.steps:
                if step.required_agent_type != "core_llm_agent":
                    step_action = step.inputs.get("action", "execute")
                    step_target = str(step.inputs.get("target") or step.inputs.get("filename") or step.inputs.get("path") or step.inputs.get("url") or step.description)
                    episodic_ledger.record(
                        request_id=req_id,
                        persona=plan.active_persona,
                        domain=step.required_agent_type,
                        action=step_action,
                        target=step_target,
                        status=step.status,
                        summary=str(step.result)[:120] if step.result else ""
                    )
                    if step.required_agent_type == "file_agent" and step.inputs.get("path"):
                        context_manager.set_file(step.inputs.get("path"), action=step_action)
                    elif step.required_agent_type == "dev_tool_agent" and step.inputs.get("branch"):
                        context_manager.set_git_branch(step.inputs.get("branch"))
                    elif step.required_agent_type == "browser_automation_agent":
                        if "youtube" in step_target.lower():
                            context_manager.update_browser(url="https://www.youtube.com", media_state="playing", media_target=step_target)
                        elif "github" in step_target.lower():
                            context_manager.update_browser(url="https://github.com/", title="GitHub")
        except Exception as led_err:
            logger.warning("[Orchestrator] Episodic ledger recording warning: %s", led_err)

        # 8. Record structured audit entry (zero raw audio, credentials redacted)
        try:
            from orchestrator.audit import audit_store, InteractionRecord

            first_agent = plan.steps[0].agent_type if plan.steps else "core_llm"
            perm_state = getattr(plan.steps[0], "permission_state", "allow") if plan.steps else "allow"
            audit_store.record_interaction(
                InteractionRecord(
                    query=event.raw_input or plan.goal,
                    persona=plan.active_persona,
                    intent=getattr(plan, "intent", "general") or "task",
                    agent_called=first_agent,
                    permission_state=perm_state,
                    provider_used="ollama",
                    action_result={"response": str(final_response)[:300], "status": exec_summary["status"]},
                    success=(exec_summary["status"] in ["success", "completed"] and verification.get("verified", True)),
                    metadata={"plan_id": plan.plan_id},
                )
            )
        except Exception as e:
            logger.debug("[Orchestrator] Failed recording audit record: %s", e)

        # 9. Update Continuous Learning Engine (Reinforcement Learning Policy & Evidence)
        try:
            from orchestrator.learning import learning_engine
            agent_act = first_agent or "core_llm"
            is_exec_ok = exec_summary.get("status") in ["success", "completed"]
            is_verified_ok = verification.get("verified", True)
            is_partial = exec_summary.get("status") == "partially_failed"
            is_user_cancelled = any(getattr(s, "inputs", {}).get("user_cancelled") for s in plan.steps)

            if is_user_cancelled:
                reward = 0.0
            elif is_exec_ok and is_verified_ok:
                reward = 1.0
            elif is_partial:
                reward = 0.5
            elif not is_verified_ok and is_exec_ok:
                reward = -1.0
            else:
                reward = -0.5

            learning_engine.record_feedback(
                action=agent_act,
                reward=reward,
                context=f"intent:{getattr(plan, 'intent', 'general')}"
            )
        except Exception as e:
            logger.debug("[Orchestrator] Continuous learning feedback recording warning: %s", e)

        return {
            "trace_id": plan.plan_id,
            "type": "task_executed",
            "active_persona": plan.active_persona,
            "status": exec_summary["status"],
            "response": final_response,
            "verification": verification,
            "execution": exec_summary,
            "plan": plan.to_dict(),
        }

    def _build_persona_switch_response(self, new_persona: str) -> str:
        """Conversational response on persona switch."""
        p_lower = new_persona.lower()
        if p_lower == "friday":
            return "Got it! Calling myself Friday from now on. What's up?"
        elif p_lower == "ultron":
            return "Understood. Ultron is active. Don't worry, the world is safe for now."
        else:
            return "Acknowledged, Sir. I shall address myself as Jarvis henceforward."

    def handle_event(self, event: PerceptionEvent) -> Dict[str, Any]:
        """Alias for process_event."""
        return self.process_event(event)


orchestrator_core = OrchestratorCore()
orchestrator = orchestrator_core

