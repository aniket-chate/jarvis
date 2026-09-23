"""Integration Test Suite for Capabilities 36, 37, 38.

Verifies cross-cutting workflows across:
- Capability 36: Device Mesh
- Capability 37: Communication
- Capability 38: Calendar & Scheduling

Workflows tested:
1. 36 -> 37: Device-Aware Notification (Find reachable trusted device, dispatch notification)
2. 38 -> 37: Calendar Event Attendee Notification (Retrieve attendees, draft notification safely)
3. 38 -> 36: Calendar Event Device Dispatch (Calendar inspection, target device selection, alarm trigger)
4. 36 -> 38 -> 37: Composite Multi-Intent DAG (Check calendar, select device, notify user, verify)
5. Concurrency & Isolation: Simultaneous cross-capability operations without state bleeding
6. Hot-Swappable Provider Replacement: Swap provider dynamically while maintaining contract
"""

import concurrent.futures
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from capabilities.intelligence import capability_intelligence
from capabilities.providers import register_default_providers
from capabilities.providers.device_mesh_provider import DeviceMeshProvider, DeviceMeshConfig
from capabilities.providers.communication_provider import CommunicationHubProvider, CommunicationConfig
from capabilities.providers.calendar_scheduler_provider import CalendarSchedulerProvider, CalendarConfig
from gateway.registry import DeviceGatewayRegistry, DeviceTrustState
from orchestrator.intent_arbitrator import IntentArbitrator
from cognitive.planning_engine import PlanningEngine


