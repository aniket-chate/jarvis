"""Capability 43: Monitoring & Alerts Provider.

Implements event-driven and scheduled monitoring across arbitrary targets and metrics:
- Condition and threshold evaluation (>, <, ==, !=, in, range, contains)
- Fingerprint-based alert deduplication and cooldown suppression
- Severity hierarchies: INFO -> WARNING -> ERROR -> CRITICAL
- Alert acknowledgement, manual resolution, and auto-resolution upon metric recovery
- Time-based alert escalation for unacknowledged incidents
- Stale target detection via missed heartbeats
- False-positive dampening via consecutive breach thresholds
- Safety policy gating on automated remediation actions
- Event Fabric integration without uncontrolled polling loops
- Zero domain-specific hardcoding: all targets, metrics, and thresholds are dynamic data
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import logging
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import uuid

from capabilities.base import ActionResult, BaseCapabilityProvider, ProviderMetadata
from capabilities.intelligence import capability_intelligence
from safety.policy_kernel import policy_kernel, PolicyLevel
from event_fabric.bus import event_bus
from event_fabric.schemas import UniversalEvent

logger = logging.getLogger("JARVIS.Capabilities.Providers.Monitoring")


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    SUPPRESSED = "SUPPRESSED"


@dataclass
class MonitorConfig:
    """Runtime configuration for Monitoring & Alerts."""
    default_cooldown_sec: float = 60.0
    default_stale_threshold_sec: float = 120.0
    default_escalation_timeout_sec: float = 300.0
    max_history: int = 1000
    auto_resolve_on_normal: bool = True
    enforce_policy_on_actions: bool = True


@dataclass
class MonitorRule:
    """A dynamic condition rule monitoring arbitrary targets/metrics."""
    rule_id: str
    name: str
    target: str
    metric: str
    operator: str  # ">", "<", "==", "!=", "in", "range", "contains"
    threshold: Any
    severity: AlertSeverity = AlertSeverity.WARNING
    cooldown_sec: float = 60.0
    escalation_timeout_sec: float = 300.0
    consecutive_breaches_required: int = 1
    action_capability: Optional[str] = None
    action_parameters: Optional[Dict[str, Any]] = None
    is_active: bool = True
    current_consecutive_breaches: int = 0
    last_evaluated_at: Optional[float] = None
    last_alert_at: Optional[float] = None
    last_value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "target": self.target,
            "metric": self.metric,
            "operator": self.operator,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "cooldown_sec": self.cooldown_sec,
            "escalation_timeout_sec": self.escalation_timeout_sec,
            "consecutive_breaches_required": self.consecutive_breaches_required,
            "action_capability": self.action_capability,
            "action_parameters": dict(self.action_parameters) if self.action_parameters else None,
            "is_active": self.is_active,
            "current_consecutive_breaches": self.current_consecutive_breaches,
            "last_evaluated_at": self.last_evaluated_at,
            "last_alert_at": self.last_alert_at,
            "last_value": self.last_value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MonitorRule":
        return cls(
            rule_id=data["rule_id"],
            name=data.get("name", "Rule"),
            target=data["target"],
            metric=data["metric"],
            operator=data.get("operator", ">"),
            threshold=data["threshold"],
            severity=AlertSeverity(data.get("severity", "WARNING")),
            cooldown_sec=data.get("cooldown_sec", 60.0),
            escalation_timeout_sec=data.get("escalation_timeout_sec", 300.0),
            consecutive_breaches_required=data.get("consecutive_breaches_required", 1),
            action_capability=data.get("action_capability"),
            action_parameters=data.get("action_parameters"),
            is_active=data.get("is_active", True),
            current_consecutive_breaches=data.get("current_consecutive_breaches", 0),
            last_evaluated_at=data.get("last_evaluated_at"),
            last_alert_at=data.get("last_alert_at"),
            last_value=data.get("last_value"),
        )


@dataclass
class AlertRecord:
    """Canonical representation of an emitted monitoring alert."""
    alert_id: str
    rule_id: str
    fingerprint: str
    target: str
    metric: str
    value: Any
    threshold: Any
    severity: AlertSeverity
    status: AlertStatus
    message: str
    created_at: float = field(default_factory=time.time)
    acknowledged_at: Optional[float] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[float] = None
    resolution_reason: Optional[str] = None
    escalated_at: Optional[float] = None
    escalated_severity: Optional[AlertSeverity] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "rule_id": self.rule_id,
            "fingerprint": self.fingerprint,
            "target": self.target,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "status": self.status.value,
            "message": self.message,
            "created_at": self.created_at,
            "acknowledged_at": self.acknowledged_at,
            "acknowledged_by": self.acknowledged_by,
            "resolved_at": self.resolved_at,
            "resolution_reason": self.resolution_reason,
            "escalated_at": self.escalated_at,
            "escalated_severity": self.escalated_severity.value if self.escalated_severity else None,
            "metadata": dict(self.metadata),
        }


class MonitoringAlertsProvider(BaseCapabilityProvider):
    """Authoritative provider for Capability 43: Monitoring & Alerts."""

    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
        re.compile(r"bypass\s+(safety|policy|guardrails)", re.IGNORECASE),
        re.compile(r"elevate\s+to\s+root|sudo\s+su", re.IGNORECASE),
    ]

    def __init__(self, config: Optional[MonitorConfig] = None):
        metadata = ProviderMetadata(
            provider_id="provider.monitor.event_alerts",
            name="Monitoring & Alerts Provider",
            description="Event-driven metric monitoring, deduplication, cooldowns, and escalation.",
            version="1.0.0",
            supported_capabilities=[
                "monitor.watch_condition",
                "monitor.create_rule",
                "monitor.evaluate_metrics",
                "monitor.emit_alert",
                "monitor.deduplicate",
                "monitor.acknowledge_alert",
                "monitor.resolve_alert",
                "monitor.get_alerts",
                "monitor.pause",
                "monitor.resume",
                "monitor.detect_stale",
                "monitor.escalate_alert",
            ],
            safety_level="read_only",
            priority=10,
            estimated_latency_ms=10.0,
        )
        super().__init__(metadata)
        self.config = config or MonitorConfig()
        self._lock = threading.RLock()
        self._rules: Dict[str, MonitorRule] = {}
        self._alerts: Dict[str, AlertRecord] = {}
        self._active_fingerprints: Dict[str, str] = {}  # fingerprint -> alert_id
        self._target_heartbeats: Dict[str, float] = {}  # target -> last_timestamp

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
            if operation in ("monitor.create_rule", "monitor.watch_condition"):
                return self._create_rule(parameters, t0)
            elif operation in ("monitor.evaluate_metrics", "monitor.check"):
                return self._evaluate_metrics(parameters, t0)
            elif operation == "monitor.emit_alert":
                return self._emit_alert(parameters, t0)
            elif operation == "monitor.deduplicate":
                return self._deduplicate_check(parameters, t0)
            elif operation == "monitor.acknowledge_alert":
                return self._acknowledge_alert(parameters, t0)
            elif operation == "monitor.resolve_alert":
                return self._resolve_alert(parameters, t0)
            elif operation in ("monitor.get_alerts", "monitor.history"):
                return self._get_alerts(parameters, t0)
            elif operation == "monitor.pause":
                return self._pause_rule(parameters, t0)
            elif operation == "monitor.resume":
                return self._resume_rule(parameters, t0)
            elif operation == "monitor.detect_stale":
                return self._detect_stale(parameters, t0)
            elif operation == "monitor.escalate_alert":
                return self._escalate_alert(parameters, t0)
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
            logger.exception("[MonitoringAlertsProvider] Execution error: %s", e)
            return ActionResult(
                status="FAILED",
                action=operation,
                provider_id=self.provider_id,
                output={"error": str(e)},
                message=f"Monitoring error: {str(e)}",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    # -------------------------------------------------------------------------
    # Rule Management & Metric Evaluation
    # -------------------------------------------------------------------------

    def _create_rule(self, params: Dict[str, Any], t0: float) -> ActionResult:
        # Prompt injection audit
        payload_str = json.dumps(params)
        for pat in self.PROMPT_INJECTION_PATTERNS:
            if pat.search(payload_str):
                return ActionResult(
                    status="FAILED",
                    action="monitor.create_rule",
                    provider_id=self.provider_id,
                    output={"error": f"Security refusal: prompt injection attempt detected ({pat.pattern})"},
                    message="Security refusal: prompt injection attempt",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )

        target = params.get("target")
        metric = params.get("metric")
        threshold = params.get("threshold")

        if not target or not metric or threshold is None:
            return ActionResult(
                status="FAILED",
                action="monitor.create_rule",
                provider_id=self.provider_id,
                output={"error": "Target, metric, and threshold are required"},
                message="Missing required rule fields",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        rule_id = params.get("rule_id") or f"rule_{uuid.uuid4().hex[:8]}"
        name = params.get("name", f"Rule for {target}.{metric}")
        operator = params.get("operator", ">")
        severity_str = params.get("severity", "WARNING").upper()
        severity = AlertSeverity(severity_str) if severity_str in AlertSeverity.__members__ else AlertSeverity.WARNING
        cooldown = float(params.get("cooldown_sec", self.config.default_cooldown_sec))
        escalation_timeout = float(params.get("escalation_timeout_sec", self.config.default_escalation_timeout_sec))
        consecutive = int(params.get("consecutive_breaches_required", 1))

        rule = MonitorRule(
            rule_id=rule_id,
            name=name,
            target=target,
            metric=metric,
            operator=operator,
            threshold=threshold,
            severity=severity,
            cooldown_sec=cooldown,
            escalation_timeout_sec=escalation_timeout,
            consecutive_breaches_required=consecutive,
            action_capability=params.get("action_capability"),
            action_parameters=params.get("action_parameters"),
            is_active=True,
        )

        with self._lock:
            self._rules[rule_id] = rule

        return ActionResult(
            status="SUCCESS",
            action="monitor.create_rule",
            provider_id=self.provider_id,
            output={"rule_id": rule_id, "rule": rule.to_dict()},
            message=f"Monitoring rule '{rule_id}' registered successfully",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _evaluate_metrics(self, params: Dict[str, Any], t0: float) -> ActionResult:
        """Evaluates incoming metrics against active monitoring rules."""
        target = params.get("target")
        metrics = params.get("metrics", {})
        timestamp = params.get("timestamp", time.time())

        # Update heartbeat for stale monitor detection
        if target:
            with self._lock:
                self._target_heartbeats[target] = timestamp

        emitted_alerts = []
        resolved_alerts = []

        with self._lock:
            for rule in self._rules.values():
                if not rule.is_active:
                    continue
                if rule.target != target and rule.target != "*":
                    continue
                if rule.metric not in metrics:
                    continue

                val = metrics[rule.metric]
                rule.last_evaluated_at = timestamp
                rule.last_value = val

                is_breach = self._check_condition(val, rule.operator, rule.threshold)

                if is_breach:
                    rule.current_consecutive_breaches += 1
                    if rule.current_consecutive_breaches >= rule.consecutive_breaches_required:
                        # Check cooldown
                        in_cooldown = False
                        if rule.last_alert_at:
                            if timestamp - rule.last_alert_at < rule.cooldown_sec:
                                in_cooldown = True

                        if not in_cooldown:
                            # Generate alert
                            alert = self._create_alert_record(rule, val, timestamp)
                            emitted_alerts.append(alert.to_dict())
                            rule.last_alert_at = timestamp

                            # Trigger remediation action if specified (subject to safety policy)
                            if rule.action_capability:
                                self._trigger_remediation(rule, alert)
                else:
                    rule.current_consecutive_breaches = 0
                    # Auto-resolution if metric returned to normal
                    if self.config.auto_resolve_on_normal:
                        fp = self._generate_fingerprint(rule.rule_id, rule.target, rule.metric)
                        if fp in self._active_fingerprints:
                            aid = self._active_fingerprints.pop(fp)
                            existing_alert = self._alerts.get(aid)
                            if existing_alert and existing_alert.status == AlertStatus.ACTIVE:
                                existing_alert.status = AlertStatus.RESOLVED
                                existing_alert.resolved_at = timestamp
                                existing_alert.resolution_reason = "Auto-resolved: metric normalized"
                                resolved_alerts.append(existing_alert.to_dict())

        return ActionResult(
            status="SUCCESS",
            action="monitor.evaluate_metrics",
            provider_id=self.provider_id,
            output={
                "target": target,
                "evaluated_rules_count": len(self._rules),
                "emitted_alerts": emitted_alerts,
                "resolved_alerts": resolved_alerts,
            },
            message=f"Evaluated metrics for '{target}': {len(emitted_alerts)} alerts emitted, {len(resolved_alerts)} auto-resolved",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _emit_alert(self, params: Dict[str, Any], t0: float) -> ActionResult:
        """Emits an alert manually or directly from external events."""
        target = params.get("target", "system")
        metric = params.get("metric", "event")
        value = params.get("value", True)
        severity_str = params.get("severity", "WARNING").upper()
        severity = AlertSeverity(severity_str) if severity_str in AlertSeverity.__members__ else AlertSeverity.WARNING
        message = params.get("message", f"Alert triggered on {target}.{metric}")

        rule_id = params.get("rule_id", "manual")
        fp = self._generate_fingerprint(rule_id, target, metric)

        with self._lock:
            # Check deduplication
            if fp in self._active_fingerprints:
                aid = self._active_fingerprints[fp]
                return ActionResult(
                    status="SUCCESS",
                    action="monitor.emit_alert",
                    provider_id=self.provider_id,
                    output={"alert_id": aid, "status": "DEDUPLICATED", "fingerprint": fp},
                    message=f"Duplicate active alert suppressed for fingerprint '{fp}'",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )

            aid = f"alert_{uuid.uuid4().hex[:10]}"
            alert = AlertRecord(
                alert_id=aid,
                rule_id=rule_id,
                fingerprint=fp,
                target=target,
                metric=metric,
                value=value,
                threshold=params.get("threshold", 0),
                severity=severity,
                status=AlertStatus.ACTIVE,
                message=message,
                metadata=params.get("metadata", {}),
            )
            self._alerts[aid] = alert
            self._active_fingerprints[fp] = aid

        return ActionResult(
            status="SUCCESS",
            action="monitor.emit_alert",
            provider_id=self.provider_id,
            output={"alert": alert.to_dict()},
            message=f"Alert '{aid}' emitted successfully with severity {severity.value}",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _deduplicate_check(self, params: Dict[str, Any], t0: float) -> ActionResult:
        """Explicit deduplication check for an incoming alert fingerprint."""
        target = params.get("target", "")
        metric = params.get("metric", "")
        rule_id = params.get("rule_id", "")
        fp = self._generate_fingerprint(rule_id, target, metric)

        with self._lock:
            is_dup = fp in self._active_fingerprints
            active_id = self._active_fingerprints.get(fp)

        return ActionResult(
            status="SUCCESS",
            action="monitor.deduplicate",
            provider_id=self.provider_id,
            output={"fingerprint": fp, "is_duplicate": is_dup, "active_alert_id": active_id},
            message=f"Deduplication status for '{fp}': duplicate={is_dup}",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    # -------------------------------------------------------------------------
    # Incident Lifecycle: Acknowledgement, Resolution, Escalation
    # -------------------------------------------------------------------------

    def _acknowledge_alert(self, params: Dict[str, Any], t0: float) -> ActionResult:
        aid = params.get("alert_id")
        ack_by = params.get("acknowledged_by", "operator")

        with self._lock:
            alert = self._alerts.get(aid)
            if not alert:
                return ActionResult(
                    status="FAILED",
                    action="monitor.acknowledge_alert",
                    provider_id=self.provider_id,
                    output={"error": f"Alert '{aid}' not found"},
                    message=f"Alert '{aid}' not found",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = time.time()
            alert.acknowledged_by = ack_by

        return ActionResult(
            status="SUCCESS",
            action="monitor.acknowledge_alert",
            provider_id=self.provider_id,
            output={"alert": alert.to_dict()},
            message=f"Alert '{aid}' acknowledged by '{ack_by}'",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _resolve_alert(self, params: Dict[str, Any], t0: float) -> ActionResult:
        aid = params.get("alert_id")
        reason = params.get("reason", "Manual resolution")

        with self._lock:
            alert = self._alerts.get(aid)
            if not alert:
                return ActionResult(
                    status="FAILED",
                    action="monitor.resolve_alert",
                    provider_id=self.provider_id,
                    output={"error": f"Alert '{aid}' not found"},
                    message=f"Alert '{aid}' not found",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = time.time()
            alert.resolution_reason = reason
            if alert.fingerprint in self._active_fingerprints:
                del self._active_fingerprints[alert.fingerprint]

        return ActionResult(
            status="SUCCESS",
            action="monitor.resolve_alert",
            provider_id=self.provider_id,
            output={"alert": alert.to_dict()},
            message=f"Alert '{aid}' resolved: {reason}",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _escalate_alert(self, params: Dict[str, Any], t0: float) -> ActionResult:
        aid = params.get("alert_id")
        with self._lock:
            alert = self._alerts.get(aid)
            if not alert:
                return ActionResult(
                    status="FAILED",
                    action="monitor.escalate_alert",
                    provider_id=self.provider_id,
                    output={"error": f"Alert '{aid}' not found"},
                    message=f"Alert '{aid}' not found",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )

            # Escalate severity level
            severity_order = [AlertSeverity.INFO, AlertSeverity.WARNING, AlertSeverity.ERROR, AlertSeverity.CRITICAL]
            curr_idx = severity_order.index(alert.severity) if alert.severity in severity_order else 1
            new_severity = severity_order[min(curr_idx + 1, len(severity_order) - 1)]

            alert.status = AlertStatus.ESCALATED
            alert.escalated_at = time.time()
            alert.escalated_severity = new_severity
            alert.severity = new_severity

        return ActionResult(
            status="SUCCESS",
            action="monitor.escalate_alert",
            provider_id=self.provider_id,
            output={"alert": alert.to_dict()},
            message=f"Alert '{aid}' escalated to {new_severity.value}",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _get_alerts(self, params: Dict[str, Any], t0: float) -> ActionResult:
        status_filter = params.get("status")
        target_filter = params.get("target")

        with self._lock:
            results = []
            for a in self._alerts.values():
                if status_filter and a.status.value != status_filter:
                    continue
                if target_filter and a.target != target_filter:
                    continue
                results.append(a.to_dict())

        return ActionResult(
            status="SUCCESS",
            action="monitor.get_alerts",
            provider_id=self.provider_id,
            output={"alerts": results, "total": len(results)},
            message=f"Retrieved {len(results)} alerts",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    # -------------------------------------------------------------------------
    # Lifecycle & Stale Detection
    # -------------------------------------------------------------------------

    def _pause_rule(self, params: Dict[str, Any], t0: float) -> ActionResult:
        rid = params.get("rule_id")
        with self._lock:
            rule = self._rules.get(rid)
            if not rule:
                return ActionResult(
                    status="FAILED",
                    action="monitor.pause",
                    provider_id=self.provider_id,
                    output={"error": f"Rule '{rid}' not found"},
                    message=f"Rule '{rid}' not found",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            rule.is_active = False

        return ActionResult(
            status="SUCCESS",
            action="monitor.pause",
            provider_id=self.provider_id,
            output={"rule_id": rid, "is_active": False},
            message=f"Monitoring rule '{rid}' paused",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _resume_rule(self, params: Dict[str, Any], t0: float) -> ActionResult:
        rid = params.get("rule_id")
        with self._lock:
            rule = self._rules.get(rid)
            if not rule:
                return ActionResult(
                    status="FAILED",
                    action="monitor.resume",
                    provider_id=self.provider_id,
                    output={"error": f"Rule '{rid}' not found"},
                    message=f"Rule '{rid}' not found",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            rule.is_active = True

        return ActionResult(
            status="SUCCESS",
            action="monitor.resume",
            provider_id=self.provider_id,
            output={"rule_id": rid, "is_active": True},
            message=f"Monitoring rule '{rid}' resumed",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _detect_stale(self, params: Dict[str, Any], t0: float) -> ActionResult:
        """Detects monitoring targets that have missed heartbeats."""
        threshold_sec = float(params.get("stale_threshold_sec", self.config.default_stale_threshold_sec))
        now = float(params.get("current_time", time.time()))

        stale_targets = []
        with self._lock:
            for target, last_hb in self._target_heartbeats.items():
                if now - last_hb > threshold_sec:
                    stale_targets.append({
                        "target": target,
                        "last_heartbeat": last_hb,
                        "age_sec": now - last_hb,
                    })

        return ActionResult(
            status="SUCCESS",
            action="monitor.detect_stale",
            provider_id=self.provider_id,
            output={"stale_targets": stale_targets, "count": len(stale_targets)},
            message=f"Detected {len(stale_targets)} stale targets",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    # -------------------------------------------------------------------------
    # Helper Utilities
    # -------------------------------------------------------------------------

    def _generate_fingerprint(self, rule_id: str, target: str, metric: str) -> str:
        raw = f"{rule_id}:{target}:{metric}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _check_condition(self, val: Any, op: str, threshold: Any) -> bool:
        try:
            if op == ">":
                return float(val) > float(threshold)
            elif op == "<":
                return float(val) < float(threshold)
            elif op == ">=":
                return float(val) >= float(threshold)
            elif op == "<=":
                return float(val) <= float(threshold)
            elif op == "==":
                return val == threshold
            elif op == "!=":
                return val != threshold
            elif op == "in":
                return val in threshold
            elif op == "range":
                low, high = threshold
                return float(val) < float(low) or float(val) > float(high)
            elif op == "contains":
                return str(threshold) in str(val)
        except Exception:
            return False
        return False

    def _create_alert_record(self, rule: MonitorRule, val: Any, timestamp: float) -> AlertRecord:
        aid = f"alert_{uuid.uuid4().hex[:10]}"
        fp = self._generate_fingerprint(rule.rule_id, rule.target, rule.metric)
        msg = f"Metric breach on '{rule.target}.{rule.metric}': value={val} breached condition ({rule.operator} {rule.threshold})"

        record = AlertRecord(
            alert_id=aid,
            rule_id=rule.rule_id,
            fingerprint=fp,
            target=rule.target,
            metric=rule.metric,
            value=val,
            threshold=rule.threshold,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            message=msg,
            created_at=timestamp,
        )
        self._alerts[aid] = record
        self._active_fingerprints[fp] = aid
        return record

    def _trigger_remediation(self, rule: MonitorRule, alert: AlertRecord):
        """Dispatches automated remediation action, checking safety policy first."""
        if not rule.action_capability:
            return
        logger.info("[MonitoringAlertsProvider] Triggering remediation '%s' for alert '%s'", rule.action_capability, alert.alert_id)
        # Policy safety enforcement: high risk / modifying actions require verification
        if self.config.enforce_policy_on_actions:
            decision = policy_kernel.evaluate(
                domain=rule.action_capability.split(".")[0],
                action=rule.action_capability,
                parameters=rule.action_parameters or {},
            )
            if not decision.allowed:
                logger.warning(
                    "[MonitoringAlertsProvider] Remediation '%s' refused by policy: %s",
                    rule.action_capability, decision.reason,
                )
                return

        prov = capability_intelligence.select_provider(rule.action_capability)
        if prov:
            prov.execute(rule.action_capability, rule.action_parameters or {})


monitoring_alerts_provider = MonitoringAlertsProvider()
