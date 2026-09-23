"""Browser Capability Provider wrapping browser_automation_agent."""

import logging
import time
from typing import Any, Dict, Optional
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from agents.browser_automation_agent import browser_automation_agent

logger = logging.getLogger("JARVIS.Providers.Browser")


class ChromeCDPBrowserProvider(BaseCapabilityProvider):
    """Provides web navigation, YouTube playback, media control, and tab management."""

    def __init__(self):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.browser.chrome_cdp",
                name="Google Chrome CDP Automation",
                supported_capabilities=[
                    "browser.playback",
                    "browser.media_control",
                    "browser.tab_control",
                    "browser.navigate",
                    "browser.search",
                ],
                priority=10,
                estimated_latency_ms=800.0,
            )
        )
        self.agent = browser_automation_agent

    def is_available(self) -> bool:
        return True

    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t_start = time.perf_counter()
        try:
            if capability == "browser.playback":
                query = parameters.get("query", "lofi music")
                res = self.agent.play_youtube_video(query)
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                return ActionResult(status="SUCCESS", output=res, message=str(res), execution_time_ms=elapsed)

            elif capability == "browser.media_control":
                action = parameters.get("action", "pause")
                if "resume" in action:
                    res = self.agent.resume_media()
                else:
                    res = self.agent.pause_media()
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                return ActionResult(status="SUCCESS", output=res, message=str(res), execution_time_ms=elapsed)

            elif capability == "browser.tab_control":
                res = self.agent.close_active_tab()
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                return ActionResult(status="SUCCESS", output=res, message=str(res), execution_time_ms=elapsed)

            elif capability == "browser.navigate":
                url = parameters.get("url") or parameters.get("site") or parameters.get("target") or "https://www.google.com"
                res = self.agent.open_site(site_or_url=url)
                elapsed = (time.perf_counter() - t_start) * 1000
                success = res.get("success", True) if isinstance(res, dict) else True
                self.record_outcome(success)
                msg = res.get("message") or res.get("response") or str(res)
                return ActionResult(status="SUCCESS" if success else "FAILED", output=res, message=str(msg), execution_time_ms=elapsed)

            elif capability == "browser.search":
                query = parameters.get("query") or parameters.get("search_query") or ""
                site = parameters.get("site") or "google"
                res = self.agent.chained_search(site=site, query=query)
                elapsed = (time.perf_counter() - t_start) * 1000
                success = res.get("success", True) if isinstance(res, dict) else True
                self.record_outcome(success)
                msg = res.get("message") or res.get("response") or str(res)
                return ActionResult(status="SUCCESS" if success else "FAILED", output=res, message=str(msg), execution_time_ms=elapsed)

            else:
                elapsed = (time.perf_counter() - t_start) * 1000
                return ActionResult(status="FAILED", output=None, message=f"Unsupported capability: {capability}", execution_time_ms=elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(False)
            return ActionResult(status="FAILED", output=str(e), message=str(e), execution_time_ms=elapsed)

