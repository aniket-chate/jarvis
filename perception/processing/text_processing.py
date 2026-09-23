"""Text Processing Module for JARVIS Layer 1.

Performs lexical normalization, token counting, and heuristic intent/entity tagging
without LLM overhead, converting raw text input into structured text_processed events.
"""

import re
import logging
from typing import Dict, Any, List
from perception.events import PerceptionEvent, event_bus
from config.settings import settings

logger = logging.getLogger("JARVIS.Processing.Text")


class TextProcessor:
    """Performs deterministic text analysis and normalization."""

    def process(self, text: str, source_event: str = "text_input") -> PerceptionEvent:
        """Analyzes text and emits a 'text_processed' PerceptionEvent."""
        raw = text or ""
        normalized = re.sub(r"\s+", " ", raw).strip()

        words = normalized.split() if normalized else []
        word_count = len(words)
        char_count = len(normalized)

        # Heuristic intent classification
        intents: List[str] = []
        lower = normalized.lower()
        if lower.endswith("?") or any(lower.startswith(w) for w in ["what", "who", "where", "when", "why", "how", "is", "can", "could"]):
            intents.append("inquiry")
        if any(w in lower for w in ["open", "run", "start", "switch", "turn", "set", "play", "stop"]):
            intents.append("action_command")
        if any(w in lower for w in ["hello", "hi", "hey", "good morning", "good evening"]):
            intents.append("greeting")
        if any(w in lower for w in ["status", "battery", "storage", "time", "date"]):
            intents.append("system_query")

        payload: Dict[str, Any] = {
            "raw_text": raw,
            "normalized_text": normalized,
            "word_count": word_count,
            "char_count": char_count,
            "inferred_intents": intents or ["general_dialogue"],
            "has_digits": any(c.isdigit() for c in normalized),
        }

        event = PerceptionEvent(
            type="text_processed",
            payload=payload,
            source="text_processing",
            active_persona=settings.active_persona_name,
        )

        logger.debug("[TextProcessor] Processed '%s' -> %d words, intents: %s", normalized[:30], word_count, intents)
        event_bus.publish(event)
        return event


text_processor = TextProcessor()
