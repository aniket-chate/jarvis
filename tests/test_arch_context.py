"""Architectural Verification Test: World Model & Context/Pronoun Resolution."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cognitive.world_model import WorldModel


def test_pronoun_and_context_resolution():
    wm = WorldModel()

    # 1. Test persona stickiness
    wm.set_persona("Friday")
    assert wm.get_persona() == "Friday"

    # 2. Test code context and pronoun resolution: "run it with 5"
    sample_code = "def factorial(n):\n    return 1 if n <= 1 else n * factorial(n - 1)"
    wm.update_code_context(sample_code, language="python")

    resolved_code = wm.resolve_reference("run it with 5")
    assert "code_snippet" in resolved_code
    assert resolved_code["code_snippet"] == sample_code
    assert resolved_code.get("code_arg") == "5"

    # 3. Test browser tab reference: "close that tab"
    wm.state.active_browser_tab_id = "TAB_12345"
    wm.state.active_browser_url = "https://www.youtube.com"
    resolved_tab = wm.resolve_reference("close that tab")
    assert resolved_tab.get("tab_id") == "TAB_12345"

    # 4. Test git branch reference: "switch back"
    wm.update_git_branch("temp-test-branch")
    wm.update_git_branch("feature-branch")
    resolved_git = wm.resolve_reference("switch back")
    assert resolved_git.get("git_target_branch") == "temp-test-branch"

    # 5. Test media reference: "pause it"
    resolved_media = wm.resolve_reference("hold on, pause it")
    assert resolved_media.get("media_target") == "active_browser_player"


if __name__ == "__main__":
    test_pronoun_and_context_resolution()
    print("ALL CONTEXT AND PRONOUN RESOLUTION TESTS PASSED CLEANLY!")
