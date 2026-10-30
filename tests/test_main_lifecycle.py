"""Regression tests for safe JARVIS entrypoint startup failure handling."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.mark.parametrize(
    "arguments",
    [
        ["--cli"],
        ["--start"],
        ["--learn"],
        ["--scenario", "a"],
        [],
    ],
)
def test_entrypoints_abort_when_required_layers_fail(monkeypatch, arguments):
    import main

    monkeypatch.setattr(main, "init_all_layers", lambda: False)
    monkeypatch.setattr(sys, "argv", ["main.py", *arguments])

    with pytest.raises(SystemExit) as exc:
        main.main()

    assert exc.value.code == 1



def test_status_command_reports_configuration_without_starting_runtime(monkeypatch, capsys):
    import main

    monkeypatch.setattr(sys, "argv", ["main.py", "--status"])
    monkeypatch.setattr(main.settings, "check_secrets", lambda: {"modules_status": {}})
    monkeypatch.setattr(main, "init_all_layers", lambda: pytest.fail("status must not initialize runtime layers"))

    main.main()
    output = capsys.readouterr().out
    assert "JARVIS RUNTIME STATUS" in output
    assert "Active persona" in output


def test_shutdown_only_terminates_registered_child_processes(monkeypatch):
    import main

    class FakeProcess:
        pid = 43210

        def __init__(self):
            self.running = True
            self.terminated = False

        def poll(self):
            return None if self.running else 0

        def terminate(self):
            self.terminated = True
            self.running = False

        def wait(self, timeout=None):
            return 0

        def kill(self):
            self.running = False

    registered = FakeProcess()
    unrelated = FakeProcess()
    monkeypatch.setattr(main.memory_manager, "_save_persistent", lambda: None)
    main.CHILD_PROCESSES.clear()
    main.register_child_process(registered)

    main.shutdown_all_layers()

    assert registered.terminated is True
    assert unrelated.terminated is False
    assert main.CHILD_PROCESSES == []



def test_demo_scenario_c_drafts_without_sending(monkeypatch):
    import asyncio
    import types
    import main

    calls = {"draft": 0, "send": 0}

    def draft_email(**kwargs):
        calls["draft"] += 1
        return {"success": True, "status": "DRAFT"}

    def send_email(*args, **kwargs):
        calls["send"] += 1
        pytest.fail("Scenario C must never send an email")

    communication = types.SimpleNamespace(
        draft_email=draft_email,
        send_email=send_email,
    )
    calendar = types.SimpleNamespace(
        get_upcoming_events=lambda **kwargs: {"events": []},
    )
    monkeypatch.setitem(
        sys.modules,
        "agents.calendar_agent",
        types.SimpleNamespace(calendar_agent=calendar),
    )
    monkeypatch.setitem(
        sys.modules,
        "agents.communication_agent",
        types.SimpleNamespace(communication_agent=communication),
    )

    asyncio.run(main.run_scenario("c", initialize=False))

    assert calls == {"draft": 1, "send": 0}



def test_check_secrets_command_does_not_initialize_runtime(monkeypatch):
    import main

    calls = []
    monkeypatch.setattr(sys, "argv", ["main.py", "--check-secrets"])
    monkeypatch.setattr(main.settings, "check_secrets", lambda: calls.append("checked"))
    monkeypatch.setattr(main, "init_all_layers", lambda: pytest.fail("check-secrets must not initialize runtime layers"))

    main.main()

    assert calls == ["checked"]


def test_scenario_entrypoint_always_runs_shutdown(monkeypatch):
    import main

    shutdown_calls = []
    monkeypatch.setattr(sys, "argv", ["main.py", "--scenario", "a"])
    monkeypatch.setattr(main, "require_layers_initialized", lambda: None)

    def fail_run(coroutine):
        coroutine.close()
        raise RuntimeError("scenario failed")

    monkeypatch.setattr(main.asyncio, "run", fail_run)
    monkeypatch.setattr(main, "shutdown_all_layers", lambda: shutdown_calls.append(True))

    with pytest.raises(RuntimeError, match="scenario failed"):
        main.main()

    assert shutdown_calls == [True]
