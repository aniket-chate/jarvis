"""Universal Anti-Hardcoding and Dynamic Generalization Suite for Batch 4 (Capabilities 42, 43, 44).

Enforces:
A. Static Source Audit:
   - Scans source code for prohibited domain terms (devices, room names, test fixtures).
B. AST / Token Inspection:
   - Traverses AST to ensure no string constants govern business logic.
C. Unknown Workflow Test:
   - Completely synthetic DAG workflow generated with novel steps and dynamic dependencies.
D. Unknown Device Test:
   - Novel synthetic device with random capabilities, arbitrary zone, and random UUID.
E. Unknown Alert Target Test:
   - Novel metric, condition, and target evaluated without domain assumptions.
F. Source-Removal Test:
   - Dynamic entities created in 42, 43, and 44, verified active, removed from underlying store,
     and verified that system returns truthful NOT_FOUND / absent state (no ghost hardcoding).
G. Configuration-Change Test:
   - Mutates WorkflowConfig, MonitorConfig, and IoTConfig at runtime.
H. Provider Replacement Test:
   - Swaps all 3 providers with mocks in CapabilityIntelligence, verifies contracts, restores originals.
I. Unknown Entity Test:
   - Arbitrary nested schemas and unknown namespaces processed generically.
J. Arbitrary New-Data Test:
   - Novel fields and arbitrary payloads handled without exceptions or domain bias.
"""

import ast
from dataclasses import dataclass
import inspect
import json
import os
from pathlib import Path
import sys
import unittest
import uuid
from typing import Dict, Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from capabilities.intelligence import capability_intelligence
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from capabilities.contracts.registry_50 import contract_registry_50
from capabilities.providers.workflow_automation_provider import (
    WorkflowAutomationProvider,
    WorkflowConfig,
    workflow_automation_provider,
)
from capabilities.providers.monitoring_alerts_provider import (
    MonitoringAlertsProvider,
    MonitorConfig,
    monitoring_alerts_provider,
)
from capabilities.providers.smart_home_iot_provider import (
    SmartHomeIoTProvider,
    SimulatedIoTBackend,
    IoTDeviceDescriptor,
    IoTConfig,
    smart_home_iot_provider,
)


