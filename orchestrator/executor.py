"""Execution Manager for JARVIS Layer 2.

Executes TaskPlan steps according to dependency order, handles status tracking,
implements retries with exponential backoff, and reports partial or complete failures.
"""

import time
import logging
from typing import Dict, Any, List, Optional

from orchestrator.planner import TaskPlan, TaskStep
from orchestrator.router import agent_router

logger = logging.getLogger("JARVIS.Executor")


class ExecutionManager:
    """Manages the lifecycle, retries, and dependency resolution of TaskPlans."""

    def __init__(self, router=agent_router, backoff_base: float = 0.05):
        self.router = router
        self.backoff_base = backoff_base  # Fast backoff for tests/local runtime

    def execute_plan(self, plan: TaskPlan) -> Dict[str, Any]:
        """Executes all steps in a TaskPlan respecting dependencies and retries."""
        logger.info(
            "[ExecutionManager] [%s] Starting execution of plan '%s' (%d step(s))",
            plan.active_persona,
            plan.plan_id,
            len(plan.steps),
        )
        plan.status = "in_progress"

        completed_step_ids = set()
        failed_step_ids = set()
        step_outputs: Dict[str, Any] = {}

        for step in plan.steps:
            # 1. Dependency check
            unmet_deps = [dep for dep in step.depends_on if dep not in completed_step_ids]
            if unmet_deps:
                logger.warning(
                    "[ExecutionManager] [%s] Step '%s' BLOCKED: unmet dependencies %s",
                    plan.active_persona,
                    step.step_id,
                    unmet_deps,
                )
                step.status = "blocked"
                step.result = {"error": f"Prerequisite steps {unmet_deps} did not complete successfully"}
                failed_step_ids.add(step.step_id)
                continue

            # 2. Inject results from previous dependent steps if needed
            merged_inputs = dict(step.inputs)
            for dep in step.depends_on:
                if dep in step_outputs:
                    merged_inputs[f"input_from_{dep}"] = step_outputs[dep]

            # 3. Execute step with retries and exponential backoff
            step_success = self._execute_step_with_retries(step, merged_inputs, plan.active_persona)

            if step_success:
                completed_step_ids.add(step.step_id)
                step_outputs[step.step_id] = step.result
            else:
                failed_step_ids.add(step.step_id)

        # 4. Determine final plan status
        if len(completed_step_ids) == len(plan.steps):
            plan.status = "completed"
        elif len(completed_step_ids) > 0 and len(failed_step_ids) > 0:
            plan.status = "partially_failed"
        elif len(completed_step_ids) == 0:
            plan.status = "failed"

        logger.info(
            "[ExecutionManager] [%s] Plan '%s' finished with status '%s' (%d completed, %d failed)",
            plan.active_persona,
            plan.plan_id,
            plan.status,
            len(completed_step_ids),
            len(failed_step_ids),
        )

        return {
            "plan_id": plan.plan_id,
            "status": plan.status,
            "active_persona": plan.active_persona,
            "completed_steps": list(completed_step_ids),
            "failed_steps": list(failed_step_ids),
            "step_results": [s.to_dict() for s in plan.steps],
        }

    def _execute_step_with_retries(self, step: TaskStep, inputs: Dict[str, Any], persona: str) -> bool:
        """Runs a single step, retrying up to max_retries on failure."""
        step.status = "running"

        while step.retries <= step.max_retries:
            attempt = step.retries + 1
            logger.info(
                "[ExecutionManager] [%s] Executing step '%s' (Attempt %d/%d, Agent='%s')",
                persona,
                step.step_id,
                attempt,
                step.max_retries + 1,
                step.required_agent_type,
            )

            try:
                res = self.router.route_and_execute(step.required_agent_type, inputs, persona)
                if res.get("status") in ["success", "refused_by_policy", "refused", "blocked"] or res.get("success") is True:
                    step.status = "completed"
                    step.result = res
                    logger.info(
                        "[ExecutionManager] [%s] Step '%s' SUCCEEDED on attempt %d",
                        persona,
                        step.step_id,
                        attempt,
                    )
                    return True
                else:
                    error_msg = res.get("error", "Agent reported failure")
                    logger.warning(
                        "[ExecutionManager] [%s] Step '%s' attempt %d failed: %s",
                        persona,
                        step.step_id,
                        attempt,
                        error_msg,
                    )
            except Exception as e:
                logger.error(
                    "[ExecutionManager] [%s] Step '%s' exception on attempt %d: %s",
                    persona,
                    step.step_id,
                    attempt,
                    str(e),
                )
                res = {"status": "failed", "error": str(e)}

            step.retries += 1
            if step.retries <= step.max_retries:
                backoff_time = self.backoff_base * (2 ** (step.retries - 1))
                logger.info(
                    "[ExecutionManager] [%s] Retrying step '%s' after %.2fs backoff...",
                    persona,
                    step.step_id,
                    backoff_time,
                )
                time.sleep(backoff_time)

        # All retries exhausted
        step.status = "failed"
        step.result = res
        logger.error(
            "[ExecutionManager] [%s] Step '%s' FAILED after %d retries.",
            persona,
            step.step_id,
            step.retries,
        )
        return False


execution_manager = ExecutionManager()
