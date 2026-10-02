"""Device Gateway Registry for Multi-Device JARVIS Ecosystem.

Tracks and routes commands, audio casting, and notifications to other JARVIS clients
(Android phones, secondary PCs, tablets, web portals, TVs) connected via Local Network or Tailscale.
"""

import time
import asyncio
import logging
import threading
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from typing import Dict, List, Optional, Any
from fastapi import WebSocket

from enum import Enum

logger = logging.getLogger("JARVIS.Gateway")


class DeviceTrustState(str, Enum):
    """Explicit trust state for devices in the user mesh."""
    UNKNOWN = "UNKNOWN"
    PENDING = "PENDING"
    TRUSTED = "TRUSTED"
    REVOKED = "REVOKED"
    OFFLINE = "OFFLINE"


class ClientDevice:
    """Represents a connected physical or virtual device in the JARVIS mesh."""

    def __init__(
        self,
        device_id: str,
        name: str,
        client_type: str,
        ip_address: str,
        capabilities: Optional[List[str]] = None,
        websocket: Optional[WebSocket] = None,
        trust_state: DeviceTrustState = DeviceTrustState.PENDING,
        latency_ms: float = 10.0,
    ):
        self.device_id = device_id
        self.name = name
        self.client_type = client_type.lower()  # "phone", "pc", "tv", "tablet", "web", "iot"
        self.ip_address = ip_address
        self.capabilities = capabilities or ["audio_output", "notifications", "display"]
        self.trust_state = trust_state
        self.latency_ms = latency_ms
        self.last_seen = time.time()
        self.paired_at = time.time()
        self.websocket: Optional[WebSocket] = websocket
        self.pending_messages: List[Dict[str, Any]] = []

    def touch(self) -> None:
        """Refreshes device heartbeat."""
        self.last_seen = time.time()

    def is_alive(self, timeout_seconds: float = 120.0) -> bool:
        """Determines if device is currently online based on heartbeat or active WebSocket."""
        if self.trust_state == DeviceTrustState.REVOKED:
            return False
        if self.websocket is not None:
            return True
        return (time.time() - self.last_seen) < timeout_seconds

    def to_dict(self) -> Dict[str, Any]:
        """Serializes device status for REST API and registry queries."""
        online = self.is_alive()
        effective_trust = self.trust_state.value if online or self.trust_state == DeviceTrustState.REVOKED else DeviceTrustState.OFFLINE.value
        return {
            "device_id": self.device_id,
            "name": self.name,
            "client_type": self.client_type,
            "ip_address": self.ip_address,
            "capabilities": self.capabilities,
            "trust_state": effective_trust,
            "online": online,
            "latency_ms": self.latency_ms,
            "has_active_ws": self.websocket is not None,
            "last_seen_epoch": self.last_seen,
            "paired_at": self.paired_at,
        }


