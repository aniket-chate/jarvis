"""Google Gmail Skill for JARVIS.

Uses shared Google Cloud OAuth App covering Calendar and Gmail.
Supports inspecting unread messages and creating email drafts.
Graceful degradation: If unconfigured or unauthorized, disables itself cleanly.
"""

import base64
import logging
from email.mime.text import MIMEText
from typing import Dict, List, Any, Optional

from config.settings import settings
from skills.google_auth import get_shared_credentials

logger = logging.getLogger("JARVIS.Skills.Gmail")


class GoogleGmailSkill:
    def __init__(self):
        self.is_configured = settings.google_oauth_configured
        self._service = None

        if not self.is_configured:
            logger.warning("[Gmail Skill] Disabled: No Google OAuth credentials configured")

    def _get_service(self):
        """Builds and returns Gmail v1 service client."""
        if self._service is not None:
            return self._service

        creds = get_shared_credentials()
        if not creds:
            return None

        try:
            from googleapiclient.discovery import build
            self._service = build("gmail", "v1", credentials=creds)
            return self._service
        except Exception as e:
            logger.error("[Gmail Error] Service construction failed: %s", str(e))
            return None

    def list_unread_messages(self, max_results: int = 5) -> Dict[str, Any]:
        """Fetches unread email snippets from primary inbox."""
        if not self.is_configured:
            return {
                "success": False,
                "error": "Gmail skill is unconfigured. Add credentials to enable.",
                "messages": [],
            }

        service = self._get_service()
        if not service:
            return {
                "success": False,
                "error": "Gmail is not authorized. Run 'python main.py --auth' to connect.",
                "messages": [],
            }

        try:
            results = service.users().messages().list(
                userId="me",
                q="is:unread label:INBOX",
                maxResults=max_results,
            ).execute()

            messages = results.get("messages", [])
            snippets = []
            for msg in messages:
                detail = service.users().messages().get(userId="me", id=msg["id"], format="snippet").execute()
                snippets.append({
                    "id": msg["id"],
                    "snippet": detail.get("snippet", ""),
                })

            return {"success": True, "messages": snippets}
        except Exception as e:
            logger.error("[Gmail Error] %s", str(e))
            return {"success": False, "error": str(e), "messages": []}

    def create_draft(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        """Creates an email draft in Gmail without sending."""
        if not self.is_configured:
            return {
                "success": False,
                "error": "Gmail skill is unconfigured. Add credentials to enable.",
            }

        service = self._get_service()
        if not service:
            return {
                "success": False,
                "error": "Gmail is not authorized. Run 'python main.py --auth' to connect.",
            }

        try:
            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            raw_encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

            draft_body = {"message": {"raw": raw_encoded}}
            draft = service.users().drafts().create(userId="me", body=draft_body).execute()

            logger.info("[Gmail Skill] Draft created successfully with ID: %s", draft.get("id"))
            return {
                "success": True,
                "draft_id": draft.get("id"),
                "to": to,
                "subject": subject,
                "message": "Email draft created successfully in Gmail.",
            }
        except Exception as e:
            logger.error("[Gmail Error] Draft creation failed: %s", str(e))
            return {"success": False, "error": str(e)}

    def send_message(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        """Sends an email via Gmail API."""
        if not self.is_configured:
            return {
                "success": False,
                "error": "Gmail skill is unconfigured. Add credentials to enable.",
            }

        service = self._get_service()
        if not service:
            return {
                "success": False,
                "error": "Gmail is not authorized. Run auth to connect your account.",
            }

        try:
            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            raw_encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

            send_body = {"raw": raw_encoded}
            sent_msg = service.users().messages().send(userId="me", body=send_body).execute()

            logger.info("[Gmail Skill] Email sent successfully with ID: %s to %s", sent_msg.get("id"), to)
            return {
                "success": True,
                "message_id": sent_msg.get("id"),
                "to": to,
                "subject": subject,
                "status": "sent"
            }
        except Exception as e:
            logger.error("[Gmail Error] Send failed: %s", str(e))
            return {"success": False, "error": str(e)}


gmail_skill = GoogleGmailSkill()

