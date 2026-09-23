"""Device Mesh Capability Provider for JARVIS Capability 36.

Discovers, authenticates, monitors, and routes commands across trusted devices
in the user mesh without domain-specific hardcoded device identities.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from gateway.registry import gateway_registry, DeviceTrustState, ClientDevice

logger = logging.getLogger("JARVIS.Providers.DeviceMesh")


@dataclass
class DeviceMeshConfig:
    """Configurable parameters for device mesh discovery and heartbeat policy."""
    heartbeat_timeout_sec: float = 120.0
    stale_threshold_sec: float = 300.0
    default_trust: str = "PENDING"
    default_latency_ms: float = 10.0
    max_payload_size_bytes: int = 1_000_000
    require_trust_for_routing: bool = True


class DeviceMeshProvider(BaseCapabilityProvider):
    """Provides dynamic device mesh operations over Tailscale and local network."""

    def __init__(self, config: Optional[DeviceMeshConfig] = None):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.mesh.device_mesh",
                name="JARVIS Device Mesh Provider",
                supported_capabilities=[
                    "mesh.discover_peers",
                    "mesh.register_device",
                    "mesh.get_device_status",
                    "mesh.route_to_device",
                    "mesh.sync_state",
                    "mesh.device_heartbeat",
                    "mesh.revoke_device",
                    "mesh.select_device",
                    "mesh.set_device_trust",
                ],
                priority=10,
                estimated_latency_ms=15.0,
                safety_level="modifying",
                description="Dynamic device discovery, trust lifecycle, routing, and selection.",
            )
        )
        self.config = config or DeviceMeshConfig()
        self.registry = gateway_registry

    def is_available(self) -> bool:
        return self.registry is not None

    def execute(
        self,
        capability: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        t0 = time.perf_counter()
        try:
            if capability == "mesh.discover_peers":
                res = self._discover_peers(parameters)
            elif capability == "mesh.register_device":
                res = self._register_device(parameters)
            elif capability == "mesh.get_device_status":
                res = self._get_device_status(parameters)
            elif capability == "mesh.route_to_device":
                res = self._route_to_device(parameters)
            elif capability == "mesh.sync_state":
                res = self._sync_state(parameters)
            elif capability == "mesh.device_heartbeat":
                res = self._device_heartbeat(parameters)
            elif capability == "mesh.revoke_device":
                res = self._revoke_device(parameters)
            elif capability == "mesh.select_device":
                res = self._select_device(parameters)
            elif capability == "mesh.set_device_trust":
                res = self._set_device_trust(parameters)
            else:
                elapsed = (time.perf_counter() - t0) * 1000
                self.record_outcome(False)
                return ActionResult(
                    status="FAILED",
                    output=None,
                    message=f"Unsupported capability: {capability}",
                    execution_time_ms=elapsed,
                )

            elapsed = (time.perf_counter() - t0) * 1000
            self.record_outcome(True)
            return ActionResult(
                status="SUCCESS",
                output=res,
                message="Device mesh operation completed successfully.",
                execution_time_ms=elapsed,
            )
        except Exception as e:
            logger.error("[DeviceMeshProvider] Error executing '%s': %s", capability, str(e), exc_info=True)
            elapsed = (time.perf_counter() - t0) * 1000
            self.record_outcome(False)
            return ActionResult(
                status="FAILED",
                output={"error": str(e)},
                message=str(e),
                execution_time_ms=elapsed,
            )

    def _discover_peers(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Discovers all peer nodes in the mesh matching optional filters."""
        all_devices = self.registry.list_active_devices()
        online_only = params.get("online_only", False)
        required_cap = params.get("capability")
        trust_filter = params.get("trust_state")

        filtered = []
        for d in all_devices:
            if online_only and not d.get("online"):
                continue
            if trust_filter and d.get("trust_state") != trust_filter:
                continue
            if required_cap and required_cap not in d.get("capabilities", []):
                continue
            filtered.append(d)

        return {
            "devices": filtered,
            "count": len(filtered),
            "total_count": len(all_devices),
            "matched_count": len(filtered),
            "online_count": sum(1 for d in all_devices if d.get("online")),
        }

    def _register_device(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Dynamically registers or updates a device in the mesh."""
        device_id = params.get("device_id")
        if not device_id or not str(device_id).strip():
            raise ValueError("device_id must be provided and non-empty")

        device_id = str(device_id).strip()
        name = params.get("name") or f"Device {device_id}"
        client_type = params.get("client_type", "device")
        ip_address = params.get("ip_address", "127.0.0.1")
        capabilities = params.get("capabilities") or ["audio_output", "notifications", "display"]
        latency_ms = float(params.get("latency_ms", self.config.default_latency_ms))

        trust_str = params.get("trust_state", self.config.default_trust).upper()
        try:
            trust_state = DeviceTrustState[trust_str]
        except KeyError:
            trust_state = DeviceTrustState.TRUSTED

        dev = self.registry.register_device(
            device_id=device_id,
            name=name,
            client_type=client_type,
            ip_address=ip_address,
            capabilities=capabilities,
            trust_state=trust_state,
            latency_ms=latency_ms,
        )

        return {
            "device_id": dev.device_id,
            "name": dev.name,
            "client_type": dev.client_type,
            "ip_address": dev.ip_address,
            "capabilities": dev.capabilities,
            "trust_state": dev.trust_state.value,
            "online": dev.is_alive(),
            "registered": True,
        }

    def _get_device_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieves real-time status and health of a specific device."""
        device_id = params.get("device_id")
        if not device_id:
            raise ValueError("device_id is required")

        dev = self.registry.get_device(device_id) or self.registry.find_device(device_id)
        if not dev:
            return {
                "device_id": device_id,
                "found": False,
                "online": False,
                "error": f"Device '{device_id}' not found in mesh registry.",
            }

        return {
            "found": True,
            **dev.to_dict(),
        }

    def _route_to_device(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Routes payload to target device, strictly rejecting offline or revoked nodes."""
        target_id = params.get("target_device_id") or params.get("device_id")
        if not target_id:
            raise ValueError("target_device_id is required")

        payload = params.get("payload") or {
            "type": params.get("type", "command"),
            "data": params.get("data") or params.get("message") or {},
        }

        # Run dispatch synchronously safely
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    result = pool.submit(asyncio.run, self.registry.dispatch_to_device(target_id, payload, require_trusted=self.config.require_trust_for_routing)).result()
            else:
                result = loop.run_until_complete(self.registry.dispatch_to_device(target_id, payload, require_trusted=self.config.require_trust_for_routing))
        except RuntimeError:
            result = asyncio.run(self.registry.dispatch_to_device(target_id, payload, require_trusted=self.config.require_trust_for_routing))

        return result

    def _sync_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronizes state payload across all reachable mesh nodes."""
        state_payload = params.get("state") or params.get("payload") or {}
        wrap = {
            "type": "mesh_sync_state",
            "state": state_payload,
            "timestamp": time.time(),
        }

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    cnt = pool.submit(asyncio.run, self.registry.broadcast_all(wrap)).result()
            else:
                cnt = loop.run_until_complete(self.registry.broadcast_all(wrap))
        except RuntimeError:
            cnt = asyncio.run(self.registry.broadcast_all(wrap))

        return {
            "success": True,
            "synced_nodes": cnt,
            "timestamp": time.time(),
        }

    def _device_heartbeat(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Refreshes device presence heartbeat."""
        device_id = params.get("device_id")
        if not device_id:
            raise ValueError("device_id is required for heartbeat")

        touched = self.registry.touch(device_id)
        dev = self.registry.get_device(device_id)
        return {
            "device_id": device_id,
            "touched": touched,
            "online": dev.is_alive() if dev else False,
            "last_seen_epoch": dev.last_seen if dev else 0.0,
        }

    def _revoke_device(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Isolates and revokes a device from mesh participation."""
        device_id = params.get("device_id")
        if not device_id:
            raise ValueError("device_id is required for revocation")

        revoked = self.registry.revoke_device(device_id)
        return {
            "device_id": device_id,
            "revoked": revoked,
            "trust_state": DeviceTrustState.REVOKED.value if revoked else "NOT_FOUND",
        }

    def _select_device(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Selects the best trusted online device matching capability requirements."""
        req_cap = params.get("required_capability") or params.get("capability")
        if not req_cap:
            raise ValueError("required_capability is required for device selection")

        require_trusted = params.get("require_trusted", True)
        selected = self.registry.select_device(req_cap, require_trusted=require_trusted)

        if not selected:
            return {
                "found": False,
                "required_capability": req_cap,
                "error": f"No online trusted device found advertising capability '{req_cap}'.",
            }

        dev_dict = {
            "device_id": selected.device_id,
            "name": selected.name,
            "client_type": selected.client_type,
            "ip_address": selected.ip_address,
            "capabilities": selected.capabilities,
            "latency_ms": selected.latency_ms,
        }
        return {
            "found": True,
            "selected_device": dev_dict,
            **dev_dict,
        }

    def _set_device_trust(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Explicitly updates or escalates device trust state under policy authority."""
        device_id = params.get("device_id")
        if not device_id:
            raise ValueError("device_id is required to update trust state")

        trust_str = str(params.get("trust_state", "TRUSTED")).upper()
        try:
            new_state = DeviceTrustState[trust_str]
        except KeyError:
            raise ValueError(f"Invalid trust state: '{trust_str}'")

        success = self.registry.set_device_trust(device_id, new_state)
        dev = self.registry.get_device(device_id)
        return {
            "device_id": device_id,
            "success": success,
            "trust_state": dev.trust_state.value if dev else "NOT_FOUND",
        }
