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



def test_demo_scenario_c_never_reuses_stored_biometrics_or_sends_email():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    scenario_c = source.split('elif scenario == "c":', 1)[1].split("shutdown_all_layers()", 1)[0]

    assert ".send_email(" not in scenario_c
    assert "face_embedding" not in scenario_c
    assert "draft_email(" in scenario_c
