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


def test_health_endpoint_defines_ollama_online_before_use():
    source = (ROOT / "server/app.py").read_text(encoding="utf-8")
    start = source.index("async def health_check():")
    block = source[start:source.index("\n\n# -------------------------------------------------------------------------", start)]
    assert "ollama_online = bool(" in block
    assert '"status": "healthy" if ollama_online and not ollama_warming else "degraded"' in block


def test_capability_gateway_validates_action_provider_and_confirmation_token():
    source = (ROOT / "server/app.py").read_text(encoding="utf-8")
    start = source.index("async def execute_capability(")
    block = source[start:source.index("\n\n@app.get("/api/personas")", start)]
    assert "supported_capabilities" in block
    assert "req.action not in supported" in block
    assert "policy_kernel.confirm_token" in block
    assert "Invalid, expired, or already-used confirmation token" in block


def test_no_legacy_token_or_in_process_exec_in_runtime_sources():
    forbidden_token = "jarvis-gateway-token-2026-auth"
    for path in ["config/settings.py", "server/app.py", "client/unified/app.js", "client/mobile/app.js"]:
        assert forbidden_token not in (ROOT / path).read_text(encoding="utf-8")
    developer_source = (ROOT / "capabilities/providers/developer_provider.py").read_text(encoding="utf-8")
    assert "shell=True" not in developer_source
    assert "exec(code" not in developer_source


def test_learning_does_not_self_reward_non_empty_text():
    source = (ROOT / "server/app.py").read_text(encoding="utf-8")
    assert 'reward=1.0 if len(final_resp) > 0 else -0.5' not in source
    assert "Skipping automatic RL reward for conversational turn" in source


def test_notification_provider_does_not_fake_delivery():
    from capabilities.providers.communication_provider import CommunicationHubProvider
    result = CommunicationHubProvider().execute(
        "comm.notify_user",
        {"message": "test notification"},
    )
    assert result.status == "FAILED"
    assert result.output["status"] == "NOT_DELIVERED"
