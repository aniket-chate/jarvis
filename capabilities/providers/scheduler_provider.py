"""Scheduler Capability Provider wrapping scheduler_agent."""

import logging
import time
from typing import Any, Dict, Optional
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from agents.scheduler_agent import scheduler_agent

logger = logging.getLogger("JARVIS.Providers.Scheduler")


class APSchedulerProvider(BaseCapabilityProvider):
    """Provides alarms, reminders, and background execution triggers."""

    def __init__(self):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.scheduler.apscheduler",
                name="In-App Background Scheduler",
                supported_capabilities=[
                    "scheduler.alarm",
                    "scheduler.reminder",
                    "scheduler.interval",
                ],
                priority=10,
                estimated_latency_ms=10.0,
            )
        )
        self.agent = scheduler_agent

    def is_available(self) -> bool:
        return True

    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t_start = time.perf_counter()
        try:
            delay = parameters.get("delay_seconds", 60)
            msg = parameters.get("message", "Reminder")
            res = self.agent.schedule_delayed_alarm(delay_seconds=delay, message=msg)
            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(True)
            return ActionResult(status="SUCCESS", output=res, message=str(res), execution_time_ms=elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(False)
            return ActionResult(status="FAILED", output=str(e), message=str(e), execution_time_ms=elapsed)
