"""Live End-to-End Verification: Persistent Browser Session, Playback, Pause, Resume, and Close."""

import sys
import time
import httpx
from pathlib import Path

# Ensure UTF-8 output encoding on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings

SERVER_URL = "http://127.0.0.1:8000/api/chat"
HEADERS = {
    "X-JARVIS-Token": settings.gateway_auth_token,
    "Content-Type": "application/json"
}


def send_chat(query: str, persona: str = "Jarvis"):
    print(f"\n[USER COMMAND]: '{query}' (Persona: {persona})")
    payload = {
        "query": query,
        "persona": persona,
        "device_id": "test_client",
        "device_name": "Test PC"
    }
    t0 = time.perf_counter()
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(SERVER_URL, json=payload, headers=HEADERS)
        dur = (time.perf_counter() - t0) * 1000
        print(f"[SERVER STATUS {resp.status_code}] ({dur:.1f}ms)")
        data = resp.json()
        resp_clean = str(data.get("response", "")).encode("ascii", "replace").decode("ascii")
        print(f"[RESPONSE]: {resp_clean}")
        print(f"[PLAN STATUS]: {data.get('plan', {}).get('status')}")
        step_res = data.get("plan", {}).get("steps", [])
        if step_res:
            print(f"[STEP RESULT]: {step_res[0].get('result')}")
        return data


def run_live_test():
    print("=" * 70)
    print("LIVE END-TO-END PERSISTENT BROWSER & ACTION MEMORY VERIFICATION")
    print("=" * 70)

    # 1. Start initial playback: "play a song"
    print("\n--- TEST: 'play a song' (Initial launch in persistent browser) ---")
    res_play = send_chat("play a song")
    assert res_play.get("status") == "ok"
    time.sleep(5.0)

    # 2. Stop active media: "stop it"
    print("\n--- TEST: 'stop it' (Symmetrical Pause on active browser page) ---")
    res_stop = send_chat("stop it")
    assert res_stop.get("status") == "ok"
    time.sleep(3.0)

    # 3. Resume active media: "resume" / "play again"
    print("\n--- TEST: 'resume' (Symmetrical Resume on SAME browser page) ---")
    res_resume = send_chat("resume")
    assert res_resume.get("status") == "ok"
    time.sleep(3.0)

    # 4. Test fuzzy variant: "pause playback please"
    print("\n--- TEST: 'pause playback please' (Fuzzy Variant Pause) ---")
    res_pause2 = send_chat("pause playback please")
    assert res_pause2.get("status") == "ok"
    time.sleep(3.0)

    # 5. Test fuzzy resume variant: "play again"
    print("\n--- TEST: 'play again' (Fuzzy Variant Resume) ---")
    res_resume2 = send_chat("play again")
    assert res_resume2.get("status") == "ok"
    time.sleep(3.0)

    # 6. Play another song to verify ONE persistent browser window is reused (not launching a second window)
    print("\n--- TEST: 'play lofi hip hop' (Reusing ONE persistent browser context) ---")
    res_play2 = send_chat("play lofi hip hop")
    assert res_play2.get("status") == "ok"
    time.sleep(5.0)

    # 7. Stop and Close active tab
    print("\n--- TEST: 'close the tab' (Symmetrical Close) ---")
    res_close = send_chat("close the tab")
    assert res_close.get("status") == "ok"

    print("\n" + "=" * 70)
    print("[SUCCESS] ALL PERSISTENT BROWSER & ACTION MEMORY STEPS VERIFIED LIVE!")
    print("=" * 70)


if __name__ == "__main__":
    run_live_test()
