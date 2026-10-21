"""30-turn real gateway conversation and media tab-reuse regression."""
import json, os, subprocess, sys, time, urllib.request, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = uuid.uuid4().hex + uuid.uuid4().hex
TEST_NAME = f"jarvis_conversation_{uuid.uuid4().hex[:8]}.txt"
RENAMED_NAME = f"jarvis_conversation_renamed_{uuid.uuid4().hex[:8]}.txt"
BASE = "http://127.0.0.1:8765"
LOG = ROOT / "blackbox_30_server.log"

SONG_ONE = os.environ.get("JARVIS_TEST_SONG_1", "").strip()
SONG_TWO = os.environ.get("JARVIS_TEST_SONG_2", "").strip()

COMMANDS = [
    "Hi Jarvis, are you ready?",
    "What is 12 multiplied by 12?",
    "What can you do?",
    "What is the weather in Pune right now?",
    "What is the latest news about Python?",
    "Open GitHub.",
    "Search GitHub for FastAPI projects.",
    f"Create a file named {TEST_NAME} and put this information inside it: Black-box 30-turn verification.",
    "yes",
    "Read the file I just created.",
    "Show me the file you just created.",
    f"Rename {TEST_NAME} to {RENAMED_NAME}.",
    "yes",
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
    f"Play {SONG_ONE} on YouTube." if SONG_ONE else "Play a song.",
    f"Play {SONG_TWO} on YouTube." if SONG_TWO else "Play a song.",
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
    dependent_media_blocks = []
    media_query_missing_turns = []
    media_queries_configured = bool(SONG_ONE and SONG_TWO)
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
            external_media_block = n in (25, 26) and (
                result.get("status") == "external_access_required"
                or (result.get("output") or {}).get("status") == "external_access_required"
            )
            media_query_missing = n in (25, 26) and not media_queries_configured
            dependent_media_block = n in (27, 28) and (bool(set(external_blocks).intersection({25, 26})) or not media_queries_configured)
            ok = (
                status == 200
                and payload.get("status") == "ok"
                and s["plan_status"] in {"completed", "blocked", "pending_approval"}
                and not external_media_block
                and not dependent_media_block
                and not media_query_missing
            )
            if external_media_block:
                external_blocks.append(n)
            if dependent_media_block:
                dependent_media_blocks.append(n)
            if media_query_missing:
                media_query_missing_turns.append(n)
            if n == 2: ok &= "144" in response
            if n == 3: ok &= "can help" in response
            if n == 8: ok &= s["plan_status"] == "pending_approval" and "confirm" in response
            if n == 9: ok &= "successfully created file" in response
            if n == 12: ok &= s["plan_status"] == "pending_approval" and "confirm" in response
            if n == 13: ok &= "successfully renamed" in response
            if n == 15: ok &= s["plan_status"] == "pending_approval" and "confirm" in response
            if n == 16: ok &= "successfully deleted" in response
            if n == 18: ok &= "what should i name the file" in response
            if n == 19: ok &= "which file" in response
            if n == 20: ok &= "recipient" in response or "who should" in response
            if n == 21: ok &= "when should" in response
            if n == 22: ok &= "which branch" in response
            if n == 24: ok &= "which song" in response or "which media" in response
            if n == 25 and media_queries_configured and n not in external_blocks: ok &= result.get("is_playing") is True and float(result.get("delta_time", 0)) >= 0.4
            if n == 26 and media_queries_configured and n not in external_blocks: ok &= result.get("is_playing") is True and result.get("browser_tab_reused") is True
            if n in (25, 26) and not media_queries_configured:
                ok &= "which song" in response or "which media" in response
            if n == 27: ok &= "pause" in response
            if n == 28: ok &= "resume" in response or "playing" in response
            results.append((n, command, ok, latency, s))
            print(f"[{n:02d}] {'PASS' if ok else 'FAIL'} {command}")
            print("     " + json.dumps(s, ensure_ascii=False, default=str)[:2500])
    finally:
        for name in (TEST_NAME, RENAMED_NAME):
            p = Path.home() / "Documents" / name
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
    blocked = sorted(set(external_blocks + dependent_media_blocks + media_query_missing_turns))
    print(f"PASSED={passed}/32")
    if external_blocks:
        print(f"EXTERNAL_MEDIA_BLOCKED_TURNS={sorted(set(external_blocks))}")
        print("Blocked playback is reported separately and is never counted as verified playback.")
        print("Manual playback acceptance is required when the browser session is not authenticated with YouTube.")
    if media_query_missing_turns:
        print(f"MEDIA_QUERY_NOT_CONFIGURED_TURNS={sorted(set(media_query_missing_turns))}")
        print("No default song is invented; configure JARVIS_TEST_SONG_1 and JARVIS_TEST_SONG_2 to test live playback.")
    if dependent_media_blocks:
        print(f"DEPENDENT_MEDIA_NOT_VERIFIED_TURNS={sorted(set(dependent_media_blocks))}")
        print("Pause/resume turns are not counted as passing when playback itself was blocked or not configured.")
    allow_blocked = os.environ.get("JARVIS_ALLOW_EXTERNAL_MEDIA_BLOCK", "").strip().lower() == "true"
    only_explicit_media_unverified = (
        allow_blocked
        and len(results) == 32
        and passed + len(blocked) == 32
        and set(external_blocks).issubset({25, 26})
        and set(media_query_missing_turns).issubset({25, 26})
        and set(dependent_media_blocks).issubset({27, 28})
    )
    if passed != 32 and not only_explicit_media_unverified:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
