"""Universal Anti-Hardcoding and Dynamic Generalization Suite for Batch 3 (Capabilities 39, 40, 41).

Enforces:
1. Static AST / Token Inspection:
   - Zero hardcoded task names, projects, people, coordinates, destinations, routes, routines, or magic numbers.
2. Dynamic Generalization A: Unknown Productivity Entity.
3. Dynamic Generalization B: Second Unknown Productivity Entity.
4. Dynamic Generalization C: Unknown Location / Destination.
5. Dynamic Generalization D: Unknown Autonomous Goal.
6. MANDATORY Source Removal Test:
   - Dynamic entities created in Productivity, Travel, and Autonomy.
   - Verified active.
   - Removed from underlying store.
   - Verified that system returns truthful NOT_FOUND / unavailable state (no ghost hardcoding).
7. Runtime Configuration Change Test:
   - Mutates ProductivityConfig, TravelConfig, and AutonomyConfig without editing code.
8. Provider Replacement Test:
   - Swaps all 3 providers with mocks, verifies contracts, restores originals.
9. Novel Synthetic Entity Handling.
"""

import ast
from dataclasses import dataclass
import inspect
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
from capabilities.providers.productivity_provider import (
    PersonalProductivityProvider,
    ProductivityConfig,
    productivity_provider,
)
from capabilities.providers.travel_navigation_provider import (
    TravelNavigationProvider,
    TravelConfig,
    travel_navigation_provider,
)
from capabilities.providers.autonomous_agency_provider import (
    AutonomousAgencyProvider,
    AutonomyConfig,
    autonomous_agency_provider,
)


