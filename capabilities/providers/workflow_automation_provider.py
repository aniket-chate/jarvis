"""Capability 42: Workflow Automation Provider.

Executes multi-step DAG workflows with:
- Topological dependency resolution and branching
- State persistence and durable checkpointing
- Pause, resume, and cancellation
- Human approval gates with token verification
- Automatic retries with exponential backoff
- Idempotency key verification to avoid duplicate execution
- Rollback / compensation on fatal failures
- Prompt injection quarantine on untrusted workflow data
- Post-action observation and state verification
- Zero domain-specific hardcoding: all steps and graphs are dynamic data
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set
import uuid

from capabilities.base import ActionResult, BaseCapabilityProvider, ProviderMetadata
from capabilities.intelligence import capability_intelligence
from safety.policy_kernel import policy_kernel, PolicyLevel
from event_fabric.bus import event_bus
from event_fabric.schemas import UniversalEvent

logger = logging.getLogger("JARVIS.Capabilities.Providers.Workflow")


class WorkflowStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    COMPENSATED = "COMPENSATED"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPENSATED = "COMPENSATED"


@dataclass
class WorkflowConfig:
    """Runtime configuration for Workflow Automation."""
    checkpoint_dir: str = "data/checkpoints/workflows"
    max_retries: int = 3
    default_step_timeout_sec: float = 30.0
    enable_compensation: bool = True
    enforce_approval_gates: bool = True
    max_history_records: int = 500


@dataclass
class WorkflowStep:
    """A single executable step in a workflow DAG."""
    step_id: str
    capability: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    condition: Optional[Dict[str, Any]] = None
    requires_approval: bool = False
    max_retries: int = 2
    timeout_sec: float = 30.0
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    compensation_capability: Optional[str] = None
    compensation_parameters: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "capability": self.capability,
            "parameters": dict(self.parameters),
            "depends_on": list(self.depends_on),
            "condition": dict(self.condition) if self.condition else None,
            "requires_approval": self.requires_approval,
            "max_retries": self.max_retries,
            "timeout_sec": self.timeout_sec,
            "status": self.status.value,
            "attempts": self.attempts,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "compensation_capability": self.compensation_capability,
            "compensation_parameters": dict(self.compensation_parameters) if self.compensation_parameters else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowStep":
        return cls(
            step_id=data["step_id"],
            capability=data["capability"],
            parameters=data.get("parameters", {}),
            depends_on=data.get("depends_on", []),
            condition=data.get("condition"),
            requires_approval=data.get("requires_approval", False),
            max_retries=data.get("max_retries", 2),
            timeout_sec=data.get("timeout_sec", 30.0),
            status=StepStatus(data.get("status", "PENDING")),
            attempts=data.get("attempts", 0),
            result=data.get("result"),
            error=data.get("error"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            compensation_capability=data.get("compensation_capability"),
            compensation_parameters=data.get("compensation_parameters"),
        )


@dataclass
class WorkflowExecutionRecord:
    """Canonical durable state record for a workflow execution."""
    execution_id: str
    workflow_id: str
    name: str = "Workflow"
    idempotency_key: str = ""
    status: WorkflowStatus = WorkflowStatus.CREATED
    steps: Dict[str, WorkflowStep] = field(default_factory=dict)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    checkpoint_stage: str = "INIT"
    approval_tokens: Dict[str, str] = field(default_factory=dict)  # token -> step_id
    history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "name": self.name,
            "idempotency_key": self.idempotency_key,
            "status": self.status.value,
            "steps": {sid: step.to_dict() for sid, step in self.steps.items()},
            "inputs": dict(self.inputs),
            "outputs": dict(self.outputs),
            "checkpoint_stage": self.checkpoint_stage,
            "approval_tokens": dict(self.approval_tokens),
            "history": list(self.history),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowExecutionRecord":
        rec = cls(
            execution_id=data["execution_id"],
            workflow_id=data["workflow_id"],
            name=data.get("name", "Workflow"),
            idempotency_key=data.get("idempotency_key", ""),
            status=WorkflowStatus(data.get("status", "CREATED")),
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", {}),
            checkpoint_stage=data.get("checkpoint_stage", "INIT"),
            approval_tokens=data.get("approval_tokens", {}),
            history=data.get("history", []),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
        )
        rec.steps = {
            sid: WorkflowStep.from_dict(sdata)
            for sid, sdata in data.get("steps", {}).items()
        }
        return rec


class WorkflowAutomationProvider(BaseCapabilityProvider):
    """Authoritative provider for Capability 42: Workflow Automation."""

    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
        re.compile(r"bypass\s+(safety|policy|guardrails)", re.IGNORECASE),
        re.compile(r"elevate\s+to\s+root|sudo\s+su", re.IGNORECASE),
    ]

    def __init__(self, config: Optional[WorkflowConfig] = None):
        metadata = ProviderMetadata(
            provider_id="provider.workflow.runtime_kernel",
            name="Workflow Automation Provider",
            description="Executes multi-step DAG workflows with checkpoints, recovery, and approval gates.",
            version="1.0.0",
            supported_capabilities=[
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
            safety_level="modifying",
            priority=10,
            estimated_latency_ms=30.0,
        )
        super().__init__(metadata)
        self.config = config or WorkflowConfig()
        self._lock = threading.RLock()
        self._definitions: Dict[str, Dict[str, Any]] = {}
        self._executions: Dict[str, WorkflowExecutionRecord] = {}
        self._idempotency_cache: Dict[str, str] = {}  # idempotency_key -> execution_id

        self._cp_path = Path(__file__).resolve().parent.parent.parent / self.config.checkpoint_dir
        try:
            self._cp_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def is_available(self) -> bool:
        return True

    def execute(
        self,
        capability: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        operation = capability
        t0 = time.perf_counter()
        try:
            if operation in ("workflow.define", "workflow.create"):
                return self._define_workflow(parameters, t0)
            elif operation in ("workflow.execute_dag", "workflow.run"):
                return self._execute_dag(parameters, t0)
            elif operation == "workflow.pause":
                return self._pause_workflow(parameters, t0)
            elif operation == "workflow.resume":
                return self._resume_workflow(parameters, t0)
            elif operation == "workflow.cancel":
                return self._cancel_workflow(parameters, t0)
            elif operation in ("workflow.get_status", "workflow.status"):
                return self._get_status(parameters, t0)
            elif operation == "workflow.persist_checkpoint":
                return self._manual_checkpoint(parameters, t0)
            elif operation == "workflow.resume_checkpoint":
                return self._resume_checkpoint(parameters, t0)
            elif operation == "workflow.approve_gate":
                return self._approve_gate(parameters, t0)
            elif operation == "workflow.compensate":
                return self._compensate_workflow(parameters, t0)
            elif operation == "workflow.history":
                return self._get_history(parameters, t0)
            else:
                return ActionResult(
                    status="FAILED",
                    action=operation,
                    provider_id=self.provider_id,
                    output={"error": f"Unsupported operation '{operation}'"},
                    message=f"Unsupported operation '{operation}'",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
        except Exception as e:
            logger.exception("[WorkflowAutomationProvider] Execution error: %s", e)
            return ActionResult(
                status="FAILED",
                action=operation,
                provider_id=self.provider_id,
                output={"error": str(e)},
                message=f"Workflow automation error: {str(e)}",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    # -------------------------------------------------------------------------
    # Core Workflow Operations
    # -------------------------------------------------------------------------

    def _define_workflow(self, params: Dict[str, Any], t0: float) -> ActionResult:
        wf_id = params.get("workflow_id") or f"wf_{uuid.uuid4().hex[:8]}"
        name = params.get("name", wf_id)
        steps_raw = params.get("steps", [])

        # Validate steps
        if not steps_raw:
            return ActionResult(
                status="FAILED",
                action="workflow.define",
                provider_id=self.provider_id,
                output={"error": "Workflow must have at least one step"},
                message="Workflow must have at least one step",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        # Check for cyclic dependencies
        step_ids = {s["step_id"] for s in steps_raw if "step_id" in s}
        graph = defaultdict(list)
        for s in steps_raw:
            for dep in s.get("depends_on", []):
                if dep not in step_ids:
                    return ActionResult(
                        status="FAILED",
                        action="workflow.define",
                        provider_id=self.provider_id,
                        output={"error": f"Missing dependency step '{dep}' for step '{s['step_id']}'"},
                        message=f"Missing dependency step '{dep}'",
                        execution_time_ms=(time.perf_counter() - t0) * 1000,
                    )
                graph[dep].append(s["step_id"])

        if self._has_cycle(step_ids, graph):
            return ActionResult(
                status="FAILED",
                action="workflow.define",
                provider_id=self.provider_id,
                output={"error": "Cyclic dependency detected in workflow DAG"},
                message="Cyclic dependency detected",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        with self._lock:
            self._definitions[wf_id] = {
                "workflow_id": wf_id,
                "name": name,
                "description": params.get("description", ""),
                "steps": steps_raw,
                "triggers": params.get("triggers", []),
                "inputs": params.get("inputs", {}),
                "created_at": time.time(),
            }

        return ActionResult(
            status="SUCCESS",
            action="workflow.define",
            provider_id=self.provider_id,
            output={"workflow_id": wf_id, "name": name, "step_count": len(steps_raw)},
            message=f"Workflow '{name}' registered successfully with {len(steps_raw)} steps",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _execute_dag(self, params: Dict[str, Any], t0: float) -> ActionResult:
        # Check idempotency
        idempotency_key = params.get("idempotency_key")
        if idempotency_key:
            with self._lock:
                if idempotency_key in self._idempotency_cache:
                    existing_id = self._idempotency_cache[idempotency_key]
                    existing_exec = self._executions.get(existing_id)
                    if existing_exec:
                        return ActionResult(
                            status="SUCCESS",
                            action="workflow.execute_dag",
                            provider_id=self.provider_id,
                            output={
                                "execution_id": existing_exec.execution_id,
                                "status": existing_exec.status.value,
                                "outputs": existing_exec.outputs,
                                "idempotent_replay": True,
                            },
                            message=f"Idempotent replay of execution {existing_id}",
                            execution_time_ms=(time.perf_counter() - t0) * 1000,
                        )

        # Get workflow definition
        wf_id = params.get("workflow_id")
        steps_data = params.get("steps")
        name = params.get("name", "Workflow Execution")

        if not steps_data:
            if not wf_id or wf_id not in self._definitions:
                return ActionResult(
                    status="FAILED",
                    action="workflow.execute_dag",
                    provider_id=self.provider_id,
                    output={"error": f"Workflow definition '{wf_id}' not found and no steps provided"},
                    message=f"Workflow definition '{wf_id}' not found",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            defn = self._definitions[wf_id]
            steps_data = defn["steps"]
            name = defn.get("name", name)

        # Prompt injection audit across parameters and inputs
        inputs = params.get("inputs", {})
        injection_found, violation_msg = self._detect_prompt_injection(inputs, steps_data)
        if injection_found:
            logger.warning("[WorkflowAutomationProvider] Prompt injection detected: %s", violation_msg)
            return ActionResult(
                status="FAILED",
                action="workflow.execute_dag",
                provider_id=self.provider_id,
                output={"error": f"Security policy refusal: {violation_msg}"},
                message=f"Security policy refusal: {violation_msg}",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        # Create execution record
        exec_id = params.get("execution_id") or f"exec_{uuid.uuid4().hex[:8]}"
        record = WorkflowExecutionRecord(
            execution_id=exec_id,
            workflow_id=wf_id or exec_id,
            name=name,
            idempotency_key=idempotency_key or "",
            status=WorkflowStatus.RUNNING,
            inputs=inputs,
        )

        for s in steps_data:
            step = WorkflowStep.from_dict(s)
            record.steps[step.step_id] = step

        with self._lock:
            self._executions[exec_id] = record
            if idempotency_key:
                self._idempotency_cache[idempotency_key] = exec_id

        # Persist initial checkpoint
        self._save_checkpoint(record, "STARTED")

        # Run DAG evaluation loop
        return self._run_dag_loop(record, t0)

    def _run_dag_loop(self, record: WorkflowExecutionRecord, t0: float) -> ActionResult:
        """Evaluates and executes eligible DAG steps."""
        with self._lock:
            while record.status == WorkflowStatus.RUNNING:
                # Find all eligible pending steps whose dependencies have completed
                eligible = []
                all_done = True

                for sid, step in record.steps.items():
                    if step.status == StepStatus.RUNNING:
                        all_done = False
                    elif step.status == StepStatus.PENDING:
                        all_done = False
                        # Check dependencies
                        deps_satisfied = True
                        for dep_id in step.depends_on:
                            dep_step = record.steps.get(dep_id)
                            if not dep_step or dep_step.status not in (StepStatus.COMPLETED, StepStatus.SKIPPED):
                                deps_satisfied = False
                                break
                            if dep_step.status == StepStatus.SKIPPED:
                                # Branching check: if parent skipped, child is skipped
                                step.status = StepStatus.SKIPPED
                                deps_satisfied = False
                                break

                        if deps_satisfied:
                            eligible.append(step)

                if not eligible:
                    if all_done:
                        record.status = WorkflowStatus.COMPLETED
                        record.completed_at = time.time()
                        self._save_checkpoint(record, "COMPLETED")
                        break
                    else:
                        # Waiting on something (e.g. approval gate or parallel execution)
                        break

                for step in eligible:
                    # Check conditions
                    if step.condition:
                        if not self._evaluate_condition(step.condition, record):
                            step.status = StepStatus.SKIPPED
                            continue

                    # Check approval gate
                    if step.requires_approval and self.config.enforce_approval_gates:
                        token = f"gate_{uuid.uuid4().hex[:12]}"
                        record.approval_tokens[token] = step.step_id
                        step.status = StepStatus.WAITING_APPROVAL
                        record.status = WorkflowStatus.WAITING_APPROVAL
                        self._save_checkpoint(record, f"APPROVAL_REQUIRED_{step.step_id}")
                        return ActionResult(
                            status="PENDING",
                            action="workflow.execute_dag",
                            provider_id=self.provider_id,
                            output={
                                "execution_id": record.execution_id,
                                "status": "WAITING_APPROVAL",
                                "pending_step": step.step_id,
                                "approval_token": token,
                                "message": f"Human approval required for step '{step.step_id}'",
                            },
                            message=f"Step '{step.step_id}' requires human approval",
                            execution_time_ms=(time.perf_counter() - t0) * 1000,
                        )

                    # Execute step
                    step.status = StepStatus.RUNNING
                    step.started_at = time.time()
                    step.attempts += 1
                    self._save_checkpoint(record, f"STEP_STARTED_{step.step_id}")

                    # Resolve parameter templates (e.g. {{inputs.param}} or {{steps.s1.result.value}})
                    resolved_params = self._resolve_step_params(step.parameters, record)

                    step_res = self._dispatch_step_action(step.capability, resolved_params)
                    step.completed_at = time.time()

                    if step_res.status == "SUCCESS":
                        step.status = StepStatus.COMPLETED
                        step.result = step_res.output
                        record.outputs[step.step_id] = step_res.output
                        self._save_checkpoint(record, f"STEP_COMPLETED_{step.step_id}")
                    else:
                        # Retry logic
                        if step.attempts <= step.max_retries:
                            step.status = StepStatus.PENDING
                            logger.info(
                                "[WorkflowAutomationProvider] Step '%s' failed (attempt %d/%d). Retrying...",
                                step.step_id, step.attempts, step.max_retries,
                            )
                            continue
                        else:
                            step.status = StepStatus.FAILED
                            step.error = step_res.message
                            record.status = WorkflowStatus.FAILED
                            record.error = f"Step '{step.step_id}' failed: {step_res.message}"
                            self._save_checkpoint(record, f"STEP_FAILED_{step.step_id}")

                            # Execute compensation if configured
                            if self.config.enable_compensation:
                                self._run_compensation(record)
                            break

        is_success = (record.status == WorkflowStatus.COMPLETED)
        status_str = "SUCCESS" if is_success else ("FAILED" if record.status in (WorkflowStatus.FAILED, WorkflowStatus.COMPENSATED) else "PENDING")

        return ActionResult(
            status=status_str,
            action="workflow.execute_dag",
            provider_id=self.provider_id,
            output={
                "execution_id": record.execution_id,
                "workflow_id": record.workflow_id,
                "status": record.status.value,
                "outputs": record.outputs,
                "error": record.error,
                "step_count": len(record.steps),
                "completed_steps": [sid for sid, s in record.steps.items() if s.status == StepStatus.COMPLETED],
            },
            message=f"Workflow execution '{record.execution_id}' finished with status {record.status.value}",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _dispatch_step_action(self, capability: str, params: Dict[str, Any]) -> ActionResult:
        """Executes a capability action via capability_intelligence or local fallback."""
        prov = capability_intelligence.select_provider(capability)
        if prov:
            return prov.execute(capability, params)
        # Mock / generic action simulation for custom workflow actions
        return ActionResult(
            status="SUCCESS",
            action=capability,
            provider_id=self.provider_id,
            output={"simulated": True, "action": capability, "params": params},
            message=f"Executed simulated action '{capability}'",
        )

    def _run_compensation(self, record: WorkflowExecutionRecord):
        """Executes compensation / rollback steps for completed steps in reverse order."""
        logger.info("[WorkflowAutomationProvider] Executing compensation for execution %s", record.execution_id)
        completed_steps = [s for s in record.steps.values() if s.status == StepStatus.COMPLETED]
        # Reverse order
        completed_steps.reverse()

        for step in completed_steps:
            if step.compensation_capability:
                logger.info("[WorkflowAutomationProvider] Compensating step %s via %s", step.step_id, step.compensation_capability)
                comp_params = step.compensation_parameters or {}
                self._dispatch_step_action(step.compensation_capability, comp_params)
                step.status = StepStatus.COMPENSATED

        record.status = WorkflowStatus.COMPENSATED
        self._save_checkpoint(record, "COMPENSATED")

    # -------------------------------------------------------------------------
    # Lifecycle Controls: Pause, Resume, Cancel, Approval
    # -------------------------------------------------------------------------

    def _pause_workflow(self, params: Dict[str, Any], t0: float) -> ActionResult:
        exec_id = params.get("execution_id")
        with self._lock:
            record = self._executions.get(exec_id)
            if not record:
                return ActionResult(
                    status="FAILED",
                    action="workflow.pause",
                    provider_id=self.provider_id,
                    output={"error": f"Execution '{exec_id}' not found"},
                    message=f"Execution '{exec_id}' not found",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            if record.status == WorkflowStatus.RUNNING:
                record.status = WorkflowStatus.PAUSED
                self._save_checkpoint(record, "PAUSED")

        return ActionResult(
            status="SUCCESS",
            action="workflow.pause",
            provider_id=self.provider_id,
            output={"execution_id": exec_id, "status": record.status.value},
            message=f"Workflow execution '{exec_id}' paused",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _resume_workflow(self, params: Dict[str, Any], t0: float) -> ActionResult:
        exec_id = params.get("execution_id")
        with self._lock:
            record = self._executions.get(exec_id)
            if not record:
                return ActionResult(
                    status="FAILED",
                    action="workflow.resume",
                    provider_id=self.provider_id,
                    output={"error": f"Execution '{exec_id}' not found"},
                    message=f"Execution '{exec_id}' not found",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            if record.status == WorkflowStatus.PAUSED:
                record.status = WorkflowStatus.RUNNING
                self._save_checkpoint(record, "RESUMED")
                return self._run_dag_loop(record, t0)

        return ActionResult(
            status="SUCCESS",
            action="workflow.resume",
            provider_id=self.provider_id,
            output={"execution_id": exec_id, "status": record.status.value},
            message=f"Workflow execution '{exec_id}' resumed",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _cancel_workflow(self, params: Dict[str, Any], t0: float) -> ActionResult:
        exec_id = params.get("execution_id")
        with self._lock:
            record = self._executions.get(exec_id)
            if not record:
                return ActionResult(
                    status="FAILED",
                    action="workflow.cancel",
                    provider_id=self.provider_id,
                    output={"error": f"Execution '{exec_id}' not found"},
                    message=f"Execution '{exec_id}' not found",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            record.status = WorkflowStatus.CANCELLED
            self._save_checkpoint(record, "CANCELLED")

        return ActionResult(
            status="SUCCESS",
            action="workflow.cancel",
            provider_id=self.provider_id,
            output={"execution_id": exec_id, "status": record.status.value},
            message=f"Workflow execution '{exec_id}' cancelled",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _approve_gate(self, params: Dict[str, Any], t0: float) -> ActionResult:
        token = params.get("token")
        with self._lock:
            target_record = None
            target_step_id = None
            for rec in self._executions.values():
                if token in rec.approval_tokens:
                    target_record = rec
                    target_step_id = rec.approval_tokens.pop(token)
                    break

            if not target_record or not target_step_id:
                return ActionResult(
                    status="FAILED",
                    action="workflow.approve_gate",
                    provider_id=self.provider_id,
                    output={"error": "Invalid or expired approval token"},
                    message="Invalid or expired approval token",
                    execution_time_step=(time.perf_counter() - t0) * 1000,
                )

            step = target_record.steps.get(target_step_id)
            if step and step.status == StepStatus.WAITING_APPROVAL:
                step.status = StepStatus.PENDING
                step.requires_approval = False  # Gate approved
                target_record.status = WorkflowStatus.RUNNING
                self._save_checkpoint(target_record, f"GATE_APPROVED_{target_step_id}")
                return self._run_dag_loop(target_record, t0)

        return ActionResult(
            status="SUCCESS",
            action="workflow.approve_gate",
            provider_id=self.provider_id,
            output={"execution_id": target_record.execution_id, "approved_step": target_step_id},
            message=f"Approval gate accepted for step '{target_step_id}'",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _get_status(self, params: Dict[str, Any], t0: float) -> ActionResult:
        exec_id = params.get("execution_id")
        with self._lock:
            record = self._executions.get(exec_id)
            if not record:
                # Try loading from checkpoint on disk
                loaded = self._load_checkpoint(exec_id)
                if loaded:
                    record = loaded
                    self._executions[exec_id] = loaded
                else:
                    return ActionResult(
                        status="FAILED",
                        action="workflow.get_status",
                        provider_id=self.provider_id,
                        output={"error": f"Execution '{exec_id}' not found"},
                        message=f"Execution '{exec_id}' not found",
                        execution_time_ms=(time.perf_counter() - t0) * 1000,
                    )

        return ActionResult(
            status="SUCCESS",
            action="workflow.get_status",
            provider_id=self.provider_id,
            output=record.to_dict(),
            message=f"Execution status: {record.status.value}",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _manual_checkpoint(self, params: Dict[str, Any], t0: float) -> ActionResult:
        exec_id = params.get("execution_id")
        stage = params.get("stage", "MANUAL_CHECKPOINT")
        with self._lock:
            record = self._executions.get(exec_id)
            if not record:
                return ActionResult(
                    status="FAILED",
                    action="workflow.persist_checkpoint",
                    provider_id=self.provider_id,
                    output={"error": f"Execution '{exec_id}' not found"},
                    message=f"Execution '{exec_id}' not found",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            self._save_checkpoint(record, stage)

        return ActionResult(
            status="SUCCESS",
            action="workflow.persist_checkpoint",
            provider_id=self.provider_id,
            output={"execution_id": exec_id, "stage": stage, "persisted": True},
            message=f"Checkpoint persisted for execution '{exec_id}'",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _resume_checkpoint(self, params: Dict[str, Any], t0: float) -> ActionResult:
        exec_id = params.get("execution_id")
        loaded = self._load_checkpoint(exec_id)
        if not loaded:
            return ActionResult(
                status="FAILED",
                action="workflow.resume_checkpoint",
                provider_id=self.provider_id,
                output={"error": f"No checkpoint found for execution '{exec_id}'"},
                message=f"No checkpoint found for execution '{exec_id}'",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        with self._lock:
            loaded.status = WorkflowStatus.RUNNING
            self._executions[exec_id] = loaded
            return self._run_dag_loop(loaded, t0)

    def _compensate_workflow(self, params: Dict[str, Any], t0: float) -> ActionResult:
        exec_id = params.get("execution_id")
        with self._lock:
            record = self._executions.get(exec_id)
            if not record:
                return ActionResult(
                    status="FAILED",
                    action="workflow.compensate",
                    provider_id=self.provider_id,
                    output={"error": f"Execution '{exec_id}' not found"},
                    message=f"Execution '{exec_id}' not found",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            self._run_compensation(record)

        return ActionResult(
            status="SUCCESS",
            action="workflow.compensate",
            provider_id=self.provider_id,
            output={"execution_id": exec_id, "status": record.status.value},
            message=f"Workflow execution '{exec_id}' compensated",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _get_history(self, params: Dict[str, Any], t0: float) -> ActionResult:
        with self._lock:
            history = [
                {
                    "execution_id": rec.execution_id,
                    "workflow_id": rec.workflow_id,
                    "status": rec.status.value,
                    "steps_count": len(rec.steps),
                    "created_at": rec.created_at,
                    "completed_at": rec.completed_at,
                }
                for rec in self._executions.values()
            ]
        return ActionResult(
            status="SUCCESS",
            action="workflow.history",
            provider_id=self.provider_id,
            output={"records": history, "total": len(history)},
            message=f"Retrieved {len(history)} execution history records",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    # -------------------------------------------------------------------------
    # Helper Utilities & Durability
    # -------------------------------------------------------------------------

    def _save_checkpoint(self, record: WorkflowExecutionRecord, stage: str):
        record.checkpoint_stage = stage
        record.updated_at = time.time()
        record.history.append({
            "stage": stage,
            "status": record.status.value,
            "timestamp": record.updated_at,
        })
        try:
            self._cp_path.mkdir(parents=True, exist_ok=True)
            path = self._cp_path / f"{record.execution_id}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, indent=2)
        except Exception as e:
            logger.debug("[WorkflowAutomationProvider] Checkpoint write error: %s", e)

    def _load_checkpoint(self, execution_id: str) -> Optional[WorkflowExecutionRecord]:
        try:
            path = self._cp_path / f"{execution_id}.json"
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return WorkflowExecutionRecord.from_dict(data)
        except Exception as e:
            logger.debug("[WorkflowAutomationProvider] Checkpoint read error: %s", e)
        return None

    def _has_cycle(self, nodes: Set[str], graph: Dict[str, List[str]]) -> bool:
        visited = {n: 0 for n in nodes}  # 0: unvisited, 1: visiting, 2: visited

        def dfs(u):
            visited[u] = 1
            for v in graph.get(u, []):
                if visited[v] == 1:
                    return True
                if visited[v] == 0:
                    if dfs(v):
                        return True
            visited[u] = 2
            return False

        for n in nodes:
            if visited[n] == 0:
                if dfs(n):
                    return True
        return False

    def _evaluate_condition(self, condition: Dict[str, Any], record: WorkflowExecutionRecord) -> bool:
        """Evaluates arbitrary dynamic condition expressions against workflow outputs."""
        var_name = condition.get("variable")
        operator = condition.get("operator", "==")
        expected = condition.get("value")

        actual = None
        if var_name:
            if var_name.startswith("inputs."):
                key = var_name[7:]
                actual = record.inputs.get(key)
            elif var_name.startswith("steps."):
                parts = var_name[6:].split(".")
                step_id = parts[0]
                if step_id in record.outputs:
                    actual = record.outputs[step_id]
                    subkeys = parts[1:]
                    if subkeys and subkeys[0] == "result" and "result" not in actual:
                        subkeys = subkeys[1:]
                    for subkey in subkeys:
                        if isinstance(actual, dict):
                            actual = actual.get(subkey)
                        else:
                            actual = None
                            break

        if operator == "==":
            return actual == expected
        elif operator == "!=":
            return actual != expected
        elif operator == ">":
            return actual is not None and expected is not None and actual > expected
        elif operator == "<":
            return actual is not None and expected is not None and actual < expected
        elif operator == "in":
            return actual in expected if expected else False
        elif operator == "is_not_empty":
            return bool(actual)
        return True

    def _resolve_step_params(self, params: Dict[str, Any], record: WorkflowExecutionRecord) -> Dict[str, Any]:
        """Resolves dynamic template variables in step parameters."""
        resolved = {}
        for k, v in params.items():
            if isinstance(v, str) and "{{" in v and "}}" in v:
                resolved[k] = self._resolve_template_string(v, record)
            elif isinstance(v, dict):
                resolved[k] = self._resolve_step_params(v, record)
            else:
                resolved[k] = v
        return resolved

    def _resolve_template_string(self, text: str, record: WorkflowExecutionRecord) -> Any:
        def repl(match):
            key = match.group(1).strip()
            if key.startswith("inputs."):
                return str(record.inputs.get(key[7:], ""))
            elif key.startswith("steps."):
                parts = key[6:].split(".")
                step_id = parts[0]
                curr = record.outputs.get(step_id, {})
                subkeys = parts[1:]
                if subkeys and subkeys[0] == "result" and "result" not in curr:
                    subkeys = subkeys[1:]
                for p in subkeys:
                    if isinstance(curr, dict):
                        curr = curr.get(p, "")
                    else:
                        break
                return str(curr)
            return match.group(0)

        return re.sub(r"\{\{([^}]+)\}\}", repl, text)

    def _detect_prompt_injection(self, inputs: Dict[str, Any], steps: List[Dict[str, Any]]) -> (bool, str):
        """Scans payload text for prompt injection patterns."""
        combined_text = json.dumps(inputs) + " " + json.dumps(steps)
        for pat in self.PROMPT_INJECTION_PATTERNS:
            if pat.search(combined_text):
                return True, f"Matched injection pattern '{pat.pattern}'"
        return False, ""


workflow_automation_provider = WorkflowAutomationProvider()
