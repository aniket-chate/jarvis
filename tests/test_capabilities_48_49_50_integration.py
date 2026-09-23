"""Cross-Capability Integration Suite for Batch 6 (Capabilities 48, 49, 50).

Verifies multi-capability workflows:
1. Pipeline 1: Security Identity Registration -> Authentication -> Session -> Authorization -> Audit
2. Pipeline 2: Security Telemetry -> Self-Diagnostic Integrity Probe -> Reality Verification
3. Pipeline 3: Diagnostic Gap Detection -> Evolution Proposal -> Sandboxing -> Evaluation
4. Pipeline 4: Complete Governance Loop: Proposal -> Sandbox -> Evaluation -> Rejection of Self-Approval -> Human Approval -> Version Release -> Diagnostic Health Check -> Controlled Rollback
"""

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

from capabilities.base import ActionResult
from capabilities.intelligence import capability_intelligence
from capabilities.providers.security_identity_provider import (
    AuthState,
    AuthorizationDecision,
    SecurityIdentityProvider,
    TrustState,
)
from capabilities.providers.verification_diagnostics_provider import (
    DiagnosticStatus,
    VerificationDiagnosticsProvider,
)
from capabilities.providers.capability_evolution_provider import (
    CapabilityEvolutionProvider,
    ProposalStatus,
)


