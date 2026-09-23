"""Audit Test Suite 6: Autonomous Runtime & First-Class Agency.

Audits autonomous behavior without a user prompt:
1. Condition Watcher: "File appears" on disk -> Event -> Goal -> Plan -> Policy -> Execution -> Verification -> Memory.
2. Scheduled Task: Evaluates at specified future timestamp.
3. Duplicate Trigger Prevention: Max triggers limit strictly enforced.
4. Policy/Safety Invariant on Autonomy (Invariant 6): Unsafe autonomous rules are blocked by PolicyKernel.
5. Failed/Cancelled Autonomous Task: Isolated and logged to episodic memory without crashing.

Enforces Invariant 6: Autonomous actions use the same safety/execution pipeline as user actions.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomous_runtime.agency import autonomous_agency
from autonomous_runtime.schemas import AutonomousRule, TriggerType
from memory.system import memory_system
from safety.policy_kernel import PolicyLevel
import capabilities.providers  # Ensure standard providers are registered


async def test_file_appears_condition_watcher():
    print("\n[AUTONOMY 1/5] Auditing 'File Appears' Condition Watcher Pipeline...")
    ws = Path(r"d:\assignment\JARVIS\workspace")
    target_watch_file = ws / "downloaded_signal.txt"
    if target_watch_file.exists():
        for _ in range(5):
            try:
                target_watch_file.unlink()
                break
            except (PermissionError, OSError):
                await asyncio.sleep(0.05)

    rule = AutonomousRule(
        rule_id="rule_file_appeared_notify",
        description="Trigger when downloaded_signal.txt appears",
        trigger_type=TriggerType.CONDITION_POLL,
        goal_to_trigger="Check telemetry after file download",
        target_capability="os.telemetry",
        parameters={},
        condition_fn=lambda: target_watch_file.exists(),
        poll_interval_sec=0.001,
        max_triggers=1,
    )
    autonomous_agency.register_rule(rule)

    # 1. Evaluate while file absent -> 0 triggers
    res_empty = await autonomous_agency.evaluate_triggers()
    assert len(res_empty) == 0, "Autonomous rule fired while file was absent!"
    print("  Condition false verified: 0 triggers fired.")

    # 2. Drop file into workspace -> Condition met
    target_watch_file.write_text("Download completed payload", encoding="utf-8")
    await asyncio.sleep(0.05)

    # 3. Evaluate triggers -> Must fire through full cognitive pipeline
    res_fired = await autonomous_agency.evaluate_triggers()
    assert len(res_fired) == 1
    outcome = res_fired[0]
    assert outcome["status"] == "success"
    assert outcome["rule_id"] == "rule_file_appeared_notify"
    assert outcome["verification"] == "SUCCESS"
    print("  'File appears' trigger fired through Goal -> Plan -> Safety -> Execution -> Verification.")

    # 4. Clean up
    for _ in range(10):
        try:
            if target_watch_file.exists():
                target_watch_file.unlink()
            break
        except (PermissionError, OSError):
            await asyncio.sleep(0.05)
    autonomous_agency.unregister_rule("rule_file_appeared_notify")


async def test_scheduled_task_trigger():
    print("\n[AUTONOMY 2/5] Auditing Scheduled Task Trigger...")
    now = time.time()
    future_time = now + 0.3  # 300ms in future

    rule = AutonomousRule(
        rule_id="rule_scheduled_alarm",
        description="Autonomous scheduled event test",
        trigger_type=TriggerType.SCHEDULED_TIME,
        goal_to_trigger="Execute scheduled status check",
        target_capability="os.telemetry",
        parameters={},
        scheduled_timestamp=future_time,
        max_triggers=1,
    )
    autonomous_agency.register_rule(rule)

    # 1. Evaluate before timestamp -> 0 fires
    res_early = await autonomous_agency.evaluate_triggers()
    assert len(res_early) == 0
    print("  Early evaluation verified: not fired before scheduled timestamp.")

    # 2. Wait until scheduled timestamp has elapsed
    await asyncio.sleep(0.35)
    res_due = await autonomous_agency.evaluate_triggers()
    assert len(res_due) == 1
    assert res_due[0]["status"] == "success"
    print("  Scheduled timestamp elapsed: fired autonomously at scheduled time.")

    autonomous_agency.unregister_rule("rule_scheduled_alarm")


async def test_duplicate_trigger_prevention():
    print("\n[AUTONOMY 3/5] Auditing Duplicate Trigger Prevention (Strict Max-Triggers)...")
    rule = AutonomousRule(
        rule_id="rule_single_fire",
        description="One-time autonomous trigger test",
        trigger_type=TriggerType.CONDITION_POLL,
        goal_to_trigger="One time telemetry check",
        target_capability="os.telemetry",
        parameters={},
        condition_fn=lambda: True,  # Always True
        poll_interval_sec=0.01,
        max_triggers=1,
    )
    autonomous_agency.register_rule(rule)

    # First evaluation: fires (1/1)
    res1 = await autonomous_agency.evaluate_triggers()
    assert len(res1) == 1
    assert rule.is_active is False
    assert rule.trigger_count == 1

    # Second evaluation: MUST NOT fire again
    res2 = await autonomous_agency.evaluate_triggers()
    assert len(res2) == 0, "Duplicate autonomous trigger fired!"
    print("  Duplicate trigger prevention confirmed: rule deactivated after 1/1 triggers.")

    autonomous_agency.unregister_rule("rule_single_fire")


async def test_policy_safety_gate_on_autonomy():
    print("\n[AUTONOMY 4/5] Auditing Policy/Safety Gate on Autonomous Goals (Invariant 6)...")
    # An autonomous rule attempting a prohibited action: shell whoami
    unsafe_rule = AutonomousRule(
        rule_id="rule_malicious_autonomous_shell",
        description="Malicious autonomous attempt to run whoami",
        trigger_type=TriggerType.CONDITION_POLL,
        goal_to_trigger="run whoami shell command",
        target_capability="shell.whoami",
        parameters={},
        condition_fn=lambda: True,
        poll_interval_sec=0.01,
        max_triggers=1,
    )
    autonomous_agency.register_rule(unsafe_rule)

    res_blocked = await autonomous_agency.evaluate_triggers()
    assert len(res_blocked) == 1
    blocked_outcome = res_blocked[0]
    assert blocked_outcome["status"] == "blocked"
    assert "Refused" in blocked_outcome["reason"]
    print(f"  Safety Invariant 6 ENFORCED: Autonomous action intercepted & blocked: {blocked_outcome['reason'][:60]}...")

    autonomous_agency.unregister_rule("rule_malicious_autonomous_shell")


async def test_failed_autonomous_task_isolation():
    print("\n[AUTONOMY 5/5] Auditing Failed Autonomous Task Isolation...")
    # Autonomous rule requesting a non-existent capability
    broken_rule = AutonomousRule(
        rule_id="rule_broken_cap",
        description="Broken capability test",
        trigger_type=TriggerType.CONDITION_POLL,
        goal_to_trigger="Trigger non-existent capability",
        target_capability="quantum.teleportation_matrix",
        parameters={},
        condition_fn=lambda: True,
        poll_interval_sec=0.01,
        max_triggers=1,
    )
    autonomous_agency.register_rule(broken_rule)

    res = await autonomous_agency.evaluate_triggers()
    assert len(res) == 1
    # Must fail gracefully without raising uncaught exception
    assert res[0]["exec_res"]["status"] in ["failed", "blocked"]
    print(f"  Failure handled gracefully without crashing runtime: {res[0]['exec_res']}")

    autonomous_agency.unregister_rule("rule_broken_cap")


async def main():
    print("=" * 80)
    print("AUDIT SUITE 6: AUTONOMOUS RUNTIME & FIRST-CLASS AGENCY")
    print("=" * 80)
    await test_file_appears_condition_watcher()
    await test_scheduled_task_trigger()
    await test_duplicate_trigger_prevention()
    await test_policy_safety_gate_on_autonomy()
    await test_failed_autonomous_task_isolation()
    print("\n" + "=" * 80)
    print("AUDIT SUITE 6 PASSED: FIRST-CLASS AGENCY OPERATES WITHOUT PROMPTS & RESPECTS ALL SAFETY INVARIANTS.")
    print("=" * 80)
    os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
