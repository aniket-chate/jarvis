"""Generic bridge from conversational plans to Capability Intelligence providers.

Keeps the cognitive planner independent from individual capability providers.
The provider registry remains the source of truth for availability and execution.
"""

from typing import Any, Dict
from capabilities.intelligence import capability_intelligence


class CapabilityAgent:
    """Execute a named capability through the selected registered provider."""

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        capability = str(inputs.get("capability") or "").strip()
        parameters = dict(inputs.get("parameters") or {})
        if not capability:
            return {"success": False, "error": "No capability was specified."}

        provider = capability_intelligence.select_provider(capability, context=inputs.get("context"))
        if provider is None:
            return {
                "success": False,
                "status": "capability_unavailable",
                "capability": capability,
                "error": f"No available provider is registered for '{capability}'.",
            }

        result = provider.execute(capability, parameters, context=inputs.get("context"))
        success = result.status in {"SUCCESS", "COMPLETED"}
        return {
            "success": success,
            "status": result.status,
            "capability": capability,
            "provider": provider.provider_id,
            "output": result.output,
            "message": result.message,
            "execution_time_ms": result.execution_time_ms,
        }


capability_agent = CapabilityAgent()
