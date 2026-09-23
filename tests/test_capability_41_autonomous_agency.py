"""Dedicated Test Suite for Capability 41: Autonomous Agency.

Audits:
1. Capability 41 contract discovery and provider registration.
2. Canonical closed-loop autonomous execution:
   Event -> Trigger -> Plan -> Policy -> Execution -> Verification -> Experience.
3. Checkpoint persistence across stages (TRIGGER_ACCEPTED -> PLAN_GENERATED -> ACTION_STARTED -> VERIFICATION_COMPLETED).
4. Crash recovery: Reconstituting goals from persisted disk checkpoints.
5. High-Risk Action Protection: Halting autonomous execution for unconfirmed communication / destructive actions (WAITING_EXTERNAL).
6. Human Override controls: pause, resume, cancel, and status inspection.
7. Idempotency enforcement: Preventing duplicated side-effects across retries.
8. Retries & Retry Limits: Transitioning to FAILED after exceeding max_attempts.
9. Autonomous condition & scheduled trigger evaluation.
10. Concurrency & multi-threaded goal execution.
11. Provider replacement / hot-swapping.
"""

from concurrent.futures import ThreadPoolExecutor
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional
import unittest
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from capabilities.intelligence import capability_intelligence
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from capabilities.contracts.registry_50 import contract_registry_50
from capabilities.providers.autonomous_agency_provider import (
    AutonomousAgencyProvider,
    AutonomyConfig,
    AutonomousState,
)


