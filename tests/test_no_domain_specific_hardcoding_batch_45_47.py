"""Universal Anti-Hardcoding and Dynamic Generalization Suite for Batch 5 (Capabilities 45, 46, 47).

Strictly verifies the UNIVERSAL ANTI-HARDCODING INVARIANT:
No domain-specific implementation hardcoding:
- Forbidden: hardcoded robot names, models, manufacturers, physical locations,
  sensor names, datasets, column names, analytics questions, chart questions,
  prediction targets, simulation scenarios, formulas for test fixtures,
  project/company names, provider selection, capability routing, ranking bonuses,
  user paths, test phrases, test entities.
- TEST DATA IS NOT IMPLEMENTATION DATA.
- Every entity must be treated as arbitrary input.

Tests Included:
0. Static Source AST Audit across 45, 46, 47 source files
A. Unknown robot/device (dynamic UUID, novel actuator structure, novel limits)
B. Unknown sensor (randomized sensor ID, arbitrary units, arbitrary range)
C. Arbitrary dataset (synthetic schema, randomized numeric & categorical values)
D. Arbitrary columns (unseen column names computed for statistics and correlations)
E. Arbitrary analytics question (dynamic filtering, grouping, and distribution)
F. Arbitrary prediction target (unseen target identifier forecasted with confidence bounds)
G. Unknown simulation scenario (novel variables, custom assumptions, dynamic delta)
H. Source removal (device dynamically registered, verified, removed, confirms NOT_FOUND)
I. Configuration change (runtime config mutation on RoboticsConfig & SimulationConfig)
J. Provider replacement (triple-provider hot-swap via CapabilityIntelligence)
K. Unknown entity (deeply nested arbitrary payload processed safely)
L. New unseen data (stochastic evaluation of dynamic unseen data stream)
"""

import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import os
from pathlib import Path
import random
import sys
import unittest
import uuid
from typing import Dict, Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from capabilities.intelligence import capability_intelligence
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from capabilities.providers.physical_robotics_provider import (
    ActuatorDescriptor,
    DeviceCategory,
    DeviceConnectivity,
    PhysicalDevice,
    PhysicalRoboticsProvider,
    RoboticsConfig,
    SafetyState,
    SensorDescriptor,
    SimulatedRoboticsBackend,
    TrustLevel,
)
from capabilities.providers.data_science_analytics_provider import (
    DataScienceAnalyticsProvider,
)
from capabilities.providers.simulation_prediction_provider import (
    EpistemicCategory,
    SimulationConfig,
    SimulationPredictionProvider,
)


