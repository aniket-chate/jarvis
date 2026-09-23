"""Google Calendar Skill for JARVIS.

Uses shared Google Cloud OAuth App covering Calendar and Gmail.
Graceful degradation: If unconfigured or unauthorized, disables itself cleanly.
"""

import logging
from typing import Dict, List, Any
from config.settings import settings
from skills.google_auth import get_shared_credentials

logger = logging.getLogger("JARVIS.Skills.Calendar")


class GoogleCalendarSkill:
    def __init__(self):
        self.is_configured = settings.google_oauth_configured
        self._service = None

        if not self.is_configured:
            logger.warning("[Google Calendar] Disabled: No Google OAuth credentials found in .env or credentials/")

    def _get_service(self):
        """Builds and returns Google Calendar v3 service client."""
        if self._service is not None:
            return self._service

        creds = get_shared_credentials()
        if not creds:
            return None

        try:
            from googleapiclient.discovery import build
            self._service = build("calendar", "v3", credentials=creds)
            return self._service
        except Exception as e:
            logger.error("[Google Calendar Error] Service construction failed: %s", str(e))
            return None

    def list_upcoming_events(self, max_results: int = 5) -> Dict[str, Any]:
        """Fetches upcoming calendar events."""
        if not self.is_configured:
            return {
                "success": False,
                "error": "Google Calendar skill is unconfigured. Add credentials to enable.",
                "events": [],
            }

        service = self._get_service()
        if not service:
            return {
                "success": False,
                "error": "Google Calendar is not authorized. Run 'python main.py --auth' to connect your account.",
                "events": [],
            }

        try:
            import datetime
            now = datetime.datetime.utcnow().isoformat() + "Z"
            events_result = service.events().list(
                calendarId="primary",
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            items = events_result.get("items", [])
            events = [
                {
                    "summary": item.get("summary", "(No title)"),
                    "start": item.get("start", {}).get("dateTime", item.get("start", {}).get("date")),
                    "end": item.get("end", {}).get("dateTime", item.get("end", {}).get("date")),
                }
                for item in items
            ]
            return {"success": True, "events": events}
        except Exception as e:
            logger.error("[Google Calendar Error] Failed to list events: %s", str(e))
            return {"success": False, "error": str(e), "events": []}


calendar_skill = GoogleCalendarSkill()
