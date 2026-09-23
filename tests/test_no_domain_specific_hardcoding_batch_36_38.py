"""Universal Anti-Hardcoding Engineering Constraint Test Suite for Batch 2 (Capabilities 36, 37, 38).

Audits:
1. Zero domain-specific literals (device names, contact names, event titles, email accounts).
2. Zero query-specific routing or vendor branching in capability code.
3. Configuration dataclasses manage all timeouts, thresholds, and limits.
4. Dynamic generalization:
   - A. Unknown Device
   - B. Second Unknown Device
   - C. Unknown Contact
   - D. Unknown Calendar Event
   - E. Source Removal Test (Mandatory across all three domains)
   - F. Configuration Change Test (Runtime threshold adaptability)
   - G. Provider Replacement (Hot-swapping all three capability providers)
   - H. Unknown Entity (Resilience to arbitrary runtime UUID entities)
"""

import ast
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import unittest
import uuid

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from capabilities.providers.device_mesh_provider import DeviceMeshProvider, DeviceMeshConfig
from capabilities.providers.communication_provider import CommunicationHubProvider, CommunicationConfig, ContactRecord
from capabilities.providers.calendar_scheduler_provider import CalendarSchedulerProvider, CalendarConfig
from capabilities.intelligence import capability_intelligence
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from gateway.registry import gateway_registry, DeviceTrustState


class TestBatch2AntiHardcodingArchitecture(unittest.TestCase):
    """AST and static analysis ensuring zero domain-specific hardcoding in Batch 2."""

    def test_no_hardcoded_device_names(self):
        """Inspects capability providers and routers for forbidden device literals."""
        files_to_check = [
            PROJECT_ROOT / "capabilities" / "providers" / "device_mesh_provider.py",
            PROJECT_ROOT / "agents" / "device_mesh_agent.py",
            PROJECT_ROOT / "orchestrator" / "intent_arbitrator.py",
        ]
        forbidden_device_literals = ["vivo v29", "living room tv", "my phone", "galaxy s", "pixel 8"]

        for file_path in files_to_check:
            self.assertTrue(file_path.exists(), f"Missing file: {file_path}")
            source = file_path.read_text(encoding="utf-8").lower()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    val = node.value.strip().lower()
                    for forbidden in forbidden_device_literals:
                        self.assertNotIn(
                            forbidden,
                            val,
                            f"Forbidden hardcoded device literal '{forbidden}' in {file_path}",
                        )

    def test_no_hardcoded_contact_names(self):
        """Inspects capability providers and routers for forbidden contact literals."""
        files_to_check = [
            PROJECT_ROOT / "capabilities" / "providers" / "communication_provider.py",
            PROJECT_ROOT / "agents" / "communication_agent.py",
            PROJECT_ROOT / "orchestrator" / "intent_arbitrator.py",
        ]
        forbidden_contact_literals = ["sachin", "mrutunjay", "shreeyash", "aniket chate"]

        for file_path in files_to_check:
            self.assertTrue(file_path.exists(), f"Missing file: {file_path}")
            source = file_path.read_text(encoding="utf-8").lower()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    val = node.value.strip().lower()
                    for forbidden in forbidden_contact_literals:
                        self.assertNotIn(
                            forbidden,
                            val,
                            f"Forbidden hardcoded contact literal '{forbidden}' in {file_path}",
                        )

    def test_no_hardcoded_calendar_event_names(self):
        """Inspects calendar capability code for hardcoded event names."""
        files_to_check = [
            PROJECT_ROOT / "capabilities" / "providers" / "calendar_scheduler_provider.py",
            PROJECT_ROOT / "agents" / "calendar_agent.py",
        ]
        forbidden_event_literals = ["interview with google", "standup meeting with team", "aniket project review"]

        for file_path in files_to_check:
            source = file_path.read_text(encoding="utf-8").lower()
            for forbidden in forbidden_event_literals:
                self.assertNotIn(
                    forbidden,
                    source,
                    f"Forbidden hardcoded event literal '{forbidden}' in {file_path}",
                )

    def test_no_hardcoded_vendor_routing(self):
        """Asserts capability logic does not branch on vendor names like 'if gmail in query'."""
        provider_path = PROJECT_ROOT / "capabilities" / "providers" / "communication_provider.py"
        source = provider_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                test_dump = ast.dump(node.test).lower()
                self.assertNotIn("'gmail' in", test_dump, "Prohibited vendor routing 'gmail in query' found!")
                self.assertNotIn("'whatsapp' in", test_dump, "Prohibited vendor routing 'whatsapp in query' found!")

    def test_configuration_dataclasses_present_and_configurable(self):
        """Asserts presence and configurability of DeviceMeshConfig, CommunicationConfig, and CalendarConfig."""
        mesh_cfg = DeviceMeshConfig(heartbeat_timeout_sec=90.0, default_latency_ms=5.0)
        p_mesh = DeviceMeshProvider(config=mesh_cfg)
        self.assertEqual(p_mesh.config.heartbeat_timeout_sec, 90.0)
        self.assertEqual(p_mesh.config.default_latency_ms, 5.0)

        comm_cfg = CommunicationConfig(require_confirmation_for_send=False, max_history_items=10)
        p_comm = CommunicationHubProvider(config=comm_cfg)
        self.assertFalse(p_comm.config.require_confirmation_for_send)
        self.assertEqual(p_comm.config.max_history_items, 10)

        cal_cfg = CalendarConfig(default_event_duration_min=45, default_timezone="America/New_York")
        p_cal = CalendarSchedulerProvider(config=cal_cfg)
        self.assertEqual(p_cal.config.default_event_duration_min, 45)
        self.assertEqual(p_cal.config.default_timezone, "America/New_York")


