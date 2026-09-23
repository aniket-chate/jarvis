"""Integrated Test Suite for Capabilities 33, 34, and 35.

Audits:
1. End-to-end multi-step pipeline: Personal Search (33) -> Verification (34) -> Synthesis (35) -> Verifier.
2. Partial pipeline: Personal Search (33) -> Verification (34).
3. External pipeline: Web Search (31) -> Verification (34) -> Synthesis (35).
4. Real-time pipeline: Real-time Info (32) -> Verification (34) -> Synthesis (35).
5. Comprehensive heterogeneous pipeline: 33 + 31 + 32 -> 34 -> 35.
6. Checkpoint recovery across multi-step execution DAG.
"""

from datetime import datetime
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from capabilities.intelligence import capability_intelligence
from cognitive.understanding import understanding_engine
from cognitive.planning_engine import planning_engine
from cognitive.goal_engine import GoalTree, SubGoal
from orchestrator.planner import task_planner, TaskPlan, TaskStep
from orchestrator.verifier import task_verifier
import capabilities.providers  # Trigger default registration


def test_1_end_to_end_33_34_35_pipeline():
    print("\n[TEST 1/6] Auditing Full End-to-End Pipeline (33 -> 34 -> 35 -> Verifier)...")
    # 1. Understanding
    utterance = "What was my Jarvis project architecture?"
    intent = understanding_engine.understand(utterance)
    assert intent.domain == "search"
    assert intent.action == "search_personal"

    # 2. Planning
    tree = GoalTree(root_goal=utterance, subgoals=[
        SubGoal(goal_id="g1", description=utterance, domain="search", action="search_personal", parameters={"query": "JARVIS architecture"})
    ])
    cog_plan = planning_engine.generate_plan(tree)
    assert len(cog_plan.steps) >= 1
    assert cog_plan.steps[0].required_capability == "search.personal_vector"

    # 3. Execution: Step 33 Personal Search
    p33 = capability_intelligence.select_provider("search.personal_vector")
    res_33 = p33.execute("search.personal_vector", {"query": "JARVIS architecture", "top_k": 3})
    assert res_33.status == "SUCCESS"
    personal_docs = res_33.output.get("results", [])
    assert len(personal_docs) > 0

    # 4. Execution: Step 34 Verification
    p34 = capability_intelligence.select_provider("verification.information")
    res_34 = p34.execute("verification.information", {"claim": "JARVIS uses local AI and Windows backend", "sources": personal_docs})
    assert res_34.status == "SUCCESS"
    assert res_34.output.get("state") in ["VERIFIED", "SUPPORTED"]

    # 5. Execution: Step 35 Knowledge Synthesis
    p35 = capability_intelligence.select_provider("synthesis.combine_sources")
    res_35 = p35.execute("synthesis.combine_sources", {
        "query": utterance,
        "sources": personal_docs,
        "verification": res_34.output,
    })
    assert res_35.status == "SUCCESS"
    synth_output = res_35.output

    # 6. Verifier User Response Preservation
    mock_step = TaskStep(
        step_id="step_35",
        description="Synthesize personal architecture",
        required_agent_type="personal_search_agent",
        inputs={"query": utterance},
        status="completed",
        result=synth_output,
    )
    user_resp = task_verifier.generate_user_response(mock_step, {"status": "completed"})
    assert "Personal Knowledge & Project Records" in user_resp
    assert "Done." != user_resp.strip()
    print("  PASS: End-to-end 33 -> 34 -> 35 pipeline completed and verified.")


def test_2_partial_pipeline_33_to_34():
    print("\n[TEST 2/6] Auditing Partial Pipeline (33 Personal Search -> 34 Verification)...")
    p33 = capability_intelligence.select_provider("search.personal_vector")
    p34 = capability_intelligence.select_provider("verification.information")

    res_33 = p33.execute("search.personal_vector", {"query": "FaceSnap attendance", "top_k": 2})
    assert res_33.status == "SUCCESS"
    docs = res_33.output.get("results", [])
    assert len(docs) > 0

    # Verify claim about FaceSnap
    claim = "FaceSnap is an attendance tracking system"
    res_34 = p34.execute("verification.information", {"claim": claim, "sources": docs})
    assert res_34.status == "SUCCESS"
    assert res_34.output.get("state") in ["VERIFIED", "SUPPORTED"]
    print(f"  PASS: Partial pipeline verified claim with status: {res_34.output.get('state')}.")


