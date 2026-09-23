"""Text Output Channel for JARVIS.

Emits structured and formatted text responses to terminal console, logs, or UI streams.
"""

import sys
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from config.settings import settings

logger = logging.getLogger("JARVIS.Output.Text")


class TextOutputChannel:
    """Channel for presenting formatted text outputs."""

    def render(self, text: str, persona_name: Optional[str] = None, stream=sys.stdout) -> str:
        """Prints persona-tagged formatted text response."""
        persona = persona_name or settings.active_persona_name
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] [{persona}] > {text}"
        print(formatted, file=stream)
        stream.flush()
        logger.info("[TextOutput] Rendered for %s: '%s'", persona, text[:40])
        return formatted


text_output = TextOutputChannel()