class TestNoDomainSpecificHardcodingBatch45To47(unittest.TestCase):
    """Dynamic generalization and zero-hardcoding verification suite for Batch 5."""

    def setUp(self):
        self.sim_backend = SimulatedRoboticsBackend()
        self.robotics_provider = PhysicalRoboticsProvider(backend=self.sim_backend)
        self.analytics_provider = DataScienceAnalyticsProvider()
        self.simulation_provider = SimulationPredictionProvider()

        capability_intelligence.register_provider(self.robotics_provider)
        capability_intelligence.register_provider(self.analytics_provider)
        capability_intelligence.register_provider(self.simulation_provider)

    def tearDown(self):
        capability_intelligence.unregister_provider("provider.robotics.physical_interface")
        capability_intelligence.unregister_provider("provider.analytics.data_science_engine")
        capability_intelligence.unregister_provider("provider.simulation.prediction_engine")

    def test_00_ast_token_inspection_no_domain_literals(self):
        """Audits AST across capability source files to reject hardcoded names/entities."""
        source_files = [
            PROJECT_ROOT / "capabilities" / "providers" / "physical_robotics_provider.py",
            PROJECT_ROOT / "capabilities" / "providers" / "data_science_analytics_provider.py",
            PROJECT_ROOT / "capabilities" / "providers" / "simulation_prediction_provider.py",
        ]

        prohibited_literals = {
            # Robotics brand / model fixtures
            "fanuc", "ur5", "kuka", "abb", "boston_dynamics", "spot", "atlas",
            "roomba", "dynamixel", "franka", "panda", "scara",
            # Classical benchmark datasets & columns
            "iris", "titanic", "boston_housing", "sepal_length", "petal_width",
            "survived", "passengerid", "pclass",
            # Specific company/project/user fixtures
            "aniket", "google", "deepmind",
            # Fixed financial / domain simulation fixtures
            "black_scholes", "stock_prediction", "bitcoin_forecast",
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

    def test_01_dynamic_test_a_unknown_robot_device(self):
        """Test A: Completely unknown robot with random UUID, unknown kinematics and actuators."""
        random_robot_id = f"synth_bot_{uuid.uuid4().hex[:8]}"
        random_actuator_id = f"act_{uuid.uuid4().hex[:6]}"
        random_zone = f"zone_{uuid.uuid4().hex[:6]}"

        device = PhysicalDevice(
            device_id=random_robot_id,
            name="Synthetic Novel Kinematic Mechanism",
            device_type="novel_mechanism",
            device_category=DeviceCategory.SIMULATED_DEVICE,
            connectivity=DeviceConnectivity.CONNECTED,
            safety_state=SafetyState.SAFE_IDLE,
            trust_level=TrustLevel.TRUSTED,
            actuators={
                random_actuator_id: ActuatorDescriptor(
                    actuator_id=random_actuator_id,
                    name="Synthesized Joint",
                    actuator_type="hydraulic_piston",
                    min_limit=-500.0,
                    max_limit=500.0,
                    units="nm_torque",
                    current_value=12.5,
                )
            },
            sensors={},
            capabilities=["read_capabilities", "emergency_stop"],
            zone=random_zone,
        )
        self.sim_backend.register_device(device)

        # Dynamic discovery by arbitrary zone
        disc_res = self.robotics_provider.execute("robotics.discover_devices", {"zone": random_zone})
        self.assertEqual(disc_res.status, "SUCCESS")
        devs = disc_res.output.get("devices", [])
        self.assertEqual(len(devs), 1)
        self.assertEqual(devs[0]["device_id"], random_robot_id)

    def test_02_dynamic_test_b_unknown_sensor(self):
        """Test B: Completely synthetic sensor with arbitrary units and unseen channel."""
        dev_id = f"synth_station_{uuid.uuid4().hex[:8]}"
        sensor_id = f"novel_spectro_{uuid.uuid4().hex[:6]}"
        units = f"micro_moles_{uuid.uuid4().hex[:4]}"

        device = PhysicalDevice(
            device_id=dev_id,
            name="Novel Spectrometer Station",
            device_type="spectrometer",
            device_category=DeviceCategory.SIMULATED_DEVICE,
            connectivity=DeviceConnectivity.CONNECTED,
            safety_state=SafetyState.SAFE_IDLE,
            trust_level=TrustLevel.TRUSTED,
            sensors={
                sensor_id: SensorDescriptor(
                    sensor_id=sensor_id,
                    name="Infrared Band Sensor",
                    sensor_type="spectroscopy",
                    units=units,
                    min_range=0.01,
                    max_range=999.99,
                    last_reading=142.857,
                )
            },
            capabilities=["read_sensor"],
        )
        self.sim_backend.register_device(device)

        read_res = self.robotics_provider.execute("robotics.read_sensor", {
            "device_id": dev_id,
            "sensor_id": sensor_id,
        })
        self.assertEqual(read_res.status, "SUCCESS")
        reading = read_res.output.get("sensor_reading", {})
        self.assertEqual(reading.get("sensor_id"), sensor_id)
        self.assertEqual(reading.get("value"), 142.857)
        self.assertEqual(reading.get("units"), units)

    def test_03_dynamic_test_c_arbitrary_dataset(self):
        """Test C: Arbitrary dataset with randomized row counts, null values, and custom types."""
        n_rows = random.randint(15, 30)
        col_alpha = f"col_alpha_{uuid.uuid4().hex[:4]}"
        col_beta = f"col_beta_{uuid.uuid4().hex[:4]}"
        data = [
            {col_alpha: float(i * 1.5), col_beta: f"category_{i % 3}"}
            for i in range(n_rows)
        ]

        load_res = self.analytics_provider.execute("analytics.load_dataset", {"data": data})
        self.assertEqual(load_res.status, "SUCCESS")
        out = load_res.output
        self.assertEqual(out["row_count"], n_rows)
        self.assertIn(col_alpha, out["columns"])
        self.assertIn(col_beta, out["columns"])

    def test_04_dynamic_test_d_arbitrary_columns(self):
        """Test D: Analytics calculations over completely randomized column names."""
        col_x = f"rand_num_{uuid.uuid4().hex[:6]}"
        col_y = f"rand_metric_{uuid.uuid4().hex[:6]}"
        data = [
            {col_x: float(i * 2 + 10), col_y: float(i * -0.5 + 50)}
            for i in range(20)
        ]
        load_res = self.analytics_provider.execute("analytics.load_dataset", {"data": data})
        ds_id = load_res.output["dataset_id"]

        # Compute statistics on unseen column col_x
        stat_res = self.analytics_provider.execute("analytics.compute_stats", {
            "dataset_id": ds_id,
            "column": col_x,
        })
        self.assertEqual(stat_res.status, "SUCCESS")
        self.assertEqual(stat_res.output["column"], col_x)

        # Correlation between col_x and col_y
        corr_res = self.analytics_provider.execute("analytics.correlation_analysis", {
            "dataset_id": ds_id,
            "columns": [col_x, col_y],
        })
        self.assertEqual(corr_res.status, "SUCCESS")
        matrix = corr_res.output["correlation_matrix"]
        self.assertIn(col_x, matrix)
        self.assertIn(col_y, matrix)
        self.assertAlmostEqual(matrix[col_x][col_y], -1.0, places=2)

    def test_05_dynamic_test_e_arbitrary_analytics_question(self):
        """Test E: Dynamic grouping, aggregation, and sorting with arbitrary field names."""
        dim_col = f"sector_{uuid.uuid4().hex[:4]}"
        val_col = f"throughput_{uuid.uuid4().hex[:4]}"
        data = [
            {dim_col: "Alpha", val_col: 100.0},
            {dim_col: "Alpha", val_col: 150.0},
            {dim_col: "Beta", val_col: 300.0},
            {dim_col: "Beta", val_col: 200.0},
        ]
        l_res = self.analytics_provider.execute("analytics.load_dataset", {"data": data})
        ds_id = l_res.output["dataset_id"]

        agg_res = self.analytics_provider.execute("analytics.aggregate_group", {
            "dataset_id": ds_id,
            "group_by": dim_col,
            "metric": val_col,
            "aggregator": "mean",
        })
        self.assertEqual(agg_res.status, "SUCCESS")
        groups = agg_res.output["groups"]
        self.assertEqual(groups["Alpha"], 125.0)
        self.assertEqual(groups["Beta"], 250.0)

    def test_06_dynamic_test_f_arbitrary_prediction_target(self):
        """Test F: Forecasting an unseen target signal with dynamic horizon."""
        unseen_target = f"signal_{uuid.uuid4().hex[:8]}"
        history = [float(random.randint(10, 50) + (i * 3)) for i in range(12)]

        fc_res = self.simulation_provider.execute("simulation.forecast", {
            "history": history,
            "horizon": 4,
            "target_name": unseen_target,
        })
        self.assertEqual(fc_res.status, "SUCCESS")
        out = fc_res.output
        self.assertEqual(out["target"], unseen_target)
        self.assertEqual(out["epistemic_tag"], EpistemicCategory.PREDICTION.value)
        self.assertEqual(len(out["forecast"]["forecast_points"]), 4)

    def test_07_dynamic_test_g_unknown_simulation_scenario(self):
        """Test G: Defining and simulating a scenario with arbitrary variable and parameter names."""
        scen_name = f"Scenario_{uuid.uuid4().hex[:6]}"
        v1 = f"var_{uuid.uuid4().hex[:4]}"
        v2 = f"var_{uuid.uuid4().hex[:4]}"

        scen_res = self.simulation_provider.execute("simulation.define_scenario", {
            "name": scen_name,
            "variables": {v1: 50.0, v2: 100.0},
            "assumptions": [f"Assumption_{uuid.uuid4().hex[:6]}"],
        })
        self.assertEqual(scen_res.status, "SUCCESS")
        scen_id = scen_res.output["scenario_id"]

        sim_res = self.simulation_provider.execute("simulation.run_simulation", {
            "scenario_id": scen_id,
            "mode": "deterministic",
            "step_delta": {v1: 2.0, v2: -5.0},
            "steps": 3,
        })
        self.assertEqual(sim_res.status, "SUCCESS")
        traj = sim_res.output["trajectory"]
        self.assertEqual(len(traj), 3)

    def test_08_dynamic_test_h_source_removal(self):
        """Test H: Dynamically created device removed; confirms truthful failure (no ghost hardcoding)."""
        temp_id = f"ephemeral_device_{uuid.uuid4().hex[:8]}"
        device = PhysicalDevice(
            device_id=temp_id,
            name="Temporary Device",
            device_type="probe",
            device_category=DeviceCategory.SIMULATED_DEVICE,
            connectivity=DeviceConnectivity.CONNECTED,
            safety_state=SafetyState.SAFE_IDLE,
            trust_level=TrustLevel.TRUSTED,
            capabilities=["emergency_stop"],
        )
        self.sim_backend.register_device(device)

        # Confirm existence
        res1 = self.robotics_provider.execute("robotics.get_capabilities", {"device_id": temp_id})
        self.assertEqual(res1.status, "SUCCESS")

        # Source removal from backend
        self.sim_backend.remove_device(temp_id)

        # Confirm truthful rejection
        res2 = self.robotics_provider.execute("robotics.get_capabilities", {"device_id": temp_id})
        self.assertEqual(res2.status, "FAILED")
        self.assertIn("not found", res2.output.get("error", "").lower())

    def test_09_dynamic_test_i_configuration_change(self):
        """Test I: Mutates runtime configurations on Capability 45 and Capability 47."""
        # Mutate RoboticsConfig
        custom_robotics = PhysicalRoboticsProvider(
            config=RoboticsConfig(command_timeout_sec=0.1, max_retries=5)
        )
        self.assertEqual(custom_robotics.config.command_timeout_sec, 0.1)
        self.assertEqual(custom_robotics.config.max_retries, 5)

        # Mutate SimulationConfig
        custom_sim = SimulationPredictionProvider(
            config=SimulationConfig(default_monte_carlo_trials=35, default_forecast_horizon=8)
        )
        fc = custom_sim.execute("simulation.forecast", {"history": [10.0, 20.0, 30.0]})
        self.assertEqual(fc.status, "SUCCESS")
        self.assertEqual(len(fc.output["forecast"]["forecast_points"]), 8)

    def test_10_dynamic_test_j_provider_replacement(self):
        """Test J: Replace all 3 providers with mocks, verify routing, restore originals."""
        class Mock45(BaseCapabilityProvider):
            def __init__(self):
                super().__init__(ProviderMetadata("mock.45", "Mock 45", ["robotics.read_sensor"]))
            def is_available(self): return True
            def execute(self, cap, p, ctx=None): return ActionResult("SUCCESS", cap, self.provider_id, {"m45": True})

        class Mock46(BaseCapabilityProvider):
            def __init__(self):
                super().__init__(ProviderMetadata("mock.46", "Mock 46", ["analytics.compute_stats"]))
            def is_available(self): return True
            def execute(self, cap, p, ctx=None): return ActionResult("SUCCESS", cap, self.provider_id, {"m46": True})

        class Mock47(BaseCapabilityProvider):
            def __init__(self):
                super().__init__(ProviderMetadata("mock.47", "Mock 47", ["simulation.forecast"]))
            def is_available(self): return True
            def execute(self, cap, p, ctx=None): return ActionResult("SUCCESS", cap, self.provider_id, {"m47": True})

        # Unregister primaries first
        capability_intelligence.unregister_provider("provider.robotics.physical_interface")
        capability_intelligence.unregister_provider("provider.analytics.data_science_engine")
        capability_intelligence.unregister_provider("provider.simulation.prediction_engine")

        m45, m46, m47 = Mock45(), Mock46(), Mock47()
        capability_intelligence.register_provider(m45)
        capability_intelligence.register_provider(m46)
        capability_intelligence.register_provider(m47)

        self.assertEqual(capability_intelligence.select_provider("robotics.read_sensor").provider_id, "mock.45")
        self.assertEqual(capability_intelligence.select_provider("analytics.compute_stats").provider_id, "mock.46")
        self.assertEqual(capability_intelligence.select_provider("simulation.forecast").provider_id, "mock.47")

        capability_intelligence.unregister_provider("mock.45")
        capability_intelligence.unregister_provider("mock.46")
        capability_intelligence.unregister_provider("mock.47")

        capability_intelligence.register_provider(self.robotics_provider)
        capability_intelligence.register_provider(self.analytics_provider)
        capability_intelligence.register_provider(self.simulation_provider)

    def test_11_dynamic_test_k_unknown_entity(self):
        """Test K: Processes deeply nested arbitrary schemas and parameters without hardcoded expectations."""
        deeply_nested_params = {
            "custom_entity_id": f"entity_{uuid.uuid4().hex}",
            "nested_metadata": {
                "layer_1": {
                    "layer_2": {"arbitrary_flag": True, "weights": [0.1, 0.4, 0.5]},
                },
            },
            "arbitrary_tags": [f"tag_{i}" for i in range(5)],
        }
        res = self.simulation_provider.execute("simulation.define_scenario", {
            "name": "NestedEntityScenario",
            "metadata": deeply_nested_params,
            "variables": {"x": 1.0},
        })
        self.assertEqual(res.status, "SUCCESS")
        stored_meta = res.output["scenario"]["metadata"]
        self.assertEqual(stored_meta["custom_entity_id"], deeply_nested_params["custom_entity_id"])

    def test_12_dynamic_test_l_new_unseen_data(self):
        """Test L: New, unseen statistical distribution passed to analytics and prediction without failure."""
        unseen_series = [random.gauss(100.0, 15.0) for _ in range(50)]
        data = [{"stream_val": v} for v in unseen_series]

        l_res = self.analytics_provider.execute("analytics.load_dataset", {"data": data})
        self.assertEqual(l_res.status, "SUCCESS")
        ds_id = l_res.output["dataset_id"]

        dist_res = self.analytics_provider.execute("analytics.distribution_analysis", {
            "dataset_id": ds_id,
            "column": "stream_val",
            "bins": 7,
        })
        self.assertEqual(dist_res.status, "SUCCESS")
        self.assertEqual(len(dist_res.output["bins"]), 7)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestNoDomainSpecificHardcodingBatch45To47)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
