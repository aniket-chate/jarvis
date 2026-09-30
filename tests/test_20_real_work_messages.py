"""Black-box regression harness: 20 realistic user messages through the real JARVIS orchestrator.

The suite deliberately avoids external communication and destructive host changes. It exercises
the same PerceptionEvent -> OrchestratorCore -> Planner -> Guardrail -> Executor -> Verifier path
used by the CLI/server, while checking that incomplete requests clarify instead of fabricating data.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.core import orchestrator_core
from perception.events import PerceptionEvent


MESSAGES = [
    ("What is the weather in Jalna today?", "weather_agent"),
    ("What is the latest news about artificial intelligence?", "news_agent"),
    ("Create a file named jarvis_real_work_probe.txt with content: black-box test", "file_agent"),
    ("Read the file I just created", "file_agent"),
    ("Show me the file you just created", "file_agent"),
    ("Read that file", "file_agent"),
    ("Find a file called requirements.txt", "file_agent"),
    ("Draft an email to aniket@example.com saying the deployment test is ready", "communication_agent"),
    ("Draft a WhatsApp message to Aniket saying the regression test is ready", "communication_agent"),
    ("Remind me to review the Jarvis test tomorrow at 9 AM", "scheduler_agent"),
    ("List my active alarms", "scheduler_agent"),
    ("Create a branch called qa/runtime-probe", "dev_tool_agent"),
    ("Switch back", "core_llm_agent"),
    ("Open GitHub", "browser_automation_agent"),
    ("Play YouTube music called instrumental focus", "browser_automation_agent"),
    ("Review this Python code: def add(a, b): return a + b", "core_llm_agent"),
    ("Run it with 10", "core_llm_agent"),
    ("What is 12 multiplied by 12?", "core_llm_agent"),
    ("Delete the file I just created", "file_agent"),
    ("Cancel the pending file deletion", "core_llm_agent"),
]


def send(message: str) -> dict:
    event = PerceptionEvent(
        type="text_input",
        payload={"text": message, "raw_text": message, "source_device": "black_box_20"},
        source="black_box_20",
        active_persona="Jarvis",
    )
    return orchestrator_core.process_event(event)


def main() -> int:
    results = []
    for index, (message, expected_agent) in enumerate(MESSAGES, 1):
        try:
            result = send(message)
            plan = result.get("plan") or {}
            steps = plan.get("steps") or []
            actual_agent = steps[0].get("required_agent_type") if steps else None
            response = str(result.get("response") or "").strip()
            status = str(result.get("status") or "")
            results.append({
                "n": index,
                "message": message,
                "expected_agent": expected_agent,
                "actual_agent": actual_agent,
                "status": status,
                "response": response[:240],
            })
            print(f"[{index:02d}] {message}")
            print(f"     agent={actual_agent!r} status={status!r} response={response[:180]!r}")
        except Exception as exc:
            results.append({
                "n": index,
                "message": message,
                "expected_agent": expected_agent,
                "actual_agent": None,
                "status": "EXCEPTION",
                "response": repr(exc),
            })
            print(f"[{index:02d}] EXCEPTION: {exc!r}")

    # High-level invariants: every message must produce a plan/response path rather than crash.
    failures = []
    for row in results:
        if row["status"] == "EXCEPTION":
            failures.append(row)
        if not row["response"]:
            failures.append({**row, "reason": "empty response"})

    # The incomplete "switch back" must not fabricate a branch.
    switch_back = results[12]
    if switch_back["actual_agent"] != "core_llm_agent" and "clarif" not in switch_back["response"].lower():
        failures.append({**switch_back, "reason": "switch-back fabricated a target or failed to clarify"})

    # Communication drafts must never silently become sends.
    for idx in (7, 8):
        row = results[idx]
        if "send_email" in row["response"].lower() or "send_whatsapp" in row["response"].lower():
            failures.append({**row, "reason": "draft request appears to have become a send"})

    print("\n" + "=" * 90)
    print(f"20-MESSAGE BLACK-BOX RESULT: {20 - len(failures)}/20 passed")
    if failures:
        print("FAILURES:")
        for failure in failures:
            print(failure)

    # Clean up the non-destructive probe if the file agent created it.
    probe_candidates = [
        ROOT / "workspace" / "jarvis_real_work_probe.txt",
        ROOT / "documents" / "jarvis_real_work_probe.txt",
    ]
    for candidate in probe_candidates:
        try:
            if candidate.exists():
                candidate.unlink()
        except OSError:
            pass

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
