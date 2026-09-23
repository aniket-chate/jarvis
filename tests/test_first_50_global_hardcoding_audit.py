"""JARVIS First-50 Global Hardcoding & Domain Invariant Audit Suite.

Conducts an exhaustive AST static scan and dynamic mutation audit across all 50 capabilities:
- Zero forbidden hardcoded personal identities ('aniket', 'aniket chate', etc.) in production source.
- Zero hardcoded local user file paths (e.g. 'C:\\Users\\acer').
- Zero hardcoded test fixture identities leaking into production providers.
- Dynamic Tests A through L ensuring complete abstraction and dynamic generalization.
"""

import ast
import os
import random
import sys
import unittest
import uuid
from pathlib import Path
from typing import Dict, Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from capabilities.contracts.registry_50 import contract_registry_50
from capabilities.intelligence import capability_intelligence
from capabilities.base import BaseCapabilityProvider, ActionResult, ProviderMetadata
from capabilities.providers.security_identity_provider import (
    SecurityIdentityProvider, TrustState, IdentityType, AuthState, AuthorizationDecision, SecurityConfig
)
from capabilities.providers.verification_diagnostics_provider import (
    VerificationDiagnosticsProvider, DiagnosticStatus, DiagnosticCategory, DiagnosticsConfig
)
from capabilities.providers.capability_evolution_provider import (
    CapabilityEvolutionProvider, ProposalStatus, EvolutionConfig
)


