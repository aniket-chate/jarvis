"""Black-box 20-turn runtime QA using the real HTTP gateway."""
import json, os, subprocess, sys, time, urllib.request, uuid
from pathlib import Path

TOKEN = uuid.uuid4().hex + uuid.uuid4().hex
ROOT = Path(__file__).resolve().parents[1]
TEST_NAME = f"jarvis_blackbox_{uuid.uuid4().hex[:8]}.txt"
RENAMED_NAME = f"jarvis_blackbox_renamed_{uuid.uuid4().hex[:8]}.txt"
BASE_URL = "http://127.0.0.1:8765/api/chat"
DOCUMENTS = ROOT / "workspace" / "documents"

COMMANDS = [
    "Hi Jarvis, are you ready?",
    "What is 12 multiplied by 12?",
    f"Create a file named {TEST_NAME} and put this information inside it:\nBlack-box runtime verification.",
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
]

def request(message):
    body = json.dumps({"message": message, "device_id": "blackbox_runtime_qa"}).encode()
    req = urllib.request.Request(BASE_URL, data=body, headers={"Content-Type": "application/json", "X-JARVIS-Token": TOKEN})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.status, json.loads(resp.read().decode()), round((time.perf_counter()-t0)*1000, 2)

def wait_for_server():
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            req = urllib.request.Request("http://127.0.0.1:8765/health", headers={"X-JARVIS-Token": TOKEN})
            with urllib.request.urlopen(req, timeout=3) as r:
                if r.status == 200: return
        except Exception:
            time.sleep(1)
    raise RuntimeError("JARVIS server did not become reachable")

def summarize(payload):
    plan = payload.get("plan") or {}
    steps = plan.get("steps") or []
    step = steps[0] if steps else {}
    return {
        "status": payload.get("status"), "type": payload.get("type"),
        "response": str(payload.get("response", ""))[:500],
        "plan_status": plan.get("status"),
        "agent": step.get("required_agent_type"),
        "action": (step.get("inputs") or {}).get("action"),
        "inputs": step.get("inputs") or {},
        "step_status": step.get("status"),
        "error": (step.get("result") or {}).get("error"),
    }

def main():
    os.environ["GATEWAY_AUTH_TOKEN"] = TOKEN
    os.environ.setdefault("JARVIS_LLM_PROVIDER", "ollama")
    os.environ.setdefault("JARVIS_LLM_FALLBACK_ENABLED", "false")
    DOCUMENTS.mkdir(parents=True, exist_ok=True)
    for name in (TEST_NAME, RENAMED_NAME):
        p = DOCUMENTS / name
        if p.exists(): p.unlink()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["GATEWAY_AUTH_TOKEN"] = TOKEN
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.app:app", "--host", "127.0.0.1", "--port", "8765"], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    results = []
    try:
        wait_for_server()
        for i, command in enumerate(COMMANDS, 1):
            try:
                status, payload, latency = request(command)
                summary = summarize(payload)
                summary["latency_ms"] = latency
                ok = status == 200 and payload.get("status") == "ok"
                response = summary["response"].lower()
                if i == 15: ok = ok and ("clarif" in response or "name" in response)
                if i == 16: ok = ok and ("clarif" in response or "which file" in response)
                if i == 17: ok = ok and ("clarif" in response or "recipient" in response or "message" in response)
                if i == 18: ok = ok and ("clarif" in response or "when" in response)
                if i == 19: ok = ok and ("clarif" in response or "branch" in response)
                results.append((i, command, ok, summary))
                print(f"[{i:02d}] {'PASS' if ok else 'FAIL'} {command}")
                print("     " + json.dumps(summary, ensure_ascii=False, default=str))
            except Exception as exc:
                results.append((i, command, False, {"exception": repr(exc)}))
                print(f"[{i:02d}] FAIL {command}\n     exception={exc!r}")
    finally:
        for name in (TEST_NAME, RENAMED_NAME):
            p = DOCUMENTS / name
            if p.exists(): p.unlink()
        server.terminate()
        try: server.wait(timeout=10)
        except subprocess.TimeoutExpired: server.kill()
    passed = sum(1 for _, _, ok, _ in results if ok)
    print("\n=== BLACK-BOX 20-TURN SUMMARY ===")
    print(f"PASSED={passed}/20")
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    if passed != 20: sys.exit(1)

if __name__ == "__main__": main()
