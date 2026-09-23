"""JARVIS Event Fabric Schemas.

Defines the universal event envelopes connecting:
Experience Interfaces, Autonomous Runtime, Perception Fabric, Cognitive Core,
Policy/Safety, Execution, Action Fabric, Observation/Verification, and Memory/Learning.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, List, Optional
import uuid
import asyncio


class EventPriority(Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


class EventModality(Enum):
    TEXT = "text"
    VOICE = "voice"
    VISION = "vision"
    GESTURE = "gesture"
    SENSOR = "sensor"
    SYSTEM = "system"
    AUTONOMOUS = "autonomous"


class EventStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class UniversalEvent:
    """The canonical event envelope traversing the JARVIS Event Fabric."""
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    request_id: str = field(default_factory=lambda: f"req_{uuid.uuid4().hex[:12]}")
    parent_event_id: Optional[str] = None
    session_id: str = "default_session"
    task_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"
    event_type: str = "generic"
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    status: EventStatus = EventStatus.PENDING
    deadline: Optional[float] = None
    causality_chain: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    topic: Optional[str] = None

    def __post_init__(self):
        if self.topic and (self.event_type == "generic" or not self.event_type):
            self.event_type = self.topic

    def is_expired(self) -> bool:
        if self.deadline is not None:
            return time.time() > self.deadline
        return False


@dataclass
class PerceptionEvent(UniversalEvent):
    """Normalized sensory event from Perception Fabric."""
    modality: EventModality = EventModality.TEXT
    confidence: float = 1.0
    device_id: Optional[str] = None
    raw_source: str = ""

    def __post_init__(self):
        self.event_type = f"perception.{self.modality.value}"


@dataclass
class CommandEvent(UniversalEvent):
    """Actionable command or query entering the Cognitive Core."""
    query: str = ""
    author: str = "User"
    cancellation_token: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self):
        self.event_type = "command.user_query"


@dataclass
class InterruptEvent(UniversalEvent):
    """Explicit interrupt signaling cancellation or priority override."""
    target_request_id: str = ""
    reason: str = "User interrupt"

    def __post_init__(self):
        self.event_type = "control.interrupt"
        self.priority = EventPriority.CRITICAL


@dataclass
class ActionEvent(UniversalEvent):
    """Action dispatched to Action Fabric."""
    domain: str = "os"
    action: str = "execute"
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_two_gate: bool = False

    def __post_init__(self):
        self.event_type = f"action.{self.domain}.{self.action}"


@dataclass
class ObservationEvent(UniversalEvent):
    """Observation emitted following world change."""
    target: str = ""
    observed_state: Dict[str, Any] = field(default_factory=dict)
    evidence: str = ""

    def __post_init__(self):
        self.event_type = "observation.world_change"


@dataclass
class VerificationResult(UniversalEvent):
    """Empirical verification comparing expected vs actual state."""
    verification_status: str = "SUCCESS"  # SUCCESS, PARTIAL, FAILED, PHYSICALLY_UNVERIFIED
    expected_state: Dict[str, Any] = field(default_factory=dict)
    actual_state: Dict[str, Any] = field(default_factory=dict)
    evidence: str = ""

    def __post_init__(self):
        self.event_type = "verification.outcome"


@dataclass
class ExperienceEvent(UniversalEvent):
    """Experience record for learning and policy adaptation."""
    action_domain: str = ""
    action_name: str = ""
    reward: float = 0.0
    evaluation_notes: str = ""

    def __post_init__(self):
        self.event_type = "learning.experience"
