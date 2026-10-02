"""Regression tests for truthful device-mesh command delivery and ACK verification."""

import asyncio
import sys
import threading
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from gateway.registry import DeviceGatewayRegistry, DeviceTrustState


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, payload):
        self.messages.append(payload)


class TestDeviceMeshAck(unittest.TestCase):
    def test_reconnect_preserves_explicit_trust(self):
        registry = DeviceGatewayRegistry()
        registry.register_device(
            device_id="ack_trust_test",
            name="Phone",
            client_type="phone",
            ip_address="10.0.0.2",
            capabilities=["notifications"],
            trust_state=DeviceTrustState.TRUSTED,
        )
        registry.register_device(
            device_id="ack_trust_test",
            name="Phone",
            client_type="phone",
            ip_address="10.0.0.2",
            capabilities=["notifications"],
            trust_state=DeviceTrustState.PENDING,
        )
        self.assertEqual(
            registry.get_device("ack_trust_test").trust_state,
            DeviceTrustState.TRUSTED,
        )

    def test_skill_request_requires_real_device_ack(self):
        registry = DeviceGatewayRegistry()
        ws = FakeWebSocket()
        registry.register_device(
            device_id="ack_device",
            name="Ack Phone",
            client_type="phone",
            ip_address="10.0.0.3",
            capabilities=["ui_actions"],
            websocket=ws,
            trust_state=DeviceTrustState.TRUSTED,
        )

        async def run():
            request_id = "req_ack_001"

            def resolver():
                time.sleep(0.05)
                registry.resolve_pending_ack(
                    request_id,
                    {
                        "type": "skill_result",
                        "request_id": request_id,
                        "success": True,
                        "result": {"status": "executed"},
                    },
                )

            threading.Thread(target=resolver, daemon=True).start()
            return await registry.dispatch_to_device(
                "ack_device",
                {
                    "type": "skill_request",
                    "request_id": request_id,
                    "skill_id": "send_notification",
                    "parameters": {"message": "test"},
                },
                require_trusted=True,
                await_ack=True,
                ack_timeout_sec=1.0,
            )

        result = asyncio.run(run())
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "acknowledged")
        self.assertEqual(ws.messages[0]["request_id"], "req_ack_001")

    def test_skill_request_times_out_truthfully(self):
        registry = DeviceGatewayRegistry()
        ws = FakeWebSocket()
        registry.register_device(
            device_id="timeout_device",
            name="Timeout Phone",
            client_type="phone",
            ip_address="10.0.0.4",
            capabilities=["ui_actions"],
            websocket=ws,
            trust_state=DeviceTrustState.TRUSTED,
        )

        result = asyncio.run(
            registry.dispatch_to_device(
                "timeout_device",
                {
                    "type": "skill_request",
                    "request_id": "req_timeout_001",
                    "skill_id": "send_notification",
                    "parameters": {"message": "test"},
                },
                require_trusted=True,
                await_ack=True,
                ack_timeout_sec=0.05,
            )
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "ack_timeout")

    def test_skill_request_never_reports_offline_as_executed(self):
        registry = DeviceGatewayRegistry()
        registry.register_device(
            device_id="offline_device",
            name="Offline Phone",
            client_type="phone",
            ip_address="10.0.0.5",
            capabilities=["ui_actions"],
            trust_state=DeviceTrustState.TRUSTED,
        )

        result = asyncio.run(
            registry.dispatch_to_device(
                "offline_device",
                {
                    "type": "skill_request",
                    "request_id": "req_offline_001",
                    "skill_id": "send_notification",
                },
                require_trusted=True,
                await_ack=True,
            )
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "not_connected")


if __name__ == "__main__":
    unittest.main()
