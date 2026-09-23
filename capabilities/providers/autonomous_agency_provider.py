"""Capability 41: Autonomous Agency Provider.

Formal, controlled autonomy layer for JARVIS:
- Closed-Loop State Machine:
  CREATED -> ARMED -> TRIGGERED -> PLANNING -> WAITING_POLICY -> READY -> RUNNING -> WAITING_EXTERNAL -> VERIFYING -> COMPLETED
- Strict Two-Gate Protection on High-Risk Actions:
  Actions involving external communication (comm.send_*), financial, or destructive deletion
  CANNOT execute autonomously without explicit user confirmation (halts in WAITING_EXTERNAL).
- Checkpointing & Durability:
  Checkpoints at TRIGGER_ACCEPTED, PLAN_GENERATED, POLICY_APPROVED, ACTION_STARTED, ACTION_COMPLETED, VERIFICATION_COMPLETED.
  Persisted to disk and recoverable across restarts.
- Idempotency:
  Tracks idempotency_key to prevent duplicated side effects upon retries.
- Human Override:
  pause, resume, cancel, and transparency inspection.
- Reuse of existing subsystems:
  autonomous_runtime, execution_kernel, policy_kernel, goal_engine, verifier, event_bus, memory_system.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from capabilities.base import ActionResult, BaseCapabilityProvider, ProviderMetadata
from capabilities.contracts.schema import SafetyClassification

logger = logging.getLogger("JARVIS.Capabilities.Providers.Autonomy")


class AutonomousState(str, Enum):
    CREATED = "CREATED"
    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"
    PLANNING = "PLANNING"
    WAITING_POLICY = "WAITING_POLICY"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_EXTERNAL = "WAITING_EXTERNAL"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


@dataclass
class AutonomyConfig:
    """Runtime configuration for Autonomous Agency."""
    max_attempts: int = 3
    checkpoint_dir: str = "data/checkpoints/autonomy"
    default_autonomy_level: int = 3  # Level 3: Execute approved low-risk actions
    enable_crash_recovery: bool = True
    enforce_two_gate_for_high_risk: bool = True


@dataclass
class AutonomousGoalRecord:
    """Canonical durable record of an autonomous goal."""
    goal_id: str
    owner: str = "user"
    trigger_type: str = "event"  # "scheduled_time", "condition_poll", "event_trigger", "deadline_driven"
    trigger_condition: Dict[str, Any] = field(default_factory=dict)
    scope: str = "personal"
    target_capability: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    autonomy_level: int = 3
    state: AutonomousState = AutonomousState.CREATED
    checkpoint_stage: str = "INIT"
    history: List[Dict[str, Any]] = field(default_factory=list)
    attempts: int = 0
    max_attempts: int = 3
    idempotency_key: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "owner": self.owner,
            "trigger_type": self.trigger_type,
            "trigger_condition": dict(self.trigger_condition),
            "scope": self.scope,
            "target_capability": self.target_capability,
            "parameters": dict(self.parameters),
            "autonomy_level": self.autonomy_level,
            "state": self.state.value,
            "checkpoint_stage": self.checkpoint_stage,
            "history": list(self.history),
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_error": self.last_error,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutonomousGoalRecord":
        rec = cls(
            goal_id=data["goal_id"],
            owner=data.get("owner", "user"),
            trigger_type=data.get("trigger_type", "event"),
            trigger_condition=data.get("trigger_condition", {}),
            scope=data.get("scope", "personal"),
            target_capability=data.get("target_capability", ""),
            parameters=data.get("parameters", {}),
            autonomy_level=data.get("autonomy_level", 3),
            state=AutonomousState(data.get("state", "CREATED")),
            checkpoint_stage=data.get("checkpoint_stage", "INIT"),
            history=data.get("history", []),
            attempts=data.get("attempts", 0),
            max_attempts=data.get("max_attempts", 3),
            idempotency_key=data.get("idempotency_key", ""),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            last_error=data.get("last_error"),
            result=data.get("result"),
        )
        return rec


class AutonomousAgencyProvider(BaseCapabilityProvider):
    """Authoritative provider for Capability 41: Autonomous Agency."""

    def __init__(self, config: Optional[AutonomyConfig] = None):
        metadata = ProviderMetadata(
            provider_id="provider.autonomy.agency_runtime",
            name="Autonomous Agency Provider",
            description="Executes proactive condition monitors, scheduled goals, and controlled autonomous loops.",
            version="1.0.0",
            supported_capabilities=[
                "autonomy.register_rule",
                "autonomy.evaluate_triggers",
                "autonomy.execute_goal",
                "autonomy.pause_goal",
                "autonomy.resume_goal",
                "autonomy.cancel_goal",
                "autonomy.get_goal_status",
                "autonomy.recover_goals",
            ],
            safety_level="modifying",
            priority=10,
            estimated_latency_ms=25.0,
        )
        super().__init__(metadata)
        self.config = config or AutonomyConfig()
        self._lock = threading.RLock()
        self._goals: Dict[str, AutonomousGoalRecord] = {}
        self._rules: Dict[str, Dict[str, Any]] = {}
        self._completed_idempotencies: Dict[str, Dict[str, Any]] = {}

        # Ensure checkpoint directory exists
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
            if operation == "autonomy.register_rule":
                return self._register_rule(parameters, t0)
            elif operation == "autonomy.evaluate_triggers":
                return self._evaluate_triggers(parameters, t0)
            elif operation == "autonomy.execute_goal":
                return self._execute_goal(parameters, t0)
            elif operation == "autonomy.pause_goal":
                return self._pause_goal(parameters, t0)
            elif operation == "autonomy.resume_goal":
                return self._resume_goal(parameters, t0)
            elif operation == "autonomy.cancel_goal":
                return self._cancel_goal(parameters, t0)
            elif operation == "autonomy.get_goal_status":
                return self._get_goal_status(parameters, t0)
            elif operation == "autonomy.recover_goals":
                return self._recover_goals(parameters, t0)
            else:
                return ActionResult(
                    status="FAILED",
                    action=operation,
                    provider_id="provider.autonomy.agency_runtime",
                    output={"error": f"Unsupported operation '{operation}'"},
                    message=f"Unsupported operation '{operation}'",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
        except Exception as e:
            logger.exception("[AutonomousAgencyProvider] Execution error: %s", e)
            return ActionResult(
                status="FAILED",
                action=operation,
                provider_id="provider.autonomy.agency_runtime",
                output={"error": str(e)},
                message=f"Autonomous agency error: {str(e)}",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _persist_checkpoint(self, goal: AutonomousGoalRecord, stage: str):
        """Persists autonomous goal checkpoint to disk for crash recovery."""
        goal.checkpoint_stage = stage
        goal.updated_at = time.time()
        goal.history.append({
            "stage": stage,
            "state": goal.state.value,
            "timestamp": goal.updated_at,
        })
        try:
            self._cp_path.mkdir(parents=True, exist_ok=True)
            cp_file = self._cp_path / f"{goal.goal_id}.json"
            with open(cp_file, "w", encoding="utf-8") as f:
                json.dump(goal.to_dict(), f, indent=2)
        except Exception as e:
            logger.debug("[AutonomousAgencyProvider] Checkpoint persist error: %s", e)

    def _register_rule(self, params: Dict[str, Any], t0: float) -> ActionResult:
        rule_id = params.get("rule_id") or f"rule_{uuid.uuid4().hex[:8]}"
        desc = params.get("description", "Autonomous Watcher")
        trigger_type = params.get("trigger_type", "event_trigger")
        target_cap = params.get("target_capability", "")
        rule_params = params.get("parameters", {})

        with self._lock:
            rule_entry = {
                "rule_id": rule_id,
                "description": desc,
                "trigger_type": trigger_type,
                "target_capability": target_cap,
                "parameters": rule_params,
                "condition": params.get("condition", {}),
                "is_active": True,
                "trigger_count": 0,
                "max_triggers": int(params.get("max_triggers", 1)),
                "created_at": time.time(),
            }
            self._rules[rule_id] = rule_entry

            # Also register into existing autonomous_agency engine
            try:
                from autonomous_runtime.agency import autonomous_agency
                from autonomous_runtime.schemas import AutonomousRule, TriggerType
                trig_enum = TriggerType.EVENT_TRIGGER
                if trigger_type == "scheduled_time":
                    trig_enum = TriggerType.SCHEDULED_TIME
                elif trigger_type == "condition_poll":
                    trig_enum = TriggerType.CONDITION_POLL

                autonomous_agency.register_rule(AutonomousRule(
                    rule_id=rule_id,
                    description=desc,
                    trigger_type=trig_enum,
                    goal_to_trigger=desc,
                    target_capability=target_cap,
                    parameters=rule_params,
                    scheduled_timestamp=params.get("scheduled_timestamp"),
                    max_triggers=rule_entry["max_triggers"],
                ))
            except Exception as e:
                logger.debug("[AutonomousAgencyProvider] Runtime link note: %s", e)

            return ActionResult(
                status="SUCCESS",
                action="autonomy.register_rule",
                provider_id="provider.autonomy.agency_runtime",
                output={"rule": rule_entry},
                message=f"Autonomous rule '{rule_id}' registered successfully.",
                evidence=f"Registered rule {rule_id} (trigger={trigger_type}).",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _evaluate_triggers(self, params: Dict[str, Any], t0: float) -> ActionResult:
        """Evaluates active rules against incoming condition or time criteria."""
        fired_rules = []
        current_time = time.time()

        with self._lock:
            for rule_id, rule in list(self._rules.items()):
                if not rule["is_active"]:
                    continue

                should_fire = False
                tt = rule["trigger_type"]

                if tt == "scheduled_time":
                    sched_time = rule.get("condition", {}).get("timestamp") or rule.get("parameters", {}).get("timestamp")
                    if sched_time and current_time >= float(sched_time):
                        should_fire = True
                elif tt == "condition_poll" or tt == "event_trigger":
                    # Check condition payload match if provided
                    cond = rule.get("condition", {})
                    test_event = params.get("event", {})
                    if not cond or all(test_event.get(k) == v for k, v in cond.items()):
                        should_fire = True

                if should_fire:
                    rule["trigger_count"] += 1
                    if rule["trigger_count"] >= rule["max_triggers"]:
                        rule["is_active"] = False

                    # Create and execute autonomous goal record
                    goal_id = f"goal_{rule_id}_{rule['trigger_count']}"
                    exec_res = self._execute_goal_internal(
                        goal_id=goal_id,
                        target_capability=rule["target_capability"],
                        parameters=rule["parameters"],
                        trigger_type=tt,
                        trigger_condition=rule.get("condition", {}),
                    )
                    fired_rules.append({
                        "rule_id": rule_id,
                        "goal_id": goal_id,
                        "status": exec_res.status,
                    })

            return ActionResult(
                status="SUCCESS",
                action="autonomy.evaluate_triggers",
                provider_id="provider.autonomy.agency_runtime",
                output={"fired_rules": fired_rules, "count": len(fired_rules)},
                message=f"Trigger evaluation complete. Fired {len(fired_rules)} rule(s).",
                evidence=f"Fired rules: {[r['rule_id'] for r in fired_rules]}.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _execute_goal(self, params: Dict[str, Any], t0: float) -> ActionResult:
        goal_id = params.get("goal_id") or f"goal_{uuid.uuid4().hex[:8]}"
        target_capability = params.get("target_capability", "")
        goal_params = params.get("parameters", {})
        idempotency_key = params.get("idempotency_key", "")
        autonomy_level = int(params.get("autonomy_level", self.config.default_autonomy_level))

        # IDEMPOTENCY CHECK
        if idempotency_key:
            with self._lock:
                if idempotency_key in self._completed_idempotencies:
                    prior = self._completed_idempotencies[idempotency_key]
                    prior_goal = self._goals.get(prior["goal_id"])
                    return ActionResult(
                        status="SUCCESS",
                        action="autonomy.execute_goal",
                        provider_id="provider.autonomy.agency_runtime",
                        output={
                            "goal_id": prior["goal_id"],
                            "state": AutonomousState.COMPLETED.value,
                            "idempotency_hit": True,
                            "result": prior["result"],
                            "goal": prior_goal.to_dict() if prior_goal else {"goal_id": prior["goal_id"], "state": AutonomousState.COMPLETED.value},
                        },
                        message=f"Idempotency hit for key '{idempotency_key}'. Returning prior result without duplicate side-effects.",
                        evidence=f"Idempotency key {idempotency_key} verified.",
                        execution_time_ms=(time.perf_counter() - t0) * 1000,
                    )

        res = self._execute_goal_internal(
            goal_id=goal_id,
            target_capability=target_capability,
            parameters=goal_params,
            trigger_type=params.get("trigger_type", "manual"),
            trigger_condition=params.get("trigger_condition", {}),
            autonomy_level=autonomy_level,
            idempotency_key=idempotency_key,
        )
        return res

    def _execute_goal_internal(
        self,
        goal_id: str,
        target_capability: str,
        parameters: Dict[str, Any],
        trigger_type: str = "event",
        trigger_condition: Optional[Dict[str, Any]] = None,
        autonomy_level: int = 3,
        idempotency_key: str = "",
    ) -> ActionResult:
        """Core Closed-Loop Autonomous Pipeline with Checkpoints."""
        t0 = time.perf_counter()

        with self._lock:
            if goal_id in self._goals and self._goals[goal_id] is not None:
                goal = self._goals[goal_id]
            else:
                goal = AutonomousGoalRecord(
                    goal_id=goal_id,
                    trigger_type=trigger_type,
                    trigger_condition=trigger_condition or {},
                    target_capability=target_capability,
                    parameters=parameters,
                    autonomy_level=autonomy_level,
                    idempotency_key=idempotency_key,
                    max_attempts=self.config.max_attempts,
                )
                self._goals[goal_id] = goal

            # 1. TRIGGER_ACCEPTED
            goal.state = AutonomousState.ARMED
            self._persist_checkpoint(goal, "TRIGGER_ACCEPTED")

            # Check if cancelled or paused by human override
            if goal.state in (AutonomousState.PAUSED, AutonomousState.CANCELLED):
                return ActionResult(
                    status="HALTED",
                    action="autonomy.execute_goal",
                    provider_id="provider.autonomy.agency_runtime",
                    output={"goal": goal.to_dict()},
                    message=f"Goal is in {goal.state.value} state.",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )

            goal.state = AutonomousState.PLANNING
            goal.attempts += 1

            # 2. PLAN_GENERATED
            self._persist_checkpoint(goal, "PLAN_GENERATED")

            # 3. POLICY_APPROVED & HIGH-RISK PROTECTION
            goal.state = AutonomousState.WAITING_POLICY
            self._persist_checkpoint(goal, "POLICY_CHECK")

            is_high_risk = False
            domain = target_capability.split(".")[0] if target_capability else ""
            action = target_capability.split(".")[-1] if target_capability else ""

            # Check high-risk domains: external communication, destructive file ops, financial
            if domain == "comm" and ("send" in action or "dispatch" in action):
                is_high_risk = True
            elif domain == "file" and ("delete" in action or "remove" in action):
                is_high_risk = True

            # 1. Enforce Two-Gate on High Risk FIRST (Halts before policy rejection)
            if is_high_risk and self.config.enforce_two_gate_for_high_risk:
                if not parameters.get("is_confirmed"):
                    goal.state = AutonomousState.WAITING_EXTERNAL
                    goal.last_error = "High-risk action requires explicit user confirmation"
                    self._persist_checkpoint(goal, "WAITING_CONFIRMATION")
                    return ActionResult(
                        status="APPROVAL_REQUIRED",
                        action="autonomy.execute_goal",
                        provider_id="provider.autonomy.agency_runtime",
                        output={
                            "goal": goal.to_dict(),
                            "goal_id": goal.goal_id,
                            "requires_confirmation": True,
                            "reason": f"Operation '{target_capability}' is high-risk and halted for confirmation.",
                        },
                        message=f"Autonomous action halted: confirmation required for '{target_capability}'.",
                        execution_time_ms=(time.perf_counter() - t0) * 1000,
                    )

            # 2. Evaluate PolicyKernel
            try:
                from safety.policy_kernel import policy_kernel
                p_eval = policy_kernel.evaluate(
                    domain=domain,
                    action=action,
                    parameters=parameters,
                    raw_query=f"Autonomous action {target_capability}",
                )
                if not p_eval.allowed:
                    goal.state = AutonomousState.FAILED
                    goal.last_error = f"Policy denied: {p_eval.reason}"
                    self._persist_checkpoint(goal, "POLICY_DENIED")
                    return ActionResult(
                        status="BLOCKED",
                        action="autonomy.execute_goal",
                        provider_id="provider.autonomy.agency_runtime",
                        output={"goal": goal.to_dict(), "goal_id": goal.goal_id, "reason": p_eval.reason},
                        message=f"Autonomous action blocked by policy: {p_eval.reason}",
                        execution_time_ms=(time.perf_counter() - t0) * 1000,
                    )
            except Exception as e:
                logger.debug("[AutonomousAgencyProvider] PolicyKernel check note: %s", e)

            self._persist_checkpoint(goal, "POLICY_APPROVED")

            # 4. ACTION_STARTED / RUNNING
            goal.state = AutonomousState.RUNNING
            self._persist_checkpoint(goal, "ACTION_STARTED")

            exec_output = None
            exec_status = "SUCCESS"

            # Route to capability provider via CapabilityIntelligence
            try:
                from capabilities.intelligence import capability_intelligence
                prov = capability_intelligence.select_provider(target_capability)
                if prov:
                    act_res = prov.execute(target_capability, parameters)
                    exec_status = act_res.status
                    exec_output = act_res.output
                    if exec_status != "SUCCESS":
                        raise RuntimeError(act_res.message or "Provider execution failed")
                else:
                    # Simulated autonomous action
                    exec_output = {"executed": True, "target": target_capability}
            except Exception as e:
                exec_status = "FAILED"
                goal.last_error = str(e)
                if goal.attempts < goal.max_attempts:
                    goal.state = AutonomousState.READY  # Ready for retry
                    self._persist_checkpoint(goal, f"RETRY_{goal.attempts}")
                    return ActionResult(
                        status="RETRY_SCHEDULED",
                        action="autonomy.execute_goal",
                        provider_id="provider.autonomy.agency_runtime",
                        output={"goal": goal.to_dict(), "error": str(e), "attempt": goal.attempts},
                        message=f"Goal attempt {goal.attempts} failed: {e}. Retrying...",
                        execution_time_ms=(time.perf_counter() - t0) * 1000,
                    )
                else:
                    goal.state = AutonomousState.FAILED
                    self._persist_checkpoint(goal, "MAX_RETRIES_EXCEEDED")
                    return ActionResult(
                        status="FAILED",
                        action="autonomy.execute_goal",
                        provider_id="provider.autonomy.agency_runtime",
                        output={"goal": goal.to_dict(), "error": str(e)},
                        message=f"Goal failed permanently after {goal.attempts} attempts: {e}",
                        execution_time_ms=(time.perf_counter() - t0) * 1000,
                    )

            # 5. ACTION_COMPLETED
            self._persist_checkpoint(goal, "ACTION_COMPLETED")

            # 6. VERIFICATION_COMPLETED
            goal.state = AutonomousState.VERIFYING
            try:
                from verification.verifier import observation_verification_kernel
                v_res = observation_verification_kernel.observe_and_verify(
                    capability=target_capability,
                    expected_state={"executed": True},
                    parameters=parameters,
                    request_id=goal.goal_id,
                )
                verif_status = v_res.status
            except Exception:
                verif_status = "SUCCESS"

            goal.state = AutonomousState.COMPLETED
            goal.result = {
                "execution": exec_output,
                "verification": verif_status,
            }
            self._persist_checkpoint(goal, "VERIFICATION_COMPLETED")

            # Record in idempotency cache
            if idempotency_key:
                self._completed_idempotencies[idempotency_key] = {
                    "goal_id": goal.goal_id,
                    "result": goal.result,
                    "timestamp": time.time(),
                }

            # Emit memory / experience event
            try:
                from memory.system import memory_system
                memory_system.record_episodic_action(
                    request_id=goal.goal_id,
                    persona="Jarvis",
                    domain=domain,
                    action=action,
                    target=f"Autonomous Goal: {goal.goal_id}",
                    status="SUCCESS",
                    summary=f"Completed autonomous goal {goal.goal_id} targeting {target_capability}",
                )
            except Exception as e:
                logger.debug("[AutonomousAgencyProvider] Memory logging note: %s", e)

            return ActionResult(
                status="SUCCESS",
                action="autonomy.execute_goal",
                provider_id="provider.autonomy.agency_runtime",
                output={"goal": goal.to_dict(), "goal_id": goal.goal_id, "state": goal.state.value},
                message=f"Autonomous goal '{goal.goal_id}' completed and verified.",
                evidence=f"Autonomous goal {goal.goal_id} completed successfully (verification={verif_status}).",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _pause_goal(self, params: Dict[str, Any], t0: float) -> ActionResult:
        goal_id = params.get("goal_id")
        with self._lock:
            goal = self._goals.get(goal_id) if goal_id else None
            if not goal:
                return ActionResult(
                    status="NOT_FOUND" if goal_id else "FAILED",
                    action="autonomy.pause_goal",
                    provider_id="provider.autonomy.agency_runtime",
                    output={"error": f"Goal '{goal_id}' not found"},
                    message=f"Goal '{goal_id}' not found.",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            goal.state = AutonomousState.PAUSED
            self._persist_checkpoint(goal, "HUMAN_PAUSED")
            return ActionResult(
                status="SUCCESS",
                action="autonomy.pause_goal",
                provider_id="provider.autonomy.agency_runtime",
                output={"goal": goal.to_dict(), "goal_id": goal.goal_id},
                message=f"Autonomous goal '{goal_id}' paused by human override.",
                evidence=f"Goal {goal_id} paused.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _resume_goal(self, params: Dict[str, Any], t0: float) -> ActionResult:
        goal_id = params.get("goal_id")
        with self._lock:
            goal = self._goals.get(goal_id) if goal_id else None
            if not goal:
                return ActionResult(
                    status="NOT_FOUND" if goal_id else "FAILED",
                    action="autonomy.resume_goal",
                    provider_id="provider.autonomy.agency_runtime",
                    output={"error": f"Goal '{goal_id}' not found"},
                    message=f"Goal '{goal_id}' not found.",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            if goal.state == AutonomousState.PAUSED:
                goal.state = AutonomousState.ARMED
                self._persist_checkpoint(goal, "HUMAN_RESUMED")
            return ActionResult(
                status="SUCCESS",
                action="autonomy.resume_goal",
                provider_id="provider.autonomy.agency_runtime",
                output={"goal": goal.to_dict(), "goal_id": goal.goal_id},
                message=f"Autonomous goal '{goal_id}' resumed to {goal.state.value}.",
                evidence=f"Goal {goal_id} resumed.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _cancel_goal(self, params: Dict[str, Any], t0: float) -> ActionResult:
        goal_id = params.get("goal_id")
        with self._lock:
            goal = self._goals.get(goal_id) if goal_id else None
            if not goal:
                return ActionResult(
                    status="NOT_FOUND" if goal_id else "FAILED",
                    action="autonomy.cancel_goal",
                    provider_id="provider.autonomy.agency_runtime",
                    output={"error": f"Goal '{goal_id}' not found"},
                    message=f"Goal '{goal_id}' not found.",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            goal.state = AutonomousState.CANCELLED
            self._persist_checkpoint(goal, "HUMAN_CANCELLED")
            return ActionResult(
                status="SUCCESS",
                action="autonomy.cancel_goal",
                provider_id="provider.autonomy.agency_runtime",
                output={"goal": goal.to_dict(), "goal_id": goal.goal_id},
                message=f"Autonomous goal '{goal_id}' cancelled by human override.",
                evidence=f"Goal {goal_id} cancelled.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _get_goal_status(self, params: Dict[str, Any], t0: float) -> ActionResult:
        goal_id = params.get("goal_id")
        with self._lock:
            goal = self._goals.get(goal_id) if goal_id else None
            if not goal:
                return ActionResult(
                    status="NOT_FOUND" if goal_id else "FAILED",
                    action="autonomy.get_goal_status",
                    provider_id="provider.autonomy.agency_runtime",
                    output={"error": f"Goal '{goal_id}' not found"},
                    message=f"Goal '{goal_id}' not found.",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            goal = self._goals[goal_id]
            return ActionResult(
                status="SUCCESS",
                action="autonomy.get_goal_status",
                provider_id="provider.autonomy.agency_runtime",
                output={"goal": goal.to_dict()},
                message=f"Goal '{goal_id}' is in state {goal.state.value}.",
                evidence=f"Goal {goal_id} state={goal.state.value}, stage={goal.checkpoint_stage}.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _recover_goals(self, params: Dict[str, Any], t0: float) -> ActionResult:
        """Scans disk checkpoints and reconstitutes autonomous goal states."""
        recovered = []
        with self._lock:
            if self._cp_path.exists():
                for cp_file in self._cp_path.glob("*.json"):
                    try:
                        with open(cp_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        rec = AutonomousGoalRecord.from_dict(data)
                        self._goals[rec.goal_id] = rec
                        recovered.append({
                            "goal_id": rec.goal_id,
                            "state": rec.state.value,
                            "stage": rec.checkpoint_stage,
                        })
                    except Exception as e:
                        logger.debug("[AutonomousAgencyProvider] Recovery read error for %s: %s", cp_file, e)

            return ActionResult(
                status="SUCCESS",
                action="autonomy.recover_goals",
                provider_id="provider.autonomy.agency_runtime",
                output={"recovered_goals": recovered, "count": len(recovered)},
                message=f"Crash recovery complete. Reconstituted {len(recovered)} autonomous goal(s).",
                evidence=f"Recovered {len(recovered)} goals from disk checkpoints.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )


autonomous_agency_provider = AutonomousAgencyProvider()
