"""Live YouTube playback smoke test for a real JARVIS installation.

Requires:
  JARVIS_TEST_SONG_1
  JARVIS_TEST_SONG_2
  JARVIS_API_URL (optional; defaults to the configured local gateway URL)
  JARVIS_AUTH_TOKEN (if the gateway requires authentication)

Unlike CI, this test intentionally fails when real playback cannot be confirmed.
"""
import json
import os
import time
import urllib.request

BASE_URL = os.environ.get("JARVIS_API_URL", "http://127.0.0.1:8000").rstrip("/")
SONG_ONE = os.environ.get("JARVIS_TEST_SONG_1", "").strip()
SONG_TWO = os.environ.get("JARVIS_TEST_SONG_2", "").strip()
TOKEN = os.environ.get("JARVIS_AUTH_TOKEN", "").strip()

if not SONG_ONE or not SONG_TWO:
    raise SystemExit("Set JARVIS_TEST_SONG_1 and JARVIS_TEST_SONG_2 before running the live playback smoke test.")

def chat(message):
    body = json.dumps({"message": message, "device_id": "manual_youtube_smoke"}).encode()
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["X-JARVIS-Token"] = TOKEN
    req = urllib.request.Request(BASE_URL + "/api/chat", data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=180) as response:
        return json.loads(response.read().decode())

def step_result(payload):
    steps = (payload.get("plan") or {}).get("steps") or []
    return (steps[0].get("result") or {}) if steps else {}

first = chat(f"Play {SONG_ONE} on YouTube.")
r1 = step_result(first)
if r1.get("is_playing") is not True:
    raise SystemExit(f"First song was not confirmed playing: {json.dumps(r1, default=str)}")

if r1.get("browser_tab_count") != 1:
    raise SystemExit(f"Expected one browser tab after first playback, got: {r1.get('browser_tab_count')}")

time.sleep(2)

second = chat(f"Play {SONG_TWO} on YouTube.")
r2 = step_result(second)
if r2.get("is_playing") is not True:
    raise SystemExit(f"Second song was not confirmed playing: {json.dumps(r2, default=str)}")
if r2.get("browser_tab_reused") is not True:
    raise SystemExit(f"Second song did not reuse the existing browser tab: {json.dumps(r2, default=str)}")
if r2.get("browser_tab_count") != 1:
    raise SystemExit(f"Expected one browser tab after second playback, got: {r2.get('browser_tab_count')}")

print("LIVE_YOUTUBE_PLAYBACK=PASS")
print(json.dumps({"first": r1, "second": r2}, indent=2, default=str))
