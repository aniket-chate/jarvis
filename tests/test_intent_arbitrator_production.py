from dataclasses import dataclass
from pathlib import Path

import pytest

from orchestrator.intent_arbitrator import IntentArbitrator, StructuredIntent


@dataclass
class Tx:
    domain: str
    action: str
    target: str
    payload: dict
    original_request: str = "original request"
    is_expired: bool = False


class FakeContext:
    def __init__(self):
        self.pending = None
        self.previous_branch = ""
        self.persona = "Jarvis"
        self.browser = type("Browser", (), {
            "url": "",
            "title": "",
            "media_state": "stopped",
            "media_target": "",
        })()
        self.weather = {"active": False, "location": "", "time_target": "now"}
        self.working = {}
        self.file = None

    def has_pending_confirmation(self):
        return bool(self.pending and not self.pending.is_expired)

    def get_pending_confirmation(self):
        return self.pending

    def resolve_references(self, query):
        return {
            "is_media_control": False,
            "is_file_op": False,
            "is_code_op": False,
            "is_browser_op": False,
            "resolved_target": "",
            "resolved_action": "",
        }

    def get_previous_git_branch(self):
        return self.previous_branch

    def get_browser(self):
        return self.browser

    def get_weather_context(self):
        return dict(self.weather)

    def get_working_memory(self):
        return dict(self.working)

    def get_file(self):
        return self.file


@pytest.fixture
def arb():
    return IntentArbitrator(context=FakeContext())


def test_structured_intent_preserves_query_source_and_confidence(arb):
    query = "search GitHub for FastAPI projects"
    intent = arb.arbitrate(query)
    assert isinstance(intent, StructuredIntent)
    assert intent.raw_query == query
    assert intent.source
    assert 0.0 <= intent.confidence <= 1.0


@pytest.mark.parametrize(
    "query",
    [
        "create a file",
        "send a message",
        "delete something",
        "schedule something",
        "check the weather",
    ],
)
def test_missing_required_parameters_clarify(arb, query):
    intent = arb.arbitrate(query)
    assert intent.needs_clarification is True
    assert intent.clarification_prompt
    assert intent.raw_query == query


def test_weather_whether_disambiguation_without_location_does_not_fabricate(arb):
    intent = arb.arbitrate("what's the weather")
    assert intent.domain == "info"
    assert intent.action == "get_weather"
    assert intent.needs_clarification is True
    assert not intent.target


def test_weather_explicit_location_is_preserved(arb):
    intent = arb.arbitrate("weather in Pune tomorrow")
    assert intent.action == "get_weather"
    assert intent.params["location"] == "Pune"
    assert intent.params["time_target"] == "tomorrow"


def test_file_windows_path_has_no_machine_specific_default(arb):
    query = r"read C:\Work\reports\report.pdf"
    intent = arb.arbitrate(query)
    assert intent.domain == "file"
    assert intent.action == "read_file"
    assert "C:\\Users\\" not in str(intent.params)
    assert "acer" not in str(intent.params).lower()


@pytest.mark.parametrize(
    ("query", "recipient"),
    [
        ("message Rahul Patil saying I will be late", "Rahul Patil"),
        ("email Rahul@example.com saying the deployment is ready", "Rahul@example.com"),
    ],
)
def test_communication_supports_multiword_and_email_recipient(arb, query, recipient):
    intent = arb.arbitrate(query)
    assert intent.domain == "communication"
    assert intent.target == recipient
    assert intent.params["recipient"] == recipient
    assert intent.params["message"]


def test_generic_github_search(arb):
    intent = arb.arbitrate("search GitHub for FastAPI projects")
    assert intent.domain == "browser"
    assert intent.action == "github_search"
    assert intent.params["query"] == "FastAPI projects"


def test_generic_media_query(arb):
    intent = arb.arbitrate("play Arijit Singh")
    assert intent.domain == "browser"
    assert intent.action == "play_youtube"
    assert intent.params["song"] == "Arijit Singh"


def test_generic_browser_target(arb):
    intent = arb.arbitrate("open example.com")
    assert intent.domain == "browser"
    assert intent.action == "open_url"
    assert intent.params["url"] == "example.com"


def test_calendar_preserves_full_request_and_delegates_extraction(arb, monkeypatch):
    query = "schedule a 30 minute meeting with the project team tomorrow at 3 PM"
    intent = arb.arbitrate(query)
    assert intent.domain == "scheduler"
    assert intent.action == "create_calendar_event"
    assert intent.params["raw_query"] == query
    assert intent.params["calendar_request"] == query


@pytest.mark.parametrize(
    "query",
    [
        "CPU status",
        "CPU and RAM",
        "RAM and disk",
        "battery and temperature",
        "network and uptime",
    ],
)
def test_telemetry_accepts_arbitrary_metric_combinations(arb, query):
    intent = arb.arbitrate(query)
    assert intent.domain == "system"
    assert intent.action == "multi_telemetry"
    assert len(intent.params["metrics"]) >= 1


def test_git_branch_extraction_is_dynamic(arb):
    intent = arb.arbitrate("create a branch called feature/runtime-cleanup")
    assert intent.domain == "git"
    assert intent.action == "create_branch"
    assert intent.target == "feature/runtime-cleanup"


def test_switch_back_uses_context_without_mutating_it(arb):
    arb.context.previous_branch = "feature/original"
    intent = arb.arbitrate("switch back")
    assert intent.action == "switch_branch"
    assert intent.target == "feature/original"
    assert arb.context.previous_branch == "feature/original"


def test_confirmation_is_context_sensitive_and_non_mutating(arb):
    tx = Tx(
        domain="file",
        action="delete_file",
        target="documents/report.pdf",
        payload={"path": "documents/report.pdf"},
    )
    arb.context.pending = tx
    intent = arb.arbitrate("yes, do it")
    assert intent.domain == "file"
    assert intent.action == "confirmed_delete_file"
    assert intent.target == tx.target
    assert intent.params == tx.payload
    assert intent.params is not tx.payload
    assert arb.context.pending is tx


def test_cancellation_does_not_cancel_without_pending_transaction(arb):
    intent = arb.arbitrate("cancel")
    assert intent.domain == "chat"
    assert intent.action == "respond"


def test_demo_phrases_are_generic_not_special_cases(arb):
    intent = arb.arbitrate("play lofi beats")
    assert intent.action == "play_youtube"
    assert intent.params["song"] == "lofi beats"