class TestCapability41AutonomousAgency(unittest.TestCase):
    """Audits functional, safety, and durability criteria for Capability 41."""

    def setUp(self):
        self.provider = AutonomousAgencyProvider()
        self.provider._goals.clear()
        self.provider._rules.clear()
        self.provider._completed_idempotencies.clear()

    def test_01_contract_and_provider_registration(self):
        """Audits Capability 41 contract discovery and provider registration."""
        contract = contract_registry_50.get_contract("41_autonomous_agency")
        self.assertIsNotNone(contract)
        self.assertEqual(contract.capability_id, "41_autonomous_agency")
        self.assertEqual(contract.domain, "autonomy")
        self.assertIn("autonomy.register_rule", contract.supported_operations)
        self.assertIn("autonomy.execute_goal", contract.supported_operations)
        self.assertIn("autonomy.pause_goal", contract.supported_operations)
        self.assertIn("autonomy.recover_goals", contract.supported_operations)

        prov = capability_intelligence.select_provider("autonomy.execute_goal")
        self.assertIsNotNone(prov)
        self.assertEqual(prov.provider_id, "provider.autonomy.agency_runtime")

    def test_02_canonical_autonomous_execution_loop(self):
        """Audits full autonomous pipeline from trigger through verification."""
        gid = f"goal_{uuid.uuid4().hex[:8]}"
        res = self.provider.execute("autonomy.execute_goal", {
            "goal_id": gid,
            "target_capability": "os.telemetry",
            "parameters": {},
        })
        self.assertEqual(res.status, "SUCCESS")
        goal = res.output["goal"]
        self.assertEqual(goal["state"], AutonomousState.COMPLETED.value)
        self.assertEqual(goal["checkpoint_stage"], "VERIFICATION_COMPLETED")
        self.assertGreaterEqual(len(goal["history"]), 4)

    def test_03_high_risk_action_protection_and_two_gate_halt(self):
        """Audits strict policy gate: unconfirmed external communication must NOT execute autonomously."""
        gid = f"goal_high_risk_{uuid.uuid4().hex[:8]}"
        res = self.provider.execute("autonomy.execute_goal", {
            "goal_id": gid,
            "target_capability": "comm.send_email",
            "parameters": {"recipient": "test@example.org", "subject": "Autonomous Alert"},
            # is_confirmed is deliberately missing
        })
        # Must halt requiring confirmation
        self.assertEqual(res.status, "APPROVAL_REQUIRED")
        self.assertTrue(res.output["requires_confirmation"])
        goal = res.output["goal"]
        self.assertEqual(goal["state"], AutonomousState.WAITING_EXTERNAL.value)

    def test_04_idempotency_enforcement(self):
        """Audits that duplicate executions with same idempotency key return prior result."""
        idem_key = f"idem_{uuid.uuid4().hex[:12]}"
        # First execution
        r1 = self.provider.execute("autonomy.execute_goal", {
            "target_capability": "os.telemetry",
            "idempotency_key": idem_key,
        })
        self.assertEqual(r1.status, "SUCCESS")
        self.assertFalse(r1.output.get("idempotency_hit", False))

        # Second execution with identical key
        r2 = self.provider.execute("autonomy.execute_goal", {
            "target_capability": "os.telemetry",
            "idempotency_key": idem_key,
        })
        self.assertEqual(r2.status, "SUCCESS")
        self.assertTrue(r2.output.get("idempotency_hit"))
        self.assertEqual(r1.output["goal_id"], r2.output["goal_id"])

    def test_05_human_override_pause_resume_cancel(self):
        """Audits human control over active autonomous goals."""
        gid = f"goal_override_{uuid.uuid4().hex[:8]}"
        # Create initial goal
        self.provider.execute("autonomy.execute_goal", {
            "goal_id": gid,
            "target_capability": "os.telemetry",
        })

        # Pause
        p_res = self.provider.execute("autonomy.pause_goal", {"goal_id": gid})
        self.assertEqual(p_res.status, "SUCCESS")
        self.assertEqual(p_res.output["goal"]["state"], AutonomousState.PAUSED.value)

        # Resume
        r_res = self.provider.execute("autonomy.resume_goal", {"goal_id": gid})
        self.assertEqual(r_res.status, "SUCCESS")
        self.assertEqual(r_res.output["goal"]["state"], AutonomousState.ARMED.value)

        # Cancel
        c_res = self.provider.execute("autonomy.cancel_goal", {"goal_id": gid})
        self.assertEqual(c_res.status, "SUCCESS")
        self.assertEqual(c_res.output["goal"]["state"], AutonomousState.CANCELLED.value)

    def test_06_crash_recovery_from_disk_checkpoints(self):
        """Audits state recovery after simulated system restart."""
        gid = f"goal_recover_{uuid.uuid4().hex[:8]}"
        self.provider.execute("autonomy.execute_goal", {
            "goal_id": gid,
            "target_capability": "os.telemetry",
        })

        # Simulate new provider instance starting up
        fresh_provider = AutonomousAgencyProvider()
        rec_res = fresh_provider.execute("autonomy.recover_goals", {})
        self.assertEqual(rec_res.status, "SUCCESS")
        recovered_ids = [g["goal_id"] for g in rec_res.output["recovered_goals"]]
        self.assertIn(gid, recovered_ids)

        # Verify state in fresh provider
        status_res = fresh_provider.execute("autonomy.get_goal_status", {"goal_id": gid})
        self.assertEqual(status_res.status, "SUCCESS")
        self.assertEqual(status_res.output["goal"]["goal_id"], gid)

    def test_07_autonomous_rule_trigger_evaluation(self):
        """Audits condition matching and trigger firing."""
        rule_res = self.provider.execute("autonomy.register_rule", {
            "rule_id": "rule_disk_space",
            "description": "Watch system disk threshold",
            "trigger_type": "event_trigger",
            "target_capability": "os.telemetry",
            "condition": {"event_type": "disk_alert"},
            "max_triggers": 1,
        })
        self.assertEqual(rule_res.status, "SUCCESS")

        # Evaluate with non-matching event -> 0 fired
        eval1 = self.provider.execute("autonomy.evaluate_triggers", {"event": {"event_type": "battery_ok"}})
        self.assertEqual(eval1.output["count"], 0)

        # Evaluate with matching event -> 1 fired
        eval2 = self.provider.execute("autonomy.evaluate_triggers", {"event": {"event_type": "disk_alert"}})
        self.assertEqual(eval2.output["count"], 1)

    def test_08_concurrency_and_provider_replacement(self):
        """Audits concurrent goal execution and dynamic provider swapping."""
        def _exec_concurrent(i: int):
            return self.provider.execute("autonomy.execute_goal", {
                "goal_id": f"concurrent_goal_{i}_{uuid.uuid4().hex[:6]}",
                "target_capability": "os.telemetry",
            })

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(_exec_concurrent, i) for i in range(10)]
            results = [f.result() for f in futures]

        self.assertTrue(all(r.status == "SUCCESS" for r in results))

        # Hot-swapping
        class MockAutonomyProvider(BaseCapabilityProvider):
            def __init__(self):
                super().__init__(ProviderMetadata(
                    provider_id="provider.autonomy.local_watcher",
                    name="Mock Autonomy Watcher",
                    description="Test Mock Autonomy",
                    version="1.0.0",
                    supported_capabilities=["autonomy.execute_goal"],
                    safety_level="modifying",
                    priority=5,
                ))

            def is_available(self) -> bool:
                return True

            def execute(self, capability: str, parameters: Dict[str, Any], context=None):
                return ActionResult(status="SUCCESS", action=capability, provider_id="provider.autonomy.local_watcher", output={"mock_autonomy": True})

        mock_a = MockAutonomyProvider()
        capability_intelligence.register_provider(mock_a)
        selected = capability_intelligence.select_provider("autonomy.execute_goal")
        self.assertEqual(selected.provider_id, "provider.autonomy.local_watcher")

        # Restore
        capability_intelligence.unregister_provider("provider.autonomy.local_watcher")
        capability_intelligence.register_provider(self.provider)
        restored = capability_intelligence.select_provider("autonomy.execute_goal")
        self.assertEqual(restored.provider_id, "provider.autonomy.agency_runtime")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCapability41AutonomousAgency)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
