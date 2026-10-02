"""30-turn real gateway conversation and media tab-reuse regression."""
import json, os, subprocess, sys, time, urllib.request, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = uuid.uuid4().hex + uuid.uuid4().hex
TEST_NAME = f"jarvis_conversation_{uuid.uuid4().hex[:8]}.txt"
RENAMED_NAME = f"jarvis_conversation_renamed_{uuid.uuid4().hex[:8]}.txt"
BASE = "http://127.0.0.1:8765"
LOG = ROOT / "blackbox_30_server.log"

SONG_ONE = os.environ.get("JARVIS_TEST_SONG_1", "music").strip()
SONG_TWO = os.environ.get("JARVIS_TEST_SONG_2", "music").strip()

COMMANDS = [
    "Hi Jarvis, are you ready?",
    "What is 12 multiplied by 12?",
    "What can you do?",
    "What is the weather in Pune right now?",
    "What is the latest news about Python?",
    "Open GitHub.",
    "Search GitHub for FastAPI projects.",
    f"Create a file named {TEST_NAME} in workspace and put this information inside it: Black-box 30-turn verification.",
    "Read the file I just created.",
    "Show me the file you just created.",
    f"Rename {TEST_NAME} to {RENAMED_NAME} in workspace.",
    f"Read {RENAMED_NAME} in workspace.",
    f"Delete {RENAMED_NAME} in workspace.",
    "yes",
    "Search for Python files in my documents.",
    "Create a file without telling you its name.",
    "Delete a file that I have not identified.",
    "Send a message to someone saying hello.",
    "Create a reminder without telling you when.",
    "Switch back to the previous Git branch.",
    "Open YouTube.",
    "Play a song.",
    f"Play {SONG_ONE} on YouTube.",
    f"Play {SONG_TWO} on YouTube.",
    "Pause it.",
    "Resume it.",
    "What page am I looking at?",
    "List my active alarms.",
    "Show CPU and RAM status.",
    "What can you do?",
]

def request(message):
    body = json.dumps({"message": message, "device_id": "blackbox_30_runtime"}).encode()
    req = urllib.request.Request(
        BASE + "/api/chat", data=body,
        headers={"Content-Type": "application/json", "X-JARVIS-Token": TOKEN},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.status, json.loads(resp.read().decode()), (time.perf_counter() - t0) * 1000

def summary(payload):
    plan = payload.get("plan") or {}
    step = (plan.get("steps") or [{}])[0]
    return {
        "response": str(payload.get("response", "")),
        "plan_status": plan.get("status"),
        "action": (step.get("inputs") or {}).get("action"),
        "result": step.get("result") or {},
    }

def main():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["GATEWAY_AUTH_TOKEN"] = TOKEN
    env.setdefault("JARVIS_LLM_PROVIDER", "ollama")
    env.setdefault("JARVIS_LLM_FALLBACK_ENABLED", "false")
    log = LOG.open("w", encoding="utf-8")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.app:app", "--host", "127.0.0.1", "--port", "8765"],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    results = []
    external_blocks = []
    try:
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                req = urllib.request.Request(BASE + "/health", headers={"X-JARVIS-Token": TOKEN})
                with urllib.request.urlopen(req, timeout=3) as r:
                    if r.status == 200:
                        break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError(LOG.read_text(encoding="utf-8", errors="replace")[-12000:])

        for n, command in enumerate(COMMANDS, 1):
            try:
                status, payload, latency = request(command)
            except Exception as exc:
                server_log = LOG.read_text(encoding="utf-8", errors="replace") if LOG.exists() else ""
                print(f"[{n:02d}] HTTP/transport failure: {exc!r}")
                print("SERVER_LOG_TAIL=" + server_log[-12000:])
                raise
            s = summary(payload)
            response = s["response"].lower()
            result = s["result"]
            external_media_block = n in (23, 24) and (
                result.get("status") == "external_access_required"
                or (result.get("output") or {}).get("status") == "external_access_required"
            )
            ok = status == 200 and payload.get("status") == "ok" and s["plan_status"] in {"completed", "blocked"}
            if external_media_block:
                external_blocks.append(n)
                ok = False

            # A completed plan is not evidence that a side effect actually happened.
            result_output = result.get("output") if isinstance(result, dict) else None
            result_success = (
                isinstance(result, dict)
                and (
                    result.get("success") is True
                    or (isinstance(result_output, dict) and result_output.get("success") is True)
                )
            )
            if n == 8:
                ok &= s["action"] == "create" and result_success and TEST_NAME in json.dumps(result, ensure_ascii=False, default=str)
            elif n in (9, 10, 12):
                expected_name = RENAMED_NAME if n == 12 else TEST_NAME
                ok &= s["action"] in {"read", "show"} and result_success
                ok &= expected_name in json.dumps(result, ensure_ascii=False, default=str)
            elif n == 11:
                ok &= s["action"] in {"rename", "rename_file"} and result_success
            elif n == 13:
                ok &= s["action"] == "delete_file"
                ok &= result.get("status") in {"pending_approval", "blocked", "awaiting_confirmation"} or "confirm" in response
            elif n == 14:
                ok &= s["action"] == "delete_file" and result_success
            elif n == 15:
                ok &= s["action"] in {"search", "search_file"} and result_success
            elif n == 29:
                ok &= s["action"] in {"multi_telemetry", "system_status"} and result_success
            if n == 2: ok &= "144" in response
            if n == 3: ok &= "can help" in response
            if n == 16: ok &= "what should i name the file" in response
            if n == 17: ok &= "which file" in response
            if n == 18: ok &= "recipient" in response or "who should" in response
            if n == 19: ok &= "when should" in response
            if n == 20: ok &= "which branch" in response
            if n == 22: ok &= "which song" in response or "which media" in response
            # external_access_required is tracked as blocked, never as a verified playback pass.
            if n == 23 and n not in external_blocks: ok &= result.get("is_playing") is True and float(result.get("delta_time", 0)) >= 0.4
            if n == 24 and n not in external_blocks: ok &= result.get("is_playing") is True and result.get("browser_tab_reused") is True
            if n == 25: ok &= "pause" in response
            if n == 26: ok &= "resume" in response or "playing" in response
            results.append((n, command, ok, latency, s))
            print(f"[{n:02d}] {'PASS' if ok else 'FAIL'} {command}")
            print("     " + json.dumps(s, ensure_ascii=False, default=str)[:2500])
    finally:
        for name in (TEST_NAME, RENAMED_NAME):
            p = ROOT / "workspace" / name
            if p.exists():
                p.unlink()
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()
        if LOG.exists():
            LOG.unlink()

    passed = sum(1 for _, _, ok, _, _ in results if ok)
    ci_skip_external_media = os.environ.get("JARVIS_CI_SKIP_EXTERNAL_MEDIA", "").strip().lower() == "true"
    required_passes = 30 - len(external_blocks) if ci_skip_external_media else 30
    print(f"PASSED={passed}/{required_passes}")
    if external_blocks:
        print(f"EXTERNAL_MEDIA_BLOCKED_TURNS={external_blocks}")
        if ci_skip_external_media:
            print("SKIPPED_EXTERNAL_MEDIA_TURNS=" + json.dumps(external_blocks))
            print("Manual playback acceptance is still required for these blocked turns.")
        else:
            print("Manual playback acceptance is required when the browser session is not authenticated with YouTube.")
    if passed != required_passes:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
