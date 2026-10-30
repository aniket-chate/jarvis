"""Regression tests for API confirmation provenance and remote-device routing."""

from types import SimpleNamespace

import importlib
import pytest
from fastapi.testclient import TestClient

from config.settings import settings
from safety.policy_kernel import PolicyKernel


@pytest.fixture
def api_client(monkeypatch):
    """Create an isolated gateway client with an isolated confirmation store."""
    policy_module = importlib.import_module("safety.policy_kernel")
    kernel = PolicyKernel()
    monkeypatch.setattr(policy_module, "policy_kernel", kernel)
    monkeypatch.setattr(
        settings,
        "gateway_auth_token",
        "unit-test-gateway-token-with-sufficient-length",
    )
    from server.app import app

    return TestClient(app), kernel


def route_request(parameters, action="mesh.route_to_device"):
    """Build a capability request for the remote device mesh route."""
    return {
        "capability": "mesh.route_to_device",
        "action": action,
        "parameters": parameters,
    }


def test_remote_device_route_rejects_forged_confirmation_flags(api_client):
    client, kernel = api_client
    request_id = "req-mesh-forged-approval"
    response = client.post(
        "/api/v1/capabilities/execute",
        headers={"Authorization": "Bearer unit-test-gateway-token-with-sufficient-length"},
        json=route_request(
            {
                "request_id": request_id,
                "target_device_id": "android_test_device",
                "confirmed": True,
                "user_confirmed": True,
                "payload": {
                    "type": "skill_request",
                    "request_id": request_id,
                    "skill_id": "ui_tap",
                    "parameters": {"target": "Pay", "human_approved": True},
                },
            }
        ),
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["status"] == "BLOCKED"
    token = detail["confirmation_token"]
    assert token.startswith("auth_mesh_")

    pending = kernel._pending_confirmations[token]
    assert "confirmed" not in pending.parameters
    assert "user_confirmed" not in pending.parameters


def test_remote_device_confirmation_is_action_bound_and_one_time(api_client):
    client, _kernel = api_client
    headers = {"Authorization": "Bearer unit-test-gateway-token-with-sufficient-length"}
    request_id = "req-mesh-action-binding"
    initial = client.post(
        "/api/v1/capabilities/execute",
        headers=headers,
        json=route_request(
            {
                "request_id": request_id,
                "target_device_id": "android_test_device",
                "payload": {"type": "skill_request", "request_id": request_id, "skill_id": "ui_observe"},
            }
        ),
    )
    assert initial.status_code == 403
    token = initial.json()["detail"]["confirmation_token"]

    mismatched = client.post(
        "/api/v1/capabilities/execute",
        headers=headers,
        json=route_request(
            {
                "request_id": request_id,
                "confirmation_token": token,
                "device_id": "android_test_device",
                "trust_state": "TRUSTED",
            },
            action="mesh.set_device_trust",
        ),
    )
    assert mismatched.status_code == 403
    assert mismatched.json()["detail"] == "Confirmation token does not match requested action"

    replay = client.post(
        "/api/v1/capabilities/execute",
        headers=headers,
        json=route_request(
            {
                "request_id": request_id,
                "confirmation_token": token,
                "target_device_id": "android_test_device",
                "payload": {"type": "skill_request", "request_id": request_id, "skill_id": "ui_observe"},
            }
        ),
    )
    assert replay.status_code == 403
    assert replay.json()["detail"] == "Invalid, expired, or already-used confirmation token"


def test_confirmation_executes_only_the_parameters_that_were_staged(api_client, monkeypatch):
    client, _kernel = api_client
    from capabilities.intelligence import capability_intelligence

    provider = capability_intelligence.select_provider("mesh.route_to_device")
    assert provider is not None

    captured = {}
    monkeypatch.setattr(provider, "is_available", lambda: True)

    def fake_execute(action, parameters):
        captured.update(parameters)
        return SimpleNamespace(
            status="SUCCESS",
            output={"status": "captured"},
            message="Captured in test",
            evidence={},
            execution_time_ms=0.0,
        )

    monkeypatch.setattr(provider, "execute", fake_execute)

    headers = {"Authorization": "Bearer unit-test-gateway-token-with-sufficient-length"}
    request_id = "req-mesh-parameter-binding"
    original_payload = {
        "request_id": request_id,
        "target_device_id": "original_device",
        "payload": {
            "type": "skill_request",
            "request_id": request_id,
            "skill_id": "ui_observe",
        },
    }
    initial = client.post(
        "/api/v1/capabilities/execute",
        headers=headers,
        json=route_request(original_payload),
    )
    assert initial.status_code == 403
    token = initial.json()["detail"]["confirmation_token"]

    confirmed = client.post(
        "/api/v1/capabilities/execute",
        headers=headers,
        json=route_request(
            {
                "request_id": request_id,
                "confirmation_token": token,
                "target_device_id": "attacker_substituted_device",
                "payload": {"type": "skill_request", "skill_id": "ui_tap", "parameters": {"target": "Pay"}},
            }
        ),
    )

    assert confirmed.status_code == 200
    assert captured["target_device_id"] == "original_device"
    assert captured["payload"] == original_payload["payload"]
    assert captured["confirmed"] is True


def test_policy_kernel_requires_one_time_confirmation_for_mesh_route():
    kernel = PolicyKernel()
    parameters = {
        "request_id": "req-mesh-policy",
        "target_device_id": "android_test_device",
        "payload": {"type": "skill_request", "skill_id": "ui_tap"},
    }

    decision = kernel.evaluate(
        domain="mesh",
        action="mesh.route_to_device",
        parameters=parameters,
        request_id="req-mesh-policy",
    )

    assert decision.allowed is False
    assert decision.confirmation_token
    pending = kernel.confirm_token(decision.confirmation_token, request_id="req-mesh-policy")
    assert pending is not None
    assert pending.parameters == parameters
    assert kernel.confirm_token(decision.confirmation_token, request_id="req-mesh-policy") is None
