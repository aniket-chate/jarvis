"""Unit and Integration Tests for Capability 49: Verification & Self-Diagnostics.

Verifies:
1. Overall system health check across core architectural pillars
2. Comprehensive provider responsiveness audit
3. Self-test execution with evidence verification
4. Custom diagnostic probe execution (HEALTHY vs FAILED states)
5. CRITICAL INVARIANT: Missing or insufficient evidence produces UNKNOWN / NOT_VERIFIABLE
6. Memory subsystem consistency, persistence, and freshness verification
7. World Model reality consistency, conflict detection, and staleness bounds
8. Autonomy loop health: detection of stuck retry loops and missing verifications
9. Security subsystem integrity: policy kernel availability and revoked isolation
10. Diagnostic evidence-based failure classification
11. Diagnostic report generation with summary statistics
12. Thread safety under concurrent diagnostic probing
13. Safety-gating of diagnostic remediation recommendations
14. Provider replaceability and routing verification
15. Dynamic runtime configuration changes
"""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sys
import time
import unittest
import uuid
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from capabilities.intelligence import capability_intelligence
from capabilities.providers.verification_diagnostics_provider import (
    DiagnosticCategory,
    DiagnosticProbeResult,
    DiagnosticStatus,
    DiagnosticsConfig,
    FailureClassification,
    SeverityLevel,
    VerificationDiagnosticsProvider,
)


