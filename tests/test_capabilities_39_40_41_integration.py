"""Batch Integration Test Suite for Capabilities 39, 40, and 41.

Audits Cross-Capability Workflows:
1. Workflow 1: Productivity + Calendar + Autonomous Agency
   - Task deadline scheduled into Calendar/Scheduler; condition triggers autonomous verification action.
2. Workflow 2: Travel + Calendar
   - Calendar event destination triggers travel route and departure calculation.
3. Workflow 3: Travel + Device Mesh + Communication
   - Device location queried -> Route calculated -> Travel ETA notified to user via Communication Hub.
4. Workflow 4: Productivity + Autonomous Agency
   - Completed prerequisite task unblocks autonomous agent to execute downstream goal.
5. Workflow 5: Full Pipeline Composite DAG
   - Calendar Event -> Travel Route -> Task Creation -> Autonomous Execution -> Device Mesh Notification.
6. Concurrency: Interleaved operations across 39, 40, and 41 without cross-talk or race conditions.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import os
import sys
import time
import unittest
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from capabilities.intelligence import capability_intelligence
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
import capabilities.providers  # Register active capability providers


class TestCapabilities39To41Integration(unittest.TestCase):
    """Audits cross-capability integration workflows across Capabilities 39, 40, and 41."""

    def setUp(self):
        self.prod_prov = capability_intelligence.select_provider("productivity.create_task")
        self.travel_prov = capability_intelligence.select_provider("travel.plan_route")
        self.auto_prov = capability_intelligence.select_provider("autonomy.execute_goal")
        self.cal_prov = capability_intelligence.select_provider("calendar.create_event")
        self.mesh_prov = capability_intelligence.select_provider("mesh.register_device")
        self.comm_prov = capability_intelligence.select_provider("comm.notify_user")
        if self.cal_prov and hasattr(self.cal_prov, "_events"):
            self.cal_prov._events.clear()

    def test_01_workflow_1_productivity_calendar_autonomy(self):
        """Workflow 1: Productivity Task -> Deadline -> Calendar -> Autonomous Action."""
        # 1. Create Task with deadline and calendar link
        due_str = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
        task_res = self.prod_prov.execute("productivity.create_task", {
            "title": "Prepare executive briefing",
            "due_at": due_str,
            "create_calendar_event": True,
        })
        self.assertEqual(task_res.status, "SUCCESS")
        task = task_res.output["task"]
        self.assertIsNotNone(task_res.output["calendar_event_id"])

        # 2. Autonomous Agency monitors deadline condition and executes telemetry check
        auto_res = self.auto_prov.execute("autonomy.execute_goal", {
            "goal_id": f"deadline_check_{task['id']}",
            "target_capability": "os.telemetry",
            "parameters": {"task_id": task["id"]},
        })
        self.assertEqual(auto_res.status, "SUCCESS")
        self.assertEqual(auto_res.output["goal"]["state"], "COMPLETED")

    def test_02_workflow_2_travel_calendar_departure_planning(self):
        """Workflow 2: Calendar Event -> Destination -> Travel Route -> Departure Recommendation."""
        # 1. Create Event with destination
        evt_start = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
        evt_res = self.cal_prov.execute("calendar.create_event", {
            "title": "Symposium Opening",
            "start": evt_start,
            "location": "Innovation Convention Center",
            "allow_conflicts": True,
        })
        self.assertEqual(evt_res.status, "SUCCESS")
        evt = evt_res.output.get("event") or evt_res.output
        evt_location = evt.get("location", "Innovation Convention Center")
        evt_start_time = evt.get("start_time") or evt.get("start") or evt_start

        # 2. Travel provider plans route to event destination and computes departure time
        travel_res = self.travel_prov.execute("travel.estimate_timing", {
            "origin": "Tech Quarter",
            "destination": evt_location,
            "event_start": evt_start_time,
            "buffer_minutes": 15,
        })
        self.assertEqual(travel_res.status, "SUCCESS")
        out = travel_res.output
        self.assertIn("recommended_departure_time", out)
        self.assertLess(out["recommended_departure_time"], evt_start_time)

    def test_03_workflow_3_travel_mesh_communication(self):
        """Workflow 3: Device Mesh Location -> Route Calculation -> Communication Notification."""
        # 1. Register and elevate a trusted device in mesh
        dev_id = f"phone_{uuid.uuid4().hex[:6]}"
        self.mesh_prov.execute("mesh.register_device", {
            "device_id": dev_id,
            "name": "User Phone",
            "capabilities": ["notifications", "gps"],
        })
        # Set trusted
        self.mesh_prov.execute("mesh.set_device_trust", {
            "device_id": dev_id,
            "trust_state": "TRUSTED",
        })

        # 2. Route calculation from current location to meeting venue
        route_res = self.travel_prov.execute("travel.plan_route", {
            "origin": "Current Anchor",
            "destination": "Client Office",
            "mode": "transit",
        })
        self.assertEqual(route_res.status, "SUCCESS")
        eta = route_res.output["arrival_time"]

        # 3. Dispatch notification via Communication Hub targeted to mesh device
        notify_res = self.comm_prov.execute("comm.notify_user", {
            "title": "Transit Update",
            "message": f"Estimated arrival at {eta}",
            "target_device": dev_id,
        })
        self.assertEqual(notify_res.status, "SUCCESS")
        self.assertTrue(notify_res.output["success"])

    def test_04_workflow_4_productivity_dependency_unblocks_autonomy(self):
        """Workflow 4: Completing prerequisite task unblocks autonomous downstream execution."""
        # 1. Create Task A
        res_a = self.prod_prov.execute("productivity.create_task", {"title": "Data ingestion"})
        task_a_id = res_a.output["task"]["id"]

        # 2. Create Task B (dependent on A)
        res_b = self.prod_prov.execute("productivity.create_task", {
            "title": "Autonomous model retraining",
            "dependencies": [task_a_id],
        })
        task_b_id = res_b.output["task"]["id"]
        self.assertEqual(res_b.output["task"]["status"], "BLOCKED")

        # 3. Complete Task A
        comp_a = self.prod_prov.execute("productivity.complete_task", {"id": task_a_id})
        self.assertEqual(comp_a.status, "SUCCESS")
        self.assertIn(task_b_id, comp_a.output["unblocked_tasks"])

        # 4. Trigger Autonomous Agency for now-ready task
        auto_res = self.auto_prov.execute("autonomy.execute_goal", {
            "goal_id": f"auto_job_{task_b_id}",
            "target_capability": "os.telemetry",
            "parameters": {"task_id": task_b_id},
        })
        self.assertEqual(auto_res.status, "SUCCESS")
        self.assertEqual(auto_res.output["goal"]["state"], "COMPLETED")

    def test_05_workflow_5_full_composite_pipeline(self):
        """Workflow 5: Full Composite Pipeline: Calendar -> Travel -> Task -> Autonomy -> Mesh -> Comm -> Verification."""
        # 1. Calendar Event
        evt_res = self.cal_prov.execute("calendar.create_event", {
            "title": "Quarterly Operations Review",
            "start": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "location": "Regional Datacenter",
        })
        self.assertEqual(evt_res.status, "SUCCESS")

        # 2. Travel Route
        route_res = self.travel_prov.execute("travel.plan_route", {
            "origin": "Downtown HQ",
            "destination": evt_res.output["event"]["location"],
            "mode": "driving",
        })
        self.assertEqual(route_res.status, "SUCCESS")

        # 3. Productivity Task for travel preparation
        task_res = self.prod_prov.execute("productivity.create_task", {
            "title": f"Prepare transit pack for {evt_res.output['event']['location']}",
            "due_at": route_res.output["departure_time"],
        })
        self.assertEqual(task_res.status, "SUCCESS")

        # 4. Autonomous Verification Action
        auto_res = self.auto_prov.execute("autonomy.execute_goal", {
            "goal_id": f"auto_pipeline_{uuid.uuid4().hex[:6]}",
            "target_capability": "os.telemetry",
        })
        self.assertEqual(auto_res.status, "SUCCESS")

        # 5. Peer Notification
        comm_res = self.comm_prov.execute("comm.notify_user", {
            "title": "Pipeline Verified",
            "message": "All composite operations executed cleanly.",
        })
        self.assertEqual(comm_res.status, "SUCCESS")

    def test_06_concurrency_across_all_three_capabilities(self):
        """Audits concurrent multi-threaded execution across 39, 40, and 41 simultaneously."""
        def _task_worker(i: int):
            return self.prod_prov.execute("productivity.create_task", {"title": f"Concurrent Task {i}"})

        def _travel_worker(i: int):
            return self.travel_prov.execute("travel.plan_route", {
                "origin": f"Site Alpha {i}",
                "destination": f"Site Beta {i}",
            })

        def _autonomy_worker(i: int):
            return self.auto_prov.execute("autonomy.execute_goal", {
                "goal_id": f"concurrent_goal_{i}_{uuid.uuid4().hex[:6]}",
                "target_capability": "os.telemetry",
            })

        with ThreadPoolExecutor(max_workers=6) as pool:
            f_prod = [pool.submit(_task_worker, i) for i in range(5)]
            f_trav = [pool.submit(_travel_worker, i) for i in range(5)]
            f_auto = [pool.submit(_autonomy_worker, i) for i in range(5)]

            all_results = [f.result() for f in (f_prod + f_trav + f_auto)]

        self.assertTrue(all(r.status == "SUCCESS" for r in all_results))


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCapabilities39To41Integration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
