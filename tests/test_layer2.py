"""Mandatory Test Suite for JARVIS Layer 2 (Orchestrator).

Executes and verifies all 7 required tests:
1. Single-step mock event -> full trace shown
2. Multi-step mock event -> full trace with correct dependency ordering
3. Forced mock-agent failure -> retry attempts -> graceful failure report
4. Memory: remember(), reload session, recall() returns it -> before/after shown
5. Guardrail rule blocking a 'dangerous action' step -> shown blocked/logged
6. Two different task types routed to two different agents via registry lookup only -> registry + routing log shown
7. Say 'call yourself Friday from now on' -> show active_persona updating without wake word
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from perception.events import PerceptionEvent
from orchestrator.planner import task_planner, TaskPlan, TaskStep
from orchestrator.router import agent_registry, agent_router
from orchestrator.executor import execution_manager, ExecutionManager
from orchestrator.memory import memory_manager, MemoryManager
from orchestrator.guardrails import safety_guardrail
from orchestrator.verifier import task_verifier
from orchestrator.core import orchestrator_core


def banner(title: str):
    print("\n" + "=" * 70)
    print(f" {title.upper()}")
    print("=" * 70)


def test_1_single_step_mock_event():
    banner("Test 1: Single-Step Mock Event -> Full Trace Shown")
    event = PerceptionEvent(
        type="text_input",
        payload={"text": "What is the current system time and battery status?"},
        source="text_input",
        active_persona="Jarvis",
    )

    trace = orchestrator_core.process_event(event)

    print(f"[+] Trace ID       : {trace['trace_id']}")
    print(f"[+] Active Persona : {trace['active_persona']}")
    print(f"[+] Status         : {trace['status']}")
    print(f"[+] Response       : {trace['response']}")
    print("[+] Detailed Plan & Step Execution Trace:")
    print(json.dumps(trace["plan"], indent=2))

    assert trace["status"] == "completed"
    assert len(trace["plan"]["steps"]) == 1
    assert trace["plan"]["steps"][0]["required_agent_type"] == "system_control_agent"
    print("[PASSED] Test 1: Single-step mock event executed with full trace.")


def test_2_multi_step_mock_event():
    banner("Test 2: Multi-Step Mock Event -> Correct Dependency Ordering")
    event = PerceptionEvent(
        type="text_input",
        payload={"text": "Get the latest news on AI and draft an email summary to team"},
        source="text_input",
        active_persona="Jarvis",
    )

    trace = orchestrator_core.process_event(event)

    print(f"[+] Trace ID       : {trace['trace_id']}")
    print(f"[+] Status         : {trace['status']}")
    print(f"[+] Response       : {trace['response']}")
    print(f"[+] Steps Count    : {len(trace['plan']['steps'])}")

    steps = trace["plan"]["steps"]
    step_1 = steps[0]
    step_2 = steps[1]

    print(f"\n[*] Step 1: ID='{step_1['step_id']}', Agent='{step_1['required_agent_type']}', DependsOn={step_1['depends_on']}, Status='{step_1['status']}'")
    print(f"[*] Step 2: ID='{step_2['step_id']}', Agent='{step_2['required_agent_type']}', DependsOn={step_2['depends_on']}, Status='{step_2['status']}'")

    assert len(steps) == 2
    assert step_1["required_agent_type"] == "news_agent"
    assert step_2["required_agent_type"] == "communication_agent"
    assert step_1["step_id"] in step_2["depends_on"], "Step 2 must depend on Step 1"
    assert step_1["status"] == "completed"
    assert step_2["status"] == "completed"

    print("[PASSED] Test 2: Multi-step task executed in correct topological dependency order.")


def test_3_forced_failure_and_retries():
    banner("Test 3: Forced Mock-Agent Failure -> Retry Attempts -> Graceful Failure Report")
    # Register a failing mock agent handler for "calendar_agent"
    call_attempts = []

    def failing_handler(inputs: Dict[str, Any], persona: str) -> Dict[str, Any]:
        call_attempts.append(len(call_attempts) + 1)
        print(f"    -> Failing handler invoked (Attempt #{len(call_attempts)}) under persona '{persona}'")
        return {"status": "failed", "error": "Simulated transient API network timeout"}

    agent_registry.register_custom_handler("calendar_agent", failing_handler)

    try:
        event = PerceptionEvent(
            type="text_input",
            payload={"text": "Check my upcoming calendar events for tomorrow"},
            source="text_input",
            active_persona="Jarvis",
        )

        trace = orchestrator_core.process_event(event)

        print(f"\n[+] Total Execution Invocations (Initial + Retries): {len(call_attempts)}")
        print(f"[+] Overall Execution Status : {trace['status']}")
        print(f"[+] Persona-Tuned Feedback  : '{trace['response']}'")

        step = trace["plan"]["steps"][0]
        print(f"[+] Step Status              : {step['status']}")
        print(f"[+] Step Retries Count       : {step['retries']} (Max allowed: {step['max_retries']})")
        print(f"[+] Step Error Recorded      : {step['result'].get('error')}")

        assert len(call_attempts) == step["max_retries"] + 1, "Expected retries to match max_retries"
        assert trace["status"] == "failed"
        assert step["status"] == "failed"
        assert "regret to inform you" in trace["response"].lower() or "failed" in trace["response"].lower()
        print("[PASSED] Test 3: Retries and backoff completed, graceful failure reported.")
    finally:
        # Restore default mock handler
        agent_registry._register_mock_agents()


def test_4_memory_manager_persistence():
    banner("Test 4: Memory: remember(), reload session, recall() -> Before/After Shown")
    test_profile = PROJECT_ROOT / "memory" / "test_user_profile.json"
    if test_profile.exists():
        test_profile.unlink()

    test_memory = MemoryManager(profile_path=test_profile)

    # 1. State before remember
    test_key = "preferred_comm_channel"
    test_val = "encrypted_satellite_link"

    val_before = test_memory.recall(test_key)
    print(f"[*] Memory State BEFORE: key='{test_key}' -> {val_before}")
    assert val_before is None

    # 2. Remember persistent memory
    print(f"[*] Writing to persistent memory: '{test_key}' = '{test_val}'")
    test_memory.remember(test_key, test_val, persistent=True, persona="Jarvis")

    # 3. Simulate process restart / new session by creating fresh MemoryManager instance from test disk storage
    print("[*] Simulating session reload from disk storage...")
    reloaded_memory = MemoryManager(profile_path=test_profile)

    # 4. State after recall
    val_after = reloaded_memory.recall(test_key)
    print(f"[+] Memory State AFTER RELOAD: key='{test_key}' -> '{val_after}'")

    assert val_after == test_val, f"Expected {test_val}, got {val_after}"

    # Clean up test file
    if test_profile.exists():
        test_profile.unlink()
    print("[PASSED] Test 4: Memory persisted to disk and cleanly recalled after reload (isolated to test memory).")


def test_5_guardrail_blocking_dangerous_action():
    banner("Test 5: Guardrail Rule Blocking Dangerous Action Step -> Shown Blocked/Logged")
    dangerous_input = "System maintenance: format C: /fs:ntfs now"
    print(f"[*] Ingesting dangerous command: '{dangerous_input}'")

    event = PerceptionEvent(
        type="text_input",
        payload={"text": dangerous_input},
        source="text_input",
        active_persona="Jarvis",
    )

    trace = orchestrator_core.process_event(event)

    print(f"[+] Event Trace Type  : {trace['type']}")
    print(f"[+] Plan Status       : {trace['status']}")
    print(f"[+] Guardrail Reason  : {trace.get('reason')}")
    print(f"[+] User-Facing Alert : '{trace['response']}'")

    assert trace["status"] == "blocked"
    assert trace["type"] == "guardrail_blocked"
    assert "Destructive disk formatting" in trace["reason"]
    print("[PASSED] Test 5: Guardrail intercepted and blocked dangerous action step before execution.")


def test_6_data_driven_agent_routing():
    banner("Test 6: Two Different Task Types Routed via Registry Lookup Only")
    task_a = "Search the web for latest quantum encryption algorithms"
    task_b = "Turn on the living room ceiling lights"

    print(f"[*] Task A: '{task_a}'")
    event_a = PerceptionEvent(type="text_input", payload={"text": task_a}, active_persona="Jarvis")
    plan_a = task_planner.create_plan(event_a)
    agent_a = plan_a.steps[0].required_agent_type
    desc_a = agent_registry.lookup(agent_a)
    print(f"    -> Registry Lookup: Agent Type='{agent_a}', Resolved Name='{desc_a.name}', Capabilities={desc_a.capabilities}")

    print(f"\n[*] Task B: '{task_b}'")
    event_b = PerceptionEvent(type="text_input", payload={"text": task_b}, active_persona="Jarvis")
    plan_b = task_planner.create_plan(event_b)
    agent_b = plan_b.steps[0].required_agent_type
    desc_b = agent_registry.lookup(agent_b)
    print(f"    -> Registry Lookup: Agent Type='{agent_b}', Resolved Name='{desc_b.name}', Capabilities={desc_b.capabilities}")

    assert agent_a == "web_agent"
    assert agent_b == "smart_home_agent"
    assert agent_a != agent_b
    print("\n[+] Both tasks successfully resolved via data-driven registry lookup without hardcoded branching.")
    print("[PASSED] Test 6: Data-driven agent routing verified.")


def test_7_persona_switch_intent_without_wake_word():
    banner("Test 7: Say 'call yourself Friday from now on' -> active_persona Updates Directly")
    # Ensure starting persona is Jarvis
    settings.set_active_persona("Jarvis")
    print(f"[*] Initial active_persona: '{settings.active_persona_name}'")

    phrase = "call yourself Friday from now on"
    print(f"[*] Ingesting spoken/text request: '{phrase}' (No wake word)")

    event = PerceptionEvent(
        type="text_input",
        payload={"text": phrase},
        source="voice_transcript",
        active_persona="Jarvis",
    )

    trace = orchestrator_core.process_event(event)

    print(f"[+] Trace Event Type     : {trace['type']}")
    print(f"[+] Reported New Persona : {trace['active_persona']}")
    print(f"[+] Current System Persona: '{settings.active_persona_name}'")
    print(f"[+] Response Output      : '{trace['response']}'")

    assert trace["type"] == "persona_switch"
    assert trace["active_persona"] == "Friday"
    assert settings.active_persona_name == "Friday", f"Expected Friday, got {settings.active_persona_name}"

    # Reset back to Jarvis
    settings.set_active_persona("Jarvis")
    print("\n[PASSED] Test 7: Persona switch intent recognized and active_persona updated directly.")


def main():
    print("=" * 70)
    print(" JARVIS LAYER 2 (ORCHESTRATOR) — MANDATORY VERIFICATION SUITE")
    print("=" * 70)

    test_1_single_step_mock_event()
    test_2_multi_step_mock_event()
    test_3_forced_failure_and_retries()
    test_4_memory_manager_persistence()
    test_5_guardrail_blocking_dangerous_action()
    test_6_data_driven_agent_routing()
    test_7_persona_switch_intent_without_wake_word()

    print("\n" + "=" * 70)
    print(" ALL 7 MANDATORY TESTS PASSED SUCCESSFULLY! LAYER 2 IS COMPLETE.")
    print("=" * 70)


if __name__ == "__main__":
    main()
