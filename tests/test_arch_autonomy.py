"""Architectural Verification Test: Autonomous Runtime & First-Class Agency."""

import asyncio
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomous_runtime.agency import autonomous_agency
from autonomous_runtime.schemas import AutonomousRule, TriggerType
from memory.system import memory_system
import capabilities.providers  # Ensure OS and Scheduler providers are registered


async def test_autonomous_agency_pipeline():
    condition_met = False

    def check_download_complete():
        return condition_met

    # 1. Register an autonomous condition rule: "If my download finishes, run system telemetry"
    rule = AutonomousRule(
        rule_id="rule_telemetry_on_condition",
        description="Autonomous condition test: sample system telemetry when condition becomes true",
        trigger_type=TriggerType.CONDITION_POLL,
        goal_to_trigger="Collect system telemetry",
        target_capability="os.telemetry",
        parameters={},
        condition_fn=check_download_complete,
        poll_interval_sec=0.01,
        max_triggers=1,
    )
    autonomous_agency.register_rule(rule)

    # 2. Evaluate when condition is False -> nothing should fire
    res1 = await autonomous_agency.evaluate_triggers()
    assert len(res1) == 0, "Autonomous rule fired when condition was False!"

    # 3. Set condition to True -> should fire through Goal -> Plan -> Policy -> Execution -> Verification
    condition_met = True
    await asyncio.sleep(0.05)
    res2 = await autonomous_agency.evaluate_triggers()
    assert len(res2) == 1
    fired_result = res2[0]

    assert fired_result["status"] == "success"
    assert fired_result["rule_id"] == "rule_telemetry_on_condition"
    assert fired_result["verification"] == "SUCCESS"

    # 4. Verify Episodic Memory recorded this autonomous action
    assert memory_system.has_action_been_done("telemetry", "Autonomous") or memory_system.has_action_been_done("telemetry")

    # 5. Rule was one-off, so it should be inactive now
    assert rule.is_active is False


if __name__ == "__main__":
    import os
    asyncio.run(test_autonomous_agency_pipeline())
    print("ALL AUTONOMOUS RUNTIME & AGENCY ARCHITECTURAL TESTS PASSED CLEANLY!")
    os._exit(0)

