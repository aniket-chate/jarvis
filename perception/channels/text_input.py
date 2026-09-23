"""Text Input Channel for JARVIS.

Ingests text queries from console, API, or WebSocket, normalizes payload,
and emits 'text_input' PerceptionEvents onto the Unified Event Bus.
"""

import logging
from typing import Dict, Any, Optional
from perception.events import PerceptionEvent, event_bus
from config.settings import settings

logger = logging.getLogger("JARVIS.Channels.Text")


class TextInputChannel:
    """Channel for capturing and emitting text commands."""

    def ingest(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> PerceptionEvent:
        """Ingests raw text, constructs PerceptionEvent, and publishes to EventBus."""
        cleaned = text.strip()
        payload = {
            "text": cleaned,
            "char_count": len(cleaned),
            "metadata": metadata or {},
        }

        event = PerceptionEvent(
            type="text_input",
            payload=payload,
            source="text_input",
            active_persona=settings.active_persona_name,
        )

        logger.debug("[TextInputChannel] Ingested text: '%s'", cleaned)
        event_bus.publish(event)
        return event


text_input_channel = TextInputChannel()
