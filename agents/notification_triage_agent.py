"""Desktop Notification Triage Agent for JARVIS Layer 3 (Group 5).

Provides READ-ONLY notification triage by inspecting the Windows Action Center
notification store (wpndatabase.db).
Summarizes, clusters by application, and prioritizes desktop alerts on request.
SAFETY INVARIANT: Strictly read-only; auto-reply is deferred to a future prompt.
"""

import os
import re
import shutil
import sqlite3
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("JARVIS.NotificationTriageAgent")


class NotificationTriageAgent:
    """Read-only desktop notification triage and summarization engine."""

    def __init__(self):
        self.db_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Notifications" / "wpndatabase.db"

    def _clean_app_name(self, raw_app: Optional[str]) -> str:
        """Converts Windows internal application IDs into human-readable labels."""
        if not raw_app:
            return "Windows System"
        clean = raw_app
        if "calendar" in clean.lower():
            return "Google Calendar"
        elif "antigravity" in clean.lower():
            return "Antigravity IDE"
        elif "slack" in clean.lower():
            return "Slack"
        elif "teams" in clean.lower():
            return "Microsoft Teams"
        elif "outlook" in clean.lower():
            return "Outlook"
        elif "whatsapp" in clean.lower():
            return "WhatsApp"
        elif "chrome" in clean.lower():
            return "Google Chrome"
        elif "widgets" in clean.lower():
            return "Windows Widgets"
        elif "yourphone" in clean.lower():
            return "Phone Link"
        elif "systemtoast" in clean.lower():
            return "System Notification"
        
        # Strip long UWP package hashes
        if "!" in clean:
            clean = clean.split("!")[-1]
        if "_" in clean and len(clean) > 20:
            clean = clean.split("_")[0]
        return clean.replace(".", " ").title()

    def _extract_xml_texts(self, payload: Any) -> List[str]:
        """Extracts human-readable text elements from XML notification payloads."""
        if isinstance(payload, bytes):
            text_data = payload.decode("utf-8", errors="ignore")
        else:
            text_data = str(payload or "")

        # Find XML text node contents
        matches = re.findall(r">([^<]{2,})<", text_data)
        cleaned = []
        for m in matches:
            t = m.strip()
            # Ignore schema URLs and technical attributes
            if t and not t.startswith("http") and not t.startswith("schemas.") and not t.startswith("{"):
                cleaned.append(t)
        return cleaned

    def triage_notifications(self, limit: int = 30) -> Dict[str, Any]:
        """Queries and summarizes pending/recent Windows notifications in read-only mode."""
        if not self.db_path.exists():
            return {
                "success": False,
                "error": "Windows notification database not found.",
                "response": "Unable to access Windows notification database."
            }

        # Safe copy to avoid file locks with Windows push notification service
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_name = tmp.name
        try:
            shutil.copy2(self.db_path, tmp_name)
        except Exception as copy_err:
            try:
                os.unlink(tmp_name)
            except Exception:
                pass
            return {"success": False, "error": f"Failed to access notification store: {copy_err}"}

        notifications = []
        grouped_by_app: Dict[str, List[Dict[str, Any]]] = {}

        try:
            conn = sqlite3.connect(tmp_name)
            cur = conn.cursor()
            query = """
                SELECT n.Id, h.PrimaryId, n.Payload, n.ArrivalTime, n.Type
                FROM Notification n
                LEFT JOIN NotificationHandler h ON n.HandlerId = h.RecordId
                ORDER BY n.ArrivalTime DESC
                LIMIT ?;
            """
            cur.execute(query, (limit,))
            rows = cur.fetchall()
            conn.close()

            for nid, raw_app, payload, arrival_time, ntype in rows:
                app_name = self._clean_app_name(raw_app)
                texts = self._extract_xml_texts(payload)
                if not texts:
                    continue

                title = texts[0] if len(texts) > 0 else "Notification"
                message = texts[1] if len(texts) > 1 else (texts[0] if len(texts) == 1 else "")
                details = texts[2:] if len(texts) > 2 else []

                item = {
                    "id": nid,
                    "app": app_name,
                    "title": title,
                    "message": message[:200],
                    "details": details,
                    "arrival_raw": arrival_time
                }
                notifications.append(item)
                grouped_by_app.setdefault(app_name, []).append(item)

        except Exception as q_err:
            return {"success": False, "error": f"Error querying notifications: {q_err}"}
        finally:
            try:
                os.unlink(tmp_name)
            except Exception:
                pass

        # Build executive triage summary
        summary_lines = [f"Desktop Notification Triage ({len(notifications)} active alerts found):"]
        for app, items in grouped_by_app.items():
            summary_lines.append(f"• **{app}** ({len(items)}):")
            for it in items[:3]:
                preview = f"{it['title']}: {it['message']}" if it['message'] and it['message'] != it['title'] else it['title']
                summary_lines.append(f"   - {preview[:100]}")

        summary_text = "\n".join(summary_lines)

        return {
            "success": True,
            "action": "triage_notifications",
            "mode": "read_only",
            "total_count": len(notifications),
            "app_count": len(grouped_by_app),
            "grouped_by_app": {app: len(items) for app, items in grouped_by_app.items()},
            "notifications": notifications[:15],
            "response": summary_text,
            "output": summary_text
        }

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator Agent Router."""
        limit = int(inputs.get("limit", 25))
        return self.triage_notifications(limit=limit)


notification_triage_agent = NotificationTriageAgent()
