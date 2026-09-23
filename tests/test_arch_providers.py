"""Architectural Verification Test: Capability Intelligence & Provider Replaceability."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from capabilities.intelligence import capability_intelligence
import capabilities.providers  # Triggers default provider registration


class MockHeadlessBrowserProvider(BaseCapabilityProvider):
    """A replacement browser provider to prove zero-redesign replaceability."""

    def __init__(self):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.browser.mock_headless",
                name="Mock Headless Browser",
                supported_capabilities=["browser.playback", "browser.media_control"],
                priority=1,  # Lower priority number = higher precedence!
                estimated_latency_ms=5.0,
            )
        )

    def is_available(self) -> bool:
        return True

    def execute(self, capability: str, parameters: dict, context=None) -> ActionResult:
        return ActionResult(
            status="SUCCESS",
            output="MOCK_HEADLESS_PLAYBACK_SUCCESS",
            message="Mock headless playback completed in 5ms",
            execution_time_ms=5.0,
        )


def test_capability_intelligence_and_swapping():
    # 1. Discover default provider for browser.playback
    default_provider = capability_intelligence.select_provider("browser.playback")
    assert default_provider is not None
    assert default_provider.provider_id == "provider.browser.chrome_cdp"

    # 2. Dynamically register a replacement provider with higher priority
    mock_provider = MockHeadlessBrowserProvider()
    capability_intelligence.register_provider(mock_provider)

    # 3. Verify Cognitive Core now automatically selects the replacement provider
    selected = capability_intelligence.select_provider("browser.playback")
    assert selected is not None
    assert selected.provider_id == "provider.browser.mock_headless"

    # 4. Execute capability through new provider
    result = selected.execute("browser.playback", {"query": "chill music"})
    assert result.status == "SUCCESS"
    assert result.output == "MOCK_HEADLESS_PLAYBACK_SUCCESS"

    # 5. Unregister mock provider and verify graceful fallback to Chrome CDP
    capability_intelligence.unregister_provider("provider.browser.mock_headless")
    fallback = capability_intelligence.select_provider("browser.playback")
    assert fallback is not None
    assert fallback.provider_id == "provider.browser.chrome_cdp"


    # 6. Verify newly registered providers
    file_p = capability_intelligence.select_provider("file.read")
    assert file_p is not None
    assert file_p.provider_id == "provider.file.scoped"

    search_p = capability_intelligence.select_provider("search.web")
    assert search_p is not None
    assert search_p.provider_id == "provider.web.search_fetch"

    vision_p = capability_intelligence.select_provider("vision.ocr")
    assert vision_p is not None
    assert vision_p.provider_id == "provider.vision.ocr"

    dev_p = capability_intelligence.select_provider("git.status")
    assert dev_p is not None
    assert dev_p.provider_id == "provider.dev.git_code"


if __name__ == "__main__":
    import os
    test_capability_intelligence_and_swapping()
    print("ALL CAPABILITY INTELLIGENCE & PROVIDER REPLACEABILITY TESTS PASSED CLEANLY!")
    os._exit(0)


