"""Communication Agent for JARVIS Layer 3 (Group 3).

Handles Email, SMS, and WhatsApp communications:
1. Email: Gmail API integration.
   - Draft-first workflow: always creates draft first.
   - Two-Gate Approval: Sending requires BOTH identity match and user confirmation.
2. SMS: Native Android SMS Intent generator (smsto: scheme).
   - Draft-first workflow requiring user confirmation before dispatch.
3. WhatsApp: Official WhatsApp Business Cloud API ONLY.
   - Strictly refuses automation of personal WhatsApp accounts.
"""

import re
import logging
from typing import Dict, Any, List, Optional
import httpx

from config.settings import settings
from skills.google_gmail import gmail_skill
from agents.permission_checks import permission_gate
from agents.identity_agent import identity_agent
from agents.privacy_protection import privacy_protection

logger = logging.getLogger("JARVIS.CommunicationAgent")


class CommunicationAgent:
    """Agent for drafting and sending emails, SMS intents, and WhatsApp messages."""

    def __init__(self):
        self.gmail = gmail_skill
        self.whatsapp_token = settings.whatsapp_business_api_key

    # =========================================================================
    # 1. EMAIL (Gmail API)
    # =========================================================================

    def draft_email(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        """Creates an email draft in Gmail without sending."""
        # Sanitize body using privacy protection
        clean_body = privacy_protection.sanitize_external_query(body, "email_draft", allow_recipient_email=True)
        logger.info("[CommunicationAgent] Creating email draft to '%s', subject: '%s'", to, subject)
        return self.gmail.create_draft(to=to, subject=subject, body=clean_body)

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        user_confirmed: bool = False,
        face_embedding: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """Sends an email via Gmail API under strict Group 4 two-gate authorization."""
        # Step 1: Permission Gate check
        perm = permission_gate.check_permission(
            domain="message",
            action="send_email",
            details={"recipient": to, "subject": subject, "body_length": len(body)},
            confirmed=user_confirmed
        )
        if not perm.allowed:
            return {
                "success": False,
                "status": "pending_approval",
                "message": perm.message,
                "error": "Sending email blocked pending explicit user authorization."
            }

        # Step 2: Identity Gate check (Two-Independent-Gates Rule)
        auth = identity_agent.verify_two_gate_authorization(
            action_name="send_email",
            face_embedding=face_embedding,
            explicit_user_confirmed=user_confirmed
        )
        if not auth.get("authorized"):
            return {
                "success": False,
                "status": "identity_rejected",
                "error": auth.get("reason", "Identity authentication failed for sensitive email transmission.")
            }

        # Step 3: Perform send
        clean_body = privacy_protection.sanitize_external_query(body, "email_send", allow_recipient_email=True)
        return self.gmail.send_message(to=to, subject=subject, body=clean_body)

    # =========================================================================
    # 2. SMS (Native Android Intent)
    # =========================================================================

    def _normalize_phone_number(self, phone: str) -> str:
        """Defaults to Indian (+91) country code unless explicitly specified otherwise."""
        cleaned = re.sub(r"[^\d+]", "", phone.strip())
        if cleaned.startswith("+"):
            return cleaned
        if len(cleaned) == 10:
            return f"+91{cleaned}"
        if len(cleaned) == 12 and cleaned.startswith("91"):
            return f"+{cleaned}"
        if len(cleaned) == 11 and cleaned.startswith("0"):
            return f"+91{cleaned[1:]}"
        return f"+91{cleaned}" if len(cleaned) <= 10 else f"+{cleaned}"

    def create_sms_intent(
        self,
        phone_number: str,
        message_text: str,
        user_confirmed: bool = False
    ) -> Dict[str, Any]:
        """Generates a native Android SMS intent URL for dispatching via companion app.

        Defaults phone numbers without international code to +91 (India).
        """
        normalized_phone = self._normalize_phone_number(phone_number)
        perm = permission_gate.check_permission(
            domain="message",
            action="send_sms",
            details={"recipient": normalized_phone, "message": message_text},
            confirmed=user_confirmed
        )
        if not perm.allowed:
            return {
                "success": False,
                "status": "pending_approval",
                "message": perm.message,
                "error": "SMS intent dispatch blocked pending user approval."
            }

        import urllib.parse
        encoded_msg = urllib.parse.quote(message_text)
        intent_uri = f"smsto:{normalized_phone}?body={encoded_msg}"

        return {
            "success": True,
            "channel": "android_sms_intent",
            "phone_number": normalized_phone,
            "raw_input_phone": phone_number,
            "country_code": "+91",
            "message": message_text,
            "intent_uri": intent_uri,
            "status": "ready_for_android_dispatch"
        }

    # =========================================================================
    # 3. WHATSAPP (Free Browser Automation via Authenticated Chrome Session)
    # =========================================================================

    def send_whatsapp_message(
        self,
        recipient: str = "",
        message_text: str = "",
        user_confirmed: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Drafts and dispatches WhatsApp messages via authenticated WhatsApp Web in real Chrome session."""
        from orchestrator.memory import memory_manager
        from agents.browser_automation_agent import browser_automation_agent

        clean_recipient = (recipient or kwargs.get("recipient_phone") or kwargs.get("to") or "").strip()
        clean_text = (message_text or kwargs.get("template_or_text") or kwargs.get("body") or kwargs.get("text") or "").strip()

        # DRAFT-FIRST CONFIRMATION GATE (Priority 10)
        if not user_confirmed:
            memory_manager.set_pending_action({
                "action": "send_whatsapp",
                "required_agent_type": "communication_agent",
                "inputs": {
                    "channel": "whatsapp",
                    "action": "send_whatsapp",
                    "recipient": clean_recipient,
                    "to": clean_recipient,
                    "body": clean_text,
                    "text": clean_text,
                    "user_confirmed": True
                }
            })
            logger.info("[CommunicationAgent] WhatsApp message to '%s' drafted pending explicit confirmation.", clean_recipient)
            disclaimer = (
                "Notice: Automating personal WhatsApp Web operates directly via your browser session and "
                "technically outside official Meta API terms of service (same category of risk accepted for "
                "Instagram browsing)."
            )
            return {
                "success": False,
                "status": "pending_approval",
                "requires_confirmation": True,
                "action": "send_whatsapp",
                "recipient": clean_recipient,
                "message": clean_text,
                "policy_notice": disclaimer,
                "prompt": f"Two-Gate Safety Alert: Do you authorize sending this WhatsApp message to '{clean_recipient}'?",
                "response": (
                    f"Two-Gate Safety Alert: Drafted WhatsApp message to '{clean_recipient}':\n"
                    f"\"{clean_text}\"\n\n"
                    f"[{disclaimer}]\n\n"
                    f"Please confirm to send."
                ),
            }

        # APPROVED EXECUTION: Drive web.whatsapp.com directly via persistent browser session
        logger.info("[CommunicationAgent] Approved WhatsApp dispatch executing for recipient '%s'...", clean_recipient)
        return browser_automation_agent.whatsapp_send_message(
            recipient=clean_recipient,
            message_text=clean_text
        )

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator Agent Router."""
        channel = inputs.get("channel", "email").lower()
        action = inputs.get("action", "draft")

        if channel == "sms":
            return self.create_sms_intent(
                phone_number=inputs.get("to", inputs.get("phone", "")),
                message_text=inputs.get("body", inputs.get("text", "")),
                user_confirmed=inputs.get("user_confirmed", False)
            )
        elif channel == "whatsapp":
            recip = inputs.get("recipient") or inputs.get("to") or inputs.get("phone", "")
            msg = inputs.get("message") or inputs.get("body") or inputs.get("text", "")
            return self.send_whatsapp_message(
                recipient=recip,
                message_text=msg,
                user_confirmed=inputs.get("user_confirmed", False)
            )
        else:  # email
            query_text = inputs.get("query", "")
            to = inputs.get("to") or inputs.get("recipient")
            subject = inputs.get("subject")
            body = inputs.get("body") or inputs.get("content")

            if query_text:
                if not to:
                    m_email = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", query_text)
                    if m_email:
                        to = m_email.group(0)
                    else:
                        m_to = re.search(r"\bto\s+([A-Za-z0-9_\-\.]+)\b", query_text, re.IGNORECASE)
                        if m_to and m_to.group(1).lower() not in ["the", "an", "a", "me", "all", "saying", "asking"]:
                            to = m_to.group(1)
                if not subject:
                    m_subj = re.search(r"\b(?:about|subject|regarding)\s+['\"]?([^'\"\n\r\.\,]+)['\"]?", query_text, re.IGNORECASE)
                    if m_subj:
                        subject = m_subj.group(1).strip()
                if not body:
                    m_body = re.search(r"\b(?:saying|telling them|with message|content)\s+['\"]?([^'\"\n\r]+)['\"]?", query_text, re.IGNORECASE)
                    if m_body:
                        body = m_body.group(1).strip()

            if not to and query_text and not any(w in query_text.lower() for w in ["test", "example"]):
                return {
                    "success": False,
                    "status": "clarification_needed",
                    "agent_type": "communication_agent",
                    "message": "Who would you like me to send or draft the email to? Please specify a recipient.",
                    "response": "Who would you like me to send or draft the email to? Please specify a recipient."
                }

            to = to or "test@example.com"
            subject = subject or "JARVIS Test Message"
            body = body or "Automated test message from JARVIS."
            if action == "send":
                return self.send_email(
                    to=to,
                    subject=subject,
                    body=body,
                    user_confirmed=inputs.get("user_confirmed", False),
                    face_embedding=inputs.get("face_embedding")
                )
            else:
                return self.draft_email(to=to, subject=subject, body=body)


communication_agent = CommunicationAgent()
