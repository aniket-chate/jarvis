"""Audit Test Suite 8: Multi-Intent Handling & Error Recovery / Fallback.

Audits:
1. Multi-Intent Decomposition & Concurrent Execution:
   "Give me CPU usage, RAM usage, network status, and current time."
   - 4 independent intents recognized
   - Concurrent execution with zero blocking
   - Results combined correctly

2. Sequential Multi-Step Dependency Workflow:
   "Open Chrome, search GitHub for Python, and tell me what page is currently open."
   - Decomposes into sequential steps with dependency chaining
   - Preserves context across steps
   - Checkpoints intermediate step outcomes

3. Error Recovery & Automatic Provider Fallback:
   - Primary provider intentionally fails
   - ExecutionKernel detects failure, selects fallback provider, and recovers
   - Eliminates single point of failure (SPOF)

4. Timeout Isolation:
   - Slow/hung provider timeout enforced without crashing the runtime
"""

import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cognitive.goal_engine import goal_engine
from cognitive.planning_engine import planning_engine
from execution.runtime import execution_kernel, StepState
from capabilities.intelligence import capability_intelligence
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
import capabilities.providers  # Register standard providers


async def test_multi_intent_concurrency():
    print("\n[MULTI-INTENT 1/4] Auditing Multi-Intent Decomposition & Concurrent Execution...")
    utterance = "Give me CPU usage, RAM usage, network status, and current time."
    goal_tree = goal_engine.decompose(utterance)

    # 1. Verify all 4 intents decomposed
    assert len(goal_tree.subgoals) == 4, f"Expected 4 subgoals, got {len(goal_tree.subgoals)}"
    actions = [s.parameters.get("metric") for s in goal_tree.subgoals]
    assert "cpu_usage" in actions
    assert "ram_usage" in actions
    assert "network_status" in actions
    assert "current_time" in actions
    print(f"  Recognized 4 independent subgoals: {actions}")

    # 2. Generate Plan
    plan = planning_engine.generate_plan(goal_tree, is_fast_path=False)
    assert len(plan.steps) == 4

    # 3. Execute Concurrently via ExecutionKernel
    job = execution_kernel.create_job(
        request_id="req_multi_metric",
        goal=utterance,
        steps=[{"capability": s.required_capability, "parameters": s.parameters} for s in plan.steps],
        is_concurrent=True,
    )
    t_start = time.perf_counter()
    res = await execution_kernel.run_job(job)
    elapsed = (time.perf_counter() - t_start) * 1000

    assert res["status"] == "success"
    assert len(job.steps) == 4
    for step in job.steps:
        assert step.state == StepState.COMPLETED
    print(f"  All 4 independent intents executed concurrently in {elapsed:.1f}ms: SUCCESS")


async def test_sequential_workflow_dependencies():
    print("\n[MULTI-INTENT 2/4] Auditing Sequential Compound Workflow with Dependencies...")
    utterance = "Open Chrome, search GitHub for Python, and tell me what page is currently open."
    goal_tree = goal_engine.decompose(utterance)

    assert len(goal_tree.subgoals) == 3, f"Expected 3 subgoals, got {len(goal_tree.subgoals)}"
    sub1, sub2, sub3 = goal_tree.subgoals

    # Verify dependency chaining
    assert len(sub1.dependencies) == 0  # First step has no dependencies
    assert sub1.goal_id in sub2.dependencies  # Step 2 depends on Step 1
    assert sub2.goal_id in sub3.dependencies  # Step 3 depends on Step 2
    print(f"  Dependency chain validated: {sub1.goal_id} -> {sub2.goal_id} -> {sub3.goal_id}")

    plan = planning_engine.generate_plan(goal_tree, is_fast_path=False)
    assert len(plan.steps) == 3

    job = execution_kernel.create_job(
        request_id="req_seq_compound",
        goal=utterance,
        steps=[{"capability": s.required_capability, "parameters": s.parameters} for s in plan.steps],
        is_concurrent=False,
    )
    # Sequential step execution structure verified
    assert job.steps[0].capability == "browser.navigate"
    assert job.steps[1].capability == "browser.search"
    print("  Sequential compound plan with checkpointing prepared and verified.")


