"""Dedicated Test Suite for Capability 34: Information Verification.

Audits:
1. Contract & Provider registration in ContractRegistry50 & CapabilityIntelligence.
2. Single-source factual verification with high grounding.
3. Multi-source consensus and agreement verification.
4. Cross-source contradiction detection (Source A != Source B -> CONTRADICTED).
5. Polarity contradiction detection (True vs False, Active vs Inactive).
6. Stale evidence detection against real-time/freshness requirements.
7. Unsupported or incomplete claims (NOT_VERIFIABLE / UNCERTAIN).
8. Reality grounding via WorldModel (verification.observe_reality).
9. Truthful failure handling on empty or corrupt inputs.
10. Multi-threaded concurrency without race conditions.
11. Provider replacement and hot-swapping via CapabilityIntelligence.
"""

import concurrent.futures
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from capabilities.intelligence import capability_intelligence
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from capabilities.contracts.registry_50 import contract_registry_50
from capabilities.providers.information_verification_provider import InformationVerificationProvider
import capabilities.providers  # Trigger default registration


def test_1_contract_and_provider_registration():
    print("\n[TEST 1/11] Auditing Capability 34 Contract & Provider Registration...")
    contract = contract_registry_50.get_contract("34_information_verification")
    assert contract is not None, "Capability 34 contract missing in registry_50!"
    assert contract.capability_id == "34_information_verification"
    assert "verification.information" in contract.supported_operations
    assert "verification.cross_reference_claims" in contract.supported_operations
    assert "verification.observe_reality" in contract.supported_operations

    provider = capability_intelligence.select_provider("verification.information")
    assert provider is not None, "No provider found for verification.information!"
    assert provider.provider_id == "provider.verification.information"
    assert provider.is_available() is True
    print("  PASS: Capability 34 contract and provider discoverable via CapabilityIntelligence.")


def test_2_single_source_verification():
    print("\n[TEST 2/11] Auditing Single-Source Grounded Claim Verification...")
    provider = InformationVerificationProvider()
    sources = [
        {
            "source_id": "pkb_jarvis_core",
            "source_type": "personal_knowledge",
            "title": "JARVIS Personal AI Assistant Architecture",
            "content": "Architecture: Windows backend/laptop + Vivo V29 Android client communicating over WebSocket, plus a mobile PWA with Tailscale mesh networking.",
            "timestamp": time.time(),
        }
    ]
    claim = "JARVIS uses Windows backend and Vivo V29 Android client over WebSocket"
    res = provider.execute("verification.information", {"claim": claim, "sources": sources})
    assert res.status == "SUCCESS"
    out = res.output
    assert out.get("state") in ["VERIFIED", "SUPPORTED"]
    assert out.get("verified") is True
    assert out.get("confidence", 0) >= 0.70
    assert "pkb_jarvis_core" in out.get("provenance", [])
    print(f"  PASS: Claim successfully verified against authoritative source (State: {out['state']}).")


def test_3_multi_source_agreement():
    print("\n[TEST 3/11] Auditing Multi-Source Agreement Verification...")
    provider = InformationVerificationProvider()
    sources = [
        {"source_id": "src_1", "title": "Doc A", "content": "The system runs on port 8000 with FastAPI.", "timestamp": time.time()},
        {"source_id": "src_2", "title": "Doc B", "content": "Uvicorn server listens on port 8000 with FastAPI framework.", "timestamp": time.time()},
    ]
    claim = "The system runs on port 8000 with FastAPI"
    res = provider.execute("verification.information", {"claim": claim, "sources": sources})
    assert res.status == "SUCCESS"
    out = res.output
    assert out.get("state") == "VERIFIED"
    assert out.get("verified") is True
    assert out.get("sources_count") == 2
    print("  PASS: Multi-source consensus verified with high confidence.")


