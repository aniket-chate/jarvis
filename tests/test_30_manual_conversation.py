"""30-turn manual-use acceptance test for the real JARVIS HTTP gateway."""
import json, os, subprocess, sys, time, urllib.request, uuid
from pathlib import Path

TOKEN = uuid.uuid4().hex + uuid.uuid4().hex
ROOT = Path(__file__).resolve().parents[1]
TEST_NAME = f"jarvis_manual_{uuid.uuid4().hex[:8]}.txt"
RENAMED_NAME = f"jarvis_manual_renamed_{uuid.uuid4().hex[:8]}.txt"
BASE_URL = "http://127.0.0.1:8765/api/chat"
DOCUMENTS = ROOT / "workspace" / "documents"
SERVER_LOG = ROOT / "manual_30_server.log"

COMMANDS = [
    "Hi Jarvis, are you ready?",
    "What is 12 multiplied by 12?",
    f"Create a file named {TEST_NAME} and put this information inside it:\nManual-use acceptance verification.",
    "Read the file I just created.",
    "Show me the file you just created.",
    f"Rename {TEST_NAME} to {RENAMED_NAME}.",
    f"Read {RENAMED_NAME}.",
    f"Delete {RENAMED_NAME}.",
    "yes",
    "List my active alarms.",
    "What is the weather in Pune right now?",
    "What is the latest news about Python?",
    "Open GitHub.",
    "Search for Python files in my documents.",
    "Create a file without telling you its name.",
    "Delete a file that I have not identified.",
    "Send a message to someone saying hello.",
    "Create a reminder without telling you when.",
    "Switch back to the previous Git branch.",
    "What can you do?",
    "Open YouTube.",
    "Show me my active browser tabs.",
    "Open YouTube and play a song.",
    "Show me my active browser tabs.",
    "Pause the song.",
    "Resume the song.",
    "Show me my active browser tabs.",
    "Stop playing.",
    "Open GitHub.",
    "What page am I looking at?",
]

def request(message):
    body = json.dumps({"message": message, "device_id": "manual_30_runtime_qa"}).encode()
    req = urllib.request.Request(
        BASE_URL,
        data=body,
        headers={"Content-Type": "application/json", "X-JARVIS-Token": TOKEN},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.status, json.loads(resp.read().decode()), round((time.perf_counter() - t0) * 1000, 2)

def wait_for_server(server):
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            req = urllib.request.Request("http://127.0.0.1:8765/health", headers={"X-JARVIS-Token": TOKEN})
            with urllib.request.urlopen(req, timeout=3) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(1)
    log_text = SERVER_LOG.read_text(encoding="utf-8", errors="replace") if SERVER_LOG.exists() else ""
    raise RuntimeError(f"JARVIS server did not become reachable.\\n{log_text[-12000:]}")

def summarize(payload):
    plan = payload.get("plan") or {}
    steps = plan.get("steps") or []
    step = steps[0] if steps else {}
    result = step.get("result") or {}
    return {
        "status": payload.get("status"),
        "response": str(payload.get("response", ""))[:600],
        "plan_status": plan.get("status"),
        "agent": step.get("required_agent_type"),
        "action": (step.get("inputs") or {}).get("action"),
        "inputs": step.get("inputs") or {},
        "step_status": step.get("status"),
        "result": result,
        "error": result.get("error"),
    }

def tab_snapshot(summary):
    result = summary.get("result") or {}
    tabs = result.get("tabs")
    if isinstance(tabs, list):
        return len(tabs), [t.get("url", "") for t in tabs if isinstance(t, dict)]
    return None, []

def main():
    os.environ["GATEWAY_AUTH_TOKEN"] = TOKEN
    os.environ.setdefault("JARVIS_LLM_PROVIDER", "ollama")
    os.environ.setdefault("JARVIS_LLM_FALLBACK_ENABLED", "false")
    DOCUMENTS.mkdir(parents=True, exist_ok=True)
    for name in (TEST_NAME, RENAMED_NAME):
        p = DOCUMENTS / name
        if p.exists():
            p.unlink()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["GATEWAY_AUTH_TOKEN"] = TOKEN
    log_handle = SERVER_LOG.open("w", encoding="utf-8")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.app:app", "--host", "127.0.0.1", "--port", "8765"],
        cwd=ROOT, env=env, stdout=log_handle, stderr=subprocess.STDOUT, text=True
    )
    results = []
    browser_tabs_before_play = None
    browser_tabs_after_play = None
    playback_verified = False
    try:
        wait_for_server(server)
        for i, command in enumerate(COMMANDS, 1):
            try:
                status, payload, latency = request(command)
                summary = summarize(payload)
                summary["latency_ms"] = latency
                ok = status == 200 and payload.get("status") == "ok" and summary["plan_status"] in {"completed", "blocked"}
                response = summary["response"].lower()

                if i == 2:
                    ok = ok and "144" in response
                if i == 15:
                    ok = ok and "what should i name the file" in response
                if i == 16:
                    ok = ok and "which file would you like me to delete" in response
                if i == 17:
                    ok = ok and ("recipient" in response or "who should i send the message to" in response)
                if i == 18:
                    ok = ok and "when should i schedule it" in response
                if i == 19:
                    ok = ok and "which branch should i switch back to" in response
                if i == 20:
                    ok = ok and "i can help" in response

                if i == 22:
                    browser_tabs_before_play, _ = tab_snapshot(summary)
                    ok = ok and browser_tabs_before_play is not None and browser_tabs_before_play >= 1

                if i == 23:
                    result = summary.get("result") or {}
                    playback_verified = bool(
                        result.get("is_playing") is True
                        and str(result.get("playback_state", "")).lower() == "playing"
                        and "/watch" in str(result.get("url", ""))
                    )
                    ok = ok and playback_verified

                if i == 24:
                    browser_tabs_after_play, urls = tab_snapshot(summary)
                    ok = ok and browser_tabs_after_play == browser_tabs_before_play
                    ok = ok and any("/watch" in u for u in urls)

                if i == 25:
                    ok = ok and ("paused" in response or "pause" in response)
                if i == 26:
                    ok = ok and ("resumed" in response or "resume" in response)
                if i == 27:
                    _, urls = tab_snapshot(summary)
                    ok = ok and any("/watch" in u for u in urls)
                if i == 28:
                    ok = ok and ("paused" in response or "stopped" in response or "stop" in response)

                results.append((i, command, ok, summary))
                print(f"[{i:02d}] {'PASS' if ok else 'FAIL'} {command}")
                print("     " + json.dumps(summary, ensure_ascii=False, default=str))
            except Exception as exc:
                results.append((i, command, False, {"exception": repr(exc)}))
                print(f"[{i:02d}] FAIL {command}\\n     exception={exc!r}")
    finally:
        for name in (TEST_NAME, RENAMED_NAME):
            p = DOCUMENTS / name
            if p.exists():
                p.unlink()
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        log_handle.close()
        if SERVER_LOG.exists():
            SERVER_LOG.unlink()

    passed = sum(1 for _, _, ok, _ in results if ok)
    print("\n=== JARVIS 30-TURN MANUAL ACCEPTANCE ===")
    print(f"PASSED={passed}/30")
    print(f"PLAYBACK_VERIFIED={playback_verified}")
    print(f"TABS_BEFORE_PLAY={browser_tabs_before_play}")
    print(f"TABS_AFTER_PLAY={browser_tabs_after_play}")
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    if passed != 30 or not playback_verified or browser_tabs_before_play != browser_tabs_after_play:
        sys.exit(1)

if __name__ == "__main__":
    main()
