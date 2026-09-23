"""Device Mesh Agent for JARVIS Layer 3.

Exposes Device Mesh capability operations to the Orchestrator Agent Router.
"""

import logging
from typing import Any, Dict

from capabilities.intelligence import capability_intelligence

logger = logging.getLogger("JARVIS.DeviceMeshAgent")


class DeviceMeshAgent:
    """Agent mediating between Orchestrator and DeviceMeshProvider."""

    def __init__(self):
        pass

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        action = inputs.get("action", "discover_peers")
        provider = capability_intelligence.select_provider(f"mesh.{action}") or capability_intelligence.select_provider("mesh.discover_peers")
        if not provider:
            return {
                "success": False,
                "error": "No provider available for device mesh operations.",
            }

        res = provider.execute(f"mesh.{action}", inputs)
        return {
            "success": res.status == "SUCCESS",
            "status": res.status,
            "output": res.output,
            "message": res.message,
        }


device_mesh_agent = DeviceMeshAgent()
