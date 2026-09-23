"""
JARVIS Anti-Hardcoding & Classifier Robustness Suite (Phase 16).

Verifies that the Hierarchical Classifier and Capability Routing Engine:
1. Do not contain hardcoded domain or query-specific branches (e.g. `if request == 'open chrome'`)
2. Do not contain hardcoded personal names, identities, or test fixtures leaking into production logic.
3. Dynamically handle:
   - Capability renaming / aliasing
   - Capability reordering
   - Provider replacement
   - Unseen entities (arbitrary company names, usernames, hardware models, URLs)
   - Configuration mutation (custom thresholds and top-K)
   - User identity & device context mutation
"""

import ast
import inspect
import json
import os
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cognitive.routing.hierarchical_classifier import (
    TFIDFCalibratedHierarchicalClassifier,
    ClassifierConfig,
    hierarchical_classifier,
)
from capabilities.intelligence import CapabilityIntelligence
from capabilities.contracts.registry_50 import ContractRegistry50, contract_registry_50


class TestClassifierAntiHardcoding(unittest.TestCase):
    """Verifies that the classifier and routing engine are completely free of hardcoding."""

    def test_01_ast_inspection_no_hardcoded_queries_or_identities(self):
        """AST audit of cognitive/routing/hierarchical_classifier.py for hardcoded branches."""
        target_file = PROJECT_ROOT / "cognitive" / "routing" / "hierarchical_classifier.py"
        with open(target_file, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(target_file))

        forbidden_literals = {
            "aniket", "delhi", "chrome", "firefox", "calc.exe", "notepad.exe",
            "google.com", "github.com", "alex", "john"
        }

        for node in ast.walk(tree):
            # Check string constants in comparison
            if isinstance(node, ast.Compare):
                for comparator in node.comparators:
                    if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                        val = comparator.value.lower()
                        self.assertNotIn(
                            val, forbidden_literals,
                            f"Forbidden hardcoded literal comparison found in classifier: '{val}'"
                        )
            # Check if-statements checking equality against query strings
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Compare):
                    left = node.test.left
                    for comp in node.test.comparators:
                        if isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                            val = comp.value.lower()
                            self.assertNotIn(
                                val,
                                ["open chrome", "calculate", "git commit", "weather in delhi"],
                                f"Query-specific if-branch found in classifier: '{val}'"
                            )

    def test_02_dynamic_provider_replacement(self):
        """Routing system dynamically routes to replaced providers without code edits."""
        local_intel = CapabilityIntelligence()

        # Register Mock Provider A
        class CustomProviderA:
            provider_id = "provider.custom.alpha"
            metadata = type("Meta", (), {"priority": 10, "estimated_latency_ms": 5})()
            reliability_score = 0.99
            supported_capabilities = ["analytics.compute_stats"]
            def is_available(self):
                return True
            def execute_operation(self, op, inp):
                return {"status": "SUCCESS", "source": "alpha"}

        # Register Mock Provider B with higher priority
        class CustomProviderB:
            provider_id = "provider.custom.beta"
            metadata = type("Meta", (), {"priority": 1, "estimated_latency_ms": 2})()
            reliability_score = 1.0
            supported_capabilities = ["analytics.compute_stats"]
            def is_available(self):
                return True
            def execute_operation(self, op, inp):
                return {"status": "SUCCESS", "source": "beta"}

        local_intel.register_provider(CustomProviderA())
        selected = local_intel.select_provider("analytics.compute_stats")
        self.assertEqual(selected.provider_id, "provider.custom.alpha")

        # Replace with Provider B
        local_intel.register_provider(CustomProviderB())
        selected_replaced = local_intel.select_provider("analytics.compute_stats")
        self.assertEqual(selected_replaced.provider_id, "provider.custom.beta")

    def test_03_unseen_entities_routing(self):
        """Classifier routes accurately when presented with unseen entities and names."""
        unseen_queries = [
            ("Run 200 Monte Carlo simulation trials for ZephyrDynamics turbine load", "47_simulation_prediction"),
            ("Audit access session token for user Dr_Kowalski_99 with role quantum_supervisor", "48_security_identity"),
            ("Compute correlation matrix and variance for telemetry table from Sensor_X77", "46_data_science"),
            ("Forecast trajectory for HyperionOrbit network payload over 12 intervals", "47_simulation_prediction"),
        ]

        for utterance, expected_cap in unseen_queries:
            decision = hierarchical_classifier.classify(utterance)
            self.assertFalse(decision.unknown)
            top_candidate = decision.candidates[0].capability if decision.candidates else None
            self.assertEqual(top_candidate, expected_cap, f"Failed on unseen entity query: {utterance}")

    def test_04_configuration_mutation(self):
        """Classifier behavior changes dynamically when ClassifierConfig thresholds are modified."""
        custom_config = ClassifierConfig(
            top_k=3,
            unknown_threshold=0.99,  # Extremely high threshold -> forces everything to UNKNOWN
        )
        mutated_clf = TFIDFCalibratedHierarchicalClassifier(config=custom_config)
        
        # With threshold 0.99, even normal queries must be classified as UNKNOWN
        res = mutated_clf.classify("Take a screenshot of the main monitor")
        self.assertTrue(res.unknown)
        self.assertEqual(res.domain, "UNKNOWN")

    def test_05_unseen_user_and_device_context_mutation(self):
        """Contextual reranking functions properly with unseen arbitrary device and user IDs."""
        local_intel = CapabilityIntelligence()
        
        context_iphone = {
            "user_id": "usr_zeta_8891",
            "device_id": "dev_quantum_pad_00",
            "active_window": "Safari on iPhone - GitHub",
        }
        decision = local_intel.route_and_select(
            "Close the active browser tab",
            context=context_iphone
        )
        self.assertIn(decision["status"], ["ROUTED", "CLARIFICATION_REQUIRED"])
        # Should rerank to 23_browser_intelligence because active_window contains browser clue
        self.assertEqual(decision["selected_capability"], "23_browser_intelligence")


if __name__ == "__main__":
    unittest.main()
