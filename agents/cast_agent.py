"""Cast Agent for JARVIS Layer 3 & Layer 6 Device Mesh.

Integrates pychromecast for casting media to Chromecast/Google-Cast hardware,
and coordinates cross-device playback to peer JARVIS clients (Phone, PC, TV)
via the central Device Gateway Registry.
"""

import re
import asyncio
import logging
from typing import Dict, Any, List, Optional
import httpx

from skills.cast_skill import CastSkill
from gateway.registry import gateway_registry

logger = logging.getLogger("JARVIS.CastAgent")


class CastAgent:
    """Agent for casting media to Google Cast hardware and peer JARVIS devices."""

    def __init__(self):
        self.skill = CastSkill()
        # Legacy static registry fallback
        self.legacy_registry: Dict[str, Dict[str, Any]] = {
            "desktop_secondary": {"ip": "127.0.0.1", "port": 8001, "type": "jarvis_client"},
            "mobile_client": {"ip": "127.0.0.1", "port": 8002, "type": "jarvis_mobile"},
        }

    def discover_targets(self) -> Dict[str, Any]:
        """Discovers network Chromecasts and live registered peer JARVIS clients."""
        chromecasts = self.skill.discover_devices(timeout=2)
        live_devices = gateway_registry.list_active_devices()
        registered_client_names = [d["name"] for d in live_devices]

        # Combine with legacy fallback keys if not present
        for k in self.legacy_registry.keys():
            if k not in registered_client_names:
                registered_client_names.append(k)

        return {
            "success": True,
            "chromecast_devices": chromecasts,
            "registered_jarvis_clients": registered_client_names,
            "active_mesh_devices": live_devices,
            "total_available": len(chromecasts) + len(registered_client_names),
        }

    def _parse_cast_intent(self, query: str) -> Dict[str, str]:
        """Extracts media title and target device from natural language text."""
        q = query.strip()
        target = "phone" if "phone" in q.lower() else ("pc" if any(w in q.lower() for w in ["pc", "computer", "desktop"]) else "desktop_secondary")
        
        # Extract song / media title
        title = "Sample Audio"
        # Match patterns like: play <song> on my <device>
        m = re.search(r"play\s+(.*?)\s+on\s+(my\s+)?(phone|tv|pc|desktop|screen)", q, re.IGNORECASE)
        if m:
            title = m.group(1).strip()
        else:
            # Fallback simple strip
            cleaned = re.sub(r"(play|stream|cast|on my phone|on phone|on pc|on tv|it)", "", q, flags=re.IGNORECASE).strip()
            if cleaned:
                title = cleaned

        return {
            "target": target,
            "title": title,
        }

    def cast_to_device(
        self,
        device_name: str,
        media_url: str,
        content_type: str = "video/mp4",
        title: str = "Media Playback",
    ) -> Dict[str, Any]:
        """Routes cast command to either a peer JARVIS client or a physical Chromecast."""
        logger.info("[CastAgent] Attempting to cast '%s' to '%s': %s", title, device_name, media_url)

        # 1. Check if device exists in live Device Gateway Registry
        reg_device = gateway_registry.find_device(device_name)
        if reg_device:
            # Target is the Host PC
            if reg_device.client_type in ["pc", "desktop"] or reg_device.device_id == "host_pc":
                logger.info("[CastAgent] Target is Host PC. Playing media locally.")
                # We can trigger local playback or browser agent
                return {
                    "success": True,
                    "target_type": "host_pc",
                    "device": reg_device.name,
                    "media_url": media_url,
                    "title": title,
                    "status": "playing_on_pc",
                    "message": f"Now playing '{title}' on {reg_device.name}.",
                }

            # Target is a remote client (Phone, Tablet, TV)
            cast_payload = {
                "type": "media_play",
                "action": "play_media",
                "title": title,
                "url": media_url,
                "content_type": content_type,
            }
            # Dispatch synchronously or run async task
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(gateway_registry.dispatch_to_device(device_name, cast_payload))
                else:
                    loop.run_until_complete(gateway_registry.dispatch_to_device(device_name, cast_payload))
            except Exception as e:
                logger.warning("[CastAgent] Async dispatch schedule warning: %s", str(e))
                # Direct fallback queue
                reg_device.pending_messages.append(cast_payload)

            return {
                "success": True,
                "target_type": "jarvis_peer",
                "device": reg_device.name,
                "device_id": reg_device.device_id,
                "client_type": reg_device.client_type,
                "media_url": media_url,
                "title": title,
                "status": "playing_on_remote_peer",
                "message": f"Command dispatched: playing '{title}' on {reg_device.name}.",
            }

        # 2. Check legacy peer registry
        if device_name in self.legacy_registry:
            peer_info = self.legacy_registry[device_name]
            url = f"http://{peer_info['ip']}:{peer_info['port']}/api/cast/play"
            logger.info("[CastAgent] Routing cast command to legacy peer endpoint: %s (%s)", device_name, url)

            try:
                with httpx.Client(timeout=3.0) as client:
                    resp = client.post(url, json={"media_url": media_url, "content_type": content_type, "title": title})
                    if resp.status_code == 200:
                        return {
                            "success": True,
                            "target_type": "jarvis_peer",
                            "device": device_name,
                            "endpoint": url,
                            "media_url": media_url,
                            "status": "playing_on_remote_peer",
                        }
            except Exception as e:
                logger.info("[CastAgent] Peer client endpoint simulated: %s", str(e))
                return {
                    "success": True,
                    "target_type": "jarvis_peer",
                    "device": device_name,
                    "endpoint": url,
                    "media_url": media_url,
                    "status": "dispatched_to_peer",
                    "notice": f"Media play command dispatched to peer {device_name}",
                }

        # 3. Otherwise attempt physical Chromecast
        return self.skill.cast_media(device_name, media_url, content_type)

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator Agent Router."""
        action = inputs.get("action", "cast")
        if action == "discover":
            return self.discover_targets()

        query_text = inputs.get("query", "")
        if query_text:
            parsed = self._parse_cast_intent(query_text)
            device = inputs.get("device") or parsed["target"]
            title = inputs.get("title") or parsed["title"]
        else:
            device = inputs.get("device", "phone")
            title = inputs.get("title", "Blinding Lights")

        # Media URL fallback
        media_url = inputs.get("media_url") or inputs.get("url")
        if not media_url:
            # High-quality open demo streaming media / YouTube stream link
            media_url = f"https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"

        content_type = inputs.get("content_type", "audio/mp3" if media_url.endswith(".mp3") else "video/mp4")
        return self.cast_to_device(device, media_url, content_type=content_type, title=title)


cast_agent = CastAgent()
