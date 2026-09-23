"""Smart Home Agent for JARVIS Layer 3 (Group 2).

Integrates with Home Assistant REST API.
Operates against live Home Assistant instances or fallback demo/mock entities
if physical IoT devices are not yet on the subnet.
Gated by permission_checks for high-impact physical actuation (locks, heaters).
"""

import logging
from typing import Dict, Any, List, Optional
import httpx

from config.settings import settings
from agents.permission_checks import permission_gate

logger = logging.getLogger("JARVIS.SmartHomeAgent")


class SmartHomeAgent:
    """Agent for home automation, lights, climate, and IoT device telemetry."""

    def __init__(self):
        self.ha_url = settings.integrations.get("home_assistant", {}).get("url", "http://localhost:8123").rstrip("/")
        self.token = settings.home_assistant_token
        self.is_configured = bool(self.token)

        # Demo entities used for offline / pre-hardware testing
        self.demo_entities: Dict[str, Dict[str, Any]] = {
            "light.living_room": {"entity_id": "light.living_room", "state": "off", "friendly_name": "Living Room Light", "brightness": 0},
            "light.study_desk": {"entity_id": "light.study_desk", "state": "on", "friendly_name": "Desk Lamp", "brightness": 200},
            "switch.air_purifier": {"entity_id": "switch.air_purifier", "state": "on", "friendly_name": "Air Purifier"},
            "climate.thermostat": {"entity_id": "climate.thermostat", "state": "auto", "current_temperature": 22.5, "target_temperature": 23.0},
            "lock.front_door": {"entity_id": "lock.front_door", "state": "locked", "friendly_name": "Front Door Smart Lock"}
        }

    def get_entities(self) -> Dict[str, Any]:
        """Fetches states from Home Assistant or falls back to demo entities."""
        if self.is_configured:
            headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
            try:
                with httpx.Client(timeout=4.0) as client:
                    resp = client.get(f"{self.ha_url}/api/states", headers=headers)
                    if resp.status_code == 200:
                        entities = [
                            {"entity_id": s.get("entity_id"), "state": s.get("state"), "friendly_name": s.get("attributes", {}).get("friendly_name")}
                            for s in resp.json()
                        ]
                        return {"success": True, "mode": "live", "entities": entities}
            except Exception as e:
                logger.info("[SmartHomeAgent] Live HA instance unreachable (%s). Using demo entities.", str(e))

        # Demo mode
        return {
            "success": True,
            "mode": "demo",
            "entities": list(self.demo_entities.values()),
            "notice": "Operating against Home Assistant demo/mock entities (no live HA server detected)."
        }

    def call_service(
        self,
        domain: str,
        service: str,
        entity_id: str,
        data: Optional[Dict[str, Any]] = None,
        user_confirmed: bool = False
    ) -> Dict[str, Any]:
        """Controls a smart home entity."""
        # Check permission gate for locks or heaters
        if "lock" in domain or "climate" in domain or "lock" in entity_id:
            perm = permission_gate.check_permission(
                domain="app",
                action=f"smart_home_{service}",
                details={"domain": domain, "service": service, "entity_id": entity_id},
                confirmed=user_confirmed
            )
            if not perm.allowed:
                return {
                    "success": False,
                    "status": "pending_approval",
                    "message": perm.message,
                    "error": "Smart home actuation blocked pending user confirmation."
                }

        if self.is_configured:
            headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
            payload = {"entity_id": entity_id, **(data or {})}
            try:
                with httpx.Client(timeout=4.0) as client:
                    resp = client.post(f"{self.ha_url}/api/services/{domain}/{service}", json=payload, headers=headers)
                    if resp.status_code == 200:
                        return {"success": True, "mode": "live", "entity_id": entity_id, "service": f"{domain}.{service}"}
            except Exception as e:
                logger.warning("[SmartHomeAgent] Live HA call failed (%s). Emulating via demo entity.", str(e))

        # Demo entity emulation
        if entity_id in self.demo_entities:
            ent = self.demo_entities[entity_id]
            if service in ["turn_on", "lock"]:
                ent["state"] = "on" if service == "turn_on" else "locked"
            elif service in ["turn_off", "unlock"]:
                ent["state"] = "off" if service == "turn_off" else "unlocked"

            logger.info("[SmartHomeAgent] Updated demo entity '%s' state to '%s'", entity_id, ent["state"])
            return {
                "success": True,
                "mode": "demo",
                "entity_id": entity_id,
                "new_state": ent["state"],
                "service": f"{domain}.{service}"
            }

        return {
            "success": False,
            "error": f"Entity '{entity_id}' not found in live or demo entities."
        }

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator Agent Router."""
        action = inputs.get("action", "list")
        if action == "list" or "service" not in inputs:
            return self.get_entities()
        else:
            return self.call_service(
                domain=inputs.get("domain", "light"),
                service=inputs.get("service", "turn_on"),
                entity_id=inputs.get("entity_id", "light.living_room"),
                data=inputs.get("data"),
                user_confirmed=inputs.get("user_confirmed", False)
            )


smart_home_agent = SmartHomeAgent()