def test_3_external_pipeline_31_34_35():
    print("\n[TEST 3/6] Auditing External Pipeline (31 Web Search -> 34 Verification -> 35 Synthesis)...")
    p31 = capability_intelligence.select_provider("search.web")
    p34 = capability_intelligence.select_provider("verification.information")
    p35 = capability_intelligence.select_provider("synthesis.combine_sources")

    res_31 = p31.execute("search.web", {"query": "Python programming language", "max_results": 2})
    assert res_31.status == "SUCCESS"
    web_docs = res_31.output.get("results", [])

    res_34 = p34.execute("verification.information", {"claim": "Python is a high-level programming language", "sources": web_docs})
    assert res_34.status == "SUCCESS"

    res_35 = p35.execute("synthesis.combine_sources", {
        "query": "Python summary",
        "sources": web_docs,
        "verification": res_34.output,
    })
    assert res_35.status == "SUCCESS"
    assert res_35.output.get("external_sources_count") >= 1
    print("  PASS: External pipeline 31 -> 34 -> 35 produced verified synthesis.")


def test_4_realtime_pipeline_32_34_35():
    print("\n[TEST 4/6] Auditing Real-Time Pipeline (32 Real-Time -> 34 Verification -> 35 Synthesis)...")
    p32 = capability_intelligence.select_provider("info.get_weather")
    p34 = capability_intelligence.select_provider("verification.information")
    p35 = capability_intelligence.select_provider("synthesis.combine_sources")

    res_32 = p32.execute("info.get_weather", {"location": "Delhi", "time_target": "now"})
    assert res_32.status == "SUCCESS"
    weather_item = [{
        "source_id": "realtime_weather_delhi",
        "source_type": "realtime_feed",
        "title": f"Weather in {res_32.output.get('location', 'Delhi')}",
        "snippet": f"Temperature: {res_32.output.get('temperature')}C, Condition: {res_32.output.get('condition')}",
        "timestamp": time.time(),
    }]

    res_34 = p34.execute("verification.information", {"claim": f"Current weather in Delhi is {res_32.output.get('temperature')}C", "sources": weather_item, "require_fresh": True})
    assert res_34.status == "SUCCESS"
    assert res_34.output.get("state") in ["VERIFIED", "SUPPORTED"]

    res_35 = p35.execute("synthesis.combine_sources", {
        "query": "Delhi Weather Brief",
        "sources": weather_item,
        "verification": res_34.output,
    })
    assert res_35.status == "SUCCESS"
    print("  PASS: Real-time pipeline 32 -> 34 -> 35 verified and synthesized.")


def test_5_heterogeneous_multi_source_pipeline():
    print("\n[TEST 5/6] Auditing Heterogeneous Pipeline (33 + 31 + 32 -> 34 -> 35)...")
    p33 = capability_intelligence.select_provider("search.personal_vector")
    p31 = capability_intelligence.select_provider("search.web")
    p32 = capability_intelligence.select_provider("info.get_weather")
    p34 = capability_intelligence.select_provider("verification.information")
    p35 = capability_intelligence.select_provider("synthesis.generate_brief")

    # 1. Personal
    res_33 = p33.execute("search.personal_vector", {"query": "JARVIS", "top_k": 1})
    p_docs = res_33.output.get("results", [])

    # 2. Web
    res_31 = p31.execute("search.web", {"query": "AI assistant framework", "max_results": 1})
    w_docs = res_31.output.get("results", [])

    # 3. Realtime
    res_32 = p32.execute("info.get_weather", {"location": "Delhi"})
    rt_docs = [{
        "source_id": "rt_feed",
        "source_type": "realtime_feed",
        "title": "Local Environment",
        "snippet": f"Delhi weather {res_32.output.get('temperature')}C",
        "timestamp": time.time(),
    }]

    all_sources = p_docs + w_docs + rt_docs
    assert len(all_sources) >= 3

    # Cross-reference
    res_34 = p34.execute("verification.cross_reference_claims", {"sources": all_sources})
    assert res_34.status == "SUCCESS"

    # Synthesize brief
    res_35 = p35.execute("synthesis.generate_brief", {
        "query": "System Architecture & Operational Context Brief",
        "sources": all_sources,
        "verification": res_34.output,
    })
    assert res_35.status == "SUCCESS"
    brief = res_35.output.get("synthesis", "")
    assert "Personal Knowledge" in brief
    assert "External & Real-Time" in brief
    assert res_35.output.get("personal_sources_count") >= 1
    assert res_35.output.get("external_sources_count") >= 1
    print("  PASS: Heterogeneous multi-source pipeline successfully generated complete executive brief.")