def test_4_cross_source_contradiction():
    print("\n[TEST 4/11] Auditing Cross-Source Conflict & Contradiction Detection...")
    provider = InformationVerificationProvider()
    sources = [
        {"source_id": "src_alpha", "title": "Specification Alpha", "content": "Server runs on port 8000.", "timestamp": time.time()},
        {"source_id": "src_beta", "title": "Specification Beta", "content": "Server runs on port 9000.", "timestamp": time.time()},
    ]
    claim = "Server port specification"
    res = provider.execute("verification.information", {"claim": claim, "sources": sources})
    assert res.status == "SUCCESS"
    out = res.output
    assert out.get("state") == "CONTRADICTED"
    assert out.get("verified") is False
    assert "conflict" in out
    conflict = out["conflict"]
    assert conflict.get("conflict_detected") is True
    print(f"  PASS: Successfully detected numeric conflict: {conflict.get('explanation')}.")


def test_5_polarity_contradiction():
    print("\n[TEST 5/11] Auditing Polarity Contradiction Detection...")
    provider = InformationVerificationProvider()
    sources = [
        {"source_id": "src_pos", "title": "Audit Report 1", "content": "Firewall state is active and enabled.", "timestamp": time.time()},
        {"source_id": "src_neg", "title": "Audit Report 2", "content": "Firewall state is inactive and disabled.", "timestamp": time.time()},
    ]
    res = provider.execute("verification.cross_reference_claims", {"sources": sources})
    assert res.status == "SUCCESS"
    out = res.output
    assert out.get("conflict_detected") is True
    assert out.get("state") == "CONTRADICTED"
    print("  PASS: Polarity contradiction (active vs inactive) correctly flagged.")


def test_6_stale_source_detection():
    print("\n[TEST 6/11] Auditing Stale Source Detection for Time-Sensitive Claims...")
    provider = InformationVerificationProvider()
    old_timestamp = time.time() - 86400 * 5  # 5 days ago
    sources = [
        {"source_id": "weather_cache_old", "title": "Weather Cache", "content": "Weather in Delhi is 32C clear.", "timestamp": old_timestamp}
    ]
    claim = "What is the weather in Delhi right now?"
    res = provider.execute("verification.information", {"claim": claim, "sources": sources, "require_fresh": True})
    assert res.status == "SUCCESS"
    out = res.output
    assert out.get("state") == "STALE"
    assert out.get("verified") is False
    assert "exceeds maximum age" in out.get("reason", "")
    print("  PASS: Stale evidence rejected for real-time query.")


def test_7_unsupported_and_missing_claims():
    print("\n[TEST 7/11] Auditing Unsupported Claim Handling...")
    provider = InformationVerificationProvider()
    sources = [
        {"source_id": "src_food", "title": "Recipe", "content": "Ingredients: flour, sugar, butter, and vanilla.", "timestamp": time.time()}
    ]
    claim = "Nuclear fission requires enriched uranium and graphite rods"
    res = provider.execute("verification.information", {"claim": claim, "sources": sources})
    assert res.status == "SUCCESS"
    out = res.output
    assert out.get("state") in ["NOT_VERIFIABLE", "UNCERTAIN"]
    assert out.get("verified") is False
    print("  PASS: Unsupported claim truthfully evaluated as NOT_VERIFIABLE.")


def test_8_reality_observation():
    print("\n[TEST 8/11] Auditing Physical Reality Observation...")
    provider = InformationVerificationProvider()
    # Reality check for an existing file
    main_path = str(PROJECT_ROOT / "main.py")
    res = provider.execute("verification.observe_reality", {"target_type": "file", "target_name": main_path})
    assert res.status == "SUCCESS"
    assert res.output.get("state") == "VERIFIED"
    assert res.output.get("is_grounded") is True

    # Reality check for a nonexistent file
    fake_path = str(PROJECT_ROOT / "nonexistent_reality_probe_xyz99.txt")
    res_fake = provider.execute("verification.observe_reality", {"target_type": "file", "target_name": fake_path})
    assert res_fake.status == "SUCCESS"
    assert res_fake.output.get("state") == "CONTRADICTED"
    assert res_fake.output.get("is_grounded") is False
    print("  PASS: Reality observation correctly verified physical presence/absence.")


