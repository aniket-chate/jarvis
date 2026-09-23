"""Comprehensive 13-Stage Command-Understanding Pipeline Tracing Harness.

Phase 2 Real-World Validation:
Verifies that the Hierarchical Classifier and Semantic Arbitration actively
assist and control command understanding end-to-end.

Traces:
USER INPUT
-> PERCEPTION
-> CLASSIFIER / INTENT UNDERSTANDING
-> STRUCTURED COMMAND
-> CONTEXT / WORLD MODEL RESOLUTION
-> PLANNER
-> POLICY
-> CAPABILITY
-> EXECUTION
-> OBSERVATION
-> VERIFICATION
-> RESPONSE
-> LATENCY
-> FINAL WORLD STATE
"""

import os
import sys
import time
import json
import unittest
from pathlib import Path
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from perception.events import PerceptionEvent
from cognitive.routing.hierarchical_classifier import hierarchical_classifier
from cognitive.world_model import world_model
from capabilities.intelligence import capability_intelligence
from orchestrator.intent_arbitrator import intent_arbitrator
from orchestrator.parameter_extractor import parameter_extractor
from orchestrator.planner import task_planner
from safety.policy_kernel import policy_kernel
from orchestrator.core import orchestrator_core
from orchestrator.verifier import task_verifier


def trace_pipeline(raw_query: str, persona: str = "Jarvis") -> Dict[str, Any]:
    """Executes a query through all 13 stages of the JARVIS pipeline and captures exhaustive telemetry."""
    t0 = time.perf_counter()
    trace_record: Dict[str, Any] = {"raw_user_request": raw_query}

    # Stage 1: PERCEPTION
    event = PerceptionEvent(
        type="text_input",
        payload={"text": raw_query, "query": raw_query},
        source="user_interface",
        active_persona=persona,
    )
    trace_record["perception_event"] = {
        "type": event.type,
        "source": event.source,
        "persona": event.active_persona,
        "timestamp": event.timestamp,
    }

    # Stage 2: CLASSIFIER / INTENT UNDERSTANDING
    t_clf0 = time.perf_counter()
    clf_res = hierarchical_classifier.classify(raw_query)
    t_clf = (time.perf_counter() - t_clf0) * 1000.0
    trace_record["classifier_result"] = {
        "domain": clf_res.domain,
        "top_k": clf_res.top_k_capabilities[:3],
        "confidence": clf_res.confidence,
        "unknown": clf_res.unknown,
        "requires_context": clf_res.requires_context,
        "latency_ms": round(t_clf, 2),
    }

    # Stage 3: STRUCTURED COMMAND
    structured_intent = intent_arbitrator.arbitrate(raw_query)
    trace_record["structured_command"] = {
        "domain": structured_intent.domain,
        "action": structured_intent.action,
        "target": structured_intent.target,
        "params": structured_intent.params,
        "requires_confirmation": structured_intent.requires_confirmation,
    }

    # Stage 4: CONTEXT / WORLD MODEL RESOLUTION
    resolved_refs = world_model.resolve_reference(raw_query)
    trace_record["resolved_references"] = resolved_refs

    # Stage 5: CAPABILITY & PROVIDER SELECTION
    route_info = capability_intelligence.route_and_select(raw_query, context=world_model.get_observation())
    selected_cap = route_info.get("selected_capability")
    selected_prov = route_info.get("provider")
    trace_record["selected_capability"] = selected_cap
    trace_record["selected_provider"] = getattr(selected_prov, "name", str(selected_prov))

    # Stage 6: PLANNER RESULT
    t_plan0 = time.perf_counter()
    plan = task_planner.create_plan(event)
    t_plan = (time.perf_counter() - t_plan0) * 1000.0
    trace_record["planner_result"] = {
        "plan_id": plan.plan_id,
        "goal": plan.goal,
        "steps_count": len(plan.steps),
        "steps": [
            {
                "step_id": s.step_id,
                "agent": s.required_agent_type,
                "action": s.inputs.get("action", ""),
                "depends_on": s.depends_on,
            }
            for s in plan.steps
        ],
        "latency_ms": round(t_plan, 2),
    }

    # Stage 7: POLICY DECISION
    first_step = plan.steps[0] if plan.steps else None
    if first_step:
        policy_dec = policy_kernel.evaluate(
            domain=first_step.required_agent_type or "system",
            action=first_step.inputs.get("action", "execute"),
            parameters=first_step.inputs,
            raw_query=raw_query,
        )
        trace_record["policy_decision"] = {
            "allowed": policy_dec.allowed,
            "requires_confirmation": bool(policy_dec.confirmation_token or "confirmation" in policy_dec.level.value),
            "level": policy_dec.level.value,
            "risk_score": policy_dec.risk_score,
            "reason": policy_dec.reason,
        }
    else:
        trace_record["policy_decision"] = {"allowed": True, "reason": "No steps to evaluate"}

    # Stage 8 & 9: EXECUTION & OBSERVATION
    t_exec0 = time.perf_counter()
    exec_result = orchestrator_core.process_event(event, plan=plan)
    t_exec = (time.perf_counter() - t_exec0) * 1000.0
    trace_record["execution_result"] = {
        "status": exec_result.get("status"),
        "type": exec_result.get("type"),
        "latency_ms": round(t_exec, 2),
    }
    trace_record["observation"] = world_model.get_observation()

    # Stage 10: VERIFICATION RESULT
    verif = exec_result.get("verification", {})
    trace_record["verification_result"] = {
        "verified": verif.get("verified", False),
        "status": verif.get("status"),
        "summary": verif.get("summary") or verif.get("response", ""),
    }

    # Stage 11: FINAL RESPONSE
    trace_record["final_response"] = exec_result.get("response", "")

    # Stage 12: TOTAL LATENCY
    total_ms = (time.perf_counter() - t0) * 1000.0
    trace_record["latency_ms"] = round(total_ms, 2)

    # Stage 13: FINAL WORLD STATE
    trace_record["final_world_state"] = {
        "last_file": world_model.state.last_file_path,
        "last_created": world_model.state.last_created_file,
        "persona": world_model.state.active_persona,
        "pending_confirmation": bool(world_model.state.pending_confirmation),
    }

    return trace_record


