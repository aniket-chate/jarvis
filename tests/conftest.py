"""Shared test configuration.

Production gateway authentication remains fail-closed. Tests that exercise
protected HTTP endpoints receive an ephemeral in-process token only when the
test environment did not provide one explicitly.
"""

import os
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings


@pytest.fixture(autouse=True)
def test_gateway_token(monkeypatch):
    if not settings.gateway_auth_token:
        token = os.getenv("JARVIS_TEST_GATEWAY_TOKEN", "test-gateway-token-2026-jarvis-" + "x" * 32)
        monkeypatch.setattr(settings, "gateway_auth_token", token)
    yield
