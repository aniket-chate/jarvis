"""Security regression tests for JARVIS gateway and developer capabilities."""

import asyncio
import hmac
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_gateway_has_no_hardcoded_default_token():
    from config.settings import settings
    assert settings.gateway_auth_token is None or settings.gateway_auth_token != "jarvis-gateway-token-2026-auth"


def test_identity_fails_closed_without_enrollment(tmp_path):
    from agents.identity_agent import IdentityAgent
    agent = IdentityAgent(tmp_path / "owner_profile.json")
    result = agent.verify_two_gate_authorization(
        action_name="send_email",
        face_embedding=None,
        explicit_user_confirmed=True,
    )
    assert result["authorized"] is False
    assert result["gate_1_identity"]["passed"] is False


def test_code_execution_is_disabled_until_real_sandbox():
    from capabilities.providers.developer_provider import DeveloperTaskProvider
    result = DeveloperTaskProvider().execute(
        "code.sandbox_execution",
        {"source": "res = 1"},
    )
    assert result.status == "UNAVAILABLE"


def test_shell_diagnostics_reject_arguments():
    from capabilities.providers.developer_provider import DeveloperTaskProvider
    result = DeveloperTaskProvider().execute(
        "shell.allowlisted_diagnostics",
        {"command": "hostname && whoami"},
    )
    assert result.status == "FAILED"


def test_simulated_iot_is_not_live():
    from capabilities.providers.smart_home_iot_provider import SmartHomeIoTProvider
    provider = SmartHomeIoTProvider()
    assert provider.get_readiness() == "SIMULATED"
    assert provider.is_available() is False


def test_simulated_robotics_is_not_live():
    from capabilities.providers.physical_robotics_provider import PhysicalRoboticsProvider
    provider = PhysicalRoboticsProvider()
    assert provider.get_readiness() == "SIMULATED"
    assert provider.is_available() is False
