"""Architectural Anti-Hardcoding and Dynamic Generalization Test Suite.

Validates:
1. Universal Anti-Hardcoding Engineering Constraint:
   - Zero domain-specific hard-coding in capability providers and routing.
   - Zero project-specific branching or hardcoded entity bonuses.
   - Configurable dataclasses instead of magic thresholds.
2. Dynamic Generalization (Tests A & B):
   - Project Omega discovered dynamically from data.
   - Project Zenith discovered dynamically from data.
3. Source Removal Truthfulness (Test C):
   - Removed projects cleanly yield NOT_FOUND without code changes.
4. Unknown Entity Handling (Test D):
   - Project Nebula-47 cleanly handled without exceptions or hardcoded paths.
"""

import ast
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from capabilities.providers.personal_search_provider import (
    PersonalSearchProvider,
    PersonalSearchConfig,
)
from capabilities.providers.information_verification_provider import (
    InformationVerificationProvider,
    VerificationConfig,
)
from capabilities.providers.knowledge_synthesis_provider import (
    KnowledgeSynthesisProvider,
)
from agents.personal_knowledge_base import personal_knowledge_base
from orchestrator.intent_arbitrator import intent_arbitrator
from cognitive.understanding import understanding_engine


class TestAntiHardcodingArchitecture(unittest.TestCase):
    """AST and static source code inspection for forbidden domain-specific behavior."""

    def test_no_hardcoded_user_projects_in_code(self):
        """Inspects capability providers and routers for forbidden project literals."""
        forbidden_projects = [
            "facesnap",
            "snapclass",
            "anganwadi",
            "adain",
        ]
        files_to_audit = [
            PROJECT_ROOT / "capabilities" / "providers" / "personal_search_provider.py",
            PROJECT_ROOT / "capabilities" / "providers" / "information_verification_provider.py",
            PROJECT_ROOT / "capabilities" / "providers" / "knowledge_synthesis_provider.py",
            PROJECT_ROOT / "orchestrator" / "intent_arbitrator.py",
            PROJECT_ROOT / "cognitive" / "understanding.py",
            PROJECT_ROOT / "cognitive" / "planning_engine.py",
        ]

        violations = []
        for file_path in files_to_audit:
            self.assertTrue(file_path.exists(), f"File {file_path} must exist.")
            content = file_path.read_text(encoding="utf-8").lower()
            for proj in forbidden_projects:
                if proj in content:
                    violations.append(f"Forbidden project literal '{proj}' found in {file_path.name}")

        self.assertEqual(
            violations,
            [],
            f"Zero domain-specific hardcoding violated! Found:\n" + "\n".join(violations),
        )

    def test_no_query_specific_fallback_entities(self):
        """Ensures no fallback project strings like 'android wake word' or 'JARVIS architecture'."""
        files_to_audit = [
            PROJECT_ROOT / "capabilities" / "providers" / "personal_search_provider.py",
            PROJECT_ROOT / "orchestrator" / "intent_arbitrator.py",
            PROJECT_ROOT / "cognitive" / "understanding.py",
            PROJECT_ROOT / "cognitive" / "planning_engine.py",
        ]
        forbidden_fallbacks = [
            "android wake word",
            '"jarvis architecture"',
            "'jarvis architecture'",
        ]

        violations = []
        for file_path in files_to_audit:
            content = file_path.read_text(encoding="utf-8").lower()
            for fb in forbidden_fallbacks:
                if fb in content:
                    violations.append(f"Hardcoded fallback entity '{fb}' found in {file_path.name}")

        self.assertEqual(
            violations,
            [],
            f"Query-specific fallback entities violated!\n" + "\n".join(violations),
        )

    def test_configuration_dataclasses_present_and_configurable(self):
        """Validates that capability configurations exist and avoid magic constants."""
        search_cfg = PersonalSearchConfig(
            vector_weight=0.50,
            lexical_weight=0.30,
            metadata_match_weight=0.20,
            min_relevance_threshold=0.20,
            default_top_k=7,
        )
        self.assertEqual(search_cfg.default_top_k, 7)
        self.assertEqual(search_cfg.min_relevance_threshold, 0.20)

        provider = PersonalSearchProvider(config=search_cfg)
        self.assertEqual(provider.config.default_top_k, 7)

        verif_cfg = VerificationConfig(
            verified_threshold=0.80,
            supported_threshold=0.50,
            uncertain_threshold=0.20,
            default_max_age_sec=43200.0,
        )
        verif_provider = InformationVerificationProvider(config=verif_cfg)
        self.assertEqual(verif_provider.config.verified_threshold, 0.80)


