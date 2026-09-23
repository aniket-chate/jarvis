"""JARVIS Autonomous Runtime & Agency Schemas."""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Callable, Dict, Optional


class TriggerType(Enum):
    SCHEDULED_TIME = "scheduled_time"
    CONDITION_POLL = "condition_poll"
    EVENT_TRIGGER = "event_trigger"
    THRESHOLD_WATCH = "threshold_watch"


@dataclass
class AutonomousRule:
    """A proactive rule or background monitor running under the Autonomous Runtime."""
    rule_id: str
    description: str
    trigger_type: TriggerType
    goal_to_trigger: str
    target_capability: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    condition_fn: Optional[Callable[[], bool]] = None
    scheduled_timestamp: Optional[float] = None
    poll_interval_sec: float = 10.0
    last_evaluated_time: float = 0.0
    is_active: bool = True
    trigger_count: int = 0
    max_triggers: int = 1  # 1 for one-off, >1 for recurring
