"""Weather Agent for JARVIS Layer 3 (Group 1).

Retrieves live weather data using Open-Meteo free API (no keys required).
"""

import logging
from typing import Dict, Any

from skills.web_skills import weather_skill

logger = logging.getLogger("JARVIS.WeatherAgent")


class WeatherAgent:
    """Agent for global and local weather forecast queries."""

    def get_weather(self, location: str = "Delhi", time_target: str = "now") -> Dict[str, Any]:
        logger.info("[WeatherAgent] Fetching weather for '%s' (time_target=%s)", location, time_target)
        try:
            from capabilities.intelligence import capability_intelligence
            provider = capability_intelligence.select_provider("info.get_weather")
            if provider:
                action_res = provider.execute(
                    "info.get_weather",
                    {"location": location, "time_target": time_target},
                )
                if action_res.status == "SUCCESS" and action_res.output:
                    out = dict(action_res.output)
                    msg = action_res.message or out.get("message")
                    if not msg:
                        msg = f"Weather in {location}: {out.get('temperature')}°C, {out.get('condition', 'Clear')}."
                    out["message"] = msg
                    out["response"] = msg
                    out["output"] = msg
                    out["success"] = True
                    return out
                elif action_res.status == "FAILED":
                    err_msg = action_res.message or f"Could not retrieve weather for '{location}'."
                    return {"success": False, "status": "failed", "error": err_msg, "response": err_msg, "message": err_msg}
        except Exception as prov_err:
            logger.debug("[WeatherAgent] Capability provider route fallback: %s", prov_err)

        res = weather_skill.get_weather(location=location)
        if res.get("success"):
            msg = res.get("message", f"Weather in {location}: {res.get('temperature')}°C.")
            res["response"] = msg
            res["output"] = msg
        else:
            err_msg = res.get("error") or f"Unable to find weather for location '{location}'."
            res["response"] = err_msg
            res["message"] = err_msg
            res["status"] = "failed"
            res["success"] = False
        return res

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator Agent Router."""
        location = inputs.get("location") or inputs.get("city") or inputs.get("query") or "Delhi"
        time_target = inputs.get("time_target", "now")
        return self.get_weather(location=location, time_target=time_target)


weather_agent = WeatherAgent()