class TestDynamicEntityGeneralizationBatch2(unittest.TestCase):
    """Dynamic test suite validating that unknown entities work without modifying code."""

    def setUp(self):
        self.p_mesh = DeviceMeshProvider()
        self.p_comm = CommunicationHubProvider()
        self.p_cal = CalendarSchedulerProvider()

    # =========================================================================
    # A. Unknown Device
    # =========================================================================
    def test_a_unknown_device_generalization(self):
        """A. Unknown Device: Create unseen runtime device entity and verify lifecycle."""
        rand_id = f"dev_unseen_{uuid.uuid4().hex[:8]}"
        rand_name = f"Dynamic Node {uuid.uuid4().hex[:6]}"

        # 1. Registration
        reg_res = self.p_mesh.execute("mesh.register_device", {
            "device_id": rand_id,
            "name": rand_name,
            "client_type": "tablet",
            "ip_address": "100.64.12.34",
            "capabilities": ["custom_hologram", "laser_notifications"],
            "trust_state": "TRUSTED",
            "latency_ms": 8.5,
        })
        self.assertEqual(reg_res.status, "SUCCESS")
        self.assertTrue(reg_res.output.get("registered"))

        # 2. Discovery with capability filter
        disc_res = self.p_mesh.execute("mesh.discover_peers", {"capability": "custom_hologram"})
        self.assertEqual(disc_res.status, "SUCCESS")
        found_ids = [d["device_id"] for d in disc_res.output["devices"]]
        self.assertIn(rand_id, found_ids)

        # 3. Dynamic Selection matching capability
        sel_res = self.p_mesh.execute("mesh.select_device", {"required_capability": "custom_hologram"})
        self.assertEqual(sel_res.status, "SUCCESS")
        self.assertTrue(sel_res.output["found"])
        self.assertEqual(sel_res.output["device_id"], rand_id)

        # 4. Removal
        gateway_registry.unregister_device(rand_id)
        stat_after = self.p_mesh.execute("mesh.get_device_status", {"device_id": rand_id})
        self.assertFalse(stat_after.output["found"])

    # =========================================================================
    # B. Second Unknown Device
    # =========================================================================
    def test_b_second_unknown_device_generalization(self):
        """B. Second Unknown Device: Create completely different runtime device and verify identical generalized behavior."""
        second_id = f"dev_drone_{uuid.uuid4().hex[:8]}"
        second_name = f"Autonomous Drone {uuid.uuid4().hex[:6]}"

        reg_res = self.p_mesh.execute("mesh.register_device", {
            "device_id": second_id,
            "name": second_name,
            "client_type": "drone",
            "ip_address": "100.64.99.11",
            "capabilities": ["aerial_telemetry", "lidar_depth"],
            "trust_state": "TRUSTED",
            "latency_ms": 4.2,
        })
        self.assertEqual(reg_res.status, "SUCCESS")

        disc_res = self.p_mesh.execute("mesh.discover_peers", {"capability": "lidar_depth"})
        self.assertEqual(disc_res.status, "SUCCESS")
        found_ids = [d["device_id"] for d in disc_res.output["devices"]]
        self.assertIn(second_id, found_ids)

        sel_res = self.p_mesh.execute("mesh.select_device", {"required_capability": "lidar_depth"})
        self.assertEqual(sel_res.output["device_id"], second_id)

        gateway_registry.unregister_device(second_id)
        stat_after = self.p_mesh.execute("mesh.get_device_status", {"device_id": second_id})
        self.assertFalse(stat_after.output["found"])

    # =========================================================================
    # C. Unknown Contact
    # =========================================================================
    def test_c_unknown_contact_generalization(self):
        """C. Unknown Contact: Create runtime contact, resolve it, remove it, verify no longer resolvable."""
        cid = f"cnt_{uuid.uuid4().hex[:8]}"
        cname = f"Colleague_{uuid.uuid4().hex[:6]}"
        cemail = f"{cname.lower()}@dynamic-research.org"

        record = ContactRecord(
            contact_id=cid,
            name=cname,
            email=cemail,
            phone="+19995551234",
            tags=["quantum_lab"],
        )
        self.p_comm.register_contact(record)

        # Resolve
        lookup_res = self.p_comm.execute("comm.lookup_contact", {"query": cname})
        self.assertEqual(lookup_res.status, "SUCCESS")
        self.assertTrue(lookup_res.output.get("found"))
        self.assertEqual(lookup_res.output["contact"]["email"], cemail)

        # Remove
        removed = self.p_comm.unregister_contact(cid)
        self.assertTrue(removed)

        # Verify no longer resolvable
        lookup_after = self.p_comm.execute("comm.lookup_contact", {"query": cname})
        self.assertFalse(lookup_after.output.get("found"))

    # =========================================================================
    # D. Unknown Calendar Event
    # =========================================================================
    def test_d_unknown_calendar_event_generalization(self):
        """D. Unknown Calendar Event: Create event with dynamic title, retrieve, modify, delete, verify absence."""
        event_title = f"SYNTHETIC_EXPERIMENT_{uuid.uuid4().hex[:8]}"

        # 1. Create
        create_res = self.p_cal.execute("calendar.create_event", {
            "title": event_title,
            "start_time": "2026-11-20T16:00:00+00:00",
            "duration_minutes": 50,
            "description": "Dynamic experiment event generated entirely at runtime.",
        })
        self.assertEqual(create_res.status, "SUCCESS")
        self.assertEqual(create_res.output.get("status"), "CREATED")
        event_id = create_res.output["event_id"]

        # 2. Retrieve
        get_res = self.p_cal.execute("calendar.get_events", {"query": event_title})
        self.assertEqual(get_res.status, "SUCCESS")
        self.assertEqual(get_res.output["count"], 1)
        self.assertEqual(get_res.output["events"][0]["event_id"], event_id)

        # 3. Modify
        modified_title = f"{event_title}_UPDATED"
        mod_res = self.p_cal.execute("calendar.modify_event", {
            "event_id": event_id,
            "new_title": modified_title,
        })
        self.assertEqual(mod_res.status, "SUCCESS")
        self.assertEqual(mod_res.output["event"]["title"], modified_title)

        # 4. Delete
        del_res = self.p_cal.execute("calendar.delete_event", {"event_id": event_id})
        self.assertEqual(del_res.status, "SUCCESS")
        self.assertEqual(del_res.output.get("status"), "DELETED")

        # 5. Verify absence after deletion
        get_after = self.p_cal.execute("calendar.get_events", {"query": event_title})
        self.assertEqual(get_after.output["count"], 0)

    # =========================================================================
    # E. SOURCE REMOVAL TEST (Mandatory across all 3 domains)
    # =========================================================================
    def test_e_source_removal_all_three_domains(self):
        """E. SOURCE REMOVAL TEST: Proves data is dynamically loaded and disappears truthfully upon removal."""
        # 1. Device Mesh Source Removal
        mesh_id = f"dev_removal_{uuid.uuid4().hex[:6]}"
        self.p_mesh.execute("mesh.register_device", {
            "device_id": mesh_id,
            "name": "Temporary Removable Device",
            "client_type": "pc",
            "capabilities": ["temp_cap"],
            "trust_state": "TRUSTED",
        })
        self.assertTrue(self.p_mesh.execute("mesh.get_device_status", {"device_id": mesh_id}).output["found"])
        gateway_registry.unregister_device(mesh_id)
        # Must return found=False
        self.assertFalse(self.p_mesh.execute("mesh.get_device_status", {"device_id": mesh_id}).output["found"])

        # 2. Communication Source Removal
        comm_cid = f"cnt_removal_{uuid.uuid4().hex[:6]}"
        self.p_comm.register_contact(ContactRecord(contact_id=comm_cid, name="Removable Contact", email="rm@example.com"))
        self.assertTrue(self.p_comm.execute("comm.lookup_contact", {"query": "Removable Contact"}).output["found"])
        self.p_comm.unregister_contact(comm_cid)
        # Must return found=False
        self.assertFalse(self.p_comm.execute("comm.lookup_contact", {"query": "Removable Contact"}).output["found"])

        # 3. Calendar Source Removal
        cal_res = self.p_cal.execute("calendar.create_event", {
            "title": "Removable Calendar Event",
            "start_time": "2026-12-01T10:00:00+00:00",
            "duration_minutes": 30,
        })
        cal_id = cal_res.output["event_id"]
        self.assertEqual(self.p_cal.execute("calendar.get_events", {"query": "Removable Calendar Event"}).output["count"], 1)
        self.p_cal.execute("calendar.delete_event", {"event_id": cal_id})
        # Must return count=0 and NOT_FOUND on modify
        self.assertEqual(self.p_cal.execute("calendar.get_events", {"query": "Removable Calendar Event"}).output["count"], 0)
        mod_attempt = self.p_cal.execute("calendar.modify_event", {"event_id": cal_id, "new_title": "Ghost"})
        self.assertEqual(mod_attempt.output["status"], "NOT_FOUND")

    # =========================================================================
    # F. CONFIGURATION CHANGE TEST
    # =========================================================================
    def test_f_configuration_change(self):
        """F. CONFIGURATION CHANGE TEST: Verifies runtime configuration modifies behavior without source edits."""
        # 1. DeviceMeshConfig: Changing require_trust_for_routing blocks or permits PENDING devices
        mesh_cfg_strict = DeviceMeshConfig(default_trust="PENDING", require_trust_for_routing=True)
        p_strict = DeviceMeshProvider(config=mesh_cfg_strict)
        p_strict.execute("mesh.register_device", {
            "device_id": "cfg_test_dev",
            "name": "Config Test Device",
            "capabilities": ["ping"],
        })
        # Under strict config, routing to PENDING device fails
        strict_route = p_strict.execute("mesh.route_to_device", {"target_device_id": "cfg_test_dev", "payload": {}})
        self.assertFalse(strict_route.output["success"])
        self.assertIn("not trusted", strict_route.output["error"].lower())

        # Under permissive config, routing to PENDING device succeeds
        mesh_cfg_perm = DeviceMeshConfig(default_trust="PENDING", require_trust_for_routing=False)
        p_perm = DeviceMeshProvider(config=mesh_cfg_perm)
        perm_route = p_perm.execute("mesh.route_to_device", {"target_device_id": "cfg_test_dev", "payload": {}})
        self.assertTrue(perm_route.output["success"])
        gateway_registry.unregister_device("cfg_test_dev")

        # 2. CalendarConfig: Changing default duration and timezone
        cal_cfg = CalendarConfig(default_event_duration_min=42, default_timezone="America/Chicago")
        p_cal_cfg = CalendarSchedulerProvider(config=cal_cfg)
        ev_res = p_cal_cfg.execute("calendar.create_event", {
            "title": "Configured Duration Event",
            "start_time": "2026-11-25T10:00:00",
        })
        self.assertEqual(ev_res.output["event"]["timezone"], "America/Chicago")
        # Start 10:00 -> End must be 10:42
        self.assertIn("10:42:00", ev_res.output["event"]["end_time"])

    # =========================================================================
    # G. PROVIDER REPLACEMENT (Hot-swapping all three capability providers)
    # =========================================================================
    def test_g_provider_replacement(self):
        """G. PROVIDER REPLACEMENT: Replace each provider, verify registry selection and contract, then restore."""
        # 1. Device Mesh Provider Hot-Swap
        class MockMeshProvider(BaseCapabilityProvider):
            def __init__(self):
                super().__init__(ProviderMetadata(
                    provider_id="provider.mesh.mock_test",
                    name="Mock Mesh Provider",
                    supported_capabilities=["mesh.discover_peers"],
                    priority=1,
                ))
            def is_available(self): return True
            def execute(self, cap, params, context=None):
                return ActionResult(status="SUCCESS", output={"devices": [], "is_mock_mesh": True})

        mock_mesh = MockMeshProvider()
        capability_intelligence.register_provider(mock_mesh)
        self.assertEqual(capability_intelligence.select_provider("mesh.discover_peers").provider_id, "provider.mesh.mock_test")
        res_m = capability_intelligence.select_provider("mesh.discover_peers").execute("mesh.discover_peers", {})
        self.assertTrue(res_m.output["is_mock_mesh"])
        capability_intelligence.unregister_provider("provider.mesh.mock_test")
        self.assertEqual(capability_intelligence.select_provider("mesh.discover_peers").provider_id, "provider.mesh.device_mesh")

        # 2. Communication Provider Hot-Swap
        class MockCommProvider(BaseCapabilityProvider):
            def __init__(self):
                super().__init__(ProviderMetadata(
                    provider_id="provider.comm.mock_test",
                    name="Mock Comm Provider",
                    supported_capabilities=["comm.lookup_contact"],
                    priority=1,
                ))
            def is_available(self): return True
            def execute(self, cap, params, context=None):
                return ActionResult(status="SUCCESS", output={"candidates": [], "is_mock_comm": True})

        mock_comm = MockCommProvider()
        capability_intelligence.register_provider(mock_comm)
        self.assertEqual(capability_intelligence.select_provider("comm.lookup_contact").provider_id, "provider.comm.mock_test")
        res_c = capability_intelligence.select_provider("comm.lookup_contact").execute("comm.lookup_contact", {})
        self.assertTrue(res_c.output["is_mock_comm"])
        capability_intelligence.unregister_provider("provider.comm.mock_test")
        self.assertEqual(capability_intelligence.select_provider("comm.lookup_contact").provider_id, "provider.comm.communication_hub")

        # 3. Calendar Provider Hot-Swap
        class MockCalProvider(BaseCapabilityProvider):
            def __init__(self):
                super().__init__(ProviderMetadata(
                    provider_id="provider.calendar.mock_test",
                    name="Mock Calendar Provider",
                    supported_capabilities=["calendar.get_events"],
                    priority=1,
                ))
            def is_available(self): return True
            def execute(self, cap, params, context=None):
                return ActionResult(status="SUCCESS", output={"events": [], "is_mock_cal": True})

        mock_cal = MockCalProvider()
        capability_intelligence.register_provider(mock_cal)
        self.assertEqual(capability_intelligence.select_provider("calendar.get_events").provider_id, "provider.calendar.mock_test")
        res_cal = capability_intelligence.select_provider("calendar.get_events").execute("calendar.get_events", {})
        self.assertTrue(res_cal.output["is_mock_cal"])
        capability_intelligence.unregister_provider("provider.calendar.mock_test")
        self.assertEqual(capability_intelligence.select_provider("calendar.get_events").provider_id, "provider.calendar.scheduler")

    # =========================================================================
    # H. UNKNOWN ENTITY
    # =========================================================================
    def test_h_unknown_entity_resilience(self):
        """H. UNKNOWN ENTITY: Queries for completely novel runtime UUID entities return generic truthful responses."""
        novel_id = f"novel_{uuid.uuid4().hex}"

        # 1. Unknown device query
        dev_res = self.p_mesh.execute("mesh.get_device_status", {"device_id": novel_id})
        self.assertEqual(dev_res.status, "SUCCESS")
        self.assertFalse(dev_res.output["found"])

        # 2. Unknown contact query
        cnt_res = self.p_comm.execute("comm.lookup_contact", {"query": novel_id})
        self.assertEqual(cnt_res.status, "SUCCESS")
        self.assertFalse(cnt_res.output["found"])

        # 3. Unknown calendar event query
        cal_res = self.p_cal.execute("calendar.modify_event", {"event_id": novel_id, "new_title": "Test"})
        self.assertEqual(cal_res.status, "SUCCESS")
        self.assertEqual(cal_res.output["status"], "NOT_FOUND")


if __name__ == "__main__":
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestBatch2AntiHardcodingArchitecture))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestDynamicEntityGeneralizationBatch2))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