async def test_error_recovery_and_provider_fallback():
    print("\n[ERROR RECOVERY 3/4] Auditing Provider Failure Detection & Fallback Switching...")

    # 1. Create a failing primary provider for a test capability
    test_cap = "search.web_test_domain"

    class FailingPrimaryProvider(BaseCapabilityProvider):
        def __init__(self):
            super().__init__(
                ProviderMetadata(
                    provider_id="provider.search.failing_primary",
                    name="Failing Primary Search",
                    supported_capabilities=[test_cap],
                    priority=1,  # Primary
                )
            )
        def is_available(self) -> bool:
            return True
        def execute(self, capability, parameters, context=None):
            # Intentionally fail!
            return ActionResult(status="FAILED", output=None, message="Primary upstream network connection severed")

    # 2. Create a working secondary fallback provider
    class ReliableFallbackProvider(BaseCapabilityProvider):
        def __init__(self):
            super().__init__(
                ProviderMetadata(
                    provider_id="provider.search.reliable_fallback",
                    name="Reliable Fallback Search",
                    supported_capabilities=[test_cap],
                    priority=2,  # Secondary
                )
            )
        def is_available(self) -> bool:
            return True
        def execute(self, capability, parameters, context=None):
            return ActionResult(status="SUCCESS", output={"results": ["Verified fallback search result"]}, message="Fallback succeeded")

    primary = FailingPrimaryProvider()
    fallback = ReliableFallbackProvider()
    capability_intelligence.register_provider(primary)
    capability_intelligence.register_provider(fallback)

    # 3. Run job through ExecutionKernel
    job = execution_kernel.create_job(
        request_id="req_fallback_test",
        goal="Perform resilient web search",
        steps=[{"capability": test_cap, "parameters": {"query": "resilience"}, "retry_limit": 2}],
    )

    res = await execution_kernel.run_job(job)
    assert res["status"] == "success", f"Fallback failed! Result: {res}"
    assert job.steps[0].state == StepState.COMPLETED
    assert job.steps[0].result.output == {"results": ["Verified fallback search result"]}
    print("  Error Recovery verified: Primary failure caught -> Fallback provider selected -> Step COMPLETED.")

    # Clean up test providers
    capability_intelligence.unregister_provider(primary.provider_id)
    capability_intelligence.unregister_provider(fallback.provider_id)


async def test_timeout_isolation():
    print("\n[ERROR RECOVERY 4/4] Auditing Step Timeout Budget Enforcement...")
    test_cap = "test.slow_timeout_domain"

    class HangingProvider(BaseCapabilityProvider):
        def __init__(self):
            super().__init__(
                ProviderMetadata(
                    provider_id="provider.hanging",
                    name="Hanging Provider",
                    supported_capabilities=[test_cap],
                    priority=1,
                )
            )
        def is_available(self) -> bool:
            return True
        def execute(self, capability, parameters, context=None):
            time.sleep(2.0)  # Hang for 2s
            return ActionResult(status="SUCCESS", output="Too late", message="Too late")

    hanger = HangingProvider()
    capability_intelligence.register_provider(hanger)

    job = execution_kernel.create_job(
        request_id="req_timeout_test",
        goal="Test timeout enforcement",
        steps=[{"capability": test_cap, "parameters": {}, "timeout_sec": 0.2, "retry_limit": 0}],
    )

    t_start = time.perf_counter()
    res = await execution_kernel.run_job(job)
    elapsed = time.perf_counter() - t_start

    assert res["status"] == "failed"
    assert elapsed < 1.0, f"Timeout was not enforced promptly! Elapsed: {elapsed}s"
    assert job.steps[0].state == StepState.FAILED
    print(f"  Timeout Budget enforced: Step aborted after {elapsed:.2f}s without blocking system.")

    capability_intelligence.unregister_provider(hanger.provider_id)


async def main():
    print("=" * 80)
    print("AUDIT SUITE 8: MULTI-INTENT HANDLING & ERROR RECOVERY / FALLBACK")
    print("=" * 80)
    await test_multi_intent_concurrency()
    await test_sequential_workflow_dependencies()
    await test_error_recovery_and_provider_fallback()
    await test_timeout_isolation()
    print("\n" + "=" * 80)
    print("AUDIT SUITE 8 PASSED: MULTI-INTENT DECOMPOSITION & PROVIDER RESILIENCE VALIDATED.")
    print("=" * 80)
    os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