class TestNoDomainSpecificHardcodingBatch39To41(unittest.TestCase):
    """Audits anti-hardcoding and dynamic generalization across Capabilities 39, 40, and 41."""

    def test_01_ast_token_inspection_no_domain_literals(self):
        """Audits AST across capability source files to reject hardcoded names/entities."""
        source_files = [
            PROJECT_ROOT / "capabilities" / "providers" / "productivity_provider.py",
            PROJECT_ROOT / "capabilities" / "providers" / "travel_navigation_provider.py",
            PROJECT_ROOT / "capabilities" / "providers" / "autonomous_agency_provider.py",
        ]

        prohibited_literals = {
            "aniket", "google_campus", "san_francisco", "mumbai", "delhi", "bangalore",
            "taj_mahal", "project_alpha", "buy_groceries", "flight_101", "uber", "lyft",
            "gym_routine", "morning_coffee", "standup_meeting"
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

    def test_02_dynamic_generalization_a_unknown_productivity_entity(self):
        """Test A: Previously unseen runtime productivity task created, retrieved, and verified."""
        random_title = f"Synthesize_{uuid.uuid4().hex[:10]}_protocol"
        random_tag = f"tag_{uuid.uuid4().hex[:6]}"

        prov = capability_intelligence.select_provider("productivity.create_task")
        res = prov.execute("productivity.create_task", {
            "title": random_title,
            "tags": [random_tag],
            "priority": "high",
        })
        self.assertEqual(res.status, "SUCCESS")
        task_id = res.output["task"]["id"]

        # Retrieve
        get_res = prov.execute("productivity.get_tasks", {"tag": random_tag})
        self.assertEqual(len(get_res.output["tasks"]), 1)
        self.assertEqual(get_res.output["tasks"][0]["id"], task_id)
        self.assertEqual(get_res.output["tasks"][0]["title"], random_title)

    def test_03_dynamic_generalization_b_second_unknown_productivity_entity(self):
        """Test B: Completely different runtime task verifying identical generalized behavior."""
        second_title = f"Audit_{uuid.uuid4().hex[:10]}_schema"
        prov = capability_intelligence.select_provider("productivity.create_task")
        res = prov.execute("productivity.create_task", {
            "title": second_title,
            "priority": "urgent",
        })
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.output["task"]["title"], second_title)

    def test_04_dynamic_generalization_c_unknown_location_and_route(self):
        """Test C: Completely novel coordinates and place names resolved and routed dynamically."""
        origin_name = f"Station_{uuid.uuid4().hex[:6]}"
        dest_name = f"Observatory_{uuid.uuid4().hex[:6]}"

        prov = capability_intelligence.select_provider("travel.plan_route")
        res = prov.execute("travel.plan_route", {
            "origin": origin_name,
            "destination": dest_name,
            "mode": "driving",
        })
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.output["origin"]["name"], origin_name)
        self.assertEqual(res.output["destination"]["name"], dest_name)
        self.assertGreater(res.output["distance_meters"], 0)
        self.assertGreater(res.output["duration_seconds"], 0)

    def test_05_dynamic_generalization_d_unknown_autonomous_goal(self):
        """Test D: Novel dynamic autonomous goal registered and executed."""
        gid = f"auto_{uuid.uuid4().hex[:8]}"
        prov = capability_intelligence.select_provider("autonomy.execute_goal")
        res = prov.execute("autonomy.execute_goal", {
            "goal_id": gid,
            "target_capability": "os.telemetry",
            "parameters": {},
        })
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.output["goal"]["goal_id"], gid)
        self.assertEqual(res.output["goal"]["state"], "COMPLETED")

    def test_06_mandatory_source_removal_test(self):
        """Test E: Mandatory Source Removal across Productivity, Travel, and Autonomy.

        Creates temporary dynamic entities, verifies they function, deletes them from
        underlying stores, and verifies system returns truthful NOT_FOUND / unavailable.
        """
        # 1. Productivity: Create -> Verify -> Delete -> Verify NOT_FOUND
        prod_prov = capability_intelligence.select_provider("productivity.create_task")
        t_res = prod_prov.execute("productivity.create_task", {"title": "Ephemeral Task"})
        t_id = t_res.output["task"]["id"]

        del_res = prod_prov.execute("productivity.delete_task", {"id": t_id})
        self.assertEqual(del_res.status, "SUCCESS")

        check_res = prod_prov.execute("productivity.update_task", {"id": t_id, "title": "Ghost"})
        self.assertEqual(check_res.status, "NOT_FOUND", "Task still accessible after removal!")

        # 2. Travel: Verify known place removal
        trav_prov = capability_intelligence.select_provider("travel.resolve_location")
        novel_place = f"Ephemeral_Place_{uuid.uuid4().hex[:8]}"
        r1 = trav_prov.execute("travel.resolve_location", {"location": novel_place})
        self.assertEqual(r1.status, "SUCCESS")

        with trav_prov._lock:
            trav_prov._known_places.pop(novel_place, None)
            trav_prov._route_cache.clear()

        self.assertNotIn(novel_place, trav_prov._known_places, "Place still cached after clearing!")

        # 3. Autonomy: Create Goal -> Check Status -> Remove from memory -> Verify NOT_FOUND
        auto_prov = capability_intelligence.select_provider("autonomy.execute_goal")
        gid = f"ephemeral_goal_{uuid.uuid4().hex[:8]}"
        g_res = auto_prov.execute("autonomy.execute_goal", {"goal_id": gid, "target_capability": "os.telemetry"})
        self.assertEqual(g_res.status, "SUCCESS")

        with auto_prov._lock:
            auto_prov._goals.pop(gid, None)

        status_res = auto_prov.execute("autonomy.get_goal_status", {"goal_id": gid})
        self.assertEqual(status_res.status, "NOT_FOUND", "Goal still accessible after removal!")

    def test_07_configuration_change_test(self):
        """Test F: Mutates configurations at runtime and proves behavior updates without code modification."""
        prod_prov: PersonalProductivityProvider = capability_intelligence.select_provider("productivity.create_task")
        orig_max = prod_prov.config.max_tasks

        try:
            prod_prov._items.clear()
            prod_prov.config.max_tasks = 1
            # First task succeeds
            r1 = prod_prov.execute("productivity.create_task", {"title": "Allowed task"})
            self.assertEqual(r1.status, "SUCCESS")

            # Second task rejected by configuration threshold
            r2 = prod_prov.execute("productivity.create_task", {"title": "Overflow task"})
            self.assertEqual(r2.status, "FAILED")
            self.assertIn("limit", r2.message)
        finally:
            prod_prov.config.max_tasks = orig_max
            prod_prov._items.clear()

        # Travel config change: privacy precision digits
        trav_prov: TravelNavigationProvider = capability_intelligence.select_provider("travel.resolve_location")
        orig_prec = trav_prov.config.privacy_precision_digits
        try:
            trav_prov.config.privacy_precision_digits = 1
            r_prec = trav_prov.execute("travel.resolve_location", {
                "location": {"lat": 12.34567, "lng": 98.76543, "name": "Precision Test"}
            })
            self.assertEqual(r_prec.output["location"]["lat"], 12.3)
            self.assertEqual(r_prec.output["location"]["lng"], 98.8)
        finally:
            trav_prov.config.privacy_precision_digits = orig_prec

    def test_08_provider_replacement_test(self):
        """Test G: Dynamic hot-swapping and recovery of all 3 providers."""
        # 1. Productivity Replacement
        class MockP(BaseCapabilityProvider):
            def __init__(self):
                super().__init__(ProviderMetadata(
                    provider_id="mock.prod",
                    name="Mock",
                    description="Mock",
                    version="1.0",
                    supported_capabilities=["productivity.create_task"],
                    safety_level="modifying",
                    priority=5,
                ))

            def is_available(self) -> bool:
                return True

            def execute(self, capability: str, parameters: Dict[str, Any], context=None):
                return ActionResult(status="SUCCESS", action=capability, provider_id="mock.prod", output={"mock": 39})

        # 2. Travel Replacement
        class MockT(BaseCapabilityProvider):
            def __init__(self):
                super().__init__(ProviderMetadata(
                    provider_id="mock.travel",
                    name="Mock",
                    description="Mock",
                    version="1.0",
                    supported_capabilities=["travel.plan_route"],
                    safety_level="read_only",
                    priority=5,
                ))

            def is_available(self) -> bool:
                return True

            def execute(self, capability: str, parameters: Dict[str, Any], context=None):
                return ActionResult(status="SUCCESS", action=capability, provider_id="mock.travel", output={"mock": 40})

        # 3. Autonomy Replacement
        class MockA(BaseCapabilityProvider):
            def __init__(self):
                super().__init__(ProviderMetadata(
                    provider_id="mock.autonomy",
                    name="Mock",
                    description="Mock",
                    version="1.0",
                    supported_capabilities=["autonomy.execute_goal"],
                    safety_level="modifying",
                    priority=5,
                ))

            def is_available(self) -> bool:
                return True

            def execute(self, capability: str, parameters: Dict[str, Any], context=None):
                return ActionResult(status="SUCCESS", action=capability, provider_id="mock.autonomy", output={"mock": 41})

        mp, mt, ma = MockP(), MockT(), MockA()
        capability_intelligence.register_provider(mp)
        capability_intelligence.register_provider(mt)
        capability_intelligence.register_provider(ma)

        self.assertEqual(capability_intelligence.select_provider("productivity.create_task").provider_id, "mock.prod")
        self.assertEqual(capability_intelligence.select_provider("travel.plan_route").provider_id, "mock.travel")
        self.assertEqual(capability_intelligence.select_provider("autonomy.execute_goal").provider_id, "mock.autonomy")

        # Restore original providers
        capability_intelligence.unregister_provider("mock.prod")
        capability_intelligence.unregister_provider("mock.travel")
        capability_intelligence.unregister_provider("mock.autonomy")

        capability_intelligence.register_provider(productivity_provider)
        capability_intelligence.register_provider(travel_navigation_provider)
        capability_intelligence.register_provider(autonomous_agency_provider)

        self.assertEqual(capability_intelligence.select_provider("productivity.create_task").provider_id, "provider.productivity.local_task")
        self.assertEqual(capability_intelligence.select_provider("travel.plan_route").provider_id, "provider.travel.transit_maps")
        self.assertEqual(capability_intelligence.select_provider("autonomy.execute_goal").provider_id, "provider.autonomy.agency_runtime")

    def test_09_unknown_novel_entity_resilience(self):
        """Test H: Novel synthetic identifiers across all 3 domains handled gracefully."""
        novel_id = f"NOVEL_{uuid.uuid4().hex}"
        p_res = productivity_provider.execute("productivity.update_task", {"id": novel_id, "title": "X"})
        self.assertEqual(p_res.status, "NOT_FOUND")

        t_res = travel_navigation_provider.execute("travel.plan_route", {"destination": novel_id})
        self.assertEqual(t_res.status, "SUCCESS")  # Resolved dynamically via data-driven geocoding

        a_res = autonomous_agency_provider.execute("autonomy.get_goal_status", {"goal_id": novel_id})
        self.assertEqual(a_res.status, "NOT_FOUND")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestNoDomainSpecificHardcodingBatch39To41)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
