"""Architectural Verification Test: Cognitive Core & Dual-Process Routing."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cognitive.understanding import understanding_engine
from cognitive.world_model import world_model
from cognitive.goal_engine import goal_engine
from cognitive.planning_engine import planning_engine
from cognitive.kernel import cognitive_kernel


def test_cognitive_core_pipeline():
    # 1. Understanding Engine: Test reminder with "check" & "test" does not collide with shell/git
    context = world_model.get_context_snapshot()
    intent = understanding_engine.understand("set a reminder in 90 seconds to check on this test", context)
    assert intent.domain == "scheduler"
    assert intent.action == "set_reminder"
    assert intent.parameters.get("delay_seconds") == 90

    # 2. Goal Engine: Create atomic goal
    goal_tree = goal_engine.create_atomic_goal(
        goal_text="play lofi music",
        domain="browser",
        action="play_youtube",
        params={"query": "lofi music"}
    )
    assert len(goal_tree.subgoals) == 1
    assert goal_tree.subgoals[0].action == "play_youtube"

    # 3. Planning Engine: Converts goal to capability-driven step
    plan = planning_engine.generate_plan(goal_tree, is_fast_path=True)
    assert len(plan.steps) == 1
    assert plan.steps[0].required_capability == "browser.playback"

    # 4. Cognitive Kernel: Verify Dual-Process System 1 Fast Path
    res_fast = cognitive_kernel.process("snap this to the left please")
    assert res_fast["system_path"] == "System_1_Fast_Path"
    assert res_fast["intent"].domain == "os"
    assert res_fast["plan"].steps[0].required_capability == "os.window_management"
    assert res_fast["elapsed_ms"] < 200, f"Fast path too slow: {res_fast['elapsed_ms']}ms"


if __name__ == "__main__":
    test_cognitive_core_pipeline()
    print("ALL COGNITIVE CORE ARCHITECTURAL TESTS PASSED CLEANLY!")
