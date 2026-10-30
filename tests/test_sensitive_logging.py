"""Regression tests preventing user content from being written to runtime logs."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_policy_kernel_does_not_log_raw_shell_queries():
    source = (ROOT / "safety/policy_kernel.py").read_text(encoding="utf-8")
    assert "query='%s'" not in source
    assert "raw_query)" not in source


def test_gateway_does_not_log_raw_prompts_or_synthesized_text():
    source = (ROOT / "server/app.py").read_text(encoding="utf-8")
    forbidden = [
        "query='%s'",
        "Synthesizing: '%s'",
        "Result text: '%s'",
        "Synthesizing tool speech: '%s'",
        "media_playback_started event for: '%s'",
        "Broadcasting alarm_triggered to clients: %s",
    ]
    for fragment in forbidden:
        assert fragment not in source


def test_browser_automation_does_not_log_search_query_text():
    source = (ROOT / "agents/browser_automation_agent.py").read_text(encoding="utf-8")
    forbidden = [
        "for: '%s' (duration=",
        "submitted query '%s'",
        "for query '%s'",
        "for query: '%s'",
    ]
    for fragment in forbidden:
        assert fragment not in source