def test_9_truthful_failure_handling():
    print("\n[TEST 9/11] Auditing Truthful Failure Handling...")
    provider = InformationVerificationProvider()
    # Empty claim and empty sources
    res = provider.execute("verification.information", {})
    assert res.status == "FAILED"
    assert "Missing claim" in res.output.get("reason", "")
    print("  PASS: Empty inputs handled truthfully with failure status.")


def test_10_concurrency_stress():
    print("\n[TEST 10/11] Auditing Concurrency & Thread-Safety...")
    provider = InformationVerificationProvider()
    test_cases = [
        ("System port is 8000", [{"title": "S1", "content": "port 8000", "timestamp": time.time()}]),
        ("Python is used", [{"title": "S2", "content": "written in Python", "timestamp": time.time()}]),
        ("Contradiction check", [{"title": "A", "content": "100", "timestamp": time.time()}, {"title": "B", "content": "200", "timestamp": time.time()}]),
        ("Nonexistent claim", [{"title": "C", "content": "apples and oranges", "timestamp": time.time()}]),
    ]

    def run_verify(tc):
        c, s = tc
        return provider.execute("verification.information", {"claim": c, "sources": s})

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(run_verify, tc) for tc in test_cases]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == len(test_cases)
    for r in results:
        assert r.status == "SUCCESS"
    print("  PASS: Concurrent verifications completed without errors.")


def test_11_provider_replacement():
    print("\n[TEST 11/11] Auditing Provider Replacement / Hot-Swapping...")
    class MockVerificationProvider(BaseCapabilityProvider):
        def __init__(self):
            super().__init__(
                ProviderMetadata(
                    provider_id="provider.verification.mock_test",
                    name="Mock Verification Provider",
                    supported_capabilities=["verification.information"],
                    priority=1,
                )
            )

        def is_available(self) -> bool:
            return True

        def execute(self, capability: str, parameters: Dict[str, Any], context=None) -> ActionResult:
            return ActionResult(
                status="SUCCESS",
                output={"mock": True, "state": "VERIFIED"},
                message="Mock verification executed successfully",
            )

    original_provider = capability_intelligence.select_provider("verification.information")
    mock_provider = MockVerificationProvider()

    try:
        capability_intelligence.register_provider(mock_provider)
        selected = capability_intelligence.select_provider("verification.information")
        assert selected.provider_id == "provider.verification.mock_test"
        res = selected.execute("verification.information", {"claim": "test claim"})
        assert res.status == "SUCCESS"
        assert res.output.get("mock") is True
        print("  PASS: Hot-swapped to MockVerificationProvider successfully.")
    finally:
        capability_intelligence.unregister_provider("provider.verification.mock_test")
        capability_intelligence.register_provider(original_provider)
        restored = capability_intelligence.select_provider("verification.information")
        assert restored.provider_id == "provider.verification.information"
        print("  PASS: Restored original InformationVerificationProvider.")


def run_all_tests():
    t_start = time.perf_counter()
    print("============================================================")
    print("CAPABILITY 34: INFORMATION VERIFICATION TEST SUITE")
    print("============================================================")
    test_1_contract_and_provider_registration()
    test_2_single_source_verification()
    test_3_multi_source_agreement()
    test_4_cross_source_contradiction()
    test_5_polarity_contradiction()
    test_6_stale_source_detection()
    test_7_unsupported_and_missing_claims()
    test_8_reality_observation()
    test_9_truthful_failure_handling()
    test_10_concurrency_stress()
    test_11_provider_replacement()
    elapsed = time.perf_counter() - t_start
    print("\n============================================================")
    print(f"CAPABILITY 34 SUITE: 11/11 PASS (Duration: {elapsed:.2f}s)")
    print("============================================================")


if __name__ == "__main__":
    run_all_tests()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
