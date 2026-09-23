"""Unified Event Bus and PerceptionEvent Schema for JARVIS Layer 1.

Every raw or processed signal in the Perception Layer is normalized into a
PerceptionEvent and broadcasted across the Unified Event Bus.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import json
import logging
from typing import Dict, Any, List, Callable, Optional

from config.settings import settings

logger = logging.getLogger("JARVIS.EventBus")


@dataclass
class PerceptionEvent:
    """Standardized schema for all events flowing through the Perception Layer."""
    type: str  # e.g. "text_input", "speech_transcript", "wake_word_trigger", "face_capture", "vision_frame", "sensor_telemetry", "file_received", "context_snapshot"
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "unknown"  # "text_input", "voice_input", "vision_input", "sensor_input", "file_input"
    active_persona: str = field(default_factory=lambda: settings.active_persona_name)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


class UnifiedEventBus:
    """Pub/sub message bus orchestrating PerceptionEvents across subscribers."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[PerceptionEvent], None]]] = {}
        self._global_subscribers: List[Callable[[PerceptionEvent], None]] = []
        self._event_log: List[PerceptionEvent] = []
        self._max_history = 200

    def subscribe(self, event_type: str, handler: Callable[[PerceptionEvent], None]) -> None:
        """Subscribes a callable handler to a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

    def subscribe_all(self, handler: Callable[[PerceptionEvent], None]) -> None:
        """Subscribes a handler to receive every event regardless of type."""
        if handler not in self._global_subscribers:
            self._global_subscribers.append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[PerceptionEvent], None]) -> None:
        if event_type in self._subscribers and handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    def publish(self, event: PerceptionEvent) -> None:
        """Publishes an event to all matching subscribers and records it in history."""
        # Log event with source and active persona
        logger.debug(
            "[EventBus] Published %s from %s (Persona: %s)",
            event.type,
            event.source,
            event.active_persona,
        )

        # Store in bounded history
        self._event_log.append(event)
        if len(self._event_log) > self._max_history:
            self._event_log.pop(0)

        # Dispatch to specific subscribers
        if event.type in self._subscribers:
            for handler in self._subscribers[event.type]:
                try:
                    handler(event)
                except Exception as e:
                    logger.error("[EventBus Handler Error on %s]: %s", event.type, str(e))

        # Dispatch to global subscribers
        for global_handler in self._global_subscribers:
            try:
                global_handler(event)
            except Exception as e:
                logger.error("[EventBus Global Handler Error]: %s", str(e))

    def get_history(self, limit: int = 50, event_type: Optional[str] = None) -> List[PerceptionEvent]:
        """Returns recent published events, optionally filtered by type."""
        if event_type:
            filtered = [e for e in self._event_log if e.type == event_type]
            return filtered[-limit:]
        return self._event_log[-limit:]

    def clear_history(self) -> None:
        self._event_log.clear()


# Global event bus singleton instance
event_bus = UnifiedEventBus()
