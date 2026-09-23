"""Audit Test Suite 10: Provider Replaceability & Decoupling.

Proves that the Cognitive Core does not depend on specific implementations:
1. LLM Provider Replacement:
   - Pluggable Mock LLM replaces OllamaClient without touching Cognitive Core
2. Browser Provider Replacement:
   - Mock Browser Provider replaces ChromeCDPBrowserProvider
3. Search Provider Replacement:
   - Mock Search Provider replaces WebSearchProvider
4. File Provider Replacement:
   - Mock Storage Provider replaces FileDocumentProvider

Enforces Invariant 4: No provider is allowed to dictate Cognitive Core architecture.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from capabilities.intelligence import capability_intelligence
from cognitive.reasoning import reasoning_engine
import capabilities.providers  # Register standard providers


def test_provider_replaceability():
    print("=" * 80)
    print("AUDIT SUITE 10: PROVIDER REPLACEABILITY & ZERO-COUPLING")
    print("=" * 80)

    # 1. LLM Provider Replacement
    print("\n[REPLACE 1/4] Auditing Pluggable LLM Provider Replacement...")
    class MockLLMProvider:
        def generate(self, prompt: str, system: str = "", stream_callback=None) -> str:
            return "MOCK_LLM_DEDUCTIVE_INFERENCE_RESULT"

    original_llm = reasoning_engine.llm
    mock_llm = MockLLMProvider()
    reasoning_engine.set_llm_provider(mock_llm)

    resp = reasoning_engine.reason("What is 2 + 2?", context={})
    assert resp == "MOCK_LLM_DEDUCTIVE_INFERENCE_RESULT"
    print("  LLM provider successfully swapped at runtime -> Cognitive reasoning succeeded.")

    # Restore original LLM
    reasoning_engine.set_llm_provider(original_llm)

    # 2. Browser Provider Replacement
    print("\n[REPLACE 2/4] Auditing Browser Provider Replacement...")
    class MockBrowserProvider(BaseCapabilityProvider):
        def __init__(self):
            super().__init__(
                ProviderMetadata(
                    provider_id="provider.browser.mock_custom",
                    name="Mock Custom Browser",
                    supported_capabilities=["browser.playback", "browser.navigate"],
                    priority=1,  # Lower number = higher priority than default Chrome CDP (10)
                )
            )
        def is_available(self) -> bool:
            return True
        def execute(self, capability, parameters, context=None):
            return ActionResult(status="SUCCESS", output="MOCK_BROWSER_NAVIGATED", message="Mock browser navigated")

    mock_browser = MockBrowserProvider()
    capability_intelligence.register_provider(mock_browser)

    selected_browser = capability_intelligence.select_provider("browser.playback")
    assert selected_browser.provider_id == "provider.browser.mock_custom"
    res_b = selected_browser.execute("browser.playback", {"query": "classical"})
    assert res_b.output == "MOCK_BROWSER_NAVIGATED"
    print("  Browser provider swapped -> Capability contract preserved.")

    capability_intelligence.unregister_provider(mock_browser.provider_id)
    fallback_b = capability_intelligence.select_provider("browser.playback")
    assert fallback_b.provider_id == "provider.browser.chrome_cdp"
    print("  Unregistering mock browser gracefully restored default Chrome CDP.")

    # 3. Search Provider Replacement
    print("\n[REPLACE 3/4] Auditing Search Provider Replacement...")
    class MockSearchProvider(BaseCapabilityProvider):
        def __init__(self):
            super().__init__(
                ProviderMetadata(
                    provider_id="provider.search.mock_enterprise",
                    name="Mock Enterprise Search",
                    supported_capabilities=["search.web"],
                    priority=1,
                )
            )
        def is_available(self) -> bool:
            return True
        def execute(self, capability, parameters, context=None):
            return ActionResult(status="SUCCESS", output={"results": ["Enterprise Doc 1", "Enterprise Doc 2"]})

    mock_search = MockSearchProvider()
    capability_intelligence.register_provider(mock_search)

    selected_search = capability_intelligence.select_provider("search.web")
    assert selected_search.provider_id == "provider.search.mock_enterprise"
    res_s = selected_search.execute("search.web", {"query": "quarterly earnings"})
    assert len(res_s.output["results"]) == 2
    print("  Search provider swapped -> Capability contract preserved.")

    capability_intelligence.unregister_provider(mock_search.provider_id)
    fallback_s = capability_intelligence.select_provider("search.web")
    assert fallback_s.provider_id == "provider.web.search_fetch"
    print("  Unregistering mock search restored default WebSearchProvider.")

    # 4. File Provider Replacement
    print("\n[REPLACE 4/4] Auditing File Provider Replacement...")
    class MockEncryptedStorageProvider(BaseCapabilityProvider):
        def __init__(self):
            super().__init__(
                ProviderMetadata(
                    provider_id="provider.file.mock_encrypted",
                    name="Mock Encrypted Storage",
                    supported_capabilities=["file.read", "file.create"],
                    priority=1,
                )
            )
        def is_available(self) -> bool:
            return True
        def execute(self, capability, parameters, context=None):
            return ActionResult(status="SUCCESS", output="ENCRYPTED_PAYLOAD_CIPHERTEXT", message="Encrypted file read")

    mock_file = MockEncryptedStorageProvider()
    capability_intelligence.register_provider(mock_file)

    selected_file = capability_intelligence.select_provider("file.read")
    assert selected_file.provider_id == "provider.file.mock_encrypted"
    res_f = selected_file.execute("file.read", {"path": "classified.aes"})
    assert res_f.output == "ENCRYPTED_PAYLOAD_CIPHERTEXT"
    print("  File provider swapped -> Capability contract preserved.")

    capability_intelligence.unregister_provider(mock_file.provider_id)
    fallback_f = capability_intelligence.select_provider("file.read")
    assert fallback_f.provider_id == "provider.file.scoped"
    print("  Unregistering mock storage restored default FileDocumentProvider.")

    print("\n" + "=" * 80)
    print("AUDIT SUITE 10 PASSED: ALL PROVIDERS 100% DECOUPLED & HOT-SWAPPABLE.")
    print("=" * 80)
    os._exit(0)


if __name__ == "__main__":
    test_provider_replaceability()
