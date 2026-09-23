"""Calendar Agent for JARVIS Layer 3 (Group 1).

Real Google Calendar API integration.
Reads upcoming events and adds new calendar events.
Adding an event requires Group 4 permission gate check.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from config.settings import settings
from skills.google_calendar import GoogleCalendarSkill
from agents.permission_checks import permission_gate
from agents.identity_agent import identity_agent

logger = logging.getLogger("JARVIS.CalendarAgent")


class CalendarAgent:
    """Agent for scheduling and managing Google Calendar events."""

    def __init__(self):
        self.skill = GoogleCalendarSkill()

    def get_upcoming_events(self, max_results: int = 5) -> Dict[str, Any]:
        """Reads upcoming events from the user's primary calendar."""
        logger.info("[CalendarAgent] Reading upcoming %d calendar events", max_results)
        return self.skill.list_upcoming_events(max_results=max_results)

    def add_event(
        self,
        summary: str,
        start_time_iso: str,
        duration_minutes: int = 60,
        description: str = "",
        user_confirmed: bool = False
    ) -> Dict[str, Any]:
        """Adds an event to Google Calendar, gated by permission check."""
        event_details = {
            "summary": summary,
            "start": start_time_iso,
            "duration_minutes": duration_minutes,
            "description": description
        }

        perm = permission_gate.check_permission(
            domain="calendar",
            action="add_event",
            details=event_details,
            confirmed=user_confirmed
        )

        if not perm.allowed:
            return {
                "success": False,
                "status": "pending_approval",
                "message": perm.message,
                "error": "Calendar action blocked pending user authorization."
            }

        service = self.skill._get_service()
        if not service:
            return {
                "success": False,
                "error": "Google Calendar is not authorized. Configure credentials or run auth."
            }

        try:
            # Parse start time and compute end time
            try:
                start_dt = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
            except Exception:
                start_dt = datetime.utcnow()
            end_dt = start_dt + timedelta(minutes=duration_minutes)

            event_body = {
                "summary": summary,
                "description": description,
                "start": {"dateTime": start_dt.isoformat()},
                "end": {"dateTime": end_dt.isoformat()},
            }

            created_event = service.events().insert(calendarId="primary", body=event_body).execute()
            logger.info("[CalendarAgent] Successfully scheduled event: %s", summary)
            return {
                "success": True,
                "event_id": created_event.get("id"),
                "summary": summary,
                "html_link": created_event.get("htmlLink")
            }
        except Exception as e:
            logger.error("[CalendarAgent] Failed to insert event: %s", str(e))
            return {"success": False, "error": str(e)}

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator Agent Router."""
        action = inputs.get("action", "read")
        if action == "add" or "summary" in inputs:
            return self.add_event(
                summary=inputs.get("summary", "New Event"),
                start_time_iso=inputs.get("start", datetime.utcnow().isoformat()),
                duration_minutes=inputs.get("duration", 60),
                description=inputs.get("description", ""),
                user_confirmed=inputs.get("user_confirmed", False)
            )
        else:
            return self.get_upcoming_events(max_results=inputs.get("max_results", 5))


calendar_agent = CalendarAgent()
