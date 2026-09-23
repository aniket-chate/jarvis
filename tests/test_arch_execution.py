"""Architectural Verification Test: Execution Kernel Workflows & Deadline Budgets."""

import asyncio
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from execution.runtime import execution_kernel
from capabilities.intelligence import capability_intelligence
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult


class MockSlowFastProvider(BaseCapabilityProvider):
    def __init__(self):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.mock.slow_fast",
                name="Mock Slow/Fast Provider",
                supported_capabilities=["test.slow_action", "test.fast_action", "test.hanging_action"],
                priority=1,
            )
        )

    def is_available(self) -> bool:
        return True

    def execute(self, capability: str, parameters: dict, context=None) -> ActionResult:
        if capability == "test.slow_action":
            time.sleep(0.3)
            return ActionResult(status="SUCCESS", output="SLOW_ACTION_COMPLETE")
        elif capability == "test.fast_action":
            time.sleep(0.02)
            return ActionResult(status="SUCCESS", output="FAST_ACTION_COMPLETE")
        elif capability == "test.hanging_action":
            time.sleep(2.0)
            return ActionResult(status="SUCCESS", output="SHOULD_NEVER_FINISH")
        return ActionResult(status="FAILED", output=None)


async def test_execution_kernel_isolation_and_timeouts():
    capability_intelligence.register_provider(MockSlowFastProvider())

    # 1. Test Concurrent Long-Running Action Isolation
    job_slow = execution_kernel.create_job("req_s1", "slow task", [{"capability": "test.slow_action", "timeout_sec": 1.0}])
    job_fast = execution_kernel.create_job("req_f1", "fast task", [{"capability": "test.fast_action", "timeout_sec": 1.0}])

    t_start = time.perf_counter()
    task_slow = asyncio.create_task(execution_kernel.run_job(job_slow))
    task_fast = asyncio.create_task(execution_kernel.run_job(job_fast))

    res_fast = await task_fast
    t_fast_done = time.perf_counter() - t_start

    assert res_fast["status"] == "success"
    assert res_fast["output"] == "FAST_ACTION_COMPLETE"
    assert t_fast_done < 0.15, f"Fast action was delayed by slow action! Elapsed: {t_fast_done}s"

    res_slow = await task_slow
    assert res_slow["status"] == "success"
    assert res_slow["output"] == "SLOW_ACTION_COMPLETE"

    # 2. Test Step Deadline Timeout Enforcement
    job_hang = execution_kernel.create_job("req_h1", "hang task", [{"capability": "test.hanging_action", "timeout_sec": 0.2, "retry_limit": 0}])
    res_hang = await execution_kernel.run_job(job_hang)
    assert res_hang["status"] == "failed"
    assert "retries" in res_hang["error"]

    # 3. Test Checkpoint recording
    assert len(job_slow.checkpoint) == 1
    assert list(job_slow.checkpoint.values())[0] == "SLOW_ACTION_COMPLETE"


if __name__ == "__main__":
    asyncio.run(test_execution_kernel_isolation_and_timeouts())
    print("ALL EXECUTION KERNEL ISOLATION & TIMEOUT TESTS PASSED CLEANLY!")
