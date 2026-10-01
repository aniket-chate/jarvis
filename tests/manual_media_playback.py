"""Manual browser acceptance test for real YouTube playback.

Run this on the user's machine with Chrome already running/configured for JARVIS.
The test intentionally refuses to pass on search-only navigation or external-access
blocks. No song title is embedded in source; provide it through the environment.
"""
import os
import sys

from agents.browser_automation_agent import BrowserAutomationAgent
from config.settings import settings


def main() -> int:
    query = os.environ.get("JARVIS_MEDIA_QUERY", "").strip()
    second_query = os.environ.get("JARVIS_MEDIA_QUERY_2", "").strip() or query
    if not query:
        print("Set JARVIS_MEDIA_QUERY to the media query you want to play.")
        return 2

    cfg = settings.integrations.get("browser_automation") or {}
    platform = str(cfg.get("media_platform") or "").strip()
    if not platform:
        print("browser_automation.media_platform is not configured.")
        return 2

    agent = BrowserAutomationAgent()
    first = agent.chained_play_media(site=platform, query=query, headless=False)
    print("FIRST:", first)

    if first.get("status") == "external_access_required":
        print("FAIL: the configured browser session is not authenticated for playback.")
        return 1
    if not first.get("is_playing"):
        print("FAIL: playback was not verified. Search/navigation is not accepted.")
        return 1
    if first.get("browser_tab_count") != 1:
        print("FAIL: first playback did not use exactly one browser tab.")
        return 1

    second = agent.chained_play_media(site=platform, query=second_query, headless=False)
    print("SECOND:", second)

    if second.get("status") == "external_access_required":
        print("FAIL: second playback lost authenticated browser access.")
        return 1
    if not second.get("is_playing"):
        print("FAIL: second playback was not verified.")
        return 1
    if second.get("browser_tab_reused") is not True:
        print("FAIL: second playback did not reuse the existing browser tab.")
        return 1
    if second.get("browser_tab_count") != 1:
        print("FAIL: second playback opened an additional tab.")
        return 1

    print("PASS: real playback verified twice in one browser tab.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
