"""Screen Output Channel for JARVIS.

Renders formatted visual cards, notifications, and telemetry dashboards
suitable for UI display or enhanced terminal viewing.
"""

import sys
import logging
from typing import Dict, Any, Optional
from config.settings import settings

logger = logging.getLogger("JARVIS.Output.Screen")


class ScreenOutputChannel:
    """Channel for rendering rich visual dashboard elements."""

    def render_card(self, title: str, details: Dict[str, Any], persona_name: Optional[str] = None) -> str:
        """Renders an ASCII card display for screen presentation."""
        persona = persona_name or settings.active_persona_name
        width = 65
        lines = []
        lines.append("+" + "-" * (width - 2) + "+")
        lines.append(f"| {title.upper():<{width - 4}} |")
        lines.append(f"| Persona: {persona:<{width - 13}} |")
        lines.append("+" + "-" * (width - 2) + "+")

        for k, v in details.items():
            entry = f"{k}: {v}"
            if len(entry) > width - 4:
                entry = entry[:width - 7] + "..."
            lines.append(f"| {entry:<{width - 4}} |")

        lines.append("+" + "-" * (width - 2) + "+")
        card_str = "\n".join(lines)
        print(card_str)
        sys.stdout.flush()
        logger.debug("[ScreenOutput] Displayed card '%s'", title)
        return card_str


screen_output = ScreenOutputChannel()