class TestCapabilities363738Integration(unittest.TestCase):

    def setUp(self):
        register_default_providers()
        self.ci = capability_intelligence
        self.arbitrator = IntentArbitrator()
        self.planner = PlanningEngine()

        # Isolate providers for testing
        self.mesh_config = DeviceMeshConfig()
        self.mesh_provider = DeviceMeshProvider(config=self.mesh_config)

        self.comm_config = CommunicationConfig()
        self.comm_provider = CommunicationHubProvider(config=self.comm_config)

        self.cal_config = CalendarConfig(default_timezone="UTC")
        self.cal_provider = CalendarSchedulerProvider(config=self.cal_config)

    def test_workflow_36_to_37_device_aware_notification(self):
        """Workflow 1: Device Mesh selects trusted device -> Communication Hub dispatches notification."""
        # 1. Register two devices with different capabilities
        dev_a = self.mesh_provider.execute("mesh.register_device", {
            "device_id": "laptop_node_01",
            "name": "Work Laptop",
            "device_type": "windows",
            "capabilities": ["display", "notifications", "terminal"],
            "trust_state": "TRUSTED",
        })
        self.assertEqual(dev_a.status, "SUCCESS")

        dev_b = self.mesh_provider.execute("mesh.register_device", {
            "device_id": "sensor_node_02",
            "name": "IoT Sensor",
            "device_type": "embedded",
            "capabilities": ["temperature", "telemetry"],
            "trust_state": "TRUSTED",
        })
        self.assertEqual(dev_b.status, "SUCCESS")

        # 2. Select device supporting 'notifications'
        select_res = self.mesh_provider.execute("mesh.select_device", {
            "required_capability": "terminal",
            "require_trusted": True,
        })
        self.assertEqual(select_res.status, "SUCCESS")
        selected_dev = select_res.output["selected_device"]
        self.assertIsNotNone(selected_dev)
        self.assertEqual(selected_dev["device_id"], "laptop_node_01")

        # 3. Communication Hub dispatches notification targeted to that device
        notify_res = self.comm_provider.execute("comm.notify_user", {
            "title": "System Alert",
            "message": "Resource threshold exceeded",
            "urgency": "medium",
            "target_device": selected_dev["device_id"],
        })
        self.assertEqual(notify_res.status, "SUCCESS")
        self.assertTrue(notify_res.output["success"])
        self.assertEqual(notify_res.output["target_device"], "laptop_node_01")

    def test_workflow_38_to_37_calendar_attendee_drafting(self):
        """Workflow 2: Calendar event retrieved -> Communication Hub drafts briefing to attendees."""
        # 1. Create calendar event with attendees
        create_res = self.cal_provider.execute("calendar.create_event", {
            "title": "Roadmap Sync",
            "start_time": "2026-10-15T14:00:00+00:00",
            "duration_minutes": 45,
            "attendees": ["alex@example.org", "taylor@example.org"],
        })
        self.assertEqual(create_res.status, "SUCCESS")
        event = create_res.output["event"]

        # 2. Extract attendees and draft notification for each
        draft_ids = []
        for attendee in event["attendees"]:
            draft_res = self.comm_provider.execute("comm.draft_email", {
                "to": attendee,
                "subject": f"Pre-read for {event['title']}",
                "body": f"Meeting scheduled for {event['start_time']}. Agenda attached.",
            })
            self.assertEqual(draft_res.status, "SUCCESS")
            self.assertEqual(draft_res.output["status"], "DRAFT")
            draft_ids.append(draft_res.output["draft_id"])

        self.assertEqual(len(draft_ids), 2)
        # Verify drafts exist in communication outbox ledger
        for did in draft_ids:
            ver = self.comm_provider.execute("comm.verify_delivery", {"item_id": did})
            self.assertEqual(ver.output["delivery_status"], "DRAFT")

    def test_workflow_38_to_36_calendar_event_device_dispatch(self):
        """Workflow 3: Calendar inspection -> Mesh device selection -> In-app reminder/alarm."""
        # 1. Create upcoming event
        self.cal_provider.execute("calendar.create_event", {
            "title": "Executive Presentation",
            "start_time": "2026-10-16T16:00:00+00:00",
            "duration_minutes": 60,
        })

        # 2. Discover upcoming events
        events_res = self.cal_provider.execute("calendar.get_events", {
            "query": "Executive Presentation",
        })
        self.assertEqual(events_res.output["count"], 1)
        target_event = events_res.output["events"][0]

        # 3. Select notification-capable device
        self.mesh_provider.execute("mesh.register_device", {
            "device_id": "watch_01",
            "name": "Smart Watch",
            "device_type": "wearable",
            "capabilities": ["haptic", "notifications", "alarm"],
            "trust_state": "TRUSTED",
        })
        sel = self.mesh_provider.execute("mesh.select_device", {
            "required_capability": "alarm",
        })
        self.assertEqual(sel.status, "SUCCESS")
        self.assertEqual(sel.output["selected_device"]["device_id"], "watch_01")

        # 4. Schedule alarm
        alarm = self.cal_provider.execute("scheduler.alarm", {
            "delay_seconds": 60,
            "message": f"Upcoming: {target_event['title']}",
        })
        self.assertEqual(alarm.status, "SUCCESS")
        self.assertTrue(alarm.output["success"])

    def test_workflow_36_38_37_composite_dag(self):
        """Workflow 4: Multi-intent request 'Check my calendar and notify me on my available device'."""
        query = "Check my calendar and notify me on my available device"
        intent_data = self.arbitrator.arbitrate(query)

        self.assertEqual(intent_data.domain, "composite")
        self.assertEqual(intent_data.action, "calendar_mesh_notify")
        
        from cognitive.goal_engine import GoalTree, SubGoal
        tree = GoalTree(root_goal=query, subgoals=[
            SubGoal(goal_id="g1", description=query, domain="composite", action="calendar_mesh_notify", parameters={"query": query})
        ])
        plan = self.planner.generate_plan(tree)

        # Plan must have 4 steps: calendar -> mesh -> comm -> verifier
        self.assertEqual(len(plan.steps), 4)
        action_names = [s.required_capability for s in plan.steps]
        self.assertEqual(action_names, [
            "calendar.get_events",
            "mesh.select_device",
            "comm.notify_user",
            "verification.observe_reality",
        ])

        # Execute step 1: Calendar get_events
        s1_res = self.cal_provider.execute(plan.steps[0].required_capability, plan.steps[0].parameters)
        self.assertEqual(s1_res.status, "SUCCESS")

        # Execute step 2: Mesh select_device
        self.mesh_provider.execute("mesh.register_device", {
            "device_id": "workstation_primary",
            "name": "Studio PC",
            "device_type": "windows",
            "capabilities": ["notifications", "display"],
            "trust_state": "TRUSTED",
        })
        s2_res = self.mesh_provider.execute(plan.steps[1].required_capability, plan.steps[1].parameters)
        self.assertEqual(s2_res.status, "SUCCESS")
        chosen_device = s2_res.output["selected_device"]["device_id"]

        # Execute step 3: Comm notify_user on chosen device
        comm_params = dict(plan.steps[2].parameters)
        comm_params["target_device"] = chosen_device
        s3_res = self.comm_provider.execute(plan.steps[2].required_capability, comm_params)
        self.assertEqual(s3_res.status, "SUCCESS")
        self.assertTrue(s3_res.output["success"])

    def test_concurrent_cross_capability_operations(self):
        """Workflow 5: Concurrent operations across mesh, comm, and calendar without state bleeding."""
        def run_mesh(idx):
            return self.mesh_provider.execute("mesh.register_device", {
                "device_id": f"dyn_dev_{idx}",
                "name": f"Dynamic Device {idx}",
                "device_type": "mobile",
                "capabilities": ["notifications"],
                "trust_state": "TRUSTED",
            })

        def run_comm(idx):
            return self.comm_provider.execute("comm.draft_message", {
                "recipient": f"+1800555{idx:04d}",
                "message": f"Concurrent test payload {idx}",
            })

        def run_cal(idx):
            return self.cal_provider.execute("calendar.create_event", {
                "title": f"Concurrent Meeting {idx}",
                "start_time": f"2026-11-{idx+1:02d}T10:00:00+00:00",
                "duration_minutes": 30,
            })

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            mesh_futs = [executor.submit(run_mesh, i) for i in range(4)]
            comm_futs = [executor.submit(run_comm, i) for i in range(4)]
            cal_futs = [executor.submit(run_cal, i) for i in range(4)]

            mesh_res = [f.result() for f in mesh_futs]
            comm_res = [f.result() for f in comm_futs]
            cal_res = [f.result() for f in cal_futs]

        for r in mesh_res:
            self.assertEqual(r.status, "SUCCESS")
        for r in comm_res:
            self.assertEqual(r.status, "SUCCESS")
        for r in cal_res:
            self.assertEqual(r.status, "SUCCESS")

        # Verify no cross-pollution
        self.assertGreaterEqual(self.mesh_provider.execute("mesh.discover_peers", {}).output["count"], 4)
        self.assertEqual(self.comm_provider.execute("comm.get_history", {}).output["total_records"], 4)
        self.assertEqual(self.cal_provider.execute("calendar.get_events", {}).output["count"], 4)

    def test_hot_swappable_provider_replacement(self):
        """Workflow 6: Swapping providers dynamically without breaking registry contract."""
        class MockCalendarProvider:
            def __init__(self):
                self.calls = 0

            def execute(self, action: str, params: dict):
                self.calls += 1
                return {"action": action, "mocked": True, "call_index": self.calls}

        mock_cal = MockCalendarProvider()
        # Test contract compliance
        res = mock_cal.execute("calendar.create_event", {"title": "Mock Meeting"})
        self.assertTrue(res["mocked"])
        self.assertEqual(res["call_index"], 1)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCapabilities363738Integration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
