"""Local Network Device Announcement & Discovery Stub for JARVIS.

Broadcasts device presence over local UDP port (19842) and discovers
other JARVIS peer instances (phones, PCs, speakers) on the local network.
Foundation for Device Gateway and Prompt 6.
"""

import json
import socket
import threading
import time
import logging
from typing import Dict, Any, Optional, List
from gateway.registry import gateway_registry

logger = logging.getLogger("JARVIS.Gateway.Announcement")

BROADCAST_PORT = 19842
BROADCAST_ADDR = "127.0.0.1"  # Loopback broadcast for multi-process testing on same machine, or subnet broadcast


class DeviceAnnouncer:
    """Announces presence and listens for peer devices."""

    def __init__(
        self,
        device_id: str,
        name: str,
        client_type: str = "pc",  # "pc", "phone", "speaker"
        ip_address: str = "127.0.0.1",
        port: int = BROADCAST_PORT,
    ):
        self.device_id = device_id
        self.name = name
        self.client_type = client_type
        self.ip_address = ip_address
        self.port = port
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._socket: Optional[socket.socket] = None

        # Register self in local registry
        gateway_registry.register_device(
            device_id=self.device_id,
            name=self.name,
            client_type=self.client_type,
            ip_address=self.ip_address,
        )

    def start(self) -> None:
        """Starts the UDP broadcast listener thread."""
        if self._running:
            return

        self._running = True
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind(("", self.port))
            self._socket.settimeout(0.5)

            self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._listener_thread.start()
            logger.info("[DeviceAnnouncer] Listener bound to port %d for '%s'", self.port, self.name)
        except Exception as e:
            logger.warning("[DeviceAnnouncer] Could not bind UDP port %d: %s", self.port, str(e))

    def announce_once(self) -> None:
        """Sends a single presence broadcast packet."""
        packet = {
            "device_id": self.device_id,
            "name": self.name,
            "client_type": self.client_type,
            "ip_address": self.ip_address,
            "timestamp": time.time(),
        }
        data = json.dumps(packet).encode("utf-8")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(data, (BROADCAST_ADDR, self.port))
            sock.close()
            logger.debug("[DeviceAnnouncer] Broadcast presence: '%s' (%s)", self.name, self.client_type)
        except Exception as e:
            logger.debug("[DeviceAnnouncer] Broadcast failed: %s", str(e))

    def _listen_loop(self) -> None:
        """Listens for UDP packets from other peer devices."""
        while self._running:
            try:
                data, addr = self._socket.recvfrom(4096)
                msg = json.loads(data.decode("utf-8"))
                peer_id = msg.get("device_id")
                # Ignore self announcements
                if peer_id and peer_id != self.device_id:
                    gateway_registry.register_device(
                        device_id=peer_id,
                        name=msg.get("name", "Unknown Peer"),
                        client_type=msg.get("client_type", "pc"),
                        ip_address=msg.get("ip_address", addr[0]),
                    )
                    logger.info(
                        "[DeviceAnnouncer] Discovered peer device '%s' (%s) at %s",
                        msg.get("name"),
                        msg.get("client_type"),
                        addr[0],
                    )
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.debug("[DeviceAnnouncer] Read error: %s", str(e))

    def stop(self) -> None:
        """Stops the broadcast listener."""
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
        logger.info("[DeviceAnnouncer] Stopped announcer for '%s'", self.name)

    def list_peers(self) -> List[Dict[str, Any]]:
        """Returns all registered peer devices excluding this device."""
        all_devs = gateway_registry.list_active_devices()
        return [d for d in all_devs if d["device_id"] != self.device_id]
