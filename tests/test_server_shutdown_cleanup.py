"""Regression tests for server shutdown of JARVIS-owned background resources."""

import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_server_shutdown_stops_loaded_scheduler_and_owned_processes(monkeypatch):
    server_module = importlib.import_module("server.app")
    import utils.process_registry as process_registry

    calls = []
    scheduler = SimpleNamespace(shutdown=lambda: calls.append("scheduler"))
    monkeypatch.setitem(
        sys.modules,
        "agents.scheduler_agent",
        SimpleNamespace(scheduler_agent=scheduler),
    )
    monkeypatch.setattr(
        process_registry,
        "terminate_registered_processes",
        lambda timeout_seconds=3.0: calls.append(("processes", timeout_seconds)),
    )

    asyncio.run(server_module.shutdown_owned_runtime_resources())

    assert calls == ["scheduler", ("processes", 3.0)]
