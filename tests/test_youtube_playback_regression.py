"""Permanent Regression Test for YouTube Song Playback.

Prevents regression where YouTube search result opens but playback does not start.
Validates:
1. Fast-path browser navigation and first result selection.
2. User gesture activation and YouTube Player API playVideo invocation.
3. Actual playback progression (currentTime advances by >= 0.4s between samples, paused == False).
4. Screenshot proof capturing the active playing state.
5. Operates on a new, unique song query to avoid test caching / over-tuning.
"""

import os
import sys
import json
try:
    import pytest
except ImportError:
    pytest = None
from pathlib import Path

# Ensure project root is on PYTHONPATH
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.browser_automation_agent import browser_automation_agent

UNIQUE_TEST_SONG = os.environ.get("JARVIS_PLAYBACK_TEST_QUERY", "").strip()
REGRESSION_SCREENSHOT = f"regression_youtube_playback_{os.getpid()}.png"


def test_youtube_song_playback_regression():
    """Verify that playing a new song actually starts video playback and advances time."""
    if pytest is None:
        raise RuntimeError("pytest is required for the live playback regression test")
    if os.environ.get("JARVIS_ENABLE_LIVE_MEDIA_TESTS", "").strip().lower() != "true" or not UNIQUE_TEST_SONG:
        pytest.skip("Live YouTube playback requires explicit opt-in and JARVIS_PLAYBACK_TEST_QUERY.")
    print("\n[REGRESSION TEST] Testing YouTube playback with the configured query.")

    res = browser_automation_agent.play_youtube_song(
        song_query=UNIQUE_TEST_SONG,
        screenshot_filename=REGRESSION_SCREENSHOT,
        headless=True  # Can run headless in CI, Playwright args enable autoplay
    )

    print(f"[REGRESSION TEST RESULT]:\n{json.dumps(res, indent=2)}")

    if res and (
        res.get("status") == "external_access_required"
        or (res.get("output") or {}).get("status") == "external_access_required"
    ):
        pytest.skip("YouTube requires an authenticated browser session; playback was not verified.")
    if res and res.get("status") == "unavailable":
        pytest.skip(f"Live browser LLM is unavailable: {res.get('error')}")

    # 1. Structural assertions
    assert res is not None, "play_youtube_song returned None"
    assert res.get("success") is True, f"Expected success=True, got error: {res.get('error')}"
    assert res.get("video_title"), "Expected non-empty video_title"

    # 2. Real outcome assertions: Playback must be active and advancing
    assert res.get("is_playing") is True, f"Video is not playing: is_playing={res.get('is_playing')}"
    delta_time = res.get("delta_time", 0.0)
    assert delta_time >= 0.4, f"Video currentTime did not advance during playback verification! delta_time={delta_time:.2f}s"

    # 3. Screenshot artifact proof assertion
    screenshot_path = Path(res.get("screenshot_path", ""))
    assert screenshot_path.exists(), f"Screenshot proof not saved at {screenshot_path}"
    assert screenshot_path.stat().st_size > 5000, f"Screenshot file too small: {screenshot_path.stat().st_size} bytes"

    print(f"PASS: Verified playback for '{res.get('video_title')}' (delta={delta_time:.2f}s). Screenshot: {screenshot_path}")


def test_orchestrator_execution_route_for_play_new_song():
    """Generic 'new song' requests must ask for a choice rather than invent a media query."""
    from orchestrator.intent_arbitrator import IntentArbitrator

    intent = IntentArbitrator().arbitrate("Play new song")
    assert intent.action == "clarification"
    assert intent.needs_clarification is True
    assert intent.clarification_prompt


if __name__ == "__main__":
    test_youtube_song_playback_regression()
    test_orchestrator_execution_route_for_play_new_song()
    print("\nAll YouTube Playback Regression Tests PASSED!")
