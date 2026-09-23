"""Audit Test Suite 2: Context Resolution & Multi-Turn Conversation Grounding.

Audits World Model + Working Memory + Episodic Memory across 4 realistic multi-turn scenarios:
1. Browser: Open GitHub -> Search for Python -> What page am I looking at? -> Go back -> Close that tab.
2. Media: Play a YouTube video -> Pause it -> Continue -> Switch to the other one -> Close that tab.
3. Files: Create a file called report.txt -> Move that file to Downloads -> Open it -> Summarize it.
4. Code: Generate a factorial function -> Run it with 5 -> What happens if the input is 0? -> Fix it -> Run it again.

Validates that pronoun/reference disambiguation ('it', 'that', 'that tab', 'that file', 'continue', 'the other one')
resolves against grounded World Model state and not brittle keyword routing.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cognitive.world_model import world_model
from cognitive.understanding import understanding_engine
from memory.system import memory_system


def test_browser_context_tree():
    print("\n--- Testing Multi-Turn Browser Context ---")
    # Step 1: Open GitHub
    i1 = understanding_engine.understand("Open GitHub.", world_model.get_context_snapshot())
    assert i1.domain == "browser"
    assert i1.action == "navigate"
    world_model.state.active_browser_url = "https://github.com"
    world_model.state.active_browser_title = "GitHub: Where the world builds software"
    world_model.state.active_browser_tab_id = "CDP_TAB_GITHUB_01"

    # Step 2: Search for Python
    i2 = understanding_engine.understand("Search for Python on GitHub.", world_model.get_context_snapshot())
    assert i2.domain == "browser"
    assert "python" in i2.parameters.get("query", "").lower()
    world_model.state.active_browser_url = "https://github.com/search?q=Python"
    world_model.state.active_browser_title = "Search · Python · GitHub"

    # Step 3: What page am I looking at?
    i3 = understanding_engine.understand("What page am I looking at?", world_model.get_context_snapshot())
    assert i3.action == "inspect_page"
    snap = world_model.get_context_snapshot()
    assert snap["active_browser"]["title"] == "Search · Python · GitHub"

    # Step 4: Go back
    i4 = understanding_engine.understand("Go back", world_model.get_context_snapshot())
    assert i4.action == "navigate_back"

    # Step 5: Close that tab
    i5 = understanding_engine.understand("Close that tab.", world_model.get_context_snapshot())
    assert i5.action == "close_tab"
    res = world_model.resolve_pronoun("close that tab")
    assert res.get("tab_id") == "CDP_TAB_GITHUB_01"
    print("  [PASSED] Browser context tree resolved grounded state across 5 turns.")


def test_media_context_tree():
    print("\n--- Testing Multi-Turn Media Context ---")
    # Step 1: Play a YouTube video
    i1 = understanding_engine.understand("Play some lofi music on YouTube.", world_model.get_context_snapshot())
    assert i1.domain == "browser"
    assert i1.action == "play_youtube"
    world_model.update_media_state(True, title="Lofi Hip Hop Radio - Beats to Relax/Study to")
    world_model.state.active_browser_tab_id = "CDP_TAB_YOUTUBE_01"

    # Step 2: Pause it
    i2 = understanding_engine.understand("Pause it.", world_model.get_context_snapshot())
    assert i2.action == "pause_media"
    res_pause = world_model.resolve_pronoun("pause it")
    assert res_pause.get("media_target") == "active_browser_player"
    world_model.update_media_state(False)

    # Step 3: Continue
    i3 = understanding_engine.understand("Continue.", world_model.get_context_snapshot())
    assert i3.action == "resume_media"
    res_cont = world_model.resolve_pronoun("continue")
    assert res_cont.get("media_target") == "active_browser_player"
    world_model.update_media_state(True)

    # Step 4: Switch to the other one
    res_switch = world_model.resolve_pronoun("switch to the other one")
    assert res_switch.get("target_context") == "alternate_tab_or_window"

    # Step 5: Close that tab
    res_close = world_model.resolve_pronoun("close that tab")
    assert res_close.get("tab_id") == "CDP_TAB_YOUTUBE_01"
    print("  [PASSED] Media playback context & pronoun resolution ('it', 'continue', 'that tab') verified.")


def test_file_context_tree():
    print("\n--- Testing Multi-Turn File Context ---")
    # Step 1: Create a file called report.txt
    i1 = understanding_engine.understand("Create a file called report.txt.", world_model.get_context_snapshot())
    assert i1.domain == "file"
    assert i1.action == "create_file"
    assert i1.parameters.get("filename") == "report.txt"
    world_model.update_file_context("d:/assignment/JARVIS/workspace/report.txt")

    # Step 2: Move that file to Downloads
    i2 = understanding_engine.understand("Move that file to Downloads.", world_model.get_context_snapshot())
    assert i2.domain == "file"
    assert i2.action == "move_file"
    assert "report.txt" in i2.resolved_pronoun
    assert i2.parameters.get("destination") == "Downloads"
    world_model.update_file_context("C:/Users/acer/Downloads/report.txt")

    # Step 3: Open it
    i3 = understanding_engine.understand("Open it.", world_model.get_context_snapshot())
    assert i3.domain == "file"
    assert i3.action == "read_file"
    assert "report.txt" in i3.parameters.get("path", "")

    # Step 4: Summarize it
    i4 = understanding_engine.understand("Summarize it.", world_model.get_context_snapshot())
    assert i4.domain == "file"
    assert i4.action == "read_file"
    assert "report.txt" in i4.parameters.get("path", "")
    print("  [PASSED] File context tree ('that file', 'open it', 'summarize it') verified.")


def test_code_context_tree():
    print("\n--- Testing Multi-Turn Code Context ---")
    # Step 1: Generate a factorial function
    i1 = understanding_engine.understand("Generate a factorial function in Python.", world_model.get_context_snapshot())
    assert i1.domain == "code"
    assert i1.action == "generate_code"
    sample_code = "def factorial(n):\n    return 1 if n <= 1 else n * factorial(n - 1)"
    world_model.update_code_context(sample_code, "python")
    memory_system.bind_pronoun("it", "factorial_function")

    # Step 2: Run it with 5
    i2 = understanding_engine.understand("Run it with 5.", world_model.get_context_snapshot())
    assert i2.domain == "code"
    assert i2.action == "execute_code"
    assert i2.parameters.get("input_arg") == 5
    assert i2.parameters.get("source") == sample_code

    # Step 3: What happens if the input is 0?
    res_q = world_model.resolve_pronoun("what happens if the input is 0?")
    assert res_q.get("code_snippet") == sample_code

    # Step 4: Fix it
    res_fix = world_model.resolve_pronoun("Fix it.")
    assert res_fix.get("code_snippet") == sample_code

    # Step 5: Run it again
    res_run = world_model.resolve_pronoun("Run it again.")
    assert res_run.get("code_snippet") == sample_code
    print("  [PASSED] Code execution context ('run it with 5', 'fix it', 'run it again') verified.")


def main():
    print("=" * 80)
    print("AUDIT SUITE 2: CONTEXT RESOLUTION & MULTI-TURN CONVERSATION GROUNDING")
    print("=" * 80)
    test_browser_context_tree()
    test_media_context_tree()
    test_file_context_tree()
    test_code_context_tree()
    print("\n" + "=" * 80)
    print("AUDIT SUITE 2 PASSED: 100% GROUNDED CONTEXT RESOLUTION ACROSS ALL 4 DOMAINS.")
    print("=" * 80)
    os._exit(0)


if __name__ == "__main__":
    main()
