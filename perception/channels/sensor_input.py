"""Sensor Input Channel for JARVIS.

Gathers telemetry regarding the host environment:
- Active foreground window/application
- System idle duration
- Timestamps
Emits 'sensor_telemetry' PerceptionEvents onto the Unified Event Bus.
"""

import time
import logging
import ctypes
from typing import Dict, Any, Optional
import win32gui
import win32process
import psutil

from perception.events import PerceptionEvent, event_bus
from config.settings import settings

logger = logging.getLogger("JARVIS.Channels.Sensor")


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


class SensorInputChannel:
    """Channel for polling environmental and UI state."""

    def get_active_application(self) -> Dict[str, str]:
        """Detects the currently active foreground window and process name on Windows."""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return {"window_title": "None", "process_name": "unknown"}

            window_title = win32gui.GetWindowText(hwnd) or "Untitled"
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid)
                process_name = proc.name()
            except Exception:
                process_name = "unknown"

            return {
                "window_title": window_title,
                "process_name": process_name,
                "pid": str(pid),
            }
        except Exception as e:
            logger.debug("[SensorInputChannel] Error getting active window: %s", str(e))
            return {"window_title": "Desktop", "process_name": "explorer.exe"}

    def get_system_idle_seconds(self) -> float:
        """Returns the number of seconds since the last user input (mouse/keyboard)."""
        try:
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
                millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
                return max(0.0, round(millis / 1000.0, 2))
        except Exception as e:
            logger.debug("[SensorInputChannel] Error checking idle time: %s", str(e))
        return 0.0

    def capture_snapshot(self) -> PerceptionEvent:
        """Collects sensor telemetry and publishes a sensor_telemetry event."""
        app_info = self.get_active_application()
        idle_secs = self.get_system_idle_seconds()
        is_idle = idle_secs > 60.0  # Consider idle after 1 minute of inactivity

        payload: Dict[str, Any] = {
            "active_window": app_info.get("window_title"),
            "process_name": app_info.get("process_name"),
            "idle_seconds": idle_secs,
            "is_idle": is_idle,
            "epoch_timestamp": time.time(),
        }

        event = PerceptionEvent(
            type="sensor_telemetry",
            payload=payload,
            source="sensor_input",
            active_persona=settings.active_persona_name,
        )

        logger.debug("[SensorInputChannel] Telemetry captured: App='%s', Idle=%.1fs", app_info.get("process_name"), idle_secs)
        event_bus.publish(event)
        return event


sensor_input_channel = SensorInputChannel()
