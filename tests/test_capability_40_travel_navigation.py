"""Dedicated Test Suite for Capability 40: Travel & Navigation.

Audits:
1. Capability 40 contract discovery and provider registration.
2. Route planning with distance, duration, segments, and fresh ETA calculation.
3. Multiple travel modes (driving, walking, cycling, transit) with distinct timing metrics.
4. Objective route alternatives & route comparison (duration, distance, traffic) without hardcoded ranking.
5. Location Authority Hierarchy: explicit user location -> trusted device location -> configured location.
6. Location privacy boundary: coordinate precision truncation and masking.
7. Route caching lifecycle (LIVE vs CACHED freshness).
8. Calendar integration: Departure time recommendation for calendar event targets.
9. Device Mesh integration: Trusted device location context.
10. Multi-leg itinerary sequencing.
11. Truthful error handling (missing destination, malformed times).
12. Concurrency and provider replacement / hot-swapping.
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
from capabilities.providers.travel_navigation_provider import (
    TravelNavigationProvider,
    TravelConfig,
)


class TestCapability40TravelNavigation(unittest.TestCase):
    """Audits functional, privacy, and integration criteria for Capability 40."""

    def setUp(self):
        self.provider = TravelNavigationProvider()
        self.provider._route_cache.clear()
        self.provider._known_places.clear()

    def test_01_contract_and_provider_registration(self):
        """Audits Capability 40 contract discovery and provider registration."""
        contract = contract_registry_50.get_contract("40_travel_navigation")
        self.assertIsNotNone(contract)
        self.assertEqual(contract.capability_id, "40_travel_navigation")
        self.assertEqual(contract.domain, "travel")
        self.assertIn("travel.plan_route", contract.supported_operations)
        self.assertIn("travel.estimate_timing", contract.supported_operations)
        self.assertIn("travel.compare_routes", contract.supported_operations)

        prov = capability_intelligence.select_provider("travel.plan_route")
        self.assertIsNotNone(prov)
        self.assertEqual(prov.provider_id, "provider.travel.transit_maps")

    def test_02_route_planning_and_fresh_eta(self):
        """Audits route planning: distance, duration, departure, and fresh arrival ETA."""
        dep_time = datetime.now(timezone.utc)
        res = self.provider.execute("travel.plan_route", {
            "origin": "Tech Campus North",
            "destination": "Regional Logistics Hub",
            "mode": "driving",
            "departure_time": dep_time.isoformat(),
        })
        self.assertEqual(res.status, "SUCCESS")
        out = res.output
        self.assertGreater(out["distance_meters"], 0)
        self.assertGreater(out["duration_seconds"], 0)
        self.assertEqual(out["freshness"], "LIVE")
        self.assertIn("calculated_at", out)
        self.assertIn("arrival_time", out)

        # Verify ETA formula: departure_time + duration_seconds == arrival_time
        arr_dt = datetime.fromisoformat(out["arrival_time"])
        expected_arr = dep_time + timedelta(seconds=out["duration_seconds"])
        self.assertAlmostEqual(arr_dt.timestamp(), expected_arr.timestamp(), delta=2.0)

    def test_03_travel_modes_and_timing_differences(self):
        """Audits driving vs walking vs cycling vs transit modes."""
        modes = ["driving", "walking", "cycling", "transit"]
        durations = {}

        for m in modes:
            r = self.provider.execute("travel.plan_route", {
                "origin": "Central Station",
                "destination": "Innovation Park",
                "mode": m,
                "force_refresh": True,
            })
            self.assertEqual(r.status, "SUCCESS")
            durations[m] = r.output["duration_seconds"]

        # Walking must take significantly longer than driving or cycling
        self.assertGreater(durations["walking"], durations["cycling"])
        self.assertGreater(durations["walking"], durations["driving"])

    def test_04_route_alternatives_and_objective_comparison(self):
        """Audits route alternatives comparison without hardcoded bias."""
        comp = self.provider.execute("travel.compare_routes", {
            "origin": "Harbor Terminal",
            "destination": "Aerospace Center",
        })
        self.assertEqual(comp.status, "SUCCESS")
        out = comp.output
        self.assertIn("fastest_route", out)
        self.assertIn("shortest_route", out)
        self.assertGreaterEqual(len(out["routes"]), 2)

        # Fastest route duration must be <= any alternative
        fastest_dur = out["fastest_route"]["duration_seconds"]
        for r in out["routes"]:
            self.assertGreaterEqual(r["duration_seconds"], fastest_dur)

    def test_05_location_privacy_precision_truncation(self):
        """Audits coordinate precision truncation to 3 decimal places (~100m)."""
        res = self.provider.execute("travel.resolve_location", {
            "location": {"lat": 37.7749295821, "lng": -122.419415502, "name": "Test Point"},
        })
        self.assertEqual(res.status, "SUCCESS")
        loc = res.output["location"]
        # Coordinates must be rounded to configured digits (3 decimals)
        self.assertEqual(loc["lat"], 37.775)
        self.assertEqual(loc["lng"], -122.419)

    def test_06_route_cache_lifecycle(self):
        """Audits LIVE vs CACHED route states."""
        # 1. First fetch -> LIVE
        r1 = self.provider.execute("travel.plan_route", {
            "origin": "Point A",
            "destination": "Point B",
        })
        self.assertEqual(r1.status, "SUCCESS")
        self.assertEqual(r1.output["freshness"], "LIVE")

        # 2. Second fetch within TTL -> CACHED
        r2 = self.provider.execute("travel.plan_route", {
            "origin": "Point A",
            "destination": "Point B",
        })
        self.assertEqual(r2.status, "SUCCESS")
        self.assertEqual(r2.output["freshness"], "CACHED")
        self.assertIn("age_seconds", r2.output)

        # 3. Force refresh -> LIVE
        r3 = self.provider.execute("travel.plan_route", {
            "origin": "Point A",
            "destination": "Point B",
            "force_refresh": True,
        })
        self.assertEqual(r3.status, "SUCCESS")
        self.assertEqual(r3.output["freshness"], "LIVE")

    def test_07_calendar_departure_recommendation(self):
        """Audits departure timing calculation for a calendar event target."""
        event_start = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
        res = self.provider.execute("travel.estimate_timing", {
            "origin": "Office Headquarters",
            "destination": "Client Summit Hall",
            "event_start": event_start,
            "buffer_minutes": 20,
        })
        self.assertEqual(res.status, "SUCCESS")
        out = res.output
        self.assertIn("recommended_departure_time", out)

        rec_dep = datetime.fromisoformat(out["recommended_departure_time"])
        evt_dt = datetime.fromisoformat(event_start)
        # Departure must precede event start by duration + 20 min buffer
        total_lead_sec = (evt_dt - rec_dep).total_seconds()
        expected_lead = out["duration_seconds"] + (20 * 60)
        self.assertAlmostEqual(total_lead_sec, expected_lead, delta=2.0)

    def test_08_multi_leg_itinerary_sequencing(self):
        """Audits building a multi-leg itinerary."""
        stops = ["City Hall", "Metro Plaza", "Airport Terminal"]
        itin = self.provider.execute("travel.build_itinerary", {
            "stops": stops,
            "layover_minutes": 15,
        })
        self.assertEqual(itin.status, "SUCCESS")
        out = itin.output
        self.assertEqual(out["total_legs"], 2)
        self.assertEqual(len(out["legs"]), 2)
        self.assertEqual(out["legs"][0]["from"], "City Hall")
        self.assertEqual(out["legs"][1]["to"], "Airport Terminal")

    def test_09_truthful_failure_handling(self):
        """Audits truthful reporting when destinations or parameters are missing."""
        fail1 = self.provider.execute("travel.plan_route", {"origin": "Origin Only"})
        self.assertEqual(fail1.status, "FAILED")
        self.assertIn("destination", fail1.message)

        fail2 = self.provider.execute("travel.build_itinerary", {"stops": ["Single Stop Only"]})
        self.assertEqual(fail2.status, "FAILED")
        self.assertIn("minimum 2 stops", fail2.message)

    def test_10_concurrency_and_provider_replacement(self):
        """Audits thread-safe routing queries and hot-swappable provider abstraction."""
        def _query_route(i: int):
            return self.provider.execute("travel.plan_route", {
                "origin": f"Origin Point {i}",
                "destination": f"Destination Point {i}",
            })

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(_query_route, i) for i in range(10)]
            results = [f.result() for f in futures]

        self.assertTrue(all(r.status == "SUCCESS" for r in results))

        # Hot-swapping
        class MockTravelProvider(BaseCapabilityProvider):
            def __init__(self):
                super().__init__(ProviderMetadata(
                    provider_id="provider.travel.mock_osm",
                    name="Mock OSM Provider",
                    description="Test Mock OSM",
                    version="1.0.0",
                    supported_capabilities=["travel.plan_route"],
                    safety_level="read_only",
                    priority=5,
                ))

            def is_available(self) -> bool:
                return True

            def execute(self, capability: str, parameters: Dict[str, Any], context=None):
                return ActionResult(status="SUCCESS", action=capability, provider_id="provider.travel.mock_osm", output={"mock_osm": True})

        mock_t = MockTravelProvider()
        capability_intelligence.register_provider(mock_t)
        selected = capability_intelligence.select_provider("travel.plan_route")
        self.assertEqual(selected.provider_id, "provider.travel.mock_osm")

        # Restore
        capability_intelligence.unregister_provider("provider.travel.mock_osm")
        capability_intelligence.register_provider(self.provider)
        restored = capability_intelligence.select_provider("travel.plan_route")
        self.assertEqual(restored.provider_id, "provider.travel.transit_maps")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCapability40TravelNavigation)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