class TestCapabilities484950Integration(unittest.TestCase):
    """Integration test suite for Capabilities 48, 49, and 50."""

    def setUp(self):
        self.security_prov = SecurityIdentityProvider()
        self.diag_prov = VerificationDiagnosticsProvider()
        self.evol_prov = CapabilityEvolutionProvider()

    def test_01_security_identity_lifecycle_pipeline(self):
        """Pipeline 1: Register -> Authenticate -> Session -> Authorize -> Audit verification."""
        user_id = f"integ_user_{uuid.uuid4().hex[:8]}"

        # 1. Register identity
        res_reg = self.security_prov.execute("security.register_identity", {
            "identity_id": user_id,
            "display_name": "Integration User",
            "authorization_scopes": ["data.read", "analytics.execute"],
            "credential": "secure_integ_password",
            "trust_state": TrustState.TRUSTED.value,
        })
        self.assertEqual(res_reg.status, "SUCCESS")

        # 2. Authenticate
        res_auth = self.security_prov.execute("security.authenticate", {
            "identity_id": user_id,
            "credential": "secure_integ_password",
        })
        self.assertEqual(res_auth.status, "SUCCESS")
        session_id = res_auth.output["session_id"]

        # 3. Authorize with scope
        res_authz = self.security_prov.execute("security.authorize", {
            "identity_id": user_id,
            "operation": "data.read",
            "required_scope": "data.read",
        })
        self.assertEqual(res_authz.status, "SUCCESS")
        self.assertEqual(res_authz.output["decision"], AuthorizationDecision.ALLOW.value)

        # 4. Check audit trail
        res_audit = self.security_prov.execute("security.query_audit_events", {
            "identity_id": user_id,
            "limit": 5,
        })
        self.assertEqual(res_audit.status, "SUCCESS")
        self.assertGreaterEqual(res_audit.output["count"], 2)

    def test_02_security_telemetry_to_diagnostic_probe(self):
        """Pipeline 2: Security activity verified by diagnostic subsystem probe."""
        # Check security control integrity via diagnostics
        res_probe = self.diag_prov.execute("diagnostics.verify_security", {
            "evidence": {"revoked_identity_executed": False}
        })
        self.assertEqual(res_probe.status, "SUCCESS")
        self.assertEqual(res_probe.output["status"], DiagnosticStatus.HEALTHY.value)

        # Query diagnostics report
        res_report = self.diag_prov.execute("diagnostics.get_diagnostic_report", {"limit": 10})
        self.assertEqual(res_report.status, "SUCCESS")
        self.assertGreater(res_report.output["total_records"], 0)

    def test_03_diagnostic_gap_detection_to_evolution_proposal(self):
        """Pipeline 3: Diagnostics detects gap -> Evolution creates & sandboxes proposal."""
        # 1. Detect gap
        res_gaps = self.evol_prov.execute("evolution.detect_gaps", {
            "target_capability": "38_device_capability_projection",
            "telemetry": {"latency_ms": 78.5, "error_rate": 0.08},
        })
        self.assertEqual(res_gaps.status, "SUCCESS")
        self.assertGreater(res_gaps.output["gap_count"], 0)

        # 2. Formulate proposal based on detected gap
        prop_id = f"prop_integ_{uuid.uuid4().hex[:8]}"
        res_prop = self.evol_prov.execute("evolution.create_proposal", {
            "proposal_id": prop_id,
            "source_observation": "Diagnostic detected 78.5ms latency in projection",
            "problem_statement": "Projection payload requires pre-serialization",
            "expected_benefit": "Latency reduced below 20ms",
            "affected_capability": "38_device_capability_projection",
            "affected_providers": ["provider.mesh.projection_engine"],
            "proposed_change": {"pre_serialize": True},
        })
        self.assertEqual(res_prop.status, "SUCCESS")

        # 3. Sandbox proposal
        res_sand = self.evol_prov.execute("evolution.sandbox_proposal", {"proposal_id": prop_id})
        self.assertEqual(res_sand.status, "SUCCESS")
        self.assertEqual(res_sand.output["status"], ProposalStatus.SANDBOXED.value)

    def test_04_full_governance_evolution_lifecycle(self):
        """Pipeline 4: Proposal -> Sandbox -> Evaluation -> Self-Approval Rejection -> Human Approval -> Release -> Rollback."""
        prop_id = f"prop_gov_{uuid.uuid4().hex[:8]}"
        cap_id = "cap_governance_target"

        # 1. Create & Sandbox
        self.evol_prov.execute("evolution.create_proposal", {
            "proposal_id": prop_id,
            "affected_capability": cap_id,
            "version": "v2.0.0",
        })
        self.evol_prov.execute("evolution.sandbox_proposal", {"proposal_id": prop_id})

        # 2. Evaluate
        res_eval = self.evol_prov.execute("evolution.evaluate_proposal", {
            "proposal_id": prop_id,
            "pass_rate": 0.99,
            "security_tests_passed": True,
        })
        self.assertEqual(res_eval.status, "SUCCESS")

        # 3. Submit for approval
        res_sub = self.evol_prov.execute("evolution.submit_for_approval", {"proposal_id": prop_id})
        self.assertEqual(res_sub.status, "WAITING_EXTERNAL")

        # 4. Attempt Self-Approval -> REJECTED
        res_bad_app = self.evol_prov.execute("evolution.record_human_approval", {
            "proposal_id": prop_id,
            "approver": "JARVIS_AI_AGENT",
            "approval_token": "mock_tok",
        })
        self.assertEqual(res_bad_app.status, "FAILURE")
        self.assertEqual(res_bad_app.output.get("error"), "SELF_APPROVAL_FORBIDDEN")

        # 5. Human Approval -> APPROVED
        res_human_app = self.evol_prov.execute("evolution.record_human_approval", {
            "proposal_id": prop_id,
            "approver": "Dr. Aris Thorne (Human Lead)",
            "approval_token": "auth_tok_human_verified_2026",
        })
        self.assertEqual(res_human_app.status, "SUCCESS")
        self.assertEqual(res_human_app.output["status"], ProposalStatus.APPROVED.value)

        # 6. Release versioned artifact
        res_rel = self.evol_prov.execute("evolution.release_version", {"proposal_id": prop_id})
        self.assertEqual(res_rel.status, "SUCCESS")
        self.assertEqual(res_rel.output["status"], ProposalStatus.RELEASED.value)

        # 7. Diagnostic verification of released capability
        res_diag = self.diag_prov.execute("diagnostics.run_probe", {
            "target": cap_id,
            "probe_name": "post_release_canary_probe",
            "expected_state": {"active_version": "v2.0.0"},
            "observed_state": {"active_version": "v2.0.0"},
            "evidence": {"version": "v2.0.0", "canary_traffic": "100%"},
        })
        self.assertEqual(res_diag.status, "SUCCESS")
        self.assertEqual(res_diag.output["status"], DiagnosticStatus.HEALTHY.value)

        # 8. Controlled Rollback
        # Simulate an initial version first so rollback target exists
        self.evol_prov._versions["v1.0.0"] = type("MockArtifact", (), {
            "version_id": "v1.0.0", "proposal_id": "prop_old", "rollback_target": None, "is_active": False,
            "affected_capability": cap_id, "to_dict": lambda self: {}
        })()
        self.evol_prov._versions[res_rel.output["artifact"]["version_id"]].rollback_target = "v1.0.0"

        res_roll = self.evol_prov.execute("evolution.rollback_version", {
            "capability": cap_id,
            "reason": "Canary regression simulation",
        })
        self.assertEqual(res_roll.status, "SUCCESS")
        self.assertEqual(res_roll.output["restored_version"], "v1.0.0")


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestCapabilities484950Integration)
    result = runner.run(suite)
    os._exit(0 if result.wasSuccessful() else 1)
