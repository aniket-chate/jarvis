"""Shared test configuration.

Production gateway authentication remains fail-closed. Tests that exercise
protected HTTP endpoints receive an ephemeral in-process token only when the
test environment did not provide one explicitly.
"""

import os
import pytest

from config.settings import settings


@pytest.fixture(autouse=True)
def test_gateway_token(monkeypatch):
    if not settings.gateway_auth_token:
        token = os.getenv("JARVIS_TEST_GATEWAY_TOKEN", "test-gateway-token-2026-jarvis-" + "x" * 32)
        monkeypatch.setattr(settings, "gateway_auth_token", token)
    yield
