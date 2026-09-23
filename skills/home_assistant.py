"""Home Assistant Skill for JARVIS.

Integrates with local Home Assistant instance for smart home / IoT control.
Graceful degradation: Disables itself if not enabled in config.yaml or if
HOME_ASSISTANT_TOKEN is not configured in .env.
"""

import logging
from typing import Dict, List, Any
import httpx
from config.settings import settings

logger = logging.getLogger("JARVIS.Skills.HomeAssistant")


class HomeAssistantSkill:
    def __init__(self):
        self.is_available = settings.home_assistant_available
        self.ha_url = settings.integrations.get("home_assistant", {}).get("url", "http://homeassistant.local:8123").rstrip("/")
        self.token = settings.home_assistant_token

        if not self.is_available:
            logger.info("[Home Assistant] Skill disabled (no active configuration or token)")

    async def get_states(self) -> Dict[str, Any]:
        """Fetches all entity states from Home Assistant."""
        if not self.is_available:
            return {
                "success": False,
                "error": "Home Assistant is disabled or HOME_ASSISTANT_TOKEN is missing from .env",
                "entities": [],
            }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.ha_url}/api/states", headers=headers)
                if res.status_code == 200:
                    entities = [
                        {"entity_id": s.get("entity_id"), "state": s.get("state"), "friendly_name": s.get("attributes", {}).get("friendly_name")}
                        for s in res.json()
                    ]
                    return {"success": True, "entities": entities}
                return {"success": False, "status": res.status_code, "entities": []}
        except Exception as e:
            logger.error("[Home Assistant Error] %s", str(e))
            return {"success": False, "error": str(e), "entities": []}

    async def call_service(self, domain: str, service: str, entity_id: str) -> Dict[str, Any]:
        """Calls a service (e.g. light.turn_on, switch.toggle)."""
        if not self.is_available:
            return {"success": False, "error": "Home Assistant integration is not enabled"}

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id}

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(f"{self.ha_url}/api/services/{domain}/{service}", json=payload, headers=headers)
                return {"success": res.status_code == 200, "response": res.text}
        except Exception as e:
            logger.error("[Home Assistant Service Error] %s", str(e))
            return {"success": False, "error": str(e)}


home_assistant_skill = HomeAssistantSkill()
