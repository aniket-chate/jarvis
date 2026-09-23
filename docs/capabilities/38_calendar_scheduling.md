# Capability 38: Calendar & Scheduling

## 1. Capability Boundary
Capability 38 (`38_calendar_scheduling`) provides canonical, provider-neutral calendar management, conflict detection, availability computation, and precision time scheduling (alarms, reminders, intervals) across heterogeneous timezones.

It adheres to the frozen architecture:
- Uses a canonical, provider-neutral event model (`CalendarEvent`) independent of Google Calendar, Outlook, or CalDAV representations.
- **Timezone Authority Hierarchy**: Evaluates authoritative timezone data according to the 5-tier resolution hierarchy. Timestamps are mathematically normalized to UTC for interval comparisons and conflict detection, while preserving local display timezones.
- **Conflict Prevention**: Overlapping events are detected via UTC interval arithmetic. Events are never silently overwritten without explicit confirmation.
- **Precision Scheduling**: Alarms, reminders, and intervals integrate with the in-app precision scheduler (`SchedulerAgent` / APScheduler) for exact runtime callback execution.

---

## 2. Capability Contract
- **Capability ID**: `38_calendar_scheduling`
- **Domain**: `calendar`
- **Primary Provider**: `provider.calendar.scheduler` (`CalendarSchedulerProvider`)
- **Fallback Provider**: `provider.calendar.ics_local`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `EVENT_STATE_QUERY`
- **Timeout**: `15.0s`

### Supported Operations (9)
1. `calendar.create_event`: Creates a new calendar event with canonical fields (title, start, end, timezone, attendees, location, reminder minutes).
2. `calendar.get_events`: Queries events across a time window with optional text search and calendar ID filtering.
3. `calendar.modify_event`: Updates existing event fields while preserving existing unmodified attributes.
4. `calendar.delete_event`: Removes an event by ID from the canonical store.
5. `calendar.check_conflicts`: Analyzes a proposed start/end interval against existing events to identify overlapping commitments.
6. `calendar.get_availability`: Computes available free/busy time slots between start and end bounds, respecting configured working hours and minimum slot durations.
7. `scheduler.alarm`: Registers a high-precision one-shot alarm via the background scheduler daemon.
8. `scheduler.reminder`: Registers a timed reminder event with an embedded notification payload.
9. `scheduler.interval`: Configures a recurring cron/interval task via the background scheduler.

---

## 3. Timezone Authority Architecture

### 5-Tier Authority Hierarchy
```text
  1. Explicit Event Timezone      (params["timezone"])
             │ (if unavailable)
             ▼
  2. User / Session Timezone      (context["user_timezone"] / context["session_timezone"])
             │ (if unavailable)
             ▼
  3. Device Timezone              (context["device_timezone"])
             │ (if unavailable)
             ▼
  4. Configured Timezone          (config.default_timezone)
             │ (if unavailable)
             ▼
  5. Safe Fallback                ("UTC")
```

### Mathematical UTC Normalization
To prevent false-positive conflict detection across varying offsets:
1. `_resolve_authoritative_timezone(params, context)` traverses the 5-tier hierarchy.
2. Naive ISO strings are anchored to the authoritative timezone via standard library `zoneinfo.ZoneInfo`.
3. `_normalize_to_utc(dt)` transforms all event boundaries into UTC datetime objects (`dt.astimezone(timezone.utc)`).
4. Conflict comparisons evaluate the canonical interval condition:
   `max(start_a_utc, start_b_utc) < min(end_a_utc, end_b_utc)`
5. Supports arbitrary positive offsets (e.g. `Asia/Kolkata` +05:30), negative offsets (e.g. `America/New_York` -04:00/-05:00), UTC, and Daylight-Saving transitions.

---

## 4. Configuration & Anti-Hardcoding
All runtime rules are driven by `CalendarConfig`:
```python
@dataclass
class CalendarConfig:
    default_timezone: str = "UTC"
    working_hours_start: int = 9   # 09:00
    working_hours_end: int = 18    # 18:00
    default_event_duration_min: int = 30
    conflict_buffer_min: int = 0
    max_query_window_days: int = 365
```
Zero event names, attendee names, company names, or user locations are hardcoded in the calendar logic. All test fixtures generate dynamic ISO strings and arbitrary titles.

---

## 5. Security & Safety Review
- **No Silent Overwrites**: Event collisions generate explicit conflict reports with overlapping event IDs and time intervals.
- **Provider Abstraction**: Canonical operations execute identically whether backed by local memory, ICS file stores, or enterprise calendar providers.
- **Precision Scheduling**: Timed reminders and alarms schedule directly into `SchedulerAgent` and trigger clean non-blocking notifications.

---

## 6. Verification & Tests
- **Independent Suite**: `tests/test_capability_38_calendar_scheduling.py` (8/8 PASS)
  - `test_canonical_event_lifecycle`: Create, read, modify, delete with presence verification.
  - `test_conflict_detection_engine`: Overlapping interval analysis.
  - `test_availability_window_computation`: Free/busy computation within working hours.
  - `test_timezone_normalization`: Cross-timezone normalization.
  - `test_cross_timezone_conflict_detection`: Positive (+05:30) vs Negative (-04:00) vs UTC conflict detection.
  - `test_precision_alarm_scheduling`: In-app scheduler alarm registration.
  - `test_timed_reminder_dispatch`: Timed reminder callback execution.
  - `test_concurrency_calendar_operations`: Multi-threaded calendar operations.
- **Anti-Hardcoding Suite**: `tests/test_no_domain_specific_hardcoding_batch_36_38.py` (13/13 PASS)
  - Tests D (Unknown Event), E (Source Removal), F (Config Change), G (Provider Replacement), and H (Unknown Entity).
- **Live Server Integration**: `tests/test_live_batch_36_37_38.py` (LIVE 6, LIVE 7, LIVE 8 PASS)
