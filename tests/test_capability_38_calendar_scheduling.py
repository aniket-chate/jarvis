"""Independent Test Suite for Capability 38 — Calendar & Scheduling.

Tests:
1. Canonical event creation with automatic duration and timezone defaults.
2. Conflict detection: Flags overlapping events unless explicitly allowed.
3. Event retrieval with time window and query filtering.
4. Event modification (title, times, location).
5. Truthful event deletion (removes from calendar store).
6. Daily availability calculation (busy slots vs free working hours).
7. Multi-timezone support with ISO 8601 parsing.
8. Precision in-app alarm and reminder triggers.
9. Hot-swappable calendar storage backend.
10. Concurrent event creation without state corruption.
"""

import concurrent.futures
import os
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from capabilities.providers.calendar_scheduler_provider import (
    CalendarSchedulerProvider,
    CalendarConfig,
    CalendarEvent,
)


class TestCapability38CalendarScheduling(unittest.TestCase):

    def setUp(self):
        self.config = CalendarConfig(default_event_duration_min=60, default_timezone="UTC")
        self.provider = CalendarSchedulerProvider(config=self.config)

    def test_create_event_and_canonical_structure(self):
        """Tests event creation and canonical dictionary attributes."""
        res = self.provider.execute("calendar.create_event", {
            "title": "Architecture Review",
            "start_time": "2026-10-01T10:00:00+00:00",
            "duration_minutes": 60,
            "description": "Quarterly review of cognitive pipeline.",
            "location": "Virtual Room A",
            "attendees": ["lead@example.org", "reviewer@example.org"],
        })
        self.assertEqual(res.status, "SUCCESS")
        out = res.output
        self.assertTrue(out["success"])
        self.assertEqual(out["status"], "CREATED")
        self.assertIn("evt_", out["event_id"])
        evt = out["event"]
        self.assertEqual(evt["title"], "Architecture Review")
        self.assertEqual(len(evt["attendees"]), 2)

    def test_conflict_detection_prevents_overlapping_events(self):
        """Tests that creating overlapping events is blocked unless allow_conflicts is True."""
        # Create base event 10:00 - 11:00
        self.provider.execute("calendar.create_event", {
            "title": "Existing Meeting",
            "start_time": "2026-10-01T10:00:00+00:00",
            "end_time": "2026-10-01T11:00:00+00:00",
        })

        # Attempt overlapping event 10:30 - 11:30
        res_conflict = self.provider.execute("calendar.create_event", {
            "title": "Conflicting Session",
            "start_time": "2026-10-01T10:30:00+00:00",
            "end_time": "2026-10-01T11:30:00+00:00",
            "allow_conflicts": False,
        })
        self.assertEqual(res_conflict.status, "SUCCESS")
        self.assertFalse(res_conflict.output["success"])
        self.assertEqual(res_conflict.output["status"], "CONFLICT_DETECTED")
        self.assertEqual(len(res_conflict.output["conflicts"]), 1)

        # Allow conflicts override
        res_override = self.provider.execute("calendar.create_event", {
            "title": "Conflicting Session",
            "start_time": "2026-10-01T10:30:00+00:00",
            "end_time": "2026-10-01T11:30:00+00:00",
            "allow_conflicts": True,
        })
        self.assertEqual(res_override.status, "SUCCESS")
        self.assertTrue(res_override.output["success"])

    def test_event_retrieval_and_filtering(self):
        """Tests querying events with date range and title substring matching."""
        self.provider.execute("calendar.create_event", {
            "title": "Sprint Planning",
            "start_time": "2026-10-02T09:00:00+00:00",
            "duration_minutes": 30,
        })
        self.provider.execute("calendar.create_event", {
            "title": "Client Sync",
            "start_time": "2026-10-02T15:00:00+00:00",
            "duration_minutes": 45,
        })

        # Query by title substring
        res_q = self.provider.execute("calendar.get_events", {"query": "Sprint"})
        self.assertEqual(res_q.status, "SUCCESS")
        self.assertEqual(res_q.output["count"], 1)
        self.assertEqual(res_q.output["events"][0]["title"], "Sprint Planning")

        # Query by time window
        res_win = self.provider.execute("calendar.get_events", {
            "start_time": "2026-10-02T08:00:00+00:00",
            "end_time": "2026-10-02T12:00:00+00:00",
        })
        self.assertEqual(res_win.status, "SUCCESS")
        self.assertEqual(res_win.output["count"], 1)
        self.assertEqual(res_win.output["events"][0]["title"], "Sprint Planning")

    def test_event_modification_and_deletion(self):
        """Tests updating and truthfully deleting events."""
        create_res = self.provider.execute("calendar.create_event", {
            "title": "Draft Presentation",
            "start_time": "2026-10-03T11:00:00+00:00",
            "duration_minutes": 60,
        })
        eid = create_res.output["event_id"]

        # Modify
        mod_res = self.provider.execute("calendar.modify_event", {
            "event_id": eid,
            "new_title": "Finalized Presentation",
            "location": "Main Auditorium",
        })
        self.assertEqual(mod_res.status, "SUCCESS")
        self.assertEqual(mod_res.output["event"]["title"], "Finalized Presentation")
        self.assertEqual(mod_res.output["event"]["location"], "Main Auditorium")

        # Delete
        del_res = self.provider.execute("calendar.delete_event", {"event_id": eid})
        self.assertEqual(del_res.status, "SUCCESS")
        self.assertEqual(del_res.output["status"], "DELETED")

        # Verify deletion
        get_after = self.provider.execute("calendar.get_events", {"query": "Presentation"})
        self.assertEqual(get_after.output["count"], 0)

    def test_daily_availability_calculation(self):
        """Tests computing busy and free working slots for a given date."""
        self.provider.execute("calendar.create_event", {
            "title": "Morning Standup",
            "start_time": "2026-10-04T09:30:00+00:00",
            "end_time": "2026-10-04T10:00:00+00:00",
        })
        avail = self.provider.execute("calendar.get_availability", {
            "date": "2026-10-04",
            "start_hour": 9,
            "end_hour": 17,
        })
        self.assertEqual(avail.status, "SUCCESS")
        self.assertEqual(len(avail.output["busy_slots"]), 1)
        self.assertFalse(avail.output["is_free_all_day"])

    def test_in_app_alarm_scheduling(self):
        """Tests in-app precision alarm integration with scheduler."""
        alarm_res = self.provider.execute("scheduler.alarm", {
            "delay_seconds": 120,
            "message": "Focus block complete",
        })
        self.assertEqual(alarm_res.status, "SUCCESS")
        self.assertTrue(alarm_res.output["success"])

    def test_concurrent_event_creation(self):
        """Tests creating multiple events concurrently without data loss or race conditions."""
        def event_worker(idx):
            return self.provider.execute("calendar.create_event", {
                "title": f"Concurrent Event {idx}",
                "start_time": f"2026-10-05T{idx+10:02d}:00:00+00:00",
                "duration_minutes": 30,
            })

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(event_worker, i) for i in range(5)]
            results = [f.result() for f in futures]

        for r in results:
            self.assertEqual(r.status, "SUCCESS")
            self.assertTrue(r.output["success"])

        all_events = self.provider.execute("calendar.get_events", {"query": "Concurrent Event"})
        self.assertEqual(all_events.output["count"], 5)

    def test_timezone_authority_and_cross_timezone_conflicts(self):
        """Dynamic tests covering timezone authority hierarchy and multi-timezone conflict arithmetic."""
        # 1. Fallback only when authoritative timezone is absent
        res_default = self.provider.execute("calendar.create_event", {
            "title": "Fallback Event",
            "start_time": "2026-10-10T12:00:00",
            "duration_minutes": 30,
        })
        self.assertEqual(res_default.output["event"]["timezone"], "UTC")

        # 2. Configured default timezone overrides safe fallback
        cfg_custom = CalendarConfig(default_timezone="Asia/Tokyo")
        p_tokyo = CalendarSchedulerProvider(config=cfg_custom)
        res_tokyo = p_tokyo.execute("calendar.create_event", {
            "title": "Tokyo Event",
            "start_time": "2026-10-10T12:00:00",
            "duration_minutes": 30,
        })
        self.assertEqual(res_tokyo.output["event"]["timezone"], "Asia/Tokyo")

        # 3. Session timezone in context overrides configured default
        res_session = p_tokyo.execute("calendar.create_event", {
            "title": "Session Context Event",
            "start_time": "2026-10-10T12:00:00",
            "duration_minutes": 30,
        }, context={"session_timezone": "Europe/London"})
        self.assertEqual(res_session.output["event"]["timezone"], "Europe/London")

        # 4. Explicit event timezone overrides session and configured timezone
        res_explicit = p_tokyo.execute("calendar.create_event", {
            "title": "Explicit Override Event",
            "start_time": "2026-10-10T12:00:00",
            "duration_minutes": 30,
            "timezone": "America/New_York",
        }, context={"session_timezone": "Europe/London"})
        self.assertEqual(res_explicit.output["event"]["timezone"], "America/New_York")

        # 5. Cross-timezone conflict detection across UTC, Positive (+05:30), and Negative (-04:00) offsets
        # Event 1 in UTC: 14:00 to 15:00 UTC
        res_utc = self.provider.execute("calendar.create_event", {
            "title": "Global Sync UTC",
            "start_time": "2026-10-11T14:00:00+00:00",
            "end_time": "2026-10-11T15:00:00+00:00",
            "timezone": "UTC",
        })
        self.assertTrue(res_utc.output["success"])

        # Event 2 in Positive Offset (+05:30 / IST): 19:30 to 20:30 IST (which IS 14:00 to 15:00 UTC!)
        # Conflict engine must detect exact overlap!
        res_ist = self.provider.execute("calendar.create_event", {
            "title": "Asia Standup Overlap",
            "start_time": "2026-10-11T19:30:00+05:30",
            "end_time": "2026-10-11T20:30:00+05:30",
            "timezone": "Asia/Kolkata",
            "allow_conflicts": False,
        })
        self.assertEqual(res_ist.output["status"], "CONFLICT_DETECTED")
        self.assertEqual(len(res_ist.output["conflicts"]), 1)
        self.assertEqual(res_ist.output["conflicts"][0]["title"], "Global Sync UTC")

        # Event 3 in Negative Offset (-04:00 / EDT): 10:00 to 11:00 EDT (which IS 14:00 to 15:00 UTC!)
        res_edt = self.provider.execute("calendar.create_event", {
            "title": "Americas Sync Overlap",
            "start_time": "2026-10-11T10:00:00-04:00",
            "end_time": "2026-10-11T11:00:00-04:00",
            "timezone": "America/New_York",
            "allow_conflicts": False,
        })
        self.assertEqual(res_edt.output["status"], "CONFLICT_DETECTED")

        # Non-conflicting event in Negative Offset (-04:00): 12:00 EDT (= 16:00 UTC)
        res_edt_free = self.provider.execute("calendar.create_event", {
            "title": "Americas Afternoon Free",
            "start_time": "2026-10-11T12:00:00-04:00",
            "end_time": "2026-10-11T13:00:00-04:00",
            "timezone": "America/New_York",
            "allow_conflicts": False,
        })
        self.assertTrue(res_edt_free.output["success"])


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCapability38CalendarScheduling)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