class DeviceGatewayRegistry:
    """Live registry managing all active devices, presence tracking, and cross-device dispatch."""

    def __init__(self):
        self._devices: Dict[str, ClientDevice] = {}
        self._ack_lock = threading.Lock()
        self._pending_acks: Dict[str, Future] = {}
        # Pre-register the Host PC
        self._init_host_pc()

    def _init_host_pc(self) -> None:
        """Initializes default entry for the host PC running the JARVIS brain."""
        host_device = ClientDevice(
            device_id="host_pc",
            name="Host PC",
            client_type="pc",
            ip_address="127.0.0.1",
            capabilities=["audio_output", "display", "browser", "vlm", "tts", "stt", "llm", "notifications"],
            trust_state=DeviceTrustState.TRUSTED,
            latency_ms=1.0,
        )
        self._devices["host_pc"] = host_device

    def register_device(
        self,
        device_id: str,
        name: str,
        client_type: str,
        ip_address: str,
        capabilities: Optional[List[str]] = None,
        websocket: Optional[WebSocket] = None,
        trust_state: DeviceTrustState = DeviceTrustState.PENDING,
        latency_ms: float = 10.0,
    ) -> ClientDevice:
        """Registers or updates a client device."""
        if device_id in self._devices:
            dev = self._devices[device_id]
            dev.name = name
            dev.client_type = client_type.lower()
            dev.ip_address = ip_address
            # Security Rule: If a device is already REVOKED, re-registration cannot silently un-revoke it!
            if dev.trust_state == DeviceTrustState.REVOKED:
                logger.warning("[Device Gateway] Attempted re-registration of REVOKED device '%s' blocked. Trust state remains REVOKED.", device_id)
            elif dev.trust_state == DeviceTrustState.TRUSTED and trust_state == DeviceTrustState.PENDING:
                logger.debug("[Device Gateway] Preserving TRUSTED state for reconnecting device '%s'.", device_id)
            else:
                dev.trust_state = trust_state
            dev.latency_ms = latency_ms
            if capabilities:
                dev.capabilities = capabilities
            if websocket:
                dev.websocket = websocket
            dev.touch()
            logger.info("[Device Gateway] Updated client '%s' (%s, trust=%s) at %s", name, client_type, trust_state.value, ip_address)
        else:
            dev = ClientDevice(
                device_id=device_id,
                name=name,
                client_type=client_type,
                ip_address=ip_address,
                capabilities=capabilities,
                websocket=websocket,
                trust_state=trust_state,
                latency_ms=latency_ms,
            )
            self._devices[device_id] = dev
            logger.info("[Device Gateway] Registered client '%s' (%s, trust=%s) at %s", name, client_type, trust_state.value, ip_address)
        return dev

    def revoke_device(self, device_id: str) -> bool:
        """Revokes trust for a device, isolating it from the mesh."""
        dev = self._devices.get(device_id)
        if dev:
            dev.trust_state = DeviceTrustState.REVOKED
            dev.websocket = None
            logger.warning("[Device Gateway] Revoked trust for device '%s' (id=%s)", dev.name, device_id)
            return True
        return False

    def set_device_trust(self, device_id: str, trust_state: DeviceTrustState) -> bool:
        """Updates explicit trust state for a device."""
        dev = self._devices.get(device_id)
        if dev:
            dev.trust_state = trust_state
            logger.info("[Device Gateway] Set trust for device '%s' to %s", dev.name, trust_state.value)
            return True
        return False

    def select_device(
        self,
        required_capability: str,
        require_trusted: bool = True,
    ) -> Optional[ClientDevice]:
        """Data-driven device selection matching required capability and trust state."""
        candidates = []
        for dev in self._devices.values():
            if not dev.is_alive():
                continue
            if require_trusted and dev.trust_state != DeviceTrustState.TRUSTED:
                continue
            if required_capability in dev.capabilities:
                candidates.append(dev)

        if not candidates:
            return None

        # Sort by lowest latency, prioritizing active WebSocket
        candidates.sort(key=lambda d: (0 if d.websocket else 1, d.latency_ms))
        return candidates[0]

    def attach_websocket(self, device_id: str, websocket: WebSocket) -> Optional[ClientDevice]:
        """Attaches an active WebSocket channel to a registered device."""
        dev = self._devices.get(device_id)
        if dev:
            if dev.trust_state == DeviceTrustState.REVOKED:
                logger.warning("[Device Gateway] Rejected WebSocket attach for revoked device '%s'", dev.name)
                return None
            dev.websocket = websocket
            dev.touch()
            logger.info("[Device Gateway] Attached active WebSocket to device '%s'", dev.name)
        return dev

    def detach_websocket(self, device_id: str) -> None:
        """Detaches WebSocket when connection drops."""
        dev = self._devices.get(device_id)
        if dev:
            dev.websocket = None
            dev.touch()
            logger.info("[Device Gateway] Detached WebSocket for device '%s'", dev.name)

    def touch(self, device_id: str) -> bool:
        """Updates last seen timestamp for device."""
        dev = self._devices.get(device_id)
        if dev:
            dev.touch()
            return True
        return False

    def unregister_device(self, device_id: str) -> bool:
        """Removes a device from the registry."""
        if device_id in self._devices and device_id != "host_pc":
            del self._devices[device_id]
            logger.info("[Device Gateway] Unregistered device %s", device_id)
            return True
        return False

    def get_device(self, device_id: str) -> Optional[ClientDevice]:
        """Retrieves device by exact device_id."""
        return self._devices.get(device_id)

    def find_device(self, query: str) -> Optional[ClientDevice]:
        """Finds a device by device_id, name, or client_type."""
        if not query:
            return None
        q = query.strip().lower()
        if not q:
            return None
        # 1. Exact device_id match
        if q in self._devices:
            return self._devices[q]

        # 2. Match by client_type
        for dev in self._devices.values():
            if dev.client_type == q and dev.is_alive():
                return dev

        # 3. Match in name
        for dev in self._devices.values():
            if (q in dev.name.lower() or dev.name.lower() in q) and dev.is_alive():
                return dev

        # 4. Fallback search among all devices even if not marked currently online
        for dev in self._devices.values():
            if dev.client_type == q or q in dev.name.lower():
                return dev

        return None

    def list_active_devices(self) -> List[Dict[str, Any]]:
        """Returns all devices in registry with live online status."""
        return [dev.to_dict() for dev in self._devices.values()]

    async def dispatch_to_device(
        self,
        target_identifier: str,
        payload: Dict[str, Any],
        require_trusted: bool = True,
        await_ack: bool = False,
        ack_timeout_sec: float = 15.0,
    ) -> Dict[str, Any]:
        """Route a payload and optionally wait for a correlated device ACK."""
        device = self.find_device(target_identifier)
        if not device:
            return {
                "success": False,
                "error": f"Target device '{target_identifier}' not found in registry.",
            }

        if device.trust_state == DeviceTrustState.REVOKED:
            return {
                "success": False,
                "error": f"Target device '{device.device_id}' is revoked from mesh.",
            }

        if not device.is_alive():
            return {
                "success": False,
                "error": f"Target device '{device.device_id}' is currently offline.",
            }

        if require_trusted and device.trust_state in (DeviceTrustState.UNKNOWN, DeviceTrustState.PENDING):
            return {
                "success": False,
                "error": f"Target device '{device.device_id}' is not trusted (current trust state: {device.trust_state.value}). Explicit trust authorization required.",
            }

        logger.info("[Device Gateway] Routing cast payload to %s (%s, IP=%s)", device.name, device.client_type, device.ip_address)

        # If device has active WebSocket, send directly
        if device.websocket:
            try:
                ack_future = None
                request_id = payload.get("request_id") if isinstance(payload, dict) else None
                if await_ack and request_id:
                    ack_future = self.register_pending_ack(str(request_id))

                await device.websocket.send_json(payload)
                device.touch()

                if ack_future is not None:
                    try:
                        ack = await asyncio.to_thread(ack_future.result, ack_timeout_sec)
                        return {
                            "success": bool(ack.get("success")),
                            "target_device_id": device.device_id,
                            "target_name": device.name,
                            "target_type": device.client_type,
                            "ip": device.ip_address,
                            "status": "acknowledged" if ack.get("success") else "device_rejected",
                            "ack": ack,
                            "payload": payload,
                        }
                    except FutureTimeoutError:
                        self.cancel_pending_ack(str(request_id))
                        return {
                            "success": False,
                            "target_device_id": device.device_id,
                            "target_name": device.name,
                            "target_type": device.client_type,
                            "ip": device.ip_address,
                            "status": "ack_timeout",
                            "error": f"No device ACK received within {ack_timeout_sec:.1f}s.",
                            "payload": payload,
                        }

                return {
                    "success": True,
                    "target_device_id": device.device_id,
                    "target_name": device.name,
                    "target_type": device.client_type,
                    "ip": device.ip_address,
                    "status": "delivered_via_websocket",
                    "payload": payload,
                }
            except Exception as e:
                logger.warning("[Device Gateway] Failed delivering via WebSocket to %s: %s", device.name, str(e))
                device.websocket = None

        # Queue message if WebSocket not active
        device.pending_messages.append(payload)
        return {
            "success": True,
            "target_device_id": device.device_id,
            "target_name": device.name,
            "target_type": device.client_type,
            "ip": device.ip_address,
            "status": "queued_for_polling",
            "payload": payload,
        }


    def register_pending_ack(self, request_id: str) -> Future:
        """Register a thread-safe ACK waiter for a device command."""
        future = Future()
        with self._ack_lock:
            previous = self._pending_acks.pop(request_id, None)
            if previous and not previous.done():
                previous.cancel()
            self._pending_acks[request_id] = future
        return future

    def resolve_pending_ack(self, request_id: str, result: Dict[str, Any]) -> bool:
        """Resolve a device command waiter from an incoming skill_result."""
        with self._ack_lock:
            future = self._pending_acks.pop(request_id, None)
        if future is None:
            return False
        if not future.done():
            future.set_result(result)
        return True

    def cancel_pending_ack(self, request_id: str) -> None:
        with self._ack_lock:
            future = self._pending_acks.pop(request_id, None)
        if future and not future.done():
            future.cancel()

    async def broadcast_all(self, payload: Dict[str, Any], exclude_ws: Optional[Any] = None) -> int:
        """Broadcasts payload to all currently connected WebSockets, optionally skipping sender."""
        count = 0
        for dev in list(self._devices.values()):
            if dev.websocket and dev.websocket != exclude_ws:
                try:
                    await dev.websocket.send_json(payload)
                    count += 1
                except Exception as ex:
                    logger.debug("[Device Gateway] Error broadcasting to %s: %s", dev.name, ex)
                    dev.websocket = None
        return count

    def get_connected_devices(self) -> List[Dict[str, Any]]:
        """Authoritative query returning live connected devices in the mesh."""
        return [dev.to_dict() for dev in self._devices.values()]

    def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """Returns status of a specific device."""
        dev = self.get_device(device_id) or self.find_device(device_id)
        if dev:
            return dev.to_dict()
        return {"error": f"Device '{device_id}' not found", "online": False}

    def get_device_capabilities(self, device_id: str) -> List[str]:
        """Returns capabilities for a specific device."""
        dev = self.get_device(device_id) or self.find_device(device_id)
        if dev:
            return list(dev.capabilities)
        return []

    def format_devices_human_readable(self) -> str:
        """Formats the authoritative live device registry into concise, user-friendly text."""
        devices = self.get_connected_devices()
        if not devices:
            return "There are currently no connected devices detected in your device registry."

        online_devices = [d for d in devices if d.get("online")]
        total = len(devices)
        count_str = f"{len(online_devices)} online" if len(online_devices) != total else f"{total}"

        lines = [f"You have {count_str} device{'s' if total != 1 else ''} in your mesh:"]
        for d in devices:
            status = "Online" if d.get("online") else "Offline"
            ctype = d.get("client_type", "device").capitalize()
            lines.append(f"- {d.get('name')} ({ctype}, {status})")

        return "\n".join(lines)


# Global singleton registry
gateway_registry = DeviceGatewayRegistry()

# Module-level convenience functions adhering directly to user specification
def get_connected_devices() -> List[Dict[str, Any]]:
    return gateway_registry.get_connected_devices()

def get_device_status(device_id: str) -> Dict[str, Any]:
    return gateway_registry.get_device_status(device_id)

def get_device_capabilities(device_id: str) -> List[str]:
    return gateway_registry.get_device_capabilities(device_id)

def format_devices_human_readable() -> str:
    return gateway_registry.format_devices_human_readable()