class TestDynamicEntityGeneralization(unittest.TestCase):
    """Validates dynamic discovery, generalization, removal, and unknown entities."""

    def setUp(self):
        self.provider = PersonalSearchProvider()
        self.storage_dir = personal_knowledge_base.storage_dir
        self.omega_path = self.storage_dir / "project_omega.json"
        self.zenith_path = self.storage_dir / "project_zenith.json"

    def tearDown(self):
        # Clean up dynamically created test files
        for p in [self.omega_path, self.zenith_path]:
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def test_generalization_test_a_project_omega(self):
        """Test A: Add new unknown entity Project Omega -> retrieve dynamically without source changes."""
        omega_data = {
            "id": "project_omega",
            "title": "Project Omega",
            "content": "Project Omega is an advanced quantum key distribution cryptographic protocol written in Rust.",
            "tags": ["quantum", "cryptography", "omega", "rust"],
            "category": "quantum_security",
            "namespace": "projects",
            "confidence": "high",
            "source": "project_omega.json",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        with open(self.omega_path, "w", encoding="utf-8") as f:
            json.dump(omega_data, f, indent=2)

        # Query for Project Omega
        res = self.provider.execute(
            "search.personal_vector",
            {"query": "Tell me about Project Omega", "top_k": 3},
        )
        self.assertEqual(res.status, "SUCCESS")
        self.assertTrue(res.output["found"], "Project Omega must be discovered from indexed data.")
        self.assertGreater(res.output["count"], 0)
        top_match = res.output["results"][0]
        self.assertIn("omega", top_match["title"].lower())
        self.assertIn("quantum", top_match["content"].lower())
        self.assertEqual(top_match["project_association"], "quantum_security")

    def test_generalization_test_b_project_zenith(self):
        """Test B: Add unrelated entity Project Zenith -> retrieve dynamically without source changes."""
        zenith_data = {
            "id": "project_zenith",
            "title": "Project Zenith",
            "content": "Project Zenith implements autonomous satellite constellation attitude tracking algorithms using Kalman filters.",
            "tags": ["aerospace", "satellite", "zenith", "attitude"],
            "category": "aerospace_systems",
            "namespace": "projects",
            "confidence": "high",
            "source": "project_zenith.json",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        with open(self.zenith_path, "w", encoding="utf-8") as f:
            json.dump(zenith_data, f, indent=2)

        res = self.provider.execute(
            "search.personal_vector",
            {"query": "Tell me about Project Zenith", "top_k": 3},
        )
        self.assertEqual(res.status, "SUCCESS")
        self.assertTrue(res.output["found"], "Project Zenith must be discovered dynamically.")
        self.assertGreater(res.output["count"], 0)
        top_match = res.output["results"][0]
        self.assertIn("zenith", top_match["title"].lower())
        self.assertIn("satellite", top_match["content"].lower())
        self.assertEqual(top_match["project_association"], "aerospace_systems")

    def test_source_removal_test_c_truthful_not_found(self):
        """Test C: Remove entity data -> capability must stop returning it (truthful NOT_FOUND)."""
        # Ensure files are removed
        for p in [self.omega_path, self.zenith_path]:
            if p.exists():
                p.unlink()

        res_omega = self.provider.execute(
            "search.personal_vector",
            {"query": "Tell me about Project Omega", "top_k": 3},
        )
        self.assertEqual(res_omega.status, "SUCCESS")
        self.assertFalse(res_omega.output["found"], "Deleted Project Omega must return found=False.")
        self.assertEqual(res_omega.output["count"], 0)

        res_zenith = self.provider.execute(
            "search.personal_vector",
            {"query": "Tell me about Project Zenith", "top_k": 3},
        )
        self.assertEqual(res_zenith.status, "SUCCESS")
        self.assertFalse(res_zenith.output["found"], "Deleted Project Zenith must return found=False.")
        self.assertEqual(res_zenith.output["count"], 0)

    def test_unknown_entity_test_d_nebula_47(self):
        """Test D: Random unknown entity Project Nebula-47 behaves normally without error."""
        res = self.provider.execute(
            "search.personal_vector",
            {"query": "Tell me about Project Nebula-47", "top_k": 3},
        )
        self.assertEqual(res.status, "SUCCESS")
        self.assertFalse(res.output["found"])
        self.assertEqual(res.output["count"], 0)
        self.assertEqual(res.output["results"], [])


class TestUniversalIntentArbitration(unittest.TestCase):
    """Validates that routing and understanding dynamically extract any entity name."""

    def test_arbitrator_extracts_unknown_projects(self):
        """Intent arbitrator dynamically extracts any project name into personal_search."""
        queries = [
            ("Tell me about Project Omega", "Omega"),
            ("What was my Project Zenith?", "Zenith"),
            ("What do you know about Project Nebula-47?", "Nebula-47"),
            ("Show me the project I worked on", "show me the project i worked on"),
        ]
        for q, expected_token in queries:
            intent = intent_arbitrator.arbitrate(q)
            self.assertEqual(
                intent.domain,
                "personal_search",
                f"Query '{q}' must route to personal_search, got {intent.domain}",
            )
            self.assertIn(
                expected_token.lower(),
                intent.target.lower(),
                f"Target '{intent.target}' must contain entity '{expected_token}'",
            )

    def test_synthesis_arbitration_with_dynamic_projects(self):
        """Arbitrator dynamically extracts arbitrary personal and external query parts."""
        q = "Compare my Project Omega with current quantum encryption standards"
        intent = intent_arbitrator.arbitrate(q)
        self.assertEqual(intent.domain, "synthesis")
        self.assertEqual(intent.action, "personal_and_external_synthesis")
        self.assertIn("omega", intent.params["personal_query"].lower())
        self.assertIn("quantum", intent.params["external_query"].lower())

    def test_cognitive_understanding_with_dynamic_projects(self):
        """Cognitive understanding classifies dynamic unknown project entities."""
        c_intent = understanding_engine.understand("Tell me about Project Hyperion")
        self.assertEqual(c_intent.domain, "search")
        self.assertEqual(c_intent.action, "search_personal")
        self.assertIn("hyperion", c_intent.target_entity.lower())


if __name__ == "__main__":
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestAntiHardcodingArchitecture))
    suite.addTest(unittest.makeSuite(TestDynamicEntityGeneralization))
    suite.addTest(unittest.makeSuite(TestUniversalIntentArbitration))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