def test_6_durable_checkpoint_flow():
    print("\n[TEST 6/6] Auditing Durable Checkpoint Flow for Multi-Step Synthesis...")
    from execution.runtime import ExecutionKernel, WorkflowJob, WorkflowStep, StepState

    kernel = ExecutionKernel()
    wf_id = f"wf_synth_{int(time.time()*1000)}"

    steps = [
        WorkflowStep(step_id="step_33", capability="search.personal_vector", parameters={"query": "JARVIS architecture"}),
        WorkflowStep(step_id="step_34", capability="verification.information", parameters={"claim": "JARVIS uses modular capability intelligence"}),
        WorkflowStep(step_id="step_35", capability="synthesis.combine_sources", parameters={"query": "Synthesize verified findings"}),
    ]

    job = WorkflowJob(
        workflow_id=wf_id,
        request_id="req_durable_test",
        goal="Test durable checkpoint across 33->34->35 pipeline",
        steps=steps,
    )

    # Step 1 Checkpoint
    job.steps[0].state = StepState.COMPLETED
    job.current_step_index = 1
    job.checkpoint["33_personal_search"] = {"status": "SUCCESS", "docs_count": 3}
    kernel.persist_checkpoint(job)

    # Simulate restart & restore
    kernel_fresh = ExecutionKernel()
    restored_1 = kernel_fresh.restore_checkpoint(wf_id)
    assert restored_1 is not None
    assert restored_1.current_step_index == 1
    assert restored_1.steps[0].state == StepState.COMPLETED
    assert restored_1.steps[1].state == StepState.PENDING
    assert "33_personal_search" in restored_1.checkpoint

    # Step 2 Checkpoint
    restored_1.steps[1].state = StepState.COMPLETED
    restored_1.current_step_index = 2
    restored_1.checkpoint["34_verification"] = {"status": "SUCCESS", "state": "VERIFIED"}
    kernel_fresh.persist_checkpoint(restored_1)

    # Step 3 Checkpoint & Completion
    restored_2 = kernel_fresh.restore_checkpoint(wf_id)
    assert restored_2 is not None
    assert restored_2.current_step_index == 2
    restored_2.steps[2].state = StepState.COMPLETED
    restored_2.current_step_index = 3
    restored_2.is_completed = True
    restored_2.checkpoint["35_synthesis"] = {"status": "SUCCESS", "brief_generated": True}
    kernel_fresh.persist_checkpoint(restored_2)

    final_job = kernel_fresh.restore_checkpoint(wf_id)
    assert final_job is not None
    assert final_job.is_completed is True
    assert len(final_job.checkpoint) == 3
    print("  PASS: Durable execution kernel checkpointed and restored all 3 pipeline stages across simulated crashes.")


def run_all_tests():
    t_start = time.perf_counter()
    print("============================================================")
    print("CAPABILITIES 33 + 34 + 35 INTEGRATED PIPELINE TEST SUITE")
    print("============================================================")
    test_1_end_to_end_33_34_35_pipeline()
    test_2_partial_pipeline_33_to_34()
    test_3_external_pipeline_31_34_35()
    test_4_realtime_pipeline_32_34_35()
    test_5_heterogeneous_multi_source_pipeline()
    test_6_durable_checkpoint_flow()
    elapsed = time.perf_counter() - t_start
    print("\n============================================================")
    print(f"INTEGRATION SUITE: 6/6 PASS (Duration: {elapsed:.2f}s)")
    print("============================================================")


if __name__ == "__main__":
    run_all_tests()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
