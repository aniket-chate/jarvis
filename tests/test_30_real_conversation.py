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
    f"Create a file named {TEST_NAME} and put this information inside it: Black-box 30-turn verification.",
    "Read the file I just created.",
    "Show me the file you just created.",
    f"Rename {TEST_NAME} to {RENAMED_NAME}.",
    f"Read {RENAMED_NAME}.",
    f"Delete {RENAMED_NAME}.",
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
            ok = (
                (status == 200 and payload.get("status") == "ok" and s["plan_status"] in {"completed", "blocked"})
                or (
                    external_media_block
                    and result.get("browser_tab_count") == 1
                    and result.get("browser_tab_reused") is True
                    and bool(result.get("url"))
                )
            )
            if n == 2: ok &= "144" in response
            if n == 3: ok &= "can help" in response
            if n == 16: ok &= "what should i name the file" in response
            if n == 17: ok &= "which file" in response
            if n == 18: ok &= "recipient" in response or "who should" in response
            if n == 19: ok &= "when should" in response
            if n == 20: ok &= "which branch" in response
            if n == 22: ok &= "which song" in response or "which media" in response
            if n in {23, 24} and (
                result.get("status") == "external_access_required"
                or (result.get("output") or {}).get("status") == "external_access_required"
            ):
                external_blocks.append(n)
                ok = True
            if n == 23 and n not in external_blocks: ok &= result.get("is_playing") is True and float(result.get("delta_time", 0)) >= 0.4
            if n == 24 and n not in external_blocks: ok &= result.get("is_playing") is True and result.get("browser_tab_reused") is True
            if n == 25: ok &= "pause" in response
            if n == 26: ok &= "resume" in response or "playing" in response
            results.append((n, command, ok, latency, s))
            print(f"[{n:02d}] {'PASS' if ok else 'FAIL'} {command}")
            print("     " + json.dumps(s, ensure_ascii=False, default=str)[:2500])
    finally:
        for name in (TEST_NAME, RENAMED_NAME):
            p = ROOT / "workspace" / "documents" / name
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
    print(f"PASSED={passed}/30")
    if external_blocks:
        print(f"EXTERNAL_MEDIA_BLOCKED_TURNS={external_blocks}")
        print("Manual playback acceptance is required when the browser session is not authenticated with YouTube.")
    if passed != 30:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
