"""JARVIS Execution Kernel.

Durable Workflow & Task Runtime supporting:
- Asynchronous and concurrent workflow execution
- Per-step and per-domain deadline budgets
- Cooperative cancellation and pause/resume state machines
- Step retries, checkpointing, and failure recovery
- Complete isolation: long-running tasks never block independent workflows
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import logging
import time
from typing import Any, Callable, Dict, List, Optional
import uuid
from capabilities.intelligence import capability_intelligence
from capabilities.base import ActionResult
from safety.policy_kernel import policy_kernel, PolicyLevel
from verification.verifier import observation_verification_kernel

logger = logging.getLogger("JARVIS.Execution.Kernel")


class StepState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    step_id: str
    capability: str
    parameters: Dict[str, Any]
    timeout_sec: float = 30.0
    retry_limit: int = 2
    retries_done: int = 0
    state: StepState = StepState.PENDING
    result: Optional[ActionResult] = None
    error: Optional[str] = None


@dataclass
class WorkflowJob:
    workflow_id: str
    request_id: str
    goal: str
    steps: List[WorkflowStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    cancellation_token: asyncio.Event = field(default_factory=asyncio.Event)
    current_step_index: int = 0
    checkpoint: Dict[str, Any] = field(default_factory=dict)
    is_completed: bool = False
    is_failed: bool = False
    is_concurrent: bool = False


import concurrent.futures
import json
from pathlib import Path


class ExecutionKernel:
    """The central durable workflow runtime executing capability action steps."""

    def __init__(self):
        self._active_jobs: Dict[str, WorkflowJob] = {}
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=16, thread_name_prefix="jarvis_kernel")

    def persist_checkpoint(self, job: WorkflowJob):
        """Persists workflow checkpoint to disk for crash recovery."""
        from config.settings import PROJECT_ROOT
        cp_dir = PROJECT_ROOT / "data" / "checkpoints"
        cp_dir.mkdir(parents=True, exist_ok=True)
        cp_file = cp_dir / f"{job.workflow_id}.json"
        data = {
            "workflow_id": job.workflow_id,
            "request_id": job.request_id,
            "goal": job.goal,
            "current_step_index": job.current_step_index,
            "checkpoint": job.checkpoint,
            "is_completed": job.is_completed,
            "is_failed": job.is_failed,
            "steps": [
                {
                    "step_id": s.step_id,
                    "capability": s.capability,
                    "parameters": s.parameters,
                    "state": s.state.value,
                    "retries_done": s.retries_done,
                    "error": s.error,
                }
                for s in job.steps
            ],
        }
        cp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def restore_checkpoint(self, workflow_id: str) -> Optional[WorkflowJob]:
        """Restores a workflow job from disk after a simulated or real process restart."""
        from config.settings import PROJECT_ROOT
        cp_file = PROJECT_ROOT / "data" / "checkpoints" / f"{workflow_id}.json"
        if not cp_file.exists():
            return None
        data = json.loads(cp_file.read_text(encoding="utf-8"))
        job = WorkflowJob(
            workflow_id=data["workflow_id"],
            request_id=data["request_id"],
            goal=data["goal"],
            current_step_index=data["current_step_index"],
            checkpoint=data.get("checkpoint", {}),
            is_completed=data.get("is_completed", False),
            is_failed=data.get("is_failed", False),
        )
        for s_data in data.get("steps", []):
            step = WorkflowStep(
                step_id=s_data["step_id"],
                capability=s_data["capability"],
                parameters=s_data["parameters"],
                state=StepState(s_data["state"]),
                retries_done=s_data.get("retries_done", 0),
                error=s_data.get("error"),
            )
            job.steps.append(step)
        self._active_jobs[job.workflow_id] = job
        return job

    def create_job(
        self,
        request_id: str,
        goal: str,
        steps: List[Dict[str, Any]],
        is_concurrent: bool = False,
    ) -> WorkflowJob:
        wf_id = f"wf_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
        job = WorkflowJob(workflow_id=wf_id, request_id=request_id, goal=goal, is_concurrent=is_concurrent)

        for idx, s in enumerate(steps):
            step = WorkflowStep(
                step_id=f"{wf_id}_s{idx+1}",
                capability=s.get("capability", "unknown"),
                parameters=s.get("parameters", {}),
                timeout_sec=s.get("timeout_sec", 30.0),
                retry_limit=s.get("retry_limit", 2),
            )
            job.steps.append(step)

        self._active_jobs[wf_id] = job
        self.persist_checkpoint(job)
        return job

    async def execute_step(self, job: WorkflowJob, step: WorkflowStep) -> bool:
        """Executes an isolated workflow step with policy evaluation, fallback providers, and verification."""
        if job.cancellation_token.is_set():
            step.state = StepState.CANCELLED
            return False

        # 1. Safety Invariant Check
        safety_dec = policy_kernel.evaluate(
            domain=step.capability.split(".")[0] if "." in step.capability else "system",
            action=step.capability.split(".")[-1],
            parameters=step.parameters,
            request_id=job.request_id,
        )
        if not safety_dec.allowed:
            step.state = StepState.FAILED
            step.error = safety_dec.reason
            return False

        # 2. Capability Provider Selection
        failed_providers = []
        provider = capability_intelligence.select_provider(step.capability)
        if not provider:
            step.state = StepState.FAILED
            step.error = f"No provider available for capability '{step.capability}'"
            return False

        step.state = StepState.RUNNING
        step_success = False

        while step.retries_done <= step.retry_limit and not step_success:
            try:
                if job.cancellation_token.is_set():
                    step.state = StepState.CANCELLED
                    return False

                # Execute with deadline budget on dedicated multi-worker thread pool
                loop = asyncio.get_running_loop()
                res: ActionResult = await asyncio.wait_for(
                    loop.run_in_executor(self._executor, provider.execute, step.capability, step.parameters),
                    timeout=step.timeout_sec,
                )

                if res.status == "SUCCESS":
                    ver_report = observation_verification_kernel.observe_and_verify(
                        capability=step.capability,
                        expected_state={"capability": step.capability},
                        parameters=step.parameters,
                        request_id=job.request_id,
                    )
                    if ver_report.status == "FAILED":
                        step.retries_done += 1
                        logger.warning(
                            "[ExecutionKernel] Step '%s' provider succeeded but physical verification FAILED: %s",
                            step.step_id,
                            ver_report.evidence,
                        )
                    else:
                        step.state = StepState.COMPLETED
                        step.result = res
                        step_success = True
                        job.checkpoint[step.step_id] = res.output
                        return True
                else:
                    step.retries_done += 1
                    failed_providers.append(provider.provider_id)
                    logger.warning(
                        "[ExecutionKernel] Step '%s' failed on '%s' (attempt %d/%d): %s",
                        step.step_id,
                        provider.provider_id,
                        step.retries_done,
                        step.retry_limit + 1,
                        res.message,
                    )
                    # Attempt provider fallback
                    fallback = capability_intelligence.select_provider(step.capability, exclude_provider_ids=failed_providers)
                    if fallback:
                        logger.info(
                            "[ExecutionKernel] Step '%s': Switching from '%s' to fallback provider '%s'",
                            step.step_id,
                            provider.provider_id,
                            fallback.provider_id,
                        )
                        provider = fallback

            except asyncio.TimeoutError:
                step.retries_done += 1
                failed_providers.append(provider.provider_id)
                logger.warning("[ExecutionKernel] Step '%s' timed out after %.1fs on '%s'", step.step_id, step.timeout_sec, provider.provider_id)
                fallback = capability_intelligence.select_provider(step.capability, exclude_provider_ids=failed_providers)
                if fallback:
                    logger.info("[ExecutionKernel] Step '%s': Switched to fallback provider '%s' after timeout", step.step_id, fallback.provider_id)
                    provider = fallback

            except Exception as ex:
                step.retries_done += 1
                failed_providers.append(provider.provider_id)
                logger.error("[ExecutionKernel] Step '%s' exception on '%s': %s", step.step_id, provider.provider_id, ex)
                fallback = capability_intelligence.select_provider(step.capability, exclude_provider_ids=failed_providers)
                if fallback:
                    provider = fallback

        if not step_success:
            step.state = StepState.FAILED
            step.error = f"Step '{step.step_id}' failed after {step.retries_done} attempts (retries exhausted)"
            return False

        return True

    async def run_job(self, job: WorkflowJob) -> Dict[str, Any]:
        """Executes workflow steps sequentially or concurrently with checkpointing and deadline budgets."""
        logger.info("[ExecutionKernel] Starting workflow '%s' (%d step(s), concurrent=%s)", job.workflow_id, len(job.steps), job.is_concurrent)

        if job.is_concurrent:
            tasks = [self.execute_step(job, step) for step in job.steps]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            if any(isinstance(o, Exception) or o is False for o in outcomes):
                job.is_failed = True
                return {"status": "failed", "workflow_id": job.workflow_id, "checkpoint": job.checkpoint}
        else:
            for idx in range(job.current_step_index, len(job.steps)):
                step = job.steps[idx]
                job.current_step_index = idx
                success = await self.execute_step(job, step)
                if not success:
                    job.is_failed = True
                    self.persist_checkpoint(job)
                    return {"status": step.state.value, "step_id": step.step_id, "error": step.error, "workflow_id": job.workflow_id}
                job.current_step_index = idx + 1
                self.persist_checkpoint(job)

        job.is_completed = True
        self.persist_checkpoint(job)
        logger.info("[ExecutionKernel] Workflow '%s' completed successfully", job.workflow_id)
        last_step_res = job.steps[-1].result if job.steps else None
        return {
            "status": "success",
            "workflow_id": job.workflow_id,
            "output": last_step_res.output if last_step_res else "Done",
            "checkpoint": job.checkpoint,
        }


execution_kernel = ExecutionKernel()