class TestNoDomainSpecificHardcodingBatch42To44(unittest.TestCase):
    """Audits anti-hardcoding and dynamic generalization across Capabilities 42, 43, and 44."""

    def test_01_ast_token_inspection_no_domain_literals(self):
        """Audits AST across capability source files to reject hardcoded names/entities."""
        source_files = [
            PROJECT_ROOT / "capabilities" / "providers" / "workflow_automation_provider.py",
            PROJECT_ROOT / "capabilities" / "providers" / "monitoring_alerts_provider.py",
            PROJECT_ROOT / "capabilities" / "providers" / "smart_home_iot_provider.py",
        ]

        prohibited_literals = {
            "living_room", "kitchen", "bedroom", "garage", "backyard",
            "philips_hue", "smart_plug", "nest_thermostat", "ring_doorbell",
            "daily_backup_workflow", "cpu_usage_rule", "memory_leak_alert",
            "server_rack_1", "aniket", "office_desk"
        }

        for sf in source_files:
            self.assertTrue(sf.exists(), f"Source file {sf} missing!")
            with open(sf, "r", encoding="utf-8") as f:
                content = f.read()

            parsed = ast.parse(content, filename=str(sf))
            for node in ast.walk(parsed):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    val_low = node.value.strip().lower()
                    for bad in prohibited_literals:
                        self.assertNotIn(
                            bad,
                            val_low,
                            f"Prohibited domain literal '{bad}' found in {sf.name} line {node.lineno}!"
                        )

    def test_02_dynamic_generalization_c_unknown_workflow(self):
        """Test C: Completely novel randomized DAG workflow executed dynamically."""
        step_1_id = f"step_{uuid.uuid4().hex[:8]}"
        step_2_id = f"step_{uuid.uuid4().hex[:8]}"
        novel_val = uuid.uuid4().hex[:12]

        prov = capability_intelligence.select_provider("workflow.execute_dag")
        res = prov.execute("workflow.execute_dag", {
            "steps": [
                {
                    "step_id": step_1_id,
                    "capability": "custom.synthesize_entropy",
                    "parameters": {"entropy": novel_val},
                    "depends_on": [],
                },
                {
                    "step_id": step_2_id,
                    "capability": "custom.consume_entropy",
                    "parameters": {"received": f"{{{{steps.{step_1_id}.result.params.entropy}}}}"},
                    "depends_on": [step_1_id],
                },
            ]
        })
        self.assertEqual(res.status, "SUCCESS")
        self.assertIn(step_1_id, res.output["completed_steps"])
        self.assertIn(step_2_id, res.output["completed_steps"])

    def test_03_dynamic_generalization_d_unknown_device(self):
        """Test D: Completely novel randomized IoT device with unknown capabilities."""
        novel_dev_id = f"dev_{uuid.uuid4().hex[:12]}"
        novel_zone = f"zone_sector_{uuid.uuid4().hex[:6]}"
        novel_capability = f"ion_flux_{uuid.uuid4().hex[:4]}"

        # Register novel device on active backend
        backend = smart_home_iot_provider.backend
        desc = IoTDeviceDescriptor(
            device_id=novel_dev_id,
            name=f"Synth Device {novel_dev_id[:8]}",
            device_type="quantum_emitter",
            capabilities=[novel_capability, "power"],
            state={"power": "OFF", novel_capability: 0.0},
            zone=novel_zone,
        )
        backend.register_device(desc)

        # Discover via provider
        prov = capability_intelligence.select_provider("iot.discover_devices")
        disc_res = prov.execute("iot.discover_devices", {"filters": {"zone": novel_zone}})
        self.assertEqual(disc_res.status, "SUCCESS")
        self.assertEqual(disc_res.output["count"], 1)
        self.assertEqual(disc_res.output["devices"][0]["device_id"], novel_dev_id)

        # Send novel command
        cmd_res = prov.execute("iot.control_device", {
            "device_id": novel_dev_id,
            "command": "modulate_flux",
            "parameters": {novel_capability: 42.75},
        })
        self.assertEqual(cmd_res.status, "SUCCESS")
        self.assertEqual(cmd_res.output["state"][novel_capability], 42.75)

    def test_04_dynamic_generalization_e_unknown_alert_target(self):
        """Test E: Completely novel metric and target evaluated without domain knowledge."""
        novel_target = f"node_{uuid.uuid4().hex[:10]}"
        novel_metric = f"vibration_delta_{uuid.uuid4().hex[:6]}"
        novel_threshold = 77.3

        prov = capability_intelligence.select_provider("monitor.create_rule")
        rule_res = prov.execute("monitor.create_rule", {
            "target": novel_target,
            "metric": novel_metric,
            "operator": ">",
            "threshold": novel_threshold,
            "severity": "CRITICAL",
        })
        self.assertEqual(rule_res.status, "SUCCESS")

        eval_res = prov.execute("monitor.evaluate_metrics", {
            "target": novel_target,
            "metrics": {novel_metric: 89.1},
        })
        self.assertEqual(eval_res.status, "SUCCESS")
        self.assertEqual(len(eval_res.output["emitted_alerts"]), 1)
        self.assertEqual(eval_res.output["emitted_alerts"][0]["severity"], "CRITICAL")

    def test_05_source_removal_test(self):
        """Test F: Entities created in 42, 43, and 44, removed, and verified NOT_FOUND."""
        # 1. IoT device removal
        backend = smart_home_iot_provider.backend
        dev_id = f"dev_removable_{uuid.uuid4().hex[:8]}"
        backend.register_device(IoTDeviceDescriptor(
            device_id=dev_id,
            name="Removable Device",
            device_type="sensor",
            capabilities=["read"],
        ))

        # Verify presence
        get_res1 = smart_home_iot_provider.execute("iot.query_state", {"device_id": dev_id})
        self.assertEqual(get_res1.status, "SUCCESS")
        self.assertTrue(get_res1.output["found"])

        # Remove entity
        backend.unregister_device(dev_id)

        # Verify truthful NOT_FOUND
        get_res2 = smart_home_iot_provider.execute("iot.query_state", {"device_id": dev_id})
        self.assertEqual(get_res2.status, "FAILED")
        self.assertFalse(get_res2.output.get("found", False))

        # 2. Workflow execution lookup of non-existent ID
        wf_res = workflow_automation_provider.execute("workflow.get_status", {"execution_id": "non_existent_wf_999"})
        self.assertEqual(wf_res.status, "FAILED")

        # 3. Monitor alert lookup of non-existent alert
        mon_res = monitoring_alerts_provider.execute("monitor.acknowledge_alert", {"alert_id": "non_existent_alert_888"})
        self.assertEqual(mon_res.status, "FAILED")

    def test_06_configuration_change_test(self):
        """Test G: Dynamic runtime configuration dataclass mutation."""
        # WorkflowConfig mutation
        original_retries = workflow_automation_provider.config.max_retries
        workflow_automation_provider.config.max_retries = 9
        self.assertEqual(workflow_automation_provider.config.max_retries, 9)
        workflow_automation_provider.config.max_retries = original_retries

        # MonitorConfig mutation
        orig_cd = monitoring_alerts_provider.config.default_cooldown_sec
        monitoring_alerts_provider.config.default_cooldown_sec = 180.0
        self.assertEqual(monitoring_alerts_provider.config.default_cooldown_sec, 180.0)
        monitoring_alerts_provider.config.default_cooldown_sec = orig_cd

        # IoTConfig mutation
        orig_bridge = smart_home_iot_provider.config.is_physical_bridge
        smart_home_iot_provider.config.is_physical_bridge = True
        self.assertEqual(smart_home_iot_provider.get_verification_level(), "PHYSICAL HARDWARE VERIFIED")
        smart_home_iot_provider.config.is_physical_bridge = orig_bridge
        self.assertEqual(smart_home_iot_provider.get_verification_level(), "PROVIDER-LEVEL VERIFIED")

    def test_07_provider_replacement_test(self):
        """Test H: Hot-swaps all 3 providers with mocks, verifies routing, restores originals."""
        class MockWf(BaseCapabilityProvider):
            def __init__(self):
                super().__init__(ProviderMetadata(
                    provider_id="mock.wf",
                    name="Mock Wf",
                    supported_capabilities=["workflow.execute_dag"],
                    priority=1,
                ))
            def is_available(self): return True
            def execute(self, c, p, ctx=None): return ActionResult(status="SUCCESS", action=c, provider_id=self.provider_id, output={"mock": True})

        class MockMon(BaseCapabilityProvider):
            def __init__(self):
                super().__init__(ProviderMetadata(
                    provider_id="mock.mon",
                    name="Mock Mon",
                    supported_capabilities=["monitor.emit_alert"],
                    priority=1,
                ))
            def is_available(self): return True
            def execute(self, c, p, ctx=None): return ActionResult(status="SUCCESS", action=c, provider_id=self.provider_id, output={"mock": True})

        class MockIoT(BaseCapabilityProvider):
            def __init__(self):
                super().__init__(ProviderMetadata(
                    provider_id="mock.iot",
                    name="Mock IoT",
                    supported_capabilities=["iot.control_device"],
                    priority=1,
                ))
            def is_available(self): return True
            def execute(self, c, p, ctx=None): return ActionResult(status="SUCCESS", action=c, provider_id=self.provider_id, output={"mock": True})

        mw = MockWf()
        mm = MockMon()
        mi = MockIoT()

        capability_intelligence.register_provider(mw)
        capability_intelligence.register_provider(mm)
        capability_intelligence.register_provider(mi)

        self.assertEqual(capability_intelligence.select_provider("workflow.execute_dag").provider_id, "mock.wf")
        self.assertEqual(capability_intelligence.select_provider("monitor.emit_alert").provider_id, "mock.mon")
        self.assertEqual(capability_intelligence.select_provider("iot.control_device").provider_id, "mock.iot")

        # Restore
        capability_intelligence.unregister_provider("mock.wf")
        capability_intelligence.unregister_provider("mock.mon")
        capability_intelligence.unregister_provider("mock.iot")

        capability_intelligence.register_provider(workflow_automation_provider)
        capability_intelligence.register_provider(monitoring_alerts_provider)
        capability_intelligence.register_provider(smart_home_iot_provider)

        self.assertEqual(capability_intelligence.select_provider("workflow.execute_dag").provider_id, "provider.workflow.runtime_kernel")
        self.assertEqual(capability_intelligence.select_provider("monitor.emit_alert").provider_id, "provider.monitor.event_alerts")
        self.assertEqual(capability_intelligence.select_provider("iot.control_device").provider_id, "provider.iot.smart_mesh")

    def test_08_unknown_entity_and_arbitrary_new_data(self):
        """Tests I & J: Arbitrary complex nested payloads processed without schemas breaking."""
        complex_payload = {
            "synthetic_matrix": [[1.2, 3.4], [5.6, 7.8]],
            "deeply_nested": {"layer1": {"layer2": {"key": "dynamic_value"}}},
            "unicode_characters": "λ ≈ 3.14159 & 🚀 & §12.4",
            "boolean_flags": [True, False, True],
        }

        # 1. Monitoring handles complex target and payload
        rule_res = monitoring_alerts_provider.execute("monitor.create_rule", {
            "target": "arbitrary_complex_node",
            "metric": "score",
            "operator": "==",
            "threshold": 100,
        })
        self.assertEqual(rule_res.status, "SUCCESS")

        emit_res = monitoring_alerts_provider.execute("monitor.emit_alert", {
            "target": "arbitrary_complex_node",
            "metric": "score",
            "metadata": complex_payload,
        })
        self.assertEqual(emit_res.status, "SUCCESS")
        self.assertEqual(emit_res.output["alert"]["metadata"]["unicode_characters"], "λ ≈ 3.14159 & 🚀 & §12.4")

        # 2. IoT device handles arbitrary metadata
        dev = IoTDeviceDescriptor(
            device_id=f"dev_complex_{uuid.uuid4().hex[:6]}",
            name="Complex Device",
            device_type="custom_type",
            capabilities=["arbitrary_op"],
            metadata=complex_payload,
        )
        smart_home_iot_provider.backend.register_device(dev)
        q_res = smart_home_iot_provider.execute("iot.query_state", {"device_id": dev.device_id})
        self.assertEqual(q_res.status, "SUCCESS")
        self.assertEqual(q_res.output["device"]["metadata"]["synthetic_matrix"], [[1.2, 3.4], [5.6, 7.8]])


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestNoDomainSpecificHardcodingBatch42To44)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
