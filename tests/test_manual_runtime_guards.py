"""Focused regression guards for current JARVIS intent/media architecture."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.context_manager import WorkingContextManager
from orchestrator.intent_arbitrator import IntentArbitrator
from orchestrator.parameter_extractor import ParameterExtractor


def test_code_followup_regex_does_not_capture_bare_if():
    ctx = WorkingContextManager()
    ctx.set_code("result = a / b", function_name="divide")
    unrelated = ctx.resolve_references("open chrome if possible")
    followup = ctx.resolve_references("what happens if b is zero")
    assert unrelated["is_code_op"] is False
    assert followup["is_code_op"] is True
    assert followup["resolved_action"] == "code_explanation"


def test_explicit_path_has_priority_over_basename():
    params = ParameterExtractor.extract_file_params('read report.pdf from "~/notes/report.pdf"')
    assert params["action"] == "read"
    assert params["filename"].endswith("/notes/report.pdf")
    assert params["filename"] != "report.pdf"


def test_generic_youtube_request_selects_first_result_without_fabricating_song():
    intent = IntentArbitrator().arbitrate("open youtube and play a song")
    assert intent.action == "play_youtube_first_result"
    assert intent.params["category"] in {"song", "music"}


def test_browser_runtime_contains_no_known_machine_or_fake_song_defaults():
    source = Path("agents/browser_automation_agent.py").read_text(encoding="utf-8")
    assert "C:\\Users\\acer" not in source
    assert "antigravity-ide" not in source
    assert "trending top music hits" not in source
    assert "lofi beats" not in source