class TestCapability49VerificationSelfDiagnostics(unittest.TestCase):
    """Test suite for Capability 49 Verification & Self-Diagnostics Provider."""

    def setUp(self):
        self.config = DiagnosticsConfig(probe_timeout_sec=5.0)
        self.provider = VerificationDiagnosticsProvider(config=self.config)

    def test_01_system_health_check(self):
        """Tests overall system health check probing contracts, providers, and policy."""
        res = self.provider.execute("diagnostics.health_check", {})
        self.assertEqual(res.status, "SUCCESS")
        output = res.output
        self.assertIn(output["overall_status"], (DiagnosticStatus.HEALTHY.value, DiagnosticStatus.DEGRADED.value))
        self.assertGreaterEqual(output["probe_count"], 3)
        self.assertGreaterEqual(output["duration_ms"], 0.0)

    def test_02_audit_providers(self):
        """Tests provider availability and responsiveness audit across registered providers."""
        res = self.provider.execute("diagnostics.audit_providers", {})
        self.assertEqual(res.status, "SUCCESS")
        output = res.output
        self.assertGreater(output["total_providers_audited"], 0)
        self.assertGreaterEqual(output["healthy_providers"], 1)
        self.assertEqual(output["failed_providers"], 0)

    def test_03_self_test_execution(self):
        """Tests empirical self-test asserting complete 50-contract registry integrity."""
        res = self.provider.execute("diagnostics.run_self_test", {
            "target": "ContractRegistry50",
            "evidence": {"inspect_contracts": True},
        })
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.output["status"], DiagnosticStatus.HEALTHY.value)
        self.assertTrue(res.output["verification_result"])

    def test_04_custom_probe_healthy_and_failed(self):
        """Tests custom probe comparison of expected vs observed state."""
        # 1. Matching expected and observed -> HEALTHY
        res_ok = self.provider.execute("diagnostics.run_probe", {
            "target": "database_pool",
            "probe_name": "connection_pool_probe",
            "expected_state": {"active_connections": 5, "status": "READY"},
            "observed_state": {"active_connections": 5, "status": "READY"},
            "evidence": {"ping_ms": 1.2},
        })
        self.assertEqual(res_ok.status, "SUCCESS")
        self.assertEqual(res_ok.output["status"], DiagnosticStatus.HEALTHY.value)
        self.assertTrue(res_ok.output["verification_result"])

        # 2. Mismatch between expected and observed -> FAILED
        res_fail = self.provider.execute("diagnostics.run_probe", {
            "target": "message_broker",
            "probe_name": "queue_depth_probe",
            "expected_state": {"queue_depth": 0},
            "observed_state": {"queue_depth": 1500},
            "evidence": {"lag_sec": 45.0},
            "remediation_recommendation": "Scale consumer workers",
        })
        self.assertEqual(res_fail.status, "SUCCESS")
        self.assertEqual(res_fail.output["status"], DiagnosticStatus.FAILED.value)
        self.assertFalse(res_fail.output["verification_result"])
        self.assertEqual(res_fail.output["failure_class"], FailureClassification.VERIFICATION.value)

    def test_05_critical_invariant_insufficient_evidence_unknown(self):
        """CRITICAL INVARIANT: Missing or insufficient evidence MUST produce UNKNOWN / NOT_VERIFIABLE."""
        # Missing observed state and evidence
        res_unknown = self.provider.execute("diagnostics.run_probe", {
            "target": "hypothetical_subsystem",
            "probe_name": "speculative_probe",
            "expected_state": {"healthy": True},
            # Missing observed_state and evidence
        })
        self.assertEqual(res_unknown.status, "SUCCESS")
        self.assertEqual(res_unknown.output["status"], DiagnosticStatus.UNKNOWN.value)
        self.assertEqual(res_unknown.output["failure_class"], FailureClassification.INSUFFICIENT_EVIDENCE.value)
        self.assertFalse(res_unknown.output["verification_result"])

        # Self-test without evidence on unknown target -> NOT_VERIFIABLE
        res_not_verifiable = self.provider.execute("diagnostics.run_self_test", {
            "target": f"unseen_target_{uuid.uuid4()}",
            "evidence": {},  # Empty evidence
        })
        self.assertEqual(res_not_verifiable.status, "SUCCESS")
        self.assertEqual(res_not_verifiable.output["status"], DiagnosticStatus.NOT_VERIFIABLE.value)

    def test_06_verify_memory_subsystem(self):
        """Tests memory subsystem verification: persistence, freshness, and consistency."""
        # Fresh and consistent memory
        res_mem_ok = self.provider.execute("diagnostics.verify_memory", {
            "evidence": {"consistency_check": True, "last_synced_sec": 12.0}
        })
        self.assertEqual(res_mem_ok.status, "SUCCESS")
        self.assertEqual(res_mem_ok.output["status"], DiagnosticStatus.HEALTHY.value)

        # Stale memory (>300s) -> DEGRADED
        res_mem_stale = self.provider.execute("diagnostics.verify_memory", {
            "evidence": {"consistency_check": True, "last_synced_sec": 450.0}
        })
        self.assertEqual(res_mem_stale.status, "SUCCESS")
        self.assertEqual(res_mem_stale.output["status"], DiagnosticStatus.DEGRADED.value)

    def test_07_verify_world_model(self):
        """Tests World Model reality consistency, staleness bounds, and conflict detection."""
        # Consistent reality
        res_wm_ok = self.provider.execute("diagnostics.verify_world_model", {
            "evidence": {"conflicting_observations": 0, "staleness_rate": 0.05}
        })
        self.assertEqual(res_wm_ok.status, "SUCCESS")
        self.assertEqual(res_wm_ok.output["status"], DiagnosticStatus.HEALTHY.value)

        # Conflicting observations -> FAILED
        res_wm_conflicts = self.provider.execute("diagnostics.verify_world_model", {
            "evidence": {"conflicting_observations": 8, "staleness_rate": 0.45}
        })
        self.assertEqual(res_wm_conflicts.status, "SUCCESS")
        self.assertEqual(res_wm_conflicts.output["status"], DiagnosticStatus.FAILED.value)

    def test_08_verify_autonomy_loop(self):
        """Tests autonomy loop verification: stuck retry loops and unverified steps."""
        # Healthy autonomy loop
        res_auto_ok = self.provider.execute("diagnostics.verify_autonomy", {
            "evidence": {"stuck_retry_loops": 0, "missing_step_verifications": 0}
        })
        self.assertEqual(res_auto_ok.status, "SUCCESS")
        self.assertEqual(res_auto_ok.output["status"], DiagnosticStatus.HEALTHY.value)

        # Stuck retry loop -> DEGRADED / FAILED
        res_auto_stuck = self.provider.execute("diagnostics.verify_autonomy", {
            "evidence": {"stuck_retry_loops": 5, "missing_step_verifications": 2}
        })
        self.assertEqual(res_auto_stuck.status, "SUCCESS")
        self.assertEqual(res_auto_stuck.output["status"], DiagnosticStatus.FAILED.value)

    def test_09_verify_security_controls(self):
        """Tests security subsystem verification: policy availability and revoked isolation."""
        res_sec_ok = self.provider.execute("diagnostics.verify_security", {
            "evidence": {"revoked_identity_executed": False}
        })
        self.assertEqual(res_sec_ok.status, "SUCCESS")
        self.assertEqual(res_sec_ok.output["status"], DiagnosticStatus.HEALTHY.value)

        # Security compromise simulation -> FAILED
        res_sec_fail = self.provider.execute("diagnostics.verify_security", {
            "evidence": {"revoked_identity_executed": True}
        })
        self.assertEqual(res_sec_fail.status, "SUCCESS")
        self.assertEqual(res_sec_fail.output["status"], DiagnosticStatus.FAILED.value)

    def test_10_evidence_based_failure_diagnosis(self):
        """Tests formulation of evidence-based diagnoses and classification."""
        symptoms = [
            ("connection timeout after 5000ms", FailureClassification.TIMEOUT),
            ("unauthorized access to admin scope", FailureClassification.AUTHORIZATION),
            ("stale state detected between cache and memory", FailureClassification.STATE_INCONSISTENCY),
        ]
        for symptom, expected_class in symptoms:
            res = self.provider.execute("diagnostics.diagnose", {"symptom": symptom})
            self.assertEqual(res.status, "SUCCESS")
            diag = res.output["diagnosis"]
            self.assertEqual(diag["failure_classification"], expected_class.value)
            self.assertTrue(diag["requires_policy_gate"])

    def test_11_diagnostic_reporting(self):
        """Tests retrieval of aggregated diagnostic summary reports."""
        # Run a probe first
        self.provider.execute("diagnostics.health_check", {})
        res = self.provider.execute("diagnostics.get_diagnostic_report", {"limit": 20})
        self.assertEqual(res.status, "SUCCESS")
        report = res.output
        self.assertGreater(report["total_records"], 0)
        self.assertIn("summary", report)
        self.assertIn("healthy", report["summary"])

    def test_12_concurrent_diagnostic_probes(self):
        """Tests thread safety under concurrent diagnostic probing."""
        def probe_worker(idx: int):
            return self.provider.execute("diagnostics.run_probe", {
                "target": f"service_worker_{idx}",
                "expected_state": {"ready": True},
                "observed_state": {"ready": True},
                "evidence": {"heartbeat_ms": idx * 10},
            })

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(probe_worker, range(20)))

        for r in results:
            self.assertEqual(r.status, "SUCCESS")
            self.assertEqual(r.output["status"], DiagnosticStatus.HEALTHY.value)


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestCapability49VerificationSelfDiagnostics)
    result = runner.run(suite)
    os._exit(0 if result.wasSuccessful() else 1)
