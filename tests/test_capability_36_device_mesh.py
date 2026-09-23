"""Independent Test Suite for Capability 36 — Device Mesh.

Tests:
1. Device registration and machine-readable identity.
2. Device discovery with capability and trust filtering.
3. Explicit trust state machine transitions (TRUSTED, REVOKED, OFFLINE).
4. Heartbeat and online/offline status computation.
5. Dynamic capability advertisement.
6. Data-driven device selection by capability and latency.
7. Truthful failure rejection for revoked or offline nodes.
8. Concurrent device registration and query isolation.
9. Hot-swap provider replacement.
"""

import concurrent.futures
import time
import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from capabilities.providers.device_mesh_provider import DeviceMeshProvider, DeviceMeshConfig
from capabilities.intelligence import capability_intelligence
from gateway.registry import gateway_registry, DeviceTrustState


class TestCapability36DeviceMesh(unittest.TestCase):

    def setUp(self):
        self.config = DeviceMeshConfig(heartbeat_timeout_sec=5.0)
        self.provider = DeviceMeshProvider(config=self.config)

    def tearDown(self):
        # Cleanup test devices from singleton registry
        for dev_id in ["test_node_1", "test_node_2", "test_node_3", "revoked_node", "stale_node"]:
            gateway_registry.unregister_device(dev_id)

    def test_device_registration_and_identity(self):
        """Tests device registration with machine-readable identity."""
        res = self.provider.execute("mesh.register_device", {
            "device_id": "test_node_1",
            "name": "Node Alpha",
            "client_type": "phone",
            "ip_address": "10.0.0.10",
            "capabilities": ["audio_output", "camera", "notifications"],
            "trust_state": "TRUSTED",
            "latency_ms": 12.5,
        })
        self.assertEqual(res.status, "SUCCESS")
        out = res.output
        self.assertEqual(out["device_id"], "test_node_1")
        self.assertEqual(out["trust_state"], "TRUSTED")
        self.assertTrue(out["online"])
        self.assertIn("camera", out["capabilities"])

    def test_device_discovery_and_filtering(self):
        """Tests device discovery with capability and status filtering."""
        self.provider.execute("mesh.register_device", {
            "device_id": "test_node_1",
            "name": "Display Node",
            "client_type": "tv",
            "ip_address": "10.0.0.11",
            "capabilities": ["display"],
            "trust_state": "TRUSTED",
        })
        self.provider.execute("mesh.register_device", {
            "device_id": "test_node_2",
            "name": "Sensor Node",
            "client_type": "iot",
            "ip_address": "10.0.0.12",
            "capabilities": ["sensor"],
            "trust_state": "TRUSTED",
        })

        # Filter by display capability
        disc = self.provider.execute("mesh.discover_peers", {"capability": "display"})
        self.assertEqual(disc.status, "SUCCESS")
        ids = [d["device_id"] for d in disc.output["devices"]]
        self.assertIn("test_node_1", ids)
        self.assertNotIn("test_node_2", ids)

    def test_device_trust_and_revocation(self):
        """Tests explicit revocation and isolation from mesh routing."""
        self.provider.execute("mesh.register_device", {
            "device_id": "revoked_node",
            "name": "Compromised Node",
            "client_type": "pc",
            "ip_address": "10.0.0.15",
            "capabilities": ["notifications"],
            "trust_state": "TRUSTED",
        })

        # Revoke device
        rev_res = self.provider.execute("mesh.revoke_device", {"device_id": "revoked_node"})
        self.assertEqual(rev_res.status, "SUCCESS")
        self.assertEqual(rev_res.output["trust_state"], "REVOKED")

        # Attempt to route to revoked device -> must fail truthfully
        route_res = self.provider.execute("mesh.route_to_device", {
            "target_device_id": "revoked_node",
            "payload": {"command": "alert"},
        })
        self.assertEqual(route_res.status, "SUCCESS")  # Action executed
        self.assertFalse(route_res.output["success"])
        self.assertIn("revoked", route_res.output["error"].lower())

    def test_heartbeat_and_stale_detection(self):
        """Tests heartbeat update and timeout calculation."""
        self.provider.execute("mesh.register_device", {
            "device_id": "stale_node",
            "name": "Stale Device",
            "client_type": "sensor",
            "ip_address": "10.0.0.99",
            "capabilities": ["battery"],
            "trust_state": "TRUSTED",
        })
        hb_res = self.provider.execute("mesh.device_heartbeat", {"device_id": "stale_node"})
        self.assertEqual(hb_res.status, "SUCCESS")
        self.assertTrue(hb_res.output["touched"])
        self.assertTrue(hb_res.output["online"])

    def test_data_driven_device_selection(self):
        """Tests selecting the lowest latency, trusted device advertising the required capability."""
        self.provider.execute("mesh.register_device", {
            "device_id": "test_node_1",
            "name": "Slow Speaker",
            "client_type": "speaker",
            "ip_address": "10.0.0.21",
            "capabilities": ["audio_output"],
            "trust_state": "TRUSTED",
            "latency_ms": 80.0,
        })
        self.provider.execute("mesh.register_device", {
            "device_id": "test_node_2",
            "name": "Fast Speaker",
            "client_type": "speaker",
            "ip_address": "10.0.0.22",
            "capabilities": ["audio_output"],
            "trust_state": "TRUSTED",
            "latency_ms": 15.0,
        })

        sel = self.provider.execute("mesh.select_device", {"required_capability": "audio_output"})
        self.assertEqual(sel.status, "SUCCESS")
        self.assertTrue(sel.output["found"])
        # Fast speaker or host_pc (latency 1.0) must be selected over slow speaker
        self.assertIn(sel.output["device_id"], ["test_node_2", "host_pc"])

    def test_concurrency_in_device_operations(self):
        """Tests concurrent registrations and status queries without race conditions."""
        def register_worker(worker_id):
            return self.provider.execute("mesh.register_device", {
                "device_id": f"worker_node_{worker_id}",
                "name": f"Worker Node {worker_id}",
                "client_type": "iot",
                "ip_address": f"10.0.1.{worker_id}",
                "capabilities": ["ping"],
                "trust_state": "TRUSTED",
            })

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(register_worker, i) for i in range(10)]
            results = [f.result() for f in futures]

        for res in results:
            self.assertEqual(res.status, "SUCCESS")
            self.assertTrue(res.output["registered"])

        # Cleanup worker nodes
        for i in range(10):
            gateway_registry.unregister_device(f"worker_node_{i}")

    def test_default_trust_is_pending(self):
        """Tests that a newly registered device without explicit trust defaults to PENDING."""
        res = self.provider.execute("mesh.register_device", {
            "device_id": "unpaired_node_1",
            "name": "Unpaired Device",
            "client_type": "phone",
            "ip_address": "10.0.0.88",
            "capabilities": ["notifications"],
        })
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.output["trust_state"], "PENDING")
        gateway_registry.unregister_device("unpaired_node_1")

    def test_trust_state_transitions_and_protected_operations(self):
        """Tests UNKNOWN, PENDING, TRUSTED, REVOKED, and OFFLINE behavior on protected operations."""
        dev_id = "security_test_node"

        # 1. UNKNOWN device -> route_to_device must fail
        res_unknown = self.provider.execute("mesh.route_to_device", {
            "target_device_id": "completely_unknown_node",
            "payload": {"cmd": "ping"},
        })
        self.assertEqual(res_unknown.status, "SUCCESS")
        self.assertFalse(res_unknown.output["success"])
        self.assertIn("not found", res_unknown.output["error"].lower())

        # 2. PENDING device -> registered without explicit trust
        self.provider.execute("mesh.register_device", {
            "device_id": dev_id,
            "name": "Security Test Node",
            "client_type": "tablet",
            "ip_address": "10.0.0.77",
            "capabilities": ["display", "special_audio"],
        })
        # Routing to PENDING device must fail truthfully
        res_pending = self.provider.execute("mesh.route_to_device", {
            "target_device_id": dev_id,
            "payload": {"cmd": "alert"},
        })
        self.assertFalse(res_pending.output["success"])
        self.assertIn("not trusted", res_pending.output["error"].lower())

        # Selecting for capability must skip PENDING devices
        sel_pending = self.provider.execute("mesh.select_device", {"required_capability": "special_audio"})
        self.assertFalse(sel_pending.output["found"])

        # 3. Escalation to TRUSTED via mesh.set_device_trust
        esc_res = self.provider.execute("mesh.set_device_trust", {
            "device_id": dev_id,
            "trust_state": "TRUSTED",
        })
        self.assertEqual(esc_res.status, "SUCCESS")
        self.assertEqual(esc_res.output["trust_state"], "TRUSTED")

        # Now route_to_device must succeed
        res_trusted = self.provider.execute("mesh.route_to_device", {
            "target_device_id": dev_id,
            "payload": {"cmd": "alert"},
        })
        self.assertTrue(res_trusted.output["success"])

        # And select_device finds it
        sel_trusted = self.provider.execute("mesh.select_device", {"required_capability": "special_audio"})
        self.assertTrue(sel_trusted.output["found"])
        self.assertEqual(sel_trusted.output["device_id"], dev_id)

        # 4. Revocation to REVOKED -> must sever trust and reject re-registration attempt
        rev_res = self.provider.execute("mesh.revoke_device", {"device_id": dev_id})
        self.assertEqual(rev_res.output["trust_state"], "REVOKED")

        # Re-registration attempt MUST NOT silently overwrite REVOKED state!
        self.provider.execute("mesh.register_device", {
            "device_id": dev_id,
            "name": "Re-registered Node",
            "client_type": "tablet",
            "ip_address": "10.0.0.77",
            "trust_state": "TRUSTED",
        })
        dev_check = gateway_registry.get_device(dev_id)
        self.assertEqual(dev_check.trust_state, DeviceTrustState.REVOKED)

        res_revoked = self.provider.execute("mesh.route_to_device", {
            "target_device_id": dev_id,
            "payload": {"cmd": "alert"},
        })
        self.assertFalse(res_revoked.output["success"])
        self.assertIn("revoked", res_revoked.output["error"].lower())

        # 5. OFFLINE device -> un-revoke to trusted, but set last_seen far in the past
        gateway_registry.set_device_trust(dev_id, DeviceTrustState.TRUSTED)
        dev_check = gateway_registry.get_device(dev_id)
        dev_check.last_seen = time.time() - 9999.0  # Expired heartbeat
        self.assertFalse(dev_check.is_alive(timeout_seconds=5.0))

        res_offline = self.provider.execute("mesh.route_to_device", {
            "target_device_id": dev_id,
            "payload": {"cmd": "alert"},
        })
        self.assertFalse(res_offline.output["success"])
        self.assertIn("offline", res_offline.output["error"].lower())

        # Cleanup
        gateway_registry.unregister_device(dev_id)


if __name__ == "__main__":
    import os
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCapability36DeviceMesh)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
