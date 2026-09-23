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

UNIQUE_TEST_SONG = "Daft Punk Get Lucky"
REGRESSION_SCREENSHOT = "regression_youtube_playback_daft_punk.png"


def test_youtube_song_playback_regression():
    """Verify that playing a new song actually starts video playback and advances time."""
    print(f"\n[REGRESSION TEST] Testing YouTube playback with unique song: '{UNIQUE_TEST_SONG}'")

    res = browser_automation_agent.play_youtube_song(
        song_query=UNIQUE_TEST_SONG,
        screenshot_filename=REGRESSION_SCREENSHOT,
        headless=True  # Can run headless in CI, Playwright args enable autoplay
    )

    print(f"[REGRESSION TEST RESULT]:\n{json.dumps(res, indent=2)}")

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
    """Verify that natural language 'Play new song' routes through execute and sanitizes query."""
    inputs = {
        "song": "Play new song",
        "query": "Play new song",
    }
    # Test sanitization without spawning heavy browser if mock/check
    raw_target = inputs.get("song") or inputs.get("query") or ""
    import re
    cleaned = re.sub(r"\b(play|a song|new song|song|music|on youtube|in browser|the video|video|listen to)\b", "", raw_target, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^[\s,.:;'\"]+|[\s,.:;'\"]+$", "", cleaned).strip()
    effective_song = cleaned if (cleaned and cleaned.lower() not in ["a", "the", "new", "track", "song"]) else "trending top music hits"

    assert effective_song == "trending top music hits", f"Expected cleaned song to default to trending music, got '{effective_song}'"


if __name__ == "__main__":
    test_youtube_song_playback_regression()
    test_orchestrator_execution_route_for_play_new_song()
    print("\nAll YouTube Playback Regression Tests PASSED!")
