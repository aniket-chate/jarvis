"""Lightweight In-App Scheduler & Reminder Agent for JARVIS Layer 3.

Built with APScheduler (BackgroundScheduler) for precision alarms, timers,
and scheduled reminders without background polling or persistent OS cron residue.
Dispatches native Windows notifications and synthesizes TTS announcements at trigger time.
(Optional OS-level task scheduler integration flagged for future expansion).
"""

import os
import time
import uuid
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from config.settings import settings
from perception.events import PerceptionEvent, event_bus
from voice.tts_piper import tts_engine

logger = logging.getLogger("JARVIS.SchedulerAgent")


class SchedulerAgent:
    """In-app alarm and reminder scheduler powered by APScheduler."""

    def __init__(self):
        self.scheduler = BackgroundScheduler(daemon=True)
        self.scheduler.start()
        self.active_alarms: Dict[str, Dict[str, Any]] = {}
        logger.info("[SchedulerAgent] In-app scheduler initialized and running.")

    def _show_windows_notification(self, title: str, message: str) -> None:
        """Dispatches a real native Windows notification balloon and sound alert."""
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

        ps_script = f'''
        [void] [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")
        $notify = New-Object System.Windows.Forms.NotifyIcon
        $notify.Icon = [System.Drawing.SystemIcons]::Information
        $notify.BalloonTipTitle = "{title}"
        $notify.BalloonTipText = "{message}"
        $notify.Visible = $True
        $notify.ShowBalloonTip(10000)
        Start-Sleep -Seconds 3
        $notify.Dispose()
        '''
        try:
            subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_script])
            logger.info("[SchedulerAgent] Dispatched native Windows notification: '%s' - '%s'", title, message)
        except Exception as e:
            logger.warning("[SchedulerAgent] Windows notification display error: %s", e)

    def _on_alarm_fired(self, alarm_id: str, message: str, persona: str) -> None:
        """Callback executed by APScheduler when alarm triggers."""
        logger.info("[SchedulerAgent] ALARM FIRED: id=%s, message='%s', persona=%s", alarm_id, message, persona)

        # 1. Update alarm status in registry
        if alarm_id in self.active_alarms:
            self.active_alarms[alarm_id]["status"] = "fired"
            self.active_alarms[alarm_id]["fired_at"] = time.time()

        # 2. Dispatch real Windows Notification
        title = f"JARVIS Alarm ({persona})"
        self._show_windows_notification(title, message)

        # 3. Trigger spoken TTS announcement
        try:
            announcement = f"Alert: {message}"
            tts_engine.speak(announcement, persona_name=persona)
        except Exception as tts_err:
            logger.warning("[SchedulerAgent] Spoken alarm TTS warning: %s", tts_err)

        # 4. Emit PerceptionEvent for mesh & web client
        try:
            event = PerceptionEvent(
                type="alarm_triggered",
                payload={
                    "alarm_id": alarm_id,
                    "message": message,
                    "fired_at": time.time(),
                },
                source="scheduler_agent",
                active_persona=persona,
            )
            event_bus.publish(event)
        except Exception as bus_err:
            logger.warning("[SchedulerAgent] Event bus publish error: %s", bus_err)

    def set_alarm(
        self,
        delay_seconds: int,
        message: str = "Your scheduled alarm is firing!",
        persona: Optional[str] = None
    ) -> Dict[str, Any]:
        """Schedules an alarm to fire in delay_seconds seconds."""
        persona_name = persona or settings.active_persona_name
        alarm_id = f"alarm_{uuid.uuid4().hex[:8]}"
        fire_time = datetime.now() + timedelta(seconds=max(1, delay_seconds))

        trigger = DateTrigger(run_date=fire_time)
        self.scheduler.add_job(
            func=self._on_alarm_fired,
            trigger=trigger,
            args=[alarm_id, message, persona_name],
            id=alarm_id,
            replace_existing=True
        )

        alarm_record = {
            "alarm_id": alarm_id,
            "message": message,
            "delay_seconds": delay_seconds,
            "fire_time_iso": fire_time.isoformat(),
            "persona": persona_name,
            "status": "scheduled",
            "created_at": time.time(),
        }
        self.active_alarms[alarm_id] = alarm_record

        logger.info("[SchedulerAgent] Scheduled alarm '%s' for %s (%d seconds out)", alarm_id, fire_time.strftime("%H:%M:%S"), delay_seconds)
        if delay_seconds >= 3600:
            hrs = delay_seconds // 3600
            mins = (delay_seconds % 3600) // 60
            dur_str = f"{hrs} hour{'s' if hrs > 1 else ''}" + (f" and {mins} minute{'s' if mins > 1 else ''}" if mins else "")
        elif delay_seconds >= 60:
            mins = delay_seconds // 60
            secs = delay_seconds % 60
            dur_str = f"{mins} minute{'s' if mins > 1 else ''}" + (f" and {secs} second{'s' if secs > 1 else ''}" if secs else "")
        else:
            dur_str = f"{delay_seconds} second{'s' if delay_seconds > 1 else ''}"

        resp_text = f"Alarm set for {fire_time.strftime('%H:%M:%S')} ({dur_str} from now): '{message}'."
        return {
            "success": True,
            "alarm_id": alarm_id,
            "fire_time": fire_time.strftime("%H:%M:%S"),
            "delay_seconds": delay_seconds,
            "message": message,
            "persona": persona_name,
            "response": resp_text,
            "output": resp_text
        }

    # Alias for capability provider compatibility
    schedule_delayed_alarm = set_alarm

    def list_active_alarms(self) -> List[Dict[str, Any]]:
        """Lists currently pending alarms."""
        return [v for v in self.active_alarms.values() if v.get("status") == "scheduled"]

    def cancel_alarm(self, alarm_id: str) -> Dict[str, Any]:
        """Cancels a scheduled alarm."""
        if alarm_id in self.active_alarms:
            try:
                self.scheduler.remove_job(alarm_id)
            except Exception:
                pass
            self.active_alarms[alarm_id]["status"] = "cancelled"
            return {"success": True, "alarm_id": alarm_id, "message": "Alarm cancelled successfully."}
        return {"success": False, "error": f"Alarm '{alarm_id}' not found."}

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized router entry point."""
        action = inputs.get("action", "set_alarm")
        delay_sec = int(inputs.get("delay_seconds", inputs.get("seconds", 60)))
        message = inputs.get("message", inputs.get("reminder", "Scheduled reminder alarm."))
        persona = inputs.get("persona")

        if action in ["set_alarm", "set_reminder", "create_alarm"]:
            return self.set_alarm(delay_seconds=delay_sec, message=message, persona=persona)
        elif action in ["list", "list_alarms"]:
            alarms = self.list_active_alarms()
            return {"success": True, "active_alarms": alarms, "response": f"You have {len(alarms)} active alarm(s)."}
        elif action in ["cancel", "delete"]:
            alarm_id = inputs.get("alarm_id", "")
            return self.cancel_alarm(alarm_id)
        return {"success": False, "error": f"Unknown scheduler action: {action}"}


scheduler_agent = SchedulerAgent()
