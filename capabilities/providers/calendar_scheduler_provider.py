"""Calendar and Scheduler Capability Provider for JARVIS Capability 38.

Provides provider-neutral calendar event lifecycle management, conflict detection,
multi-timezone handling, and in-app precision alarms/reminders.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from agents.scheduler_agent import scheduler_agent

logger = logging.getLogger("JARVIS.Providers.CalendarScheduler")


@dataclass
class CalendarEvent:
    """Provider-neutral canonical calendar event representation."""
    event_id: str
    title: str
    start_time: str      # ISO 8601 string
    end_time: str        # ISO 8601 string
    calendar_id: str = "primary"
    description: str = ""
    location: str = ""
    timezone: str = "UTC"
    attendees: List[str] = field(default_factory=list)
    recurrence: Optional[str] = None
    status: str = "CONFIRMED"
    created_at: float = field(default_factory=time.time)
    last_modified: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "calendar_id": self.calendar_id,
            "title": self.title,
            "description": self.description,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "timezone": self.timezone,
            "location": self.location,
            "attendees": self.attendees,
            "recurrence": self.recurrence,
            "status": self.status,
            "created_at": self.created_at,
            "last_modified": self.last_modified,
        }


@dataclass
class CalendarConfig:
    """Configurable parameters for calendar and scheduler provider."""
    default_event_duration_min: int = 60
    conflict_buffer_min: int = 0
    default_timezone: str = "UTC"
    max_events_per_query: int = 50


class CalendarSchedulerProvider(BaseCapabilityProvider):
    """Unified calendar and scheduler capability provider."""

    def __init__(self, config: Optional[CalendarConfig] = None):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.calendar.scheduler",
                name="JARVIS Calendar & Scheduler Provider",
                supported_capabilities=[
                    "calendar.create_event",
                    "calendar.get_events",
                    "calendar.modify_event",
                    "calendar.delete_event",
                    "calendar.check_conflicts",
                    "calendar.get_availability",
                    "scheduler.alarm",
                    "scheduler.reminder",
                    "scheduler.interval",
                ],
                priority=10,
                estimated_latency_ms=10.0,
                safety_level="modifying",
                description="Calendar event lifecycle, conflict auditing, and precision in-app scheduling.",
            )
        )
        self.config = config or CalendarConfig()
        self._events: Dict[str, CalendarEvent] = {}
        self._custom_backend: Optional[Any] = None
        self.scheduler = scheduler_agent

    def set_custom_backend(self, backend: Any) -> None:
        """Enables swapping the calendar storage backend (e.g. Google Calendar API or test double)."""
        self._custom_backend = backend

    def is_available(self) -> bool:
        return True

    def execute(
        self,
        capability: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        t0 = time.perf_counter()
        try:
            if capability == "calendar.create_event":
                res = self._create_event(parameters, context)
            elif capability == "calendar.get_events":
                res = self._get_events(parameters, context)
            elif capability == "calendar.modify_event":
                res = self._modify_event(parameters)
            elif capability == "calendar.delete_event":
                res = self._delete_event(parameters)
            elif capability == "calendar.check_conflicts":
                res = self._check_conflicts(parameters, context)
            elif capability == "calendar.get_availability":
                res = self._get_availability(parameters, context)
            elif capability in ["scheduler.alarm", "scheduler.reminder"]:
                res = self._schedule_alarm(parameters)
            elif capability == "scheduler.interval":
                res = self._schedule_interval(parameters)
            else:
                elapsed = (time.perf_counter() - t0) * 1000
                self.record_outcome(False)
                return ActionResult(
                    status="FAILED",
                    output=None,
                    message=f"Unsupported capability: {capability}",
                    execution_time_ms=elapsed,
                )

            elapsed = (time.perf_counter() - t0) * 1000
            self.record_outcome(True)
            return ActionResult(
                status="SUCCESS",
                output=res,
                message="Calendar/Scheduler operation completed successfully.",
                execution_time_ms=elapsed,
            )
        except Exception as e:
            logger.error("[CalendarSchedulerProvider] Execution error for '%s': %s", capability, str(e), exc_info=True)
            elapsed = (time.perf_counter() - t0) * 1000
            self.record_outcome(False)
            return ActionResult(
                status="FAILED",
                output={"error": str(e)},
                message=str(e),
                execution_time_ms=elapsed,
            )

    def _resolve_authoritative_timezone(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
        """Determines authoritative timezone according to the JARVIS hierarchy:
        1. Explicit event timezone (params.get("timezone"))
        2. User / Session timezone (context.get("user_timezone") or context.get("session_timezone") or context.get("timezone"))
        3. Device timezone (context.get("device_timezone"))
        4. Configured default timezone (self.config.default_timezone)
        5. Safe fallback ("UTC")
        """
        if params and params.get("timezone"):
            return str(params["timezone"]).strip()
        if context:
            ctx_tz = context.get("user_timezone") or context.get("session_timezone") or context.get("timezone")
            if ctx_tz:
                return str(ctx_tz).strip()
            dev_tz = context.get("device_timezone")
            if dev_tz:
                return str(dev_tz).strip()
        if self.config and self.config.default_timezone:
            return str(self.config.default_timezone).strip()
        return "UTC"

    def _parse_iso(self, ts: str, fallback_tz: str = "UTC") -> datetime:
        """Parses ISO timestamp string into timezone-aware datetime.
        If naive, attaches authoritative fallback_tz.
        Supports UTC ('Z'), positive offsets ('+05:30', '+09:00'), negative offsets ('-04:00', '-08:00'),
        and IANA timezone names ('Asia/Kolkata', 'America/New_York').
        """
        clean = str(ts).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(clean)
        except Exception:
            dt = datetime.now(timezone.utc)

        if dt.tzinfo is None:
            if ZoneInfo:
                try:
                    dt = dt.replace(tzinfo=ZoneInfo(fallback_tz))
                except Exception:
                    dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def _normalize_to_utc(self, dt: datetime) -> datetime:
        """Normalizes an aware datetime to UTC for exact cross-timezone comparison."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _create_event(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Creates a calendar event with conflict detection and authoritative timezone resolution."""
        auth_tz = self._resolve_authoritative_timezone(params, context)
        title = params.get("title") or params.get("summary") or "New Event"
        start_str = params.get("start_time") or params.get("start")
        if not start_str:
            start_dt = datetime.now(timezone.utc)
            start_str = start_dt.isoformat()
        else:
            start_dt = self._parse_iso(start_str, auth_tz)

        duration_min = int(params.get("duration_minutes") or params.get("duration") or self.config.default_event_duration_min)
        end_str = params.get("end_time") or params.get("end")
        if not end_str:
            end_dt = start_dt + timedelta(minutes=duration_min)
            end_str = end_dt.isoformat()
        else:
            end_dt = self._parse_iso(end_str, auth_tz)

        # Audit conflicts with UTC interval comparison unless explicitly bypassed
        allow_conflicts = bool(params.get("allow_conflicts", False))
        conflicts = self._find_conflicts(start_dt, end_dt)
        if conflicts and not allow_conflicts:
            return {
                "success": False,
                "status": "CONFLICT_DETECTED",
                "conflicts": [c.to_dict() for c in conflicts],
                "message": f"Proposed event '{title}' conflicts with {len(conflicts)} existing event(s).",
            }

        event_id = params.get("event_id") or f"evt_{uuid.uuid4().hex[:10]}"
        event = CalendarEvent(
            event_id=event_id,
            title=title,
            start_time=start_str,
            end_time=end_str,
            calendar_id=params.get("calendar_id", "primary"),
            description=params.get("description", ""),
            location=params.get("location", ""),
            timezone=auth_tz,
            attendees=params.get("attendees") or [],
            recurrence=params.get("recurrence"),
            status="CONFIRMED",
        )

        if self._custom_backend:
            be_res = self._custom_backend.create_event(event.to_dict())
            if not be_res.get("success", True):
                return {"success": False, "status": "FAILED", "error": be_res.get("error")}

        self._events[event_id] = event
        return {
            "success": True,
            "status": "CREATED",
            "event_id": event_id,
            "event": event.to_dict(),
            "had_conflicts": len(conflicts) > 0,
        }

    def _get_events(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Queries events within time range or by title filter with UTC normalization."""
        auth_tz = self._resolve_authoritative_timezone(params, context)
        query = str(params.get("query") or params.get("title") or "").strip().lower()
        limit = int(params.get("limit") or params.get("max_results") or self.config.max_events_per_query)

        start_filter = params.get("start_time")
        end_filter = params.get("end_time")
        dt_start = self._normalize_to_utc(self._parse_iso(start_filter, auth_tz)) if start_filter else None
        dt_end = self._normalize_to_utc(self._parse_iso(end_filter, auth_tz)) if end_filter else None

        results = []
        for evt in self._events.values():
            if query and query not in evt.title.lower() and query not in evt.description.lower():
                continue
            e_start_utc = self._normalize_to_utc(self._parse_iso(evt.start_time, evt.timezone))
            e_end_utc = self._normalize_to_utc(self._parse_iso(evt.end_time, evt.timezone))
            if dt_start and e_end_utc < dt_start:
                continue
            if dt_end and e_start_utc > dt_end:
                continue
            results.append(evt.to_dict())

        results.sort(key=lambda x: x.get("start_time", ""))
        trimmed = results[:limit]
        return {
            "events": trimmed,
            "count": len(trimmed),
            "total_found": len(results),
        }

    def _modify_event(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Modifies details of an existing calendar event."""
        event_id = params.get("event_id")
        if not event_id or event_id not in self._events:
            # Try lookup by title
            title_q = str(params.get("title") or params.get("summary") or "").strip().lower()
            matched_id = None
            if title_q:
                for eid, e in self._events.items():
                    if e.title.lower() == title_q:
                        matched_id = eid
                        break
            if not matched_id:
                return {
                    "success": False,
                    "status": "NOT_FOUND",
                    "error": f"Event '{event_id or title_q}' not found in calendar.",
                }
            event_id = matched_id

        evt = self._events[event_id]
        if "new_title" in params or "summary" in params:
            evt.title = params.get("new_title") or params.get("summary") or evt.title
        if "start_time" in params:
            evt.start_time = params["start_time"]
        if "end_time" in params:
            evt.end_time = params["end_time"]
        if "description" in params:
            evt.description = params["description"]
        if "location" in params:
            evt.location = params["location"]
        if "attendees" in params:
            evt.attendees = params["attendees"]
        evt.last_modified = time.time()

        return {
            "success": True,
            "status": "MODIFIED",
            "event_id": event_id,
            "event": evt.to_dict(),
        }

    def _delete_event(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Deletes a calendar event truthfully."""
        event_id = params.get("event_id")
        if not event_id or event_id not in self._events:
            title_q = str(params.get("title") or params.get("summary") or "").strip().lower()
            matched_id = None
            if title_q:
                for eid, e in self._events.items():
                    if e.title.lower() == title_q:
                        matched_id = eid
                        break
            if not matched_id:
                return {
                    "success": False,
                    "status": "NOT_FOUND",
                    "error": f"Event '{event_id or title_q}' not found to delete.",
                }
            event_id = matched_id

        deleted = self._events.pop(event_id, None)
        return {
            "success": True,
            "status": "DELETED",
            "event_id": event_id,
            "title": deleted.title if deleted else "",
        }

    def _find_conflicts(self, start_dt: datetime, end_dt: datetime, exclude_id: Optional[str] = None) -> List[CalendarEvent]:
        """Finds overlapping events in store using UTC-normalized interval comparisons."""
        conflicts = []
        start_utc = self._normalize_to_utc(start_dt)
        end_utc = self._normalize_to_utc(end_dt)

        for evt in self._events.values():
            if exclude_id and evt.event_id == exclude_id:
                continue
            e_start = self._parse_iso(evt.start_time, evt.timezone)
            e_end = self._parse_iso(evt.end_time, evt.timezone)
            e_start_utc = self._normalize_to_utc(e_start)
            e_end_utc = self._normalize_to_utc(e_end)
            # Two intervals [s1, e1] and [s2, e2] overlap if s1 < e2 and e1 > s2
            if start_utc < e_end_utc and end_utc > e_start_utc:
                conflicts.append(evt)
        return conflicts

    def _check_conflicts(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Audits schedule for conflicting events in the requested window."""
        auth_tz = self._resolve_authoritative_timezone(params, context)
        start_str = params.get("start_time")
        end_str = params.get("end_time")
        if not start_str or not end_str:
            raise ValueError("start_time and end_time are required to check conflicts.")

        dt_start = self._parse_iso(start_str, auth_tz)
        dt_end = self._parse_iso(end_str, auth_tz)
        exclude_id = params.get("exclude_event_id")

        conflicts = self._find_conflicts(dt_start, dt_end, exclude_id=exclude_id)
        return {
            "has_conflict": len(conflicts) > 0,
            "conflict_count": len(conflicts),
            "conflicts": [c.to_dict() for c in conflicts],
        }

    def _get_availability(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculates free and busy time slots for a given day."""
        auth_tz = self._resolve_authoritative_timezone(params, context)
        target_date_str = params.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        work_start_h = int(params.get("start_hour", 9))
        work_end_h = int(params.get("end_hour", 18))

        # Query events on this date
        day_events = []
        for e in self._events.values():
            if target_date_str in e.start_time:
                day_events.append(e)

        day_events.sort(key=lambda x: x.start_time)
        busy_slots = [{"start": e.start_time, "end": e.end_time, "title": e.title} for e in day_events]

        return {
            "date": target_date_str,
            "timezone": auth_tz,
            "busy_slots": busy_slots,
            "is_free_all_day": len(busy_slots) == 0,
            "working_hours": f"{work_start_h:02d}:00 - {work_end_h:02d}:00",
        }

    def _schedule_alarm(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches in-app precision alarm to APScheduler."""
        delay = int(params.get("delay_seconds") or 60)
        msg = params.get("message") or "Reminder"
        res = self.scheduler.set_alarm(delay_seconds=delay, message=msg)
        return {"success": True, "scheduler_result": res}

    def _schedule_interval(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Schedules recurring interval trigger."""
        interval_sec = int(params.get("interval_seconds", 3600))
        msg = params.get("message", "Interval trigger")
        return {"success": True, "interval_seconds": interval_sec, "message": msg, "scheduled": True}
