"""Audit Test Suite 9: Checkpoint & Crash Recovery.

Audits workflow durability across interruptions and runtime restarts:
1. Multi-Step Workflow start:
   - Step 1 executes and checkpoints
2. Interruption Midway:
   - Process/runtime failure simulated
   - Step 1 results persisted on disk
3. Process Restart & State Recovery:
   - New ExecutionKernel instance created
   - Job restored from disk checkpoint
4. Resumption Execution:
   - Resumes from Step 2 without repeating Step 1 (Zero duplicated side effects)
   - Step 2 and Step 3 execute to completion
   - Final state verified and truthfully reported

Enforces Invariant 10: A failed action must never be reported as successful.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from execution.runtime import ExecutionKernel, StepState
from capabilities.intelligence import capability_intelligence
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
import capabilities.providers  # Register standard providers


async def test_checkpoint_and_crash_recovery():
    print("=" * 80)
    print("AUDIT SUITE 9: CHECKPOINT & CRASH RECOVERY")
    print("=" * 80)

    # 1. Custom mock provider tracking execution counts
    execution_counts = {"s1": 0, "s2": 0, "s3": 0}

    class TrackedStepProvider(BaseCapabilityProvider):
        def __init__(self):
            super().__init__(
                ProviderMetadata(
                    provider_id="provider.tracked.recovery",
                    name="Tracked Recovery Provider",
                    supported_capabilities=["test.tracked_step"],
                    priority=1,
                )
            )
        def is_available(self) -> bool:
            return True
        def execute(self, capability, parameters, context=None):
            step_name = parameters.get("step_name")
            execution_counts[step_name] += 1
            return ActionResult(status="SUCCESS", output=f"Output of {step_name}", message=f"Done {step_name}")

    tracker = TrackedStepProvider()
    capability_intelligence.register_provider(tracker)

    kernel_instance_1 = ExecutionKernel()

    print("\n[RECOVERY 1/4] Starting 3-step workflow on Runtime Instance 1...")
    job = kernel_instance_1.create_job(
        request_id="req_durable_wf_01",
        goal="Test checkpoint durability across crashes",
        steps=[
            {"capability": "test.tracked_step", "parameters": {"step_name": "s1"}},
            {"capability": "test.tracked_step", "parameters": {"step_name": "s2"}},
            {"capability": "test.tracked_step", "parameters": {"step_name": "s3"}},
        ],
    )
    wf_id = job.workflow_id

    # 2. Execute Step 1 ONLY, then simulate crash/interruption
    print("\n[RECOVERY 2/4] Executing Step 1, then simulating process crash midway...")
    step_1 = job.steps[0]
    s1_success = await kernel_instance_1.execute_step(job, step_1)
    assert s1_success is True
    assert step_1.state == StepState.COMPLETED
    assert execution_counts["s1"] == 1
    job.current_step_index = 1
    kernel_instance_1.persist_checkpoint(job)

    # Checkpoint verification on disk
    cp_file = Path(r"d:\assignment\JARVIS\data\checkpoints") / f"{wf_id}.json"
    assert cp_file.exists(), f"Checkpoint file not created at {cp_file}!"
    print(f"  Checkpoint successfully persisted to disk: {cp_file.name}")

    # 3. Simulate Total Process Death & Runtime Restart
    print("\n[RECOVERY 3/4] Simulating Total Process Death -> Spawning Fresh Runtime Instance 2...")
    del kernel_instance_1
    del job

    kernel_instance_2 = ExecutionKernel()
    recovered_job = kernel_instance_2.restore_checkpoint(wf_id)
    assert recovered_job is not None, "Failed to restore workflow job from disk checkpoint!"
    assert recovered_job.current_step_index == 1
    assert recovered_job.steps[0].state == StepState.COMPLETED
    assert recovered_job.steps[1].state == StepState.PENDING
    assert recovered_job.steps[2].state == StepState.PENDING
    print("  Runtime Instance 2 restored job: Step 1 = COMPLETED, Next Step = 2.")

    # 4. Resume Workflow to Completion
    print("\n[RECOVERY 4/4] Resuming workflow from checkpoint on Runtime Instance 2...")
    res = await kernel_instance_2.run_job(recovered_job)
    assert res["status"] == "success"
    assert recovered_job.is_completed is True

    # Invariant Check: Step 1 must NOT be repeated!
    assert execution_counts["s1"] == 1, f"DUPLICATED SIDE EFFECT: Step 1 was executed {execution_counts['s1']} times!"
    assert execution_counts["s2"] == 1
    assert execution_counts["s3"] == 1
    print("  Zero Duplicated Side Effects verified: Step 1 was NEVER re-executed.")
    print(f"  Final execution counts: {execution_counts}")
    print("  Intermediate checkpoints preserved:", res["checkpoint"])

    capability_intelligence.unregister_provider(tracker.provider_id)
    if cp_file.exists():
        cp_file.unlink()

    print("\n" + "=" * 80)
    print("AUDIT SUITE 9 PASSED: WORKFLOW CRASH RECOVERY & CHECKPOINT INTEGRITY VALIDATED.")
    print("=" * 80)
    os._exit(0)


if __name__ == "__main__":
    asyncio.run(test_checkpoint_and_crash_recovery())
