"""Proactive Output Channel for JARVIS.

Dispatches context-triggered proactive recommendations, environmental alerts,
and scheduled reminders across text, voice, or screen channels.
"""

import logging
from typing import Dict, Any, Optional
from output.text_output import text_output
from output.voice_output import voice_output
from output.screen_output import screen_output
from config.settings import settings

logger = logging.getLogger("JARVIS.Output.Proactive")


class ProactiveOutputChannel:
    """Channel for unsolicited, proactive notifications."""

    def trigger_alert(
        self,
        alert_title: str,
        message: str,
        urgency: str = "normal",  # "low", "normal", "high"
        speak: bool = False,
        persona_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatches proactive notification across configured output mediums."""
        persona = persona_name or settings.active_persona_name

        card_data = {
            "Alert": alert_title,
            "Urgency": urgency.upper(),
            "Message": message,
        }

        # Render visual card
        screen_output.render_card(f"PROACTIVE NOTIFICATION ({urgency})", card_data, persona_name=persona)

        # Print text
        formatted = f"[PROACTIVE ALERT] {alert_title}: {message}"
        text_output.render(formatted, persona_name=persona)

        # Optionally speak
        if speak:
            voice_output.speak(message, persona_name=persona)

        logger.info("[ProactiveOutput] Alert dispatched: '%s' (Urgency: %s)", alert_title, urgency)
        return {
            "status": "dispatched",
            "title": alert_title,
            "urgency": urgency,
            "persona": persona,
        }


proactive_output = ProactiveOutputChannel()