class TestCommandPipelineTrace(unittest.TestCase):
    """End-to-End Tracing across Diverse Intent Domains."""

    def test_01_trace_info_weather_request(self):
        """Pipeline trace for real-time information retrieval (Capability 32)."""
        trace = trace_pipeline("What is the current weather in Tokyo?")
        print(f"\n[Trace 1 Info Weather]:\n{json.dumps(trace, indent=2)}")

        self.assertIn(trace["classifier_result"]["domain"], ["RESEARCH_KNOWLEDGE_ANALYTICS", "info", "weather"])
        self.assertEqual(trace["selected_capability"], "32_realtime_information")
        self.assertEqual(trace["structured_command"]["domain"], "info")
        self.assertEqual(trace["structured_command"]["action"], "get_weather")
        self.assertEqual(trace["planner_result"]["steps"][0]["agent"], "weather_agent")
        self.assertTrue(trace["policy_decision"]["allowed"])
        self.assertIn(trace["execution_result"]["status"], ["completed", "success"])
        self.assertTrue(trace["verification_result"]["verified"])
        self.assertTrue(len(trace["final_response"]) > 0)
        self.assertLess(trace["latency_ms"], 15000.0)

    def test_02_trace_system_telemetry_request(self):
        """Pipeline trace for real hardware telemetry (Capability 21)."""
        trace = trace_pipeline("Check system cpu, ram, and disk status")
        print(f"\n[Trace 2 Telemetry]:\n{json.dumps(trace, indent=2)}")

        self.assertEqual(trace["planner_result"]["steps"][0]["agent"], "system_control_agent")
        self.assertTrue(trace["policy_decision"]["allowed"])
        self.assertIn(trace["execution_result"]["status"], ["completed", "success"])
        self.assertTrue(trace["verification_result"]["verified"])
        self.assertTrue(len(trace["final_response"]) > 0)

    def test_03_trace_file_creation_and_grounding(self):
        """Pipeline trace for file creation with grounded content (Capability 26)."""
        trace = trace_pipeline("create a new file called trace_sample.txt with content 'JARVIS Pipeline Verification'")
        print(f"\n[Trace 3 File Creation]:\n{json.dumps(trace, indent=2)}")

        self.assertEqual(trace["planner_result"]["steps"][0]["agent"], "file_agent")
        self.assertTrue(trace["policy_decision"]["allowed"])
        self.assertIn(trace["execution_result"]["status"], ["completed", "success"])
        self.assertTrue(trace["verification_result"]["verified"])
        # Verify World Model was updated with the created file
        self.assertIsNotNone(trace["final_world_state"]["last_created"])
        self.assertIn("trace_sample.txt", trace["final_world_state"]["last_created"])

        # Clean up file
        p = Path(trace["final_world_state"]["last_created"])
        if p.exists():
            p.unlink()


if __name__ == "__main__":
    res = unittest.main(exit=False)
    sys.exit(0 if res.result.wasSuccessful() else 1)
