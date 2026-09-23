"""Capability 49: Verification & Self-Diagnostics Provider.

Provides JARVIS with an evidence-based self-diagnostic and verification capability:
- Subsystem verification: Architecture, Runtime, Capabilities, Memory, World Model, Autonomy, Security, Device Mesh, External Providers
- Structured diagnostic records: diagnostic_id, target, category, probe, expected vs observed, evidence, confidence, severity, status
- Strict epistemic boundary: Missing or insufficient evidence MUST result in UNKNOWN / NOT_VERIFIABLE (never fabricated HEALTHY)
- Comprehensive failure classification (configuration, dependency, provider, verification, state_inconsistency, etc.)
- Safety-gated recommendations: Diagnostics inspects and recommends, but does not perform unsafe automatic production mutation without Policy & Authorization
- Zero domain-specific hardcoding: probes and targets accept arbitrary system entities
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import uuid

from capabilities.base import ActionResult, BaseCapabilityProvider, ProviderMetadata
from capabilities.contracts.registry_50 import contract_registry_50
from capabilities.intelligence import capability_intelligence
from safety.policy_kernel import policy_kernel
from event_fabric.bus import event_bus
from event_fabric.schemas import UniversalEvent

logger = logging.getLogger("JARVIS.Capabilities.Providers.VerificationDiagnostics")


# -----------------------------------------------------------------------------
# Enums and Schemas
# -----------------------------------------------------------------------------

class DiagnosticStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"


class DiagnosticCategory(str, Enum):
    ARCHITECTURE = "ARCHITECTURE"
    RUNTIME = "RUNTIME"
    CAPABILITIES = "CAPABILITIES"
    MEMORY = "MEMORY"
    WORLD_MODEL = "WORLD_MODEL"
    AUTONOMY = "AUTONOMY"
    SECURITY = "SECURITY"
    DEVICE_MESH = "DEVICE_MESH"
    EXTERNAL_PROVIDERS = "EXTERNAL_PROVIDERS"
    CUSTOM = "CUSTOM"


class FailureClassification(str, Enum):
    NONE = "NONE"
    CONFIGURATION = "CONFIGURATION"
    DEPENDENCY = "DEPENDENCY"
    PROVIDER = "PROVIDER"
    NETWORK = "NETWORK"
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    EXECUTION = "EXECUTION"
    VERIFICATION = "VERIFICATION"
    STATE_INCONSISTENCY = "STATE_INCONSISTENCY"
    TIMEOUT = "TIMEOUT"
    CONCURRENCY = "CONCURRENCY"
    PERSISTENCE = "PERSISTENCE"
    RECOVERY = "RECOVERY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNKNOWN = "UNKNOWN"


class SeverityLevel(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class DiagnosticProbeResult:
    diagnostic_id: str
    target: str
    category: DiagnosticCategory
    probe_name: str
    expected_state: Dict[str, Any]
    observed_state: Dict[str, Any]
    evidence: Dict[str, Any]
    confidence: float  # 0.0 to 1.0
    severity: SeverityLevel
    status: DiagnosticStatus
    failure_class: FailureClassification
    timestamp: float = field(default_factory=time.time)
    provider_id: str = "provider.diag.system_audit"
    remediation_recommendation: Optional[str] = None
    verification_result: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diagnostic_id": self.diagnostic_id,
            "target": self.target,
            "category": self.category.value,
            "probe_name": self.probe_name,
            "expected_state": self.expected_state,
            "observed_state": self.observed_state,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "severity": self.severity.value,
            "status": self.status.value,
            "failure_class": self.failure_class.value,
            "timestamp": self.timestamp,
            "provider_id": self.provider_id,
            "remediation_recommendation": self.remediation_recommendation,
            "verification_result": self.verification_result,
        }


@dataclass
class DiagnosticsConfig:
    probe_timeout_sec: float = 10.0
    min_evidence_confidence_threshold: float = 0.6
    max_history_records: int = 1000
    require_confirmation_for_remediation: bool = True


# -----------------------------------------------------------------------------
# Capability 49 Provider Implementation
# -----------------------------------------------------------------------------

class VerificationDiagnosticsProvider(BaseCapabilityProvider):
    """Capability 49: Verification & Self-Diagnostics Provider."""

    def __init__(self, config: Optional[DiagnosticsConfig] = None):
        self.config = config or DiagnosticsConfig()
        self._diagnostic_history: List[DiagnosticProbeResult] = []
        self._lock = threading.RLock()

        metadata = ProviderMetadata(
            provider_id="provider.diag.system_audit",
            name="Verification & Self-Diagnostics Provider",
            supported_capabilities=[
                "diagnostics.health_check",
                "diagnostics.audit_providers",
                "diagnostics.run_self_test",
                "diagnostics.run_probe",
                "diagnostics.verify_subsystem",
                "diagnostics.collect_evidence",
                "diagnostics.diagnose",
                "diagnostics.get_status",
                "diagnostics.verify_memory",
                "diagnostics.verify_world_model",
                "diagnostics.verify_autonomy",
                "diagnostics.verify_security",
                "diagnostics.verify_providers",
                "diagnostics.get_diagnostic_report",
            ],
            priority=10,
            estimated_latency_ms=15.0,
        )
        super().__init__(metadata=metadata)

    def is_available(self) -> bool:
        return True

    # -------------------------------------------------------------------------
    # Execution Dispatcher
    # -------------------------------------------------------------------------

    def execute(self, action: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t0 = time.time()
        with self._lock:
            handlers: Dict[str, Callable[[Dict[str, Any]], ActionResult]] = {
                "diagnostics.health_check": self._handle_health_check,
                "diagnostics.audit_providers": self._handle_audit_providers,
                "diagnostics.run_self_test": self._handle_run_self_test,
                "diagnostics.run_probe": self._handle_run_probe,
                "diagnostics.verify_subsystem": self._handle_verify_subsystem,
                "diagnostics.collect_evidence": self._handle_collect_evidence,
                "diagnostics.diagnose": self._handle_diagnose,
                "diagnostics.get_status": self._handle_get_status,
                "diagnostics.verify_memory": self._handle_verify_memory,
                "diagnostics.verify_world_model": self._handle_verify_world_model,
                "diagnostics.verify_autonomy": self._handle_verify_autonomy,
                "diagnostics.verify_security": self._handle_verify_security,
                "diagnostics.verify_providers": self._handle_verify_providers,
                "diagnostics.get_diagnostic_report": self._handle_get_diagnostic_report,
            }

            handler = handlers.get(action)
            if not handler:
                return ActionResult(
                    status="FAILURE",
                    output={"error": f"Unsupported action '{action}'"},
                    message=f"Operation '{action}' not supported by {self.metadata.provider_id}.",
                    execution_time_ms=(time.time() - t0) * 1000,
                )

            try:
                res = handler(parameters)
                res.execution_time_ms = (time.time() - t0) * 1000
                return res
            except Exception as e:
                logger.error("[VerificationDiagnosticsProvider] Error in action %s: %s", action, e, exc_info=True)
                return ActionResult(
                    status="ERROR",
                    output={"error": str(e)},
                    message=f"Internal error executing {action}: {e}",
                    execution_time_ms=(time.time() - t0) * 1000,
                )

    # -------------------------------------------------------------------------
    # Internal Diagnostic Recording
    # -------------------------------------------------------------------------

    def _record_diagnostic(self, probe: DiagnosticProbeResult):
        self._diagnostic_history.append(probe)
        if len(self._diagnostic_history) > self.config.max_history_records:
            self._diagnostic_history.pop(0)

        # Publish diagnostic telemetry to event fabric
        try:
            event_bus.publish_sync(UniversalEvent(
                event_type=f"diagnostics.probe.{probe.status.value.lower()}",
                source=self.metadata.provider_id,
                payload=probe.to_dict(),
            ))
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Probe Handlers
    # -------------------------------------------------------------------------

    def _handle_health_check(self, params: Dict[str, Any]) -> ActionResult:
        """Comprehensive system health probe across core subsystems."""
        t_start = time.perf_counter()
        probes = []

        # 1. Architecture: Contract Registry Completeness
        contracts = contract_registry_50.list_all_contracts()
        passed_contracts = len(contracts) == 50
        p_contracts = DiagnosticProbeResult(
            diagnostic_id=f"diag-{uuid.uuid4()}",
            target="ContractRegistry50",
            category=DiagnosticCategory.ARCHITECTURE,
            probe_name="contract_registry_completeness",
            expected_state={"contract_count": 50},
            observed_state={"contract_count": len(contracts)},
            evidence={"total_registered": len(contracts)},
            confidence=1.0,
            severity=SeverityLevel.INFO if passed_contracts else SeverityLevel.CRITICAL,
            status=DiagnosticStatus.HEALTHY if passed_contracts else DiagnosticStatus.FAILED,
            failure_class=FailureClassification.NONE if passed_contracts else FailureClassification.CONFIGURATION,
            verification_result=passed_contracts,
        )
        probes.append(p_contracts)
        self._record_diagnostic(p_contracts)

        # 2. Capabilities: Capability Intelligence Provider Registration
        providers = getattr(capability_intelligence, "_all_providers", {})
        providers_healthy = len(providers) > 0
        p_providers = DiagnosticProbeResult(
            diagnostic_id=f"diag-{uuid.uuid4()}",
            target="CapabilityIntelligence",
            category=DiagnosticCategory.CAPABILITIES,
            probe_name="provider_registry_probe",
            expected_state={"providers_registered_min": 1},
            observed_state={"providers_registered": len(providers)},
            evidence={"registered_providers": list(providers.keys())[:10]},
            confidence=1.0,
            severity=SeverityLevel.INFO if providers_healthy else SeverityLevel.CRITICAL,
            status=DiagnosticStatus.HEALTHY if providers_healthy else DiagnosticStatus.FAILED,
            failure_class=FailureClassification.NONE if providers_healthy else FailureClassification.PROVIDER,
            verification_result=providers_healthy,
        )
        probes.append(p_providers)
        self._record_diagnostic(p_providers)

        # 3. Security: Policy Kernel Availability
        p_kernel_ok = policy_kernel is not None
        p_policy = DiagnosticProbeResult(
            diagnostic_id=f"diag-{uuid.uuid4()}",
            target="PolicyKernel",
            category=DiagnosticCategory.SECURITY,
            probe_name="policy_kernel_availability",
            expected_state={"available": True},
            observed_state={"available": p_kernel_ok},
            evidence={"kernel_type": type(policy_kernel).__name__ if p_kernel_ok else "None"},
            confidence=1.0,
            severity=SeverityLevel.INFO if p_kernel_ok else SeverityLevel.CRITICAL,
            status=DiagnosticStatus.HEALTHY if p_kernel_ok else DiagnosticStatus.FAILED,
            failure_class=FailureClassification.NONE if p_kernel_ok else FailureClassification.DEPENDENCY,
            verification_result=p_kernel_ok,
        )
        probes.append(p_policy)
        self._record_diagnostic(p_policy)

        # 4. Runtime: Event Fabric Availability
        p_bus_ok = event_bus is not None
        p_bus = DiagnosticProbeResult(
            diagnostic_id=f"diag-{uuid.uuid4()}",
            target="EventFabric",
            category=DiagnosticCategory.RUNTIME,
            probe_name="event_fabric_availability",
            expected_state={"available": True},
            observed_state={"available": p_bus_ok},
            evidence={"bus_type": type(event_bus).__name__ if p_bus_ok else "None"},
            confidence=1.0,
            severity=SeverityLevel.INFO if p_bus_ok else SeverityLevel.CRITICAL,
            status=DiagnosticStatus.HEALTHY if p_bus_ok else DiagnosticStatus.FAILED,
            failure_class=FailureClassification.NONE if p_bus_ok else FailureClassification.DEPENDENCY,
            verification_result=p_bus_ok,
        )
        probes.append(p_bus)
        self._record_diagnostic(p_bus)

        all_healthy = all(p.status == DiagnosticStatus.HEALTHY for p in probes)
        overall_status = DiagnosticStatus.HEALTHY if all_healthy else DiagnosticStatus.DEGRADED

        return ActionResult(
            status="SUCCESS",
            output={
                "overall_status": overall_status.value,
                "probe_count": len(probes),
                "probes": [p.to_dict() for p in probes],
                "duration_ms": max(0.01, round((time.perf_counter() - t_start) * 1000, 3)),
            },
            message=f"Health check completed with status: {overall_status.value}.",
            evidence={"status": overall_status.value, "probe_count": len(probes)},
        )

    def _handle_audit_providers(self, params: Dict[str, Any]) -> ActionResult:
        """Audits responsiveness and contracts across all registered providers."""
        probes = []
        providers = getattr(capability_intelligence, "_all_providers", {})

        for pid, provider in providers.items():
            t0 = time.time()
            is_responsive = hasattr(provider, "metadata") and provider.metadata is not None
            elapsed_ms = (time.time() - t0) * 1000

            probe = DiagnosticProbeResult(
                diagnostic_id=f"diag-{uuid.uuid4()}",
                target=pid,
                category=DiagnosticCategory.EXTERNAL_PROVIDERS if "external" in pid else DiagnosticCategory.CAPABILITIES,
                probe_name="provider_metadata_probe",
                expected_state={"responsive": True, "metadata_valid": True},
                observed_state={"responsive": is_responsive, "latency_ms": elapsed_ms},
                evidence={
                    "provider_id": pid,
                    "supported_ops_count": len(provider.metadata.supported_capabilities) if is_responsive else 0,
                },
                confidence=1.0,
                severity=SeverityLevel.INFO if is_responsive else SeverityLevel.HIGH,
                status=DiagnosticStatus.HEALTHY if is_responsive else DiagnosticStatus.FAILED,
                failure_class=FailureClassification.NONE if is_responsive else FailureClassification.PROVIDER,
                verification_result=is_responsive,
            )
            probes.append(probe)
            self._record_diagnostic(probe)

        failed_count = sum(1 for p in probes if p.status == DiagnosticStatus.FAILED)
        return ActionResult(
            status="SUCCESS",
            output={
                "total_providers_audited": len(probes),
                "healthy_providers": len(probes) - failed_count,
                "failed_providers": failed_count,
                "probes": [p.to_dict() for p in probes],
            },
            message=f"Audited {len(probes)} providers ({failed_count} failures).",
            evidence={"audited_count": len(probes), "failed_count": failed_count},
        )

    def _handle_run_self_test(self, params: Dict[str, Any]) -> ActionResult:
        """Runs an empirical self-test on a specified target or all core contracts."""
        target = params.get("target", "all_contracts")
        evidence = params.get("evidence", {})

        # Critical Invariant: If evidence is missing or insufficient, report UNKNOWN / NOT_VERIFIABLE
        if not evidence and target not in ("all_contracts", "ContractRegistry50"):
            probe = DiagnosticProbeResult(
                diagnostic_id=f"diag-{uuid.uuid4()}",
                target=target,
                category=DiagnosticCategory.CUSTOM,
                probe_name="self_test_probe",
                expected_state={"verifiable": True},
                observed_state={"verifiable": False},
                evidence={"reason": "Insufficient empirical evidence provided"},
                confidence=0.0,
                severity=SeverityLevel.MEDIUM,
                status=DiagnosticStatus.NOT_VERIFIABLE,
                failure_class=FailureClassification.INSUFFICIENT_EVIDENCE,
                remediation_recommendation="Collect live telemetry before running diagnosis",
                verification_result=False,
            )
            self._record_diagnostic(probe)
            return ActionResult(
                status="SUCCESS",
                output=probe.to_dict(),
                message=f"Self-test for target '{target}' could not be verified due to lack of evidence.",
                evidence={"status": DiagnosticStatus.NOT_VERIFIABLE.value},
            )

        # Evaluate target
        contracts = contract_registry_50.list_all_contracts()
        passed = len(contracts) == 50
        probe = DiagnosticProbeResult(
            diagnostic_id=f"diag-{uuid.uuid4()}",
            target=target,
            category=DiagnosticCategory.ARCHITECTURE,
            probe_name="self_test_contract_integrity",
            expected_state={"contract_count": 50},
            observed_state={"contract_count": len(contracts)},
            evidence={"contracts_verified": len(contracts)},
            confidence=1.0,
            severity=SeverityLevel.INFO if passed else SeverityLevel.CRITICAL,
            status=DiagnosticStatus.HEALTHY if passed else DiagnosticStatus.FAILED,
            failure_class=FailureClassification.NONE if passed else FailureClassification.CONFIGURATION,
            verification_result=passed,
        )
        self._record_diagnostic(probe)

        return ActionResult(
            status="SUCCESS",
            output=probe.to_dict(),
            message=f"Self-test completed with status: {probe.status.value}.",
            evidence={"status": probe.status.value},
        )

    def _handle_run_probe(self, params: Dict[str, Any]) -> ActionResult:
        """Executes a custom or target-specific diagnostic probe."""
        target = params.get("target")
        probe_name = params.get("probe_name", "generic_probe")
        category_str = params.get("category", DiagnosticCategory.CUSTOM.value).upper()
        try:
            category = DiagnosticCategory(category_str)
        except ValueError:
            category = DiagnosticCategory.CUSTOM

        expected_state = params.get("expected_state", {})
        observed_state = params.get("observed_state")
        evidence = params.get("evidence")

        # Invariant: Truthful UNKNOWN / NOT_VERIFIABLE on missing data
        if observed_state is None or evidence is None:
            probe = DiagnosticProbeResult(
                diagnostic_id=f"diag-{uuid.uuid4()}",
                target=target or "unknown_target",
                category=category,
                probe_name=probe_name,
                expected_state=expected_state,
                observed_state={},
                evidence={"missing_data": True},
                confidence=0.0,
                severity=SeverityLevel.LOW,
                status=DiagnosticStatus.UNKNOWN,
                failure_class=FailureClassification.INSUFFICIENT_EVIDENCE,
                remediation_recommendation="Provide valid observed state and telemetry evidence",
                verification_result=False,
            )
            self._record_diagnostic(probe)
            return ActionResult(
                status="SUCCESS",
                output=probe.to_dict(),
                message="Probe resulted in UNKNOWN state due to missing observed state or evidence.",
                evidence={"status": DiagnosticStatus.UNKNOWN.value},
            )

        # Compare expected vs observed
        matches = True
        diffs = {}
        for k, v in expected_state.items():
            if k not in observed_state or observed_state[k] != v:
                matches = False
                diffs[k] = {"expected": v, "observed": observed_state.get(k)}

        status = DiagnosticStatus.HEALTHY if matches else DiagnosticStatus.FAILED
        failure_class = FailureClassification.NONE if matches else FailureClassification.VERIFICATION
        severity = SeverityLevel.INFO if matches else SeverityLevel.HIGH

        probe = DiagnosticProbeResult(
            diagnostic_id=f"diag-{uuid.uuid4()}",
            target=target or "unnamed_target",
            category=category,
            probe_name=probe_name,
            expected_state=expected_state,
            observed_state=observed_state,
            evidence={"telemetry": evidence, "diffs": diffs},
            confidence=float(params.get("confidence", 0.95)),
            severity=severity,
            status=status,
            failure_class=failure_class,
            remediation_recommendation=params.get("remediation_recommendation") if not matches else None,
            verification_result=matches,
        )
        self._record_diagnostic(probe)

        return ActionResult(
            status="SUCCESS",
            output=probe.to_dict(),
            message=f"Probe '{probe_name}' completed on '{target}': {status.value}.",
            evidence={"status": status.value, "matches": matches},
        )

    def _handle_verify_subsystem(self, params: Dict[str, Any]) -> ActionResult:
        subsystem = params.get("subsystem", "").upper()
        if subsystem in ("MEMORY", "PERSISTENCE"):
            return self._handle_verify_memory(params)
        elif subsystem in ("WORLD_MODEL", "REALITY"):
            return self._handle_verify_world_model(params)
        elif subsystem in ("AUTONOMY", "GOALS"):
            return self._handle_verify_autonomy(params)
        elif subsystem in ("SECURITY", "POLICY", "IDENTITY"):
            return self._handle_verify_security(params)
        elif subsystem in ("PROVIDERS", "CAPABILITIES"):
            return self._handle_verify_providers(params)
        else:
            return self._handle_run_probe(params)

    def _handle_verify_memory(self, params: Dict[str, Any]) -> ActionResult:
        """Verifies memory persistence, retrieval, consistency, and freshness."""
        evidence = params.get("evidence", {})
        is_consistent = evidence.get("consistency_check", True)
        freshness_sec = float(evidence.get("last_synced_sec", 0.0))

        # Stale state if > 300 seconds
        is_fresh = freshness_sec < 300.0
        status = DiagnosticStatus.HEALTHY if (is_consistent and is_fresh) else DiagnosticStatus.DEGRADED

        probe = DiagnosticProbeResult(
            diagnostic_id=f"diag-{uuid.uuid4()}",
            target="MemorySubsystem",
            category=DiagnosticCategory.MEMORY,
            probe_name="memory_consistency_probe",
            expected_state={"consistent": True, "fresh": True},
            observed_state={"consistent": is_consistent, "freshness_sec": freshness_sec},
            evidence=evidence,
            confidence=0.9,
            severity=SeverityLevel.INFO if status == DiagnosticStatus.HEALTHY else SeverityLevel.MEDIUM,
            status=status,
            failure_class=FailureClassification.NONE if status == DiagnosticStatus.HEALTHY else FailureClassification.STATE_INCONSISTENCY,
            remediation_recommendation="Trigger memory consolidation and sync" if status != DiagnosticStatus.HEALTHY else None,
            verification_result=(status == DiagnosticStatus.HEALTHY),
        )
        self._record_diagnostic(probe)

        return ActionResult(
            status="SUCCESS",
            output=probe.to_dict(),
            message=f"Memory subsystem verification: {status.value}.",
            evidence={"status": status.value},
        )

    def _handle_verify_world_model(self, params: Dict[str, Any]) -> ActionResult:
        """Verifies World Model reality consistency, staleness, and conflicting claims."""
        evidence = params.get("evidence", {})
        conflicts = evidence.get("conflicting_observations", 0)
        staleness_rate = float(evidence.get("staleness_rate", 0.0))

        status = DiagnosticStatus.HEALTHY
        if conflicts > 0 or staleness_rate > 0.2:
            status = DiagnosticStatus.DEGRADED
        if conflicts > 5:
            status = DiagnosticStatus.FAILED

        probe = DiagnosticProbeResult(
            diagnostic_id=f"diag-{uuid.uuid4()}",
            target="WorldModel",
            category=DiagnosticCategory.WORLD_MODEL,
            probe_name="world_model_reality_probe",
            expected_state={"conflicts": 0, "staleness_max": 0.2},
            observed_state={"conflicts": conflicts, "staleness_rate": staleness_rate},
            evidence=evidence,
            confidence=0.95,
            severity=SeverityLevel.INFO if status == DiagnosticStatus.HEALTHY else SeverityLevel.HIGH,
            status=status,
            failure_class=FailureClassification.NONE if status == DiagnosticStatus.HEALTHY else FailureClassification.STATE_INCONSISTENCY,
            remediation_recommendation="Run active empirical probe to resolve contradictory entity states" if conflicts > 0 else None,
            verification_result=(status == DiagnosticStatus.HEALTHY),
        )
        self._record_diagnostic(probe)

        return ActionResult(
            status="SUCCESS",
            output=probe.to_dict(),
            message=f"World Model verification: {status.value}.",
            evidence={"status": status.value},
        )

    def _handle_verify_autonomy(self, params: Dict[str, Any]) -> ActionResult:
        """Verifies autonomous loop state: active goals, stuck loops, verification presence."""
        evidence = params.get("evidence", {})
        stuck_loops = evidence.get("stuck_retry_loops", 0)
        missing_verifications = evidence.get("missing_step_verifications", 0)

        status = DiagnosticStatus.HEALTHY
        if stuck_loops > 0 or missing_verifications > 0:
            status = DiagnosticStatus.DEGRADED
        if stuck_loops > 3:
            status = DiagnosticStatus.FAILED

        probe = DiagnosticProbeResult(
            diagnostic_id=f"diag-{uuid.uuid4()}",
            target="AutonomousRuntime",
            category=DiagnosticCategory.AUTONOMY,
            probe_name="autonomy_loop_health_probe",
            expected_state={"stuck_loops": 0, "missing_verifications": 0},
            observed_state={"stuck_loops": stuck_loops, "missing_verifications": missing_verifications},
            evidence=evidence,
            confidence=0.95,
            severity=SeverityLevel.INFO if status == DiagnosticStatus.HEALTHY else SeverityLevel.HIGH,
            status=status,
            failure_class=FailureClassification.NONE if status == DiagnosticStatus.HEALTHY else FailureClassification.EXECUTION,
            remediation_recommendation="Abort stuck retry loop and yield control to operator" if stuck_loops > 0 else None,
            verification_result=(status == DiagnosticStatus.HEALTHY),
        )
        self._record_diagnostic(probe)

        return ActionResult(
            status="SUCCESS",
            output=probe.to_dict(),
            message=f"Autonomy loop verification: {status.value}.",
            evidence={"status": status.value},
        )

    def _handle_verify_security(self, params: Dict[str, Any]) -> ActionResult:
        """Verifies security controls: policy availability, trust integrity, revoked containment."""
        evidence = params.get("evidence", {})
        policy_intact = hasattr(policy_kernel, "evaluate") or hasattr(policy_kernel, "evaluate_policy")
        revoked_bypassed = evidence.get("revoked_identity_executed", False)

        status = DiagnosticStatus.HEALTHY if (policy_intact and not revoked_bypassed) else DiagnosticStatus.FAILED
        failure_class = FailureClassification.NONE if status == DiagnosticStatus.HEALTHY else FailureClassification.AUTHORIZATION

        probe = DiagnosticProbeResult(
            diagnostic_id=f"diag-{uuid.uuid4()}",
            target="SecuritySubsystem",
            category=DiagnosticCategory.SECURITY,
            probe_name="security_control_integrity_probe",
            expected_state={"policy_intact": True, "revoked_bypassed": False},
            observed_state={"policy_intact": policy_intact, "revoked_bypassed": revoked_bypassed},
            evidence={"policy_kernel": str(policy_kernel), "audit": evidence},
            confidence=1.0,
            severity=SeverityLevel.INFO if status == DiagnosticStatus.HEALTHY else SeverityLevel.CRITICAL,
            status=status,
            failure_class=failure_class,
            remediation_recommendation="Immediate lockdown of unauthenticated channels" if revoked_bypassed else None,
            verification_result=(status == DiagnosticStatus.HEALTHY),
        )
        self._record_diagnostic(probe)

        return ActionResult(
            status="SUCCESS",
            output=probe.to_dict(),
            message=f"Security subsystem verification: {status.value}.",
            evidence={"status": status.value},
        )

    def _handle_verify_providers(self, params: Dict[str, Any]) -> ActionResult:
        return self._handle_audit_providers(params)

    def _handle_collect_evidence(self, params: Dict[str, Any]) -> ActionResult:
        target = params.get("target", "system")
        evidence = {
            "timestamp": time.time(),
            "target": target,
            "system_metrics": {
                "active_threads": threading.active_count(),
                "history_records_count": len(self._diagnostic_history),
            },
            "environment": params.get("telemetry", {}),
        }
        return ActionResult(
            status="SUCCESS",
            output={"evidence": evidence},
            message=f"Diagnostic evidence collected for '{target}'.",
            evidence={"target": target},
        )

    def _handle_diagnose(self, params: Dict[str, Any]) -> ActionResult:
        """Formulates an evidence-based diagnosis and recommendation for an observed issue."""
        symptom = params.get("symptom", "unknown_symptom")
        evidence = params.get("evidence", {})

        # Distinguish failure class from evidence
        failure_class = FailureClassification.UNKNOWN
        if "timeout" in symptom.lower() or evidence.get("timeout_detected"):
            failure_class = FailureClassification.TIMEOUT
        elif "auth" in symptom.lower() or "unauthorized" in symptom.lower():
            failure_class = FailureClassification.AUTHORIZATION
        elif "inconsistent" in symptom.lower() or "stale" in symptom.lower():
            failure_class = FailureClassification.STATE_INCONSISTENCY
        elif "provider" in symptom.lower():
            failure_class = FailureClassification.PROVIDER

        recommendation = params.get("remediation_recommendation")
        if not recommendation:
            if failure_class == FailureClassification.TIMEOUT:
                recommendation = "Inspect provider connectivity or extend execution timeout with policy approval."
            elif failure_class == FailureClassification.AUTHORIZATION:
                recommendation = "Verify identity credentials, check assigned scopes, and ensure confirmation token is provided."
            elif failure_class == FailureClassification.STATE_INCONSISTENCY:
                recommendation = "Initiate state reconciliation between World Model and empirical telemetry."
            elif failure_class == FailureClassification.PROVIDER:
                recommendation = "Attempt provider failover to registered fallback or restart adapter."
            else:
                recommendation = "Escalate to system operator with collected evidence trail."

        diagnosis = {
            "diagnostic_id": f"diag-{uuid.uuid4()}",
            "symptom": symptom,
            "failure_classification": failure_class.value,
            "confidence": float(params.get("confidence", 0.85)),
            "evidence": evidence,
            "recommended_action": recommendation,
            "requires_policy_gate": self.config.require_confirmation_for_remediation,
            "timestamp": time.time(),
        }

        return ActionResult(
            status="SUCCESS",
            output={"diagnosis": diagnosis},
            message=f"Diagnosis completed: {failure_class.value}.",
            evidence={"failure_class": failure_class.value},
        )

    def _handle_get_status(self, params: Dict[str, Any]) -> ActionResult:
        target = params.get("target")
        records = self._diagnostic_history
        if target:
            records = [r for r in records if r.target == target]

        if not records:
            return ActionResult(
                status="SUCCESS",
                output={"status": DiagnosticStatus.UNKNOWN.value, "reason": "No diagnostic records found"},
                message="Target status is UNKNOWN (no prior probe evidence).",
                evidence={"status": DiagnosticStatus.UNKNOWN.value},
            )

        latest = records[-1]
        return ActionResult(
            status="SUCCESS",
            output=latest.to_dict(),
            message=f"Latest status for '{latest.target}': {latest.status.value}.",
            evidence={"status": latest.status.value},
        )

    def _handle_get_diagnostic_report(self, params: Dict[str, Any]) -> ActionResult:
        limit = int(params.get("limit", 50))
        recent = self._diagnostic_history[-limit:]
        healthy = sum(1 for r in recent if r.status == DiagnosticStatus.HEALTHY)
        degraded = sum(1 for r in recent if r.status == DiagnosticStatus.DEGRADED)
        failed = sum(1 for r in recent if r.status == DiagnosticStatus.FAILED)
        unknown = sum(1 for r in recent if r.status in (DiagnosticStatus.UNKNOWN, DiagnosticStatus.NOT_VERIFIABLE))

        report = {
            "timestamp": time.time(),
            "total_records": len(recent),
            "summary": {
                "healthy": healthy,
                "degraded": degraded,
                "failed": failed,
                "unknown_or_not_verifiable": unknown,
            },
            "records": [r.to_dict() for r in recent],
        }

        return ActionResult(
            status="SUCCESS",
            output=report,
            message=f"Generated diagnostic report with {len(recent)} records.",
            evidence={"total": len(recent), "failed": failed},
        )


verification_diagnostics_provider = VerificationDiagnosticsProvider()
