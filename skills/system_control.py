"""System Control and Diagnostics Skill for Windows PC."""

import datetime
import shutil
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("JARVIS.Skills.System")


class SystemControlSkill:
    def get_time(self) -> Dict[str, str]:
        """Returns current system date and time."""
        now = datetime.datetime.now()
        return {
            "date": now.strftime("%A, %B %d, %Y"),
            "time": now.strftime("%I:%M %p"),
            "iso": now.isoformat(),
        }

    def get_storage_status(self, drive_letter: Optional[str] = None) -> Dict[str, Any]:
        """Returns disk space for the requested drive or the current home volume."""
        try:
            if drive_letter:
                target = drive_letter
                if os.name == "nt" and len(drive_letter) == 2 and drive_letter[1] == ":":
                    target = drive_letter + "\\"
            elif os.name == "nt":
                target = os.environ.get("SystemDrive", "C:") + "\\"
            else:
                target = str(Path.home())
            total, used, free = shutil.disk_usage(target)
            gb = 1024 ** 3
            return {
                "drive": drive_letter or target,
                "total_gb": round(total / gb, 2),
                "used_gb": round(used / gb, 2),
                "free_gb": round(free / gb, 2),
                "free_percent": round((free / total) * 100, 1),
            }
        except Exception as e:
            logger.error("[System Storage Error] %s", str(e))
            return {"error": str(e)}

    def get_battery_status(self) -> Dict[str, Any]:
        """Inspects Windows battery status via psutil or WMI if available."""
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                return {
                    "percent": battery.percent,
                    "power_plugged": battery.power_plugged,
                    "seconds_left": battery.secsleft,
                }
        except ImportError:
            pass
        return {"notice": "Battery telemetry requires psutil or AC connection"}


system_skill = SystemControlSkill()
