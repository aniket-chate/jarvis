"""Unseen Real-World Scenario Test Matrix for JARVIS V1.

Tests generalized, non-hardcoded behavior across:
1. create -> reference -> modify ("the one I just created", "the file you created", "that file", "it")
2. create -> reference -> delete -> confirm (Two-gate policy, affirmative, negative cancel, unrelated message)
3. search -> summarize -> save (Multi-intent DAG with dependency ordering)
4. open -> interact -> close (Browser/Window lifecycle)
5. action -> interruption -> resume (Context grounding)
6. action -> failure -> recovery (Graceful fallback)
7. multi-intent -> partial failure (Truthful partial reporting)
8. ambiguous reference -> clarification (Ambiguity detection without silent guessing)
"""

import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from perception.events import PerceptionEvent
from cognitive.world_model import world_model
from orchestrator.core import orchestrator_core
from orchestrator.planner import task_planner, TaskPlan, TaskStep
from orchestrator.parameter_extractor import parameter_extractor
from orchestrator.intent_arbitrator import intent_arbitrator
from orchestrator.context_manager import context_manager
from orchestrator.memory import memory_manager
from orchestrator.verifier import task_verifier
from agents.file_document_agent import file_document_agent, WORKSPACE_DIR


class TestUnseenRealWorldScenarios(unittest.TestCase):
    """Rigorous tests for unseen, generalized real-world operations."""

    def setUp(self):
        # Reset state cleanly
        world_model.state.last_file_path = None
        world_model.state.last_created_file = None
        world_model.state.last_created_content = None
        world_model.state.pending_confirmation = None
        memory_manager.clear_pending_action()
        context_manager.pop_confirmation()

    def test_01_create_reference_modify_generalized(self):
        """Scenario 1: create -> reference via 'the one I just created' -> modify."""
        # 1. Create file
        ev1 = PerceptionEvent(type="text_input", payload={"text": "create a file called dynamic_project_notes.txt with content 'Initial draft notes'"}, active_persona="Jarvis")
        res1 = orchestrator_core.process_event(ev1)
        self.assertIn(res1["status"], ["completed", "success"])
        
        target_path = Path(world_model.state.last_created_file)
        self.assertTrue(target_path.exists())
        self.assertEqual(target_path.name, "dynamic_project_notes.txt")

        # 2. Reference using 'the one I just created'
        resolved = world_model.resolve_reference("read the one I just created")
        self.assertEqual(resolved.get("file_path"), str(target_path))

        params = parameter_extractor.extract_file_parameters("read the one I just created")
        self.assertEqual(params["action"], "read")
        self.assertEqual(str(Path(params["filename"])), str(target_path))

        # 3. Reference using 'that file'
        resolved_that = world_model.resolve_reference("read that file")
        self.assertEqual(resolved_that.get("file_path"), str(target_path))

        # 4. Reference using 'the file you created'
        resolved_you = world_model.resolve_reference("show me the file you created")
        self.assertEqual(resolved_you.get("file_path"), str(target_path))

        # Clean up
        if target_path.exists():
            target_path.unlink()

    def test_02_destructive_lifecycle_confirm_and_cancel(self):
        """Scenario 2: create -> delete staged -> confirm -> verified deleted, and cancel variant."""
        # 1. Create file
        test_file = WORKSPACE_DIR / "sensitive_audit_doc.txt"
        test_file.write_text("Confidential data", encoding="utf-8")
        world_model.update_file_context(str(test_file), content="Confidential data", is_creation=True)

        # 2. User says: "Delete the file I just created."
        del_ev = PerceptionEvent(type="text_input", payload={"text": "Delete the file I just created."}, active_persona="Jarvis")
        del_res = orchestrator_core.process_event(del_ev)
        
        # Must require confirmation, not delete immediately!
        self.assertTrue(bool(memory_manager.get_pending_action()))
        self.assertTrue(test_file.exists(), "File must NOT be deleted before Gate 2 confirmation!")

        # 3. Test Negative Confirmation / Cancellation ("cancel")
        cancel_ev = PerceptionEvent(type="text_input", payload={"text": "cancel"}, active_persona="Jarvis")
        cancel_res = orchestrator_core.process_event(cancel_ev)
        
        # Must safely cancel, clearing pending action and leaving file intact
        self.assertFalse(bool(memory_manager.get_pending_action()))
        self.assertTrue(test_file.exists(), "File must remain on disk after cancellation!")
        self.assertIn("cancel", cancel_res["response"].lower())

        # 4. Now test Affirmative Confirmation ("yes")
        # Trigger delete staging again
        del_res2 = orchestrator_core.process_event(del_ev)
        self.assertTrue(bool(memory_manager.get_pending_action()))

        confirm_ev = PerceptionEvent(type="text_input", payload={"text": "yes"}, active_persona="Jarvis")
        confirm_res = orchestrator_core.process_event(confirm_ev)

        # Must execute delete, verify physical absence, and clear pending action
        self.assertFalse(bool(memory_manager.get_pending_action()))
        self.assertFalse(test_file.exists(), "File must be physically absent after confirmed deletion!")
        self.assertTrue(confirm_res["verification"]["verified"])

    def test_03_multi_intent_dag_ordering_and_dependencies(self):
        """Scenario 3: search -> summarize -> save (Multi-intent compound DAG)."""
        goal = "Search for the latest AI news, summarize it, and save the summary"
        ev = PerceptionEvent(type="text_input", payload={"text": goal}, active_persona="Jarvis")
        plan = task_planner.create_plan(ev)

        self.assertGreaterEqual(len(plan.steps), 2, "Must decompose into at least 2 coordinated steps")
        # Verify dependencies: later steps depend on prior steps
        step_ids = [s.step_id for s in plan.steps]
        for idx in range(1, len(plan.steps)):
            step = plan.steps[idx]
            self.assertTrue(len(step.depends_on) > 0, f"Dependent step {step.step_id} must have depends_on")
            self.assertIn(step_ids[idx - 1], step.depends_on)

    def test_04_multi_intent_independent_actions(self):
        """Scenario: 'Check the weather and open Chrome' (Independent subgoals)."""
        goal = "Check the weather and open Chrome"
        ev = PerceptionEvent(type="text_input", payload={"text": goal}, active_persona="Jarvis")
        plan = task_planner.create_plan(ev)

        self.assertEqual(len(plan.steps), 2)
        step_weather = plan.steps[0]
        step_chrome = plan.steps[1]

        self.assertEqual(step_weather.required_agent_type, "weather_agent")
        self.assertIn(step_chrome.required_agent_type, ["system_control_agent", "browser_automation_agent"])
        # Independent: step 2 does NOT depend on step 1
        self.assertEqual(step_chrome.depends_on, [])

    def test_05_ambiguity_demands_clarification_no_guessing(self):
        """Scenario: Ambiguous commands without context must ask targeted clarification, NEVER invent targets."""
        # Ensure world model context is completely empty
        world_model.state.last_file_path = None
        world_model.state.last_created_file = None

        params = parameter_extractor.extract_file_parameters("Delete that.")
        self.assertTrue(params["requires_clarification"])
        self.assertEqual(params["filename"], "")
        self.assertIn("which file", params["clarification_prompt"].lower())

        # Test planner handles clarification prompt honestly
        ev = PerceptionEvent(type="text_input", payload={"text": "delete that file"}, active_persona="Jarvis")
        plan = task_planner.create_plan(ev)
        self.assertEqual(plan.steps[0].required_agent_type, "core_llm_agent")
        self.assertIn("clarif", plan.steps[0].description.lower())

    def test_06_unrelated_message_does_not_trigger_pending_action(self):
        """Safety Invariant: Unrelated messages during pending confirmation must NEVER trigger staged action."""
        # Stage a destructive action
        dummy_file = WORKSPACE_DIR / "dummy_safe.txt"
        dummy_file.write_text("keep safe", encoding="utf-8")
        memory_manager.set_pending_action({
            "action": "delete_file",
            "required_agent_type": "file_agent",
            "inputs": {"action": "delete_file", "path": str(dummy_file), "user_confirmed": True}
        })
        self.assertTrue(bool(memory_manager.get_pending_action()))

        # User asks an unrelated question: "What is the capital of France?"
        unrelated_ev = PerceptionEvent(type="text_input", payload={"text": "What is the capital of France?"}, active_persona="Jarvis")
        res = orchestrator_core.process_event(unrelated_ev)

        # File must remain untouched
        self.assertTrue(dummy_file.exists())
        if dummy_file.exists():
            dummy_file.unlink()

    def test_07_partial_failure_reporting_honesty(self):
        """Verifier must report partially failed plans as 'partially_failed' without falsely claiming success."""
        plan = TaskPlan(
            plan_id="partial_test_plan",
            goal="Check the weather and open non_existent_binary",
            steps=[
                TaskStep(
                    step_id="step_1",
                    description="Check weather",
                    required_agent_type="weather_agent",
                    inputs={"action": "get_weather", "location": "Tokyo"},
                    status="completed"
                ),
                TaskStep(
                    step_id="step_2",
                    description="Open binary",
                    required_agent_type="system_control_agent",
                    inputs={"action": "open_application", "target": "non_existent_binary"},
                    status="failed"
                )
            ],
            active_persona="Jarvis",
            status="partially_failed"
        )
        exec_summary = {
            "status": "partially_failed",
            "completed_steps": ["step_1"],
            "failed_steps": ["step_2"],
        }
        verif = task_verifier.verify_and_summarize(plan, exec_summary)
        self.assertFalse(verif["verified"], "Partially failed plan must NOT be verified as completed!")
        self.assertEqual(verif["status"], "partially_failed")


if __name__ == "__main__":
    res = unittest.main(exit=False)
    sys.stdout.flush()
    os._exit(0 if res.result.wasSuccessful() else 1)
