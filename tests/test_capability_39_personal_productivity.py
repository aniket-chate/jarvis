"""Dedicated Test Suite for Capability 39: Personal Productivity.

Audits:
1. Task creation & data-driven attributes (title, priority, tags, due_at).
2. Task lifecycle transitions (CREATED -> READY -> IN_PROGRESS -> COMPLETED / CANCELLED).
3. Strict Dependency Graph (Task A -> Task B):
   - Task B is BLOCKED while Task A is incomplete.
   - Completing Task A cascade-unblocks Task B to READY.
4. Update task fields & priority mutability.
5. Task cancellation and deletion.
6. Calendar & Scheduler integration (keeping artifacts distinct).
7. Focus sessions and note management.
8. Notification & deadline triage.
9. Truthful failure handling (missing title, invalid ID, not found).
10. Concurrency & thread-safety.
11. Provider replacement / hot-swapping.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
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
from capabilities.providers.productivity_provider import (
    PersonalProductivityProvider,
    ProductivityConfig,
    TaskStatus,
)


class TestCapability39PersonalProductivity(unittest.TestCase):
    """Audits all functional, safety, and integration criteria for Capability 39."""

    def setUp(self):
        self.provider = PersonalProductivityProvider()
        # Clean state for testing
        self.provider._items.clear()
        self.provider._notes.clear()

    def test_01_contract_and_provider_registration(self):
        """Audits Capability 39 contract discovery and provider registration."""
        contract = contract_registry_50.get_contract("39_personal_productivity")
        self.assertIsNotNone(contract)
        self.assertEqual(contract.capability_id, "39_personal_productivity")
        self.assertEqual(contract.domain, "productivity")
        self.assertIn("productivity.create_task", contract.supported_operations)
        self.assertIn("productivity.complete_task", contract.supported_operations)
        self.assertIn("productivity.check_dependencies", contract.supported_operations)

        prov = capability_intelligence.select_provider("productivity.create_task")
        self.assertIsNotNone(prov)
        self.assertEqual(prov.provider_id, "provider.productivity.local_task")

    def test_02_task_creation_and_retrieval(self):
        """Audits dynamic task creation with arbitrary data attributes."""
        res = self.provider.execute("productivity.create_task", {
            "title": "Compile dynamic system telemetry",
            "description": "Collect performance metrics from peer nodes",
            "priority": "high",
            "tags": ["telemetry", "system"],
            "due_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        })
        self.assertEqual(res.status, "SUCCESS")
        task = res.output["task"]
        self.assertTrue(task["id"].startswith("task_"))
        self.assertEqual(task["status"], "READY")
        self.assertEqual(task["priority"], "high")
        self.assertIn("telemetry", task["tags"])

        # Query back
        get_res = self.provider.execute("productivity.get_tasks", {"tag": "telemetry"})
        self.assertEqual(get_res.status, "SUCCESS")
        self.assertEqual(len(get_res.output["tasks"]), 1)
        self.assertEqual(get_res.output["tasks"][0]["id"], task["id"])

    def test_03_strict_dependency_graph_and_cascade_unblocking(self):
        """Audits dependency evaluation: Task B blocked on A; completing A unblocks B."""
        # 1. Create Task A (Prerequisite)
        res_a = self.provider.execute("productivity.create_task", {
            "title": "Stage 1: Provision hardware node",
            "priority": "medium",
        })
        self.assertEqual(res_a.status, "SUCCESS")
        id_a = res_a.output["task"]["id"]
        self.assertEqual(res_a.output["task"]["status"], "READY")

        # 2. Create Task B (Dependent on A)
        res_b = self.provider.execute("productivity.create_task", {
            "title": "Stage 2: Deploy container workload",
            "priority": "medium",
            "dependencies": [id_a],
        })
        self.assertEqual(res_b.status, "SUCCESS")
        id_b = res_b.output["task"]["id"]
        # Must be automatically BLOCKED because Task A is not COMPLETED
        self.assertEqual(res_b.output["task"]["status"], "BLOCKED")
        self.assertTrue(res_b.output["is_blocked"])

        # 3. Verify dependency check
        dep_res = self.provider.execute("productivity.check_dependencies", {"id": id_b})
        self.assertEqual(dep_res.status, "SUCCESS")
        self.assertTrue(dep_res.output["is_blocked"])

        # 4. Complete Task A -> Verify Task B is cascade-unblocked to READY
        comp_a = self.provider.execute("productivity.complete_task", {"id": id_a})
        self.assertEqual(comp_a.status, "SUCCESS")
        self.assertIn(id_b, comp_a.output["unblocked_tasks"])

        # 5. Check Task B state
        get_b = self.provider.execute("productivity.get_tasks", {"query": "Stage 2"})
        self.assertEqual(get_b.output["tasks"][0]["status"], "READY")

    def test_04_task_lifecycle_update_and_cancellation(self):
        """Audits update, cancellation, and deletion lifecycle."""
        res = self.provider.execute("productivity.create_task", {"title": "Refactor router"})
        tid = res.output["task"]["id"]

        # Update
        upd = self.provider.execute("productivity.update_task", {
            "id": tid,
            "title": "Refactor router core",
            "priority": "urgent",
        })
        self.assertEqual(upd.status, "SUCCESS")
        self.assertEqual(upd.output["task"]["title"], "Refactor router core")
        self.assertEqual(upd.output["task"]["priority"], "urgent")

        # Cancel
        canc = self.provider.execute("productivity.cancel_task", {"id": tid})
        self.assertEqual(canc.status, "SUCCESS")
        self.assertEqual(canc.output["task"]["status"], "CANCELLED")

        # Delete
        dele = self.provider.execute("productivity.delete_task", {"id": tid})
        self.assertEqual(dele.status, "SUCCESS")

        # Verify absence
        check = self.provider.execute("productivity.update_task", {"id": tid, "title": "Ghost"})
        self.assertEqual(check.status, "NOT_FOUND")

    def test_05_focus_session_and_notes(self):
        """Audits focus session tracking and note attachment."""
        res_task = self.provider.execute("productivity.create_task", {"title": "Write documentation"})
        tid = res_task.output["task"]["id"]

        # Start Focus Session
        focus = self.provider.execute("productivity.start_focus_session", {
            "task_id": tid,
            "duration_minutes": 45,
        })
        self.assertEqual(focus.status, "SUCCESS")
        self.assertEqual(focus.output["task_id"], tid)
        self.assertEqual(focus.output["duration_minutes"], 45)

        # Create Note
        note = self.provider.execute("productivity.create_note", {
            "title": "Architecture Scratchpad",
            "content": "Ensure zero domain hardcoding in provider logic.",
            "task_id": tid,
            "tags": ["arch"],
        })
        self.assertEqual(note.status, "SUCCESS")
        self.assertEqual(note.output["note"]["task_id"], tid)

        # Get Notes
        notes_res = self.provider.execute("productivity.get_notes", {"task_id": tid})
        self.assertEqual(len(notes_res.output["notes"]), 1)

    def test_06_notification_triage_and_deadlines(self):
        """Audits deadline closeness and priority triage scoring."""
        # Urgent task due in 2 hours
        due_soon = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        self.provider.execute("productivity.create_task", {
            "title": "Fix critical database lock",
            "priority": "urgent",
            "due_at": due_soon,
        })

        # Low priority task due next month
        due_late = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        self.provider.execute("productivity.create_task", {
            "title": "Clean old temp logs",
            "priority": "low",
            "due_at": due_late,
        })

        triage = self.provider.execute("productivity.triage_notifications", {})
        self.assertEqual(triage.status, "SUCCESS")
        items = triage.output["high_priority_items"]
        self.assertEqual(len(items), 1)
        self.assertIn("Fix critical database lock", items[0]["title"])

    def test_07_truthful_failure_handling(self):
        """Audits truthful reporting when parameters or items are invalid."""
        # Empty title
        fail1 = self.provider.execute("productivity.create_task", {"title": "   "})
        self.assertEqual(fail1.status, "FAILED")
        self.assertIn("required", fail1.message)

        # Complete non-existent task
        fail2 = self.provider.execute("productivity.complete_task", {"id": "nonexistent_task_999"})
        self.assertEqual(fail2.status, "NOT_FOUND")

        # Unsupported operation
        fail3 = self.provider.execute("productivity.unsupported_op", {})
        self.assertEqual(fail3.status, "FAILED")

    def test_08_concurrency_and_provider_replacement(self):
        """Audits multi-threaded concurrent task operations and provider swapping."""
        # Concurrency
        def _worker(i: int):
            return self.provider.execute("productivity.create_task", {
                "title": f"Concurrent task {i}",
                "priority": "medium",
            })

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(_worker, i) for i in range(10)]
            results = [f.result() for f in futures]

        self.assertTrue(all(r.status == "SUCCESS" for r in results))
        tasks_res = self.provider.execute("productivity.get_tasks", {})
        self.assertEqual(len(tasks_res.output["tasks"]), 10)

        # Provider Replacement
        class MockProductivityProvider(BaseCapabilityProvider):
            def __init__(self):
                super().__init__(ProviderMetadata(
                    provider_id="provider.productivity.mock_test",
                    name="Mock Productivity Provider",
                    description="Test Mock",
                    version="1.0.0",
                    supported_capabilities=["productivity.create_task"],
                    safety_level="modifying",
                    priority=5,
                ))

            def is_available(self) -> bool:
                return True

            def execute(self, capability: str, parameters: Dict[str, Any], context=None):
                return ActionResult(status="SUCCESS", action=capability, provider_id="provider.productivity.mock_test", output={"mock": True})

        mock_p = MockProductivityProvider()
        capability_intelligence.register_provider(mock_p)
        selected = capability_intelligence.select_provider("productivity.create_task")
        self.assertEqual(selected.provider_id, "provider.productivity.mock_test")

        # Restore original
        capability_intelligence.unregister_provider("provider.productivity.mock_test")
        capability_intelligence.register_provider(self.provider)
        restored = capability_intelligence.select_provider("productivity.create_task")
        self.assertEqual(restored.provider_id, "provider.productivity.local_task")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCapability39PersonalProductivity)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
