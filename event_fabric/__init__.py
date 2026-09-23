"""Event Fabric package."""
from event_fabric.schemas import (
    EventPriority,
    EventModality,
    EventStatus,
    UniversalEvent,
    PerceptionEvent,
    CommandEvent,
    InterruptEvent,
    ActionEvent,
    ObservationEvent,
    VerificationResult,
    ExperienceEvent,
)
from event_fabric.bus import EventFabricBus, event_bus

# Backward-compat alias
FeedbackEvent = ExperienceEvent
EventBus = EventFabricBus

__all__ = [
    "EventPriority",
    "EventModality",
    "EventStatus",
    "UniversalEvent",
    "PerceptionEvent",
    "CommandEvent",
    "InterruptEvent",
    "ActionEvent",
    "ObservationEvent",
    "VerificationResult",
    "ExperienceEvent",
    "FeedbackEvent",
    "EventFabricBus",
    "EventBus",
    "event_bus",
]
