"""Regression tests for safe JARVIS entrypoint startup failure handling."""

import sys

import pytest


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
