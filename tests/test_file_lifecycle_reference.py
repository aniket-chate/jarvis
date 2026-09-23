"""Comprehensive File Lifecycle, Reference Resolution, and Semantic Content Verification Tests.

Audits:
1. create with explicit inline content ("Create a file named jarvis_test.txt and put this information inside it: This is a real context reference test.")
2. semantic verifier confirms content is physically written to disk
3. read "the file I just created"
4. show "the file you just created"
5. read "that file"
6. unrelated intervening question followed by file reference
7. rename/move "that file"
8. delete "the file I just created" with confirmation
9. create with explicit content requested but omitted -> clarification stops execution, 0-byte file not created
10. verifier rejects empty file if content was demanded
"""

import os
import sys
import unittest
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from perception.events import PerceptionEvent
from orchestrator.core import orchestrator_core
from orchestrator.parameter_extractor import parameter_extractor
from orchestrator.planner import task_planner, TaskPlan, TaskStep
from orchestrator.verifier import task_verifier
from orchestrator.memory import memory_manager
from cognitive.world_model import world_model
from agents.file_document_agent import DOCUMENTS_DIR, WORKSPACE_DIR


class TestFileLifecycleAndContentVerification(unittest.TestCase):
    def setUp(self):
        # Clean up any leftover jarvis_test.txt or test files
        for p in [DOCUMENTS_DIR / "jarvis_test.txt", DOCUMENTS_DIR / "jarvis_test_renamed.txt", WORKSPACE_DIR / "jarvis_test.txt"]:
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def tearDown(self):
        for p in [DOCUMENTS_DIR / "jarvis_test.txt", DOCUMENTS_DIR / "jarvis_test_renamed.txt", WORKSPACE_DIR / "jarvis_test.txt"]:
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def test_01_create_with_explicit_inline_content_and_semantic_verification(self):
        """Test 1: 'Create a file named jarvis_test.txt and put this information inside it: This is a real context reference test.'"""
        query = "Create a file named jarvis_test.txt and put this information inside it:\nThis is a real context reference test."
        
        # 1. Parameter extraction check
        params = parameter_extractor.extract_file_parameters(query)
        self.assertEqual(params["action"], "create")
        self.assertEqual(params["filename"], "jarvis_test.txt")
        self.assertEqual(params["content"], "This is a real context reference test.")
        self.assertFalse(params["requires_clarification"])

        # 2. Execution via Orchestrator Core
        ev = PerceptionEvent(type="text_input", payload={"text": query}, active_persona="Jarvis")
        res = orchestrator_core.process_event(ev)

        self.assertEqual(res["status"], "completed")
        self.assertTrue(res["verification"]["verified"])

        # Verify physical disk state
        target_file = DOCUMENTS_DIR / "jarvis_test.txt"
        self.assertTrue(target_file.exists(), "Target file must exist on disk")
        written_content = target_file.read_text(encoding="utf-8")
        self.assertEqual(written_content, "This is a real context reference test.")
        self.assertGreater(len(written_content), 0, "File must not be 0 bytes")

    def test_02_read_references_anaphora(self):
        """Test 2 & 3: 'Read the file I just created', 'Show me the file you just created', 'read that file'."""
        # 1. First create the file
        target_file = DOCUMENTS_DIR / "jarvis_test.txt"
        test_content = "This is a real context reference test."
        target_file.write_text(test_content, encoding="utf-8")
        world_model.update_file_context(str(target_file), content=test_content, is_creation=True)

        # 2. Test 'Read the file I just created'
        read_ev = PerceptionEvent(type="text_input", payload={"text": "Read the file I just created"}, active_persona="Jarvis")
        read_res = orchestrator_core.process_event(read_ev)

        self.assertEqual(read_res["status"], "completed")
        self.assertTrue(read_res["verification"]["verified"])
        self.assertIn("This is a real context reference test.", read_res["response"])

        # 3. Test 'Show me the file you just created.'
        show_ev = PerceptionEvent(type="text_input", payload={"text": "Show me the file you just created."}, active_persona="Jarvis")
        show_res = orchestrator_core.process_event(show_ev)

        self.assertEqual(show_res["status"], "completed")
        self.assertTrue(show_res["verification"]["verified"])
        self.assertIn("This is a real context reference test.", show_res["response"])

        # 4. Test 'read that file'
        that_ev = PerceptionEvent(type="text_input", payload={"text": "read that file"}, active_persona="Jarvis")
        that_res = orchestrator_core.process_event(that_ev)

        self.assertEqual(that_res["status"], "completed")
        self.assertTrue(that_res["verification"]["verified"])
        self.assertIn("This is a real context reference test.", that_res["response"])

    def test_03_intervening_question_preserves_file_reference(self):
        """Test: Unrelated intervening question followed by file reference."""
        target_file = DOCUMENTS_DIR / "jarvis_test.txt"
        test_content = "Context retention across conversation turns."
        target_file.write_text(test_content, encoding="utf-8")
        world_model.update_file_context(str(target_file), content=test_content, is_creation=True)

        # Intervening conversation
        intervene_ev = PerceptionEvent(type="text_input", payload={"text": "What is the boiling point of water?"}, active_persona="Jarvis")
        intervene_res = orchestrator_core.process_event(intervene_ev)
        self.assertEqual(intervene_res["status"], "completed")

        # Now refer back to 'that file'
        follow_ev = PerceptionEvent(type="text_input", payload={"text": "Read that file"}, active_persona="Jarvis")
        follow_res = orchestrator_core.process_event(follow_ev)

        self.assertEqual(follow_res["status"], "completed")
        self.assertTrue(follow_res["verification"]["verified"])
        self.assertIn("Context retention across conversation turns.", follow_res["response"])

    def test_04_rename_move_that_file(self):
        """Test: rename/move 'that file'."""
        target_file = DOCUMENTS_DIR / "jarvis_test.txt"
        target_file.write_text("Renaming test content", encoding="utf-8")
        world_model.update_file_context(str(target_file), content="Renaming test content", is_creation=True)

        rename_ev = PerceptionEvent(type="text_input", payload={"text": "Rename that file to jarvis_test_renamed.txt"}, active_persona="Jarvis")
        rename_res = orchestrator_core.process_event(rename_ev)

        self.assertEqual(rename_res["status"], "completed")
        renamed_file = DOCUMENTS_DIR / "jarvis_test_renamed.txt"
        self.assertTrue(renamed_file.exists(), "Renamed file must exist on disk")

    def test_05_delete_file_i_just_created_with_confirmation(self):
        """Test: delete 'the file I just created' with Two-Gate confirmation."""
        target_file = DOCUMENTS_DIR / "jarvis_test.txt"
        target_file.write_text("Deletion candidate", encoding="utf-8")
        world_model.update_file_context(str(target_file), content="Deletion candidate", is_creation=True)

        # 1. Ask to delete
        del_ev = PerceptionEvent(type="text_input", payload={"text": "Delete the file I just created"}, active_persona="Jarvis")
        del_res = orchestrator_core.process_event(del_ev)

        # Must stage confirmation, file must still exist
        self.assertTrue(bool(memory_manager.get_pending_action()))
        self.assertTrue(target_file.exists(), "File must not be deleted before confirmation")

        # 2. Confirm
        confirm_ev = PerceptionEvent(type="text_input", payload={"text": "yes"}, active_persona="Jarvis")
        confirm_res = orchestrator_core.process_event(confirm_ev)

        self.assertEqual(confirm_res["status"], "completed")
        self.assertTrue(confirm_res["verification"]["verified"])
        self.assertFalse(target_file.exists(), "File must be physically absent after confirmation")

    def test_06_ambiguous_content_stops_execution(self):
        """Test: If content is explicitly demanded but missing and unresolved, clarification must stop execution."""
        query = "Create a file named missing_info.txt and put the information inside it"
        # No previous memory / content exists
        memory_manager.remember("last_response", "")
        world_model.state.last_tool_output = None
        world_model.state.last_file_content = None

        params = parameter_extractor.extract_file_parameters(query)
        self.assertTrue(params["requires_clarification"])

        ev = PerceptionEvent(type="text_input", payload={"text": query}, active_persona="Jarvis")
        res = orchestrator_core.process_event(ev)

        # Must NOT execute file creation with 0 bytes! Must request clarification!
        missing_file = DOCUMENTS_DIR / "missing_info.txt"
        self.assertFalse(missing_file.exists(), "0-byte file must NOT be created when content is missing/ambiguous!")
        self.assertTrue("what" in res["response"].lower() or "clarify" in res["response"].lower() or "content" in res["response"].lower())

    def test_07_semantic_verifier_rejects_empty_file_when_content_expected(self):
        """Test: Semantic verifier flags failure if file on disk is empty despite content demanded."""
        empty_file = DOCUMENTS_DIR / "jarvis_test.txt"
        empty_file.write_text("", encoding="utf-8") # 0 bytes

        plan = TaskPlan(
            plan_id="test_plan_empty",
            goal="Create a file named jarvis_test.txt with content 'Critical data'",
            steps=[
                TaskStep(
                    step_id="step_1",
                    description="Create file",
                    required_agent_type="file_agent",
                    inputs={"action": "create", "path": str(empty_file), "content": "Critical data"},
                    status="completed"
                )
            ],
            active_persona="Jarvis"
        )
        exec_summary = {"status": "completed", "completed_steps": ["step_1"], "failed_steps": []}

        verif = task_verifier.verify_and_summarize(plan, exec_summary)
        self.assertFalse(verif["verified"], "Verifier must fail if expected content is not in file!")
        self.assertEqual(exec_summary["status"], "failed")
        self.assertIn("content", verif["summary"].lower())


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFileLifecycleAndContentVerification)
    result = runner.run(suite)
    sys.stdout.flush()
    os._exit(0 if result.wasSuccessful() else 1)
