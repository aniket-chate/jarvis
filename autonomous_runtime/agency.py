"""JARVIS Autonomous Runtime & Agency Engine.

First-class Autonomous Agency:
Operates independently of immediate user prompts.
Evaluates:
- Scheduled goals & timers
- Environmental condition changes ("If my download finishes...")
- Background monitors & triggers

CRITICAL INVARIANT:
Autonomy creates goals/events that traverse the exact same:
Cognitive Core -> Policy/Safety -> Execution -> Verification -> Memory pipeline.
It NEVER bypasses safety or cognitive planning.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional
from autonomous_runtime.schemas import AutonomousRule, TriggerType
from cognitive.goal_engine import goal_engine, GoalTree
from cognitive.planning_engine import planning_engine, CognitivePlan
from safety.policy_kernel import policy_kernel
from execution.runtime import execution_kernel, WorkflowJob
from verification.verifier import observation_verification_kernel
from event_fabric.bus import event_bus
from event_fabric.schemas import UniversalEvent, EventPriority
from memory.system import memory_system

logger = logging.getLogger("JARVIS.AutonomousAgency")


class AutonomousAgency:
    """The proactive autonomous runtime managing background goals and condition watchers."""

    def __init__(self):
        self._rules: Dict[str, AutonomousRule] = {}
        self._is_running: bool = False
        self._monitor_task: Optional[asyncio.Task] = None

    def register_rule(self, rule: AutonomousRule):
        self._rules[rule.rule_id] = rule
        logger.info("[AutonomousAgency] Registered rule '%s': %s (type=%s)", rule.rule_id, rule.description, rule.trigger_type.value)

    def unregister_rule(self, rule_id: str):
        self._rules.pop(rule_id, None)

    async def evaluate_triggers(self) -> List[Dict[str, Any]]:
        """Evaluates all registered rules and executes fired goals through the Cognitive Pipeline."""
        t_now = time.time()
        results = []

        for rule_id, rule in list(self._rules.items()):
            if not rule.is_active:
                continue

            should_fire = False

            # Check 1: Scheduled Time
            if rule.trigger_type == TriggerType.SCHEDULED_TIME and rule.scheduled_timestamp:
                if t_now >= rule.scheduled_timestamp:
                    should_fire = True

            # Check 2: Condition Poll
            elif rule.trigger_type == TriggerType.CONDITION_POLL and rule.condition_fn:
                if rule.last_evaluated_time == 0.0 or (t_now - rule.last_evaluated_time >= rule.poll_interval_sec):
                    rule.last_evaluated_time = t_now
                    try:
                        if rule.condition_fn():
                            should_fire = True
                    except Exception as e:
                        logger.error("[AutonomousAgency] Error evaluating condition for rule '%s': %s", rule_id, e)

            if should_fire:
                logger.info("[AutonomousAgency] FIRED autonomous rule '%s': '%s'", rule_id, rule.description)
                rule.trigger_count += 1
                if rule.trigger_count >= rule.max_triggers:
                    rule.is_active = False

                # Route through full cognitive pipeline!
                pipeline_result = await self._execute_autonomous_goal(rule)
                results.append(pipeline_result)

        return results

    async def _execute_autonomous_goal(self, rule: AutonomousRule) -> Dict[str, Any]:
        """Runs the triggered autonomous goal through: Goal -> Plan -> Safety -> Execution -> Verification -> Memory."""
        req_id = f"auto_{int(time.time()*1000)}"
        domain = rule.target_capability.split(".")[0]
        action = rule.target_capability.split(".")[-1]

        # 1. Goal Engine
        goal_tree = goal_engine.create_atomic_goal(
            goal_text=rule.goal_to_trigger,
            domain=domain,
            action=action,
            params=rule.parameters,
        )

        # 2. Planning Engine
        plan = planning_engine.generate_plan(goal_tree, is_fast_path=True)
        step = plan.steps[0] if plan.steps else None
        if not step:
            return {"status": "failed", "error": "No plan generated"}

        # 3. Policy & Safety Invariant
        safety_dec = policy_kernel.evaluate(
            domain=domain,
            action=action,
            parameters=rule.parameters,
            raw_query=rule.goal_to_trigger,
        )
        if not safety_dec.allowed:
            logger.warning("[AutonomousAgency] BLOCKED by PolicyKernel: %s", safety_dec.reason)
            return {"status": "blocked", "reason": safety_dec.reason}

        # 4. Execution Kernel
        job: WorkflowJob = execution_kernel.create_job(
            request_id=req_id,
            goal=rule.goal_to_trigger,
            steps=[{"capability": rule.target_capability, "parameters": rule.parameters, "timeout_sec": step.timeout_sec}],
        )
        exec_res = await execution_kernel.run_job(job)

        # 5. Observation & Verification
        verification = observation_verification_kernel.observe_and_verify(
            capability=rule.target_capability,
            expected_state={"executed": True},
            parameters=rule.parameters,
            request_id=req_id,
        )

        # 6. Memory & Episodic Logging
        memory_system.record_episodic_action(
            request_id=req_id,
            persona="Friday",
            domain=domain,
            action=action,
            target=rule.description,
            status=verification.status,
            summary=f"Autonomous action triggered: {rule.description}",
        )

        # 7. Publish to Event Fabric
        await event_bus.publish(UniversalEvent(
            request_id=req_id,
            event_type="autonomous.goal_completed",
            priority=EventPriority.NORMAL,
            payload={"rule_id": rule.rule_id, "result": exec_res, "verification": verification.status},
        ))

        return {
            "status": "success",
            "rule_id": rule.rule_id,
            "exec_res": exec_res,
            "verification": verification.status,
        }


# Master Autonomous Agency singleton
autonomous_agency = AutonomousAgency()