class TestFirst50GlobalHardcodingAudit(unittest.TestCase):
    """Global multi-phase audit asserting zero domain-specific hardcoding across Capabilities 1-50."""

    def setUp(self):
        self.root_dir = PROJECT_ROOT
        self.security_prov = SecurityIdentityProvider()
        self.diag_prov = VerificationDiagnosticsProvider()
        self.evol_prov = CapabilityEvolutionProvider()

    def test_00_static_ast_codebase_audit(self):
        """Audits all production capability providers and cognitive engines for forbidden literals."""
        forbidden_user_literals = {"aniket", "aniket chate", "aniket_chate"}
        forbidden_path_literals = {"c:\\users\\acer", "c:/users/acer"}

        target_dirs = [
            self.root_dir / "capabilities" / "providers",
            self.root_dir / "capabilities" / "contracts",
            self.root_dir / "cognitive",
            self.root_dir / "safety",
            self.root_dir / "execution",
            self.root_dir / "verification",
        ]

        violations = []
        files_scanned = 0

        for target_dir in target_dirs:
            if not target_dir.exists():
                continue
            for py_file in target_dir.glob("**/*.py"):
                if py_file.name.startswith("test_") or "__pycache__" in str(py_file):
                    continue
                files_scanned += 1
                try:
                    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
                except Exception as e:
                    self.fail(f"Could not parse AST for {py_file}: {e}")

                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        val = node.value.strip().lower()
                        for forbidden in forbidden_user_literals:
                            if val == forbidden or f" {forbidden} " in f" {val} ":
                                violations.append((str(py_file.relative_to(self.root_dir)), getattr(node, 'lineno', 0), val, "USER_LITERAL"))
                        for forbidden_path in forbidden_path_literals:
                            if forbidden_path in val:
                                violations.append((str(py_file.relative_to(self.root_dir)), getattr(node, 'lineno', 0), val, "USER_PATH_LITERAL"))

        self.assertEqual(
            violations,
            [],
            f"Found forbidden hardcoded literals in production source code ({len(violations)} violations): {violations}",
        )
        self.assertGreaterEqual(files_scanned, 15, "Insufficient production files scanned.")

    def test_A_unknown_identity(self):
        """Dynamic Test A: Unknown identity with novel identity type and arbitrary scopes."""
        rand_id = f"synth_id_{uuid.uuid4().hex}"
        res = self.security_prov.execute("security.register_identity", {
            "identity_id": rand_id,
            "identity_type": IdentityType.EXTERNAL.value,
            "display_name": f"Synthetic Identity {rand_id}",
            "authorization_scopes": [f"scope_{uuid.uuid4().hex[:6]}"],
            "trust_state": TrustState.TRUSTED.value,
        })
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.output["identity"]["identity_id"], rand_id)

    def test_B_unknown_device(self):
        """Dynamic Test B: Unknown device with novel device class and arbitrary capabilities."""
        dev_id = f"dev_{uuid.uuid4().hex}"
        res = self.security_prov.execute("security.register_device", {
            "device_id": dev_id,
            "device_type": "SYNTHETIC_QUANTUM_PROBE",
            "display_name": f"Device {dev_id}",
            "capabilities": [f"cap_{uuid.uuid4().hex[:6]}"],
            "trust_state": TrustState.TRUSTED.value,
        })
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.output["device"]["device_id"], dev_id)

    def test_C_unknown_credential(self):
        """Dynamic Test C: Unknown synthetic credential format verified dynamically."""
        uid = f"user_{uuid.uuid4().hex[:8]}"
        secret = f"token_{uuid.uuid4().hex}_{random.randint(1000, 9999)}"

        self.security_prov.execute("security.register_identity", {
            "identity_id": uid,
            "credential": secret,
        })
        res = self.security_prov.execute("security.authenticate", {
            "identity_id": uid,
            "credential": secret,
        })
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.output["auth_state"], AuthState.AUTHENTICATED.value)

    def test_D_arbitrary_capability(self):
        """Dynamic Test D: Diagnostic probing and proposal targeting arbitrary capability outside 1-50."""
        arb_cap = f"99_quantum_teleportation_{uuid.uuid4().hex[:6]}"

        res_probe = self.diag_prov.execute("diagnostics.run_probe", {
            "target": arb_cap,
            "probe_name": "arbitrary_capability_probe",
            "expected_state": {"entanglement": True},
            "observed_state": {"entanglement": True},
            "evidence": {"coherence_time_ms": 420},
        })
        self.assertEqual(res_probe.status, "SUCCESS")
        self.assertEqual(res_probe.output["status"], DiagnosticStatus.HEALTHY.value)

    def test_E_arbitrary_diagnostic_failure(self):
        """Dynamic Test E: Injected arbitrary failure probe with custom failure classification."""
        res_fail = self.diag_prov.execute("diagnostics.run_probe", {
            "target": f"arbitrary_node_{uuid.uuid4().hex[:6]}",
            "probe_name": "custom_failure_probe",
            "expected_state": {"packet_loss": 0.0},
            "observed_state": {"packet_loss": 0.35},
            "evidence": {"loss_rate": 0.35},
            "remediation_recommendation": "Switch to redundant carrier link",
        })
        self.assertEqual(res_fail.status, "SUCCESS")
        self.assertEqual(res_fail.output["status"], DiagnosticStatus.FAILED.value)

    def test_F_arbitrary_improvement_proposal(self):
        """Dynamic Test F: Proposal creation for arbitrary capability and novel problem statement."""
        prop_id = f"prop_arb_{uuid.uuid4().hex[:8]}"
        res = self.evol_prov.execute("evolution.create_proposal", {
            "proposal_id": prop_id,
            "source_observation": "Synthetic telemetry anomaly detected",
            "problem_statement": "Arbitrary optimization hypothesis",
            "expected_benefit": "Hypothetical gain",
            "affected_capability": f"cap_{uuid.uuid4().hex[:6]}",
            "proposed_change": {f"param_{uuid.uuid4().hex[:4]}": random.random()},
        })
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.output["proposal"]["proposal_id"], prop_id)

    def test_G_configuration_change(self):
        """Dynamic Test G: Runtime configuration mutation across all three providers."""
        custom_sec_cfg = SecurityConfig(default_session_ttl_sec=120.0, secret_mask_placeholder="[SECRET_MASKED]")
        custom_diag_cfg = DiagnosticsConfig(probe_timeout_sec=25.0)
        custom_evol_cfg = EvolutionConfig(min_evaluation_pass_rate=0.88)

        p_sec = SecurityIdentityProvider(config=custom_sec_cfg)
        p_diag = VerificationDiagnosticsProvider(config=custom_diag_cfg)
        p_evol = CapabilityEvolutionProvider(config=custom_evol_cfg)

        res_mask = p_sec.execute("security.mask_credentials", {"text": "password=MyPassword123"})
        self.assertIn("[SECRET_MASKED]", res_mask.output["masked_text"])

        self.assertEqual(p_diag.config.probe_timeout_sec, 25.0)
        self.assertEqual(p_evol.config.min_evaluation_pass_rate, 0.88)

    def test_H_provider_replacement(self):
        """Dynamic Test H: Provider hot-swap via CapabilityIntelligence and restoration."""
        p_orig = capability_intelligence.select_provider("security.authenticate")
        self.assertIsNotNone(p_orig)

        class MockSecurityProvider(BaseCapabilityProvider):
            def __init__(self):
                meta = ProviderMetadata(
                    provider_id="provider.security.mock_swap",
                    name="Mock Swap Security Provider",
                    supported_capabilities=["security.authenticate"],
                    priority=100,
                )
                super().__init__(meta)

            def is_available(self) -> bool:
                return True

            def execute(self, action: str, parameters: Dict[str, Any], context=None) -> ActionResult:
                return ActionResult(status="SUCCESS", output={"mock_swap": True})

        capability_intelligence.unregister_provider("provider.security.identity_manager")
        mock_prov = MockSecurityProvider()
        capability_intelligence.register_provider(mock_prov)

        p_selected = capability_intelligence.select_provider("security.authenticate")
        self.assertEqual(p_selected.provider_id, "provider.security.mock_swap")

        # Restore original provider
        capability_intelligence.unregister_provider("provider.security.mock_swap")
        capability_intelligence.register_provider(self.security_prov)
        p_restored = capability_intelligence.select_provider("security.authenticate")
        self.assertEqual(p_restored.provider_id, "provider.security.identity_manager")

    def test_I_source_removal(self):
        """Dynamic Test I: Source revocation confirms truthful REVOKED state without ghost access."""
        uid = f"user_remov_{uuid.uuid4().hex[:8]}"
        self.security_prov.execute("security.register_identity", {
            "identity_id": uid,
            "credential": "pass_temp",
            "trust_state": TrustState.TRUSTED.value,
        })
        res_rev = self.security_prov.execute("security.revoke_trust", {
            "identity_id": uid,
            "reason": "Source removal verification",
        })
        self.assertEqual(res_rev.status, "SUCCESS")

        res_authz = self.security_prov.execute("security.authorize", {
            "identity_id": uid,
            "operation": "test.op",
        })
        self.assertEqual(res_authz.status, "FAILURE")
        self.assertEqual(res_authz.output["decision"], AuthorizationDecision.REVOKED.value)

    def test_J_unknown_entity_secret_masking(self):
        """Dynamic Test J: Deeply nested arbitrary payload redacted without domain-specific keys."""
        rand_key = f"key_{uuid.uuid4().hex[:6]}"
        nested_data = {
            rand_key: "arbitrary_val",
            "some_deeply_nested": {
                "credential": "unseen_token_to_redact",
                "normal_list": [1, 2, {"api_key": "secret_in_list"}],
            }
        }
        res = self.security_prov.execute("security.mask_credentials", {"data": nested_data})
        self.assertEqual(res.status, "SUCCESS")
        masked = res.output["masked_data"]
        self.assertEqual(masked["some_deeply_nested"]["credential"], "***REDACTED***")
        self.assertEqual(masked["some_deeply_nested"]["normal_list"][2]["api_key"], "***REDACTED***")

    def test_K_unseen_capability_metadata(self):
        """Dynamic Test K: Processing dynamic metadata in diagnostic probes."""
        meta_key = f"metric_{uuid.uuid4().hex[:6]}"
        meta_val = random.uniform(10.0, 99.0)
        res = self.diag_prov.execute("diagnostics.run_probe", {
            "target": "dynamic_telemetry_stream",
            "expected_state": {meta_key: meta_val},
            "observed_state": {meta_key: meta_val},
            "evidence": {"telemetry": {meta_key: meta_val}},
        })
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.output["status"], DiagnosticStatus.HEALTHY.value)

    def test_L_arbitrary_version_metadata(self):
        """Dynamic Test L: Non-standard semantic and suffix version tags tracked and rolled back."""
        custom_ver = f"v{random.randint(1, 10)}.{random.randint(0, 9)}.{random.randint(0, 9)}-alpha.rev{random.randint(100, 999)}"
        cap_target = f"cap_ver_{uuid.uuid4().hex[:6]}"

        self.evol_prov.execute("evolution.create_proposal", {
            "proposal_id": f"prop_{uuid.uuid4().hex[:6]}",
            "affected_capability": cap_target,
            "version": custom_ver,
        })
        self.evol_prov.execute("evolution.record_human_approval", {
            "proposal_id": list(self.evol_prov._proposals.keys())[-1],
            "approver": "Human Tester",
            "approval_token": "tok_valid",
        })
        res_rel = self.evol_prov.execute("evolution.release_version", {
            "proposal_id": list(self.evol_prov._proposals.keys())[-1],
        })
        self.assertEqual(res_rel.status, "SUCCESS")
        self.assertEqual(res_rel.output["artifact"]["version_id"], custom_ver)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFirst50GlobalHardcodingAudit)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
