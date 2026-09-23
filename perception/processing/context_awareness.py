"""Context Awareness Module for JARVIS Layer 1.

Produces a live unified environmental and system state snapshot:
active window, idle state, CPU/RAM utilization, disk headroom, and time.
"""

import time
import shutil
import logging
from datetime import datetime, timezone
from typing import Dict, Any
import psutil

from perception.channels.sensor_input import sensor_input_channel
from perception.events import PerceptionEvent, event_bus
from config.settings import settings

logger = logging.getLogger("JARVIS.Processing.Context")


class ContextAwarenessEngine:
    """Aggregates multi-source environment and host state into live snapshots."""

    def get_live_snapshot(self) -> PerceptionEvent:
        """Constructs an environmental snapshot and emits a 'context_snapshot' event."""
        # 1. UI and input state
        app_info = sensor_input_channel.get_active_application()
        idle_secs = sensor_input_channel.get_system_idle_seconds()

        # 2. Hardware telemetry
        cpu_pct = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        mem_pct = mem.percent
        mem_avail_gb = round(mem.available / (1024 ** 3), 2)

        # 3. Disk storage
        total, used, free = shutil.disk_usage("C:\\")
        disk_free_gb = round(free / (1024 ** 3), 2)
        disk_total_gb = round(total / (1024 ** 3), 2)
        disk_free_pct = round((free / total) * 100, 1)

        # 4. Temporal state (Explicitly localized to Asia/Kolkata IST)
        try:
            from zoneinfo import ZoneInfo
            tz_ist = ZoneInfo("Asia/Kolkata")
            now_ist = datetime.now(tz_ist)
        except Exception:
            from datetime import timedelta
            tz_ist = timezone(timedelta(hours=5, minutes=30))
            now_ist = datetime.now(tz_ist)

        payload: Dict[str, Any] = {
            "ui_state": {
                "active_window": app_info.get("window_title", "Desktop"),
                "process_name": app_info.get("process_name", "unknown"),
                "pid": app_info.get("pid"),
                "idle_seconds": idle_secs,
                "is_user_idle": idle_secs > 60.0,
            },
            "system_resources": {
                "cpu_percent": cpu_pct,
                "cpu_cores": psutil.cpu_count(logical=True),
                "ram_used_percent": mem_pct,
                "ram_available_gb": mem_avail_gb,
                "disk_free_gb": disk_free_gb,
                "disk_total_gb": disk_total_gb,
                "disk_free_percent": disk_free_pct,
            },
            "temporal": {
                "timezone": "Asia/Kolkata (IST)",
                "timezone_offset": "+05:30",
                "iso_utc": datetime.now(timezone.utc).isoformat(),
                "local_time": now_ist.strftime("%I:%M:%S %p IST"),
                "local_date": now_ist.strftime("%d-%m-%Y"),
                "date_format": "DD-MM-YYYY",
            },
            "locale": {
                "region": "India",
                "currency": "INR",
                "currency_symbol": "₹",
                "country_code": "+91",
            },
            "active_persona": settings.active_persona_name,
        }

        event = PerceptionEvent(
            type="context_snapshot",
            payload=payload,
            source="context_awareness",
            active_persona=settings.active_persona_name,
        )

        logger.info(
            "[ContextAwareness] Live Snapshot: Window='%s', CPU=%.1f%%, RAM=%.1f%%, Idle=%.1fs",
            payload["ui_state"]["active_window"][:35],
            cpu_pct,
            mem_pct,
            idle_secs,
        )
        event_bus.publish(event)
        return event


context_engine = ContextAwarenessEngine()
