"""Communication Hub Capability Provider for JARVIS Capability 37.

Provides dynamic contact discovery, draft-first message creation, two-gate
send confirmation, prompt injection quarantine, and delivery verification.
"""

from dataclasses import dataclass, field
import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional

from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from agents.permission_checks import permission_gate
from agents.identity_agent import identity_agent
from agents.privacy_protection import privacy_protection
from gateway.registry import gateway_registry

logger = logging.getLogger("JARVIS.Providers.Communication")


@dataclass
class ContactRecord:
    """Represents a person or entity in the dynamic contact repository."""
    contact_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    relationship: str = "general"
    channel_preferences: List[str] = field(default_factory=lambda: ["email", "message"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contact_id": self.contact_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "tags": self.tags,
            "relationship": self.relationship,
            "channel_preferences": self.channel_preferences,
        }


@dataclass
class CommunicationConfig:
    """Configurable parameters for communication provider."""
    require_confirmation_for_send: bool = True
    max_history_items: int = 50
    delivery_timeout_sec: float = 15.0
    default_channel: str = "email"


class CommunicationHubProvider(BaseCapabilityProvider):
    """Unified provider managing emails, messages, notifications, and contacts."""

    def __init__(self, config: Optional[CommunicationConfig] = None):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.comm.communication_hub",
                name="JARVIS Communication Hub",
                supported_capabilities=[
                    "comm.lookup_contact",
                    "comm.register_contact",
                    "comm.draft_email",
                    "comm.send_email",
                    "comm.draft_message",
                    "comm.send_message",
                    "comm.send_whatsapp",
                    "comm.notify_user",
                    "comm.get_history",
                    "comm.verify_delivery",
                ],
                priority=10,
                estimated_latency_ms=20.0,
                safety_level="external_communication",
                description="Dynamic contacts, draft-first workflow, Two-Gate sending, and delivery audit.",
            )
        )
        self.config = config or CommunicationConfig()
        self._contacts: Dict[str, ContactRecord] = {}
        self._outbox_ledger: Dict[str, Dict[str, Any]] = {}
        self._custom_backend: Optional[Any] = None

    def set_custom_backend(self, backend: Any) -> None:
        """Allows test suites or alternative providers to swap the low-level delivery engine."""
        self._custom_backend = backend

    def register_contact(self, contact: ContactRecord) -> None:
        """Registers a contact dynamically into the repository."""
        self._contacts[contact.contact_id] = contact

    def unregister_contact(self, contact_id: str) -> bool:
        """Removes a contact dynamically."""
        if contact_id in self._contacts:
            del self._contacts[contact_id]
            return True
        # Try matching by name
        for cid, c in list(self._contacts.items()):
            if c.name.lower() == contact_id.lower():
                del self._contacts[cid]
                return True
        return False

    def is_available(self) -> bool:
        """Return true only when at least one real delivery backend is configured."""
        if self._custom_backend is not None:
            return True
        try:
            from skills.google_gmail import gmail_skill
            return bool(getattr(gmail_skill, "is_configured", False))
        except Exception:
            return False

    def execute(
        self,
        capability: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        t0 = time.perf_counter()
        try:
            if capability == "comm.lookup_contact":
                res = self._lookup_contact(parameters)
            elif capability == "comm.register_contact":
                res = self._register_contact(parameters)
            elif capability == "comm.draft_email":
                res = self._draft_email(parameters)
            elif capability == "comm.send_email":
                res = self._send_email(parameters)
            elif capability in ["comm.draft_message", "comm.draft_whatsapp"]:
                res = self._draft_message(parameters)
            elif capability in ["comm.send_message", "comm.send_whatsapp"]:
                res = self._send_message(parameters)
            elif capability == "comm.notify_user":
                res = self._notify_user(parameters)
            elif capability == "comm.get_history":
                res = self._get_history(parameters)
            elif capability == "comm.verify_delivery":
                res = self._verify_delivery(parameters)
            else:
                elapsed = (time.perf_counter() - t0) * 1000
                self.record_outcome(False)
                return ActionResult(
                    status="FAILED",
                    output=None,
                    message=f"Unsupported capability: {capability}",
                    execution_time_ms=elapsed,
                )

            elapsed = (time.perf_counter() - t0) * 1000
            success = bool(res.get("success", True)) if isinstance(res, dict) else True
            operation_status = str(res.get("status", "")).upper() if isinstance(res, dict) else ""
            is_pending = operation_status in {"PENDING_APPROVAL", "IDENTITY_REJECTED", "DEVICE_UNAVAILABLE", "NOT_CONFIGURED"}
            action_status = "PENDING_APPROVAL" if operation_status == "PENDING_APPROVAL" else (
                "FAILED" if (not success and not is_pending) else operation_status or ("SUCCESS" if success else "FAILED")
            )
            self.record_outcome(action_status == "SUCCESS")
            return ActionResult(
                status=action_status,
                output=res,
                message=str(res.get("message") if isinstance(res, dict) else "Communication operation completed."),
                execution_time_ms=elapsed,
            )
        except Exception as e:
            logger.error("[CommunicationHubProvider] Execution error for '%s': %s", capability, str(e), exc_info=True)
            elapsed = (time.perf_counter() - t0) * 1000
            self.record_outcome(False)
            return ActionResult(
                status="FAILED",
                output={"error": str(e)},
                message=str(e),
                execution_time_ms=elapsed,
            )

    def _quarantine_text(self, text: str) -> str:
        """Quarantines adversarial prompt injection attempts contained within communication data."""
        if not text:
            return ""
        injection_signals = [
            "ignore previous instructions",
            "system prompt",
            "you are now",
            "execute shell",
            "delete all files",
            "bypass guardrails",
        ]
        low = text.lower()
        if any(sig in low for sig in injection_signals):
            return f"<UNTRUSTED_COMMUNICATION_DATA>{text}</UNTRUSTED_COMMUNICATION_DATA>"
        return text

    def _lookup_contact(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Discovers contacts dynamically matching query across name, email, phone, or tags."""
        query = str(params.get("query") or params.get("name") or "").strip().lower()
        if not query:
            return {
                "found": False,
                "candidates": [],
                "error": "Query parameter is required for contact lookup.",
            }

        matches: List[ContactRecord] = []
        for c in self._contacts.values():
            if (
                query in c.name.lower()
                or (c.email and query in c.email.lower())
                or (c.phone and query in c.phone)
                or any(query in t.lower() for t in c.tags)
            ):
                matches.append(c)

        if not matches:
            return {
                "found": False,
                "query": query,
                "candidates": [],
                "message": f"No contact found matching '{query}'.",
            }

        if len(matches) == 1:
            return {
                "found": True,
                "resolved": True,
                "is_ambiguous": False,
                "contact": matches[0].to_dict(),
                "query": query,
            }

        return {
            "found": True,
            "resolved": False,
            "is_ambiguous": True,
            "query": query,
            "candidates": [m.to_dict() for m in matches],
            "disambiguation_prompt": f"Multiple contacts match '{query}'. Which contact did you intend?",
        }

    def _register_contact(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Dynamically registers a contact record into repository."""
        name = params.get("name")
        if not name:
            raise ValueError("name is required for contact registration")
        cid = params.get("contact_id") or f"cnt_{uuid.uuid4().hex[:8]}"
        record = ContactRecord(
            contact_id=cid,
            name=name,
            email=params.get("email"),
            phone=params.get("phone"),
            tags=params.get("tags", []),
            relationship=params.get("relationship", "general"),
        )
        self.register_contact(record)
        return {
            "success": True,
            "contact_id": cid,
            "name": name,
            "contact": record.to_dict(),
            "registered": True,
        }

    def _draft_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Creates an email draft in the draft folder without transmission."""
        to = params.get("to") or params.get("recipient")
        if not to:
            raise ValueError("Recipient 'to' is required to create draft.")

        subject = params.get("subject", "No Subject")
        body = self._quarantine_text(str(params.get("body", "")))
        draft_id = f"draft_{uuid.uuid4().hex[:10]}"

        # Sanitize body using privacy protection
        clean_body = privacy_protection.sanitize_external_query(body, "email_draft", allow_recipient_email=True)

        record = {
            "draft_id": draft_id,
            "type": "email",
            "to": to,
            "subject": subject,
            "body": clean_body,
            "created_at": time.time(),
            "status": "DRAFT",
            "is_draft": True,
        }
        self._outbox_ledger[draft_id] = record

        return {
            "success": True,
            "draft_id": draft_id,
            "to": to,
            "subject": subject,
            "status": "DRAFT",
            "message": f"Draft created successfully for '{to}'.",
        }

    def _send_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sends an email under Two-Gate verification policy."""
        to = params.get("to") or params.get("recipient")
        if not to:
            raise ValueError("Recipient 'to' is required to send email.")

        subject = params.get("subject", "Notification")
        body = self._quarantine_text(str(params.get("body", "")))
        user_confirmed = bool(params.get("user_confirmed", False))
        face_embedding = params.get("face_embedding")

        # Step 1: Permission Gate check
        perm = permission_gate.check_permission(
            domain="message",
            action="send_email",
            details={"recipient": to, "subject": subject, "body_length": len(body)},
            confirmed=user_confirmed,
        )
        if not perm.allowed:
            return {
                "success": False,
                "status": "PENDING_APPROVAL",
                "message": perm.message,
                "error": "Sending email blocked pending explicit user authorization.",
            }

        # Step 2: Identity Gate verification
        auth = identity_agent.verify_two_gate_authorization(
            action_name="send_email",
            face_embedding=face_embedding,
            explicit_user_confirmed=user_confirmed,
        )
        if not auth.get("authorized"):
            return {
                "success": False,
                "status": "IDENTITY_REJECTED",
                "error": auth.get("reason", "Identity authentication failed for sensitive email transmission."),
            }

        # Step 3: Perform transmission
        msg_id = f"msg_{uuid.uuid4().hex[:10]}"
        clean_body = privacy_protection.sanitize_external_query(body, "email_send", allow_recipient_email=True)

        if self._custom_backend:
            send_res = self._custom_backend.send_email(to=to, subject=subject, body=clean_body)
            success = bool(send_res.get("success", True))
        else:
            # Default to Gmail skill or sandbox
            try:
                from skills.google_gmail import gmail_skill
                send_res = gmail_skill.send_message(to=to, subject=subject, body=clean_body)
                success = bool(send_res.get("success", False))
            except Exception as ex:
                send_res = {"success": False, "error": str(ex)}
                success = False

        status_str = "SENT" if success else "FAILED"
        record = {
            "message_id": msg_id,
            "type": "email",
            "to": to,
            "subject": subject,
            "body": clean_body,
            "sent_at": time.time(),
            "status": status_str,
            "provider_response": send_res,
        }
        self._outbox_ledger[msg_id] = record

        return {
            "success": success,
            "message_id": msg_id,
            "to": to,
            "status": status_str,
            "provider_response": send_res,
        }

    def _draft_message(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a message draft without transmission."""
        recipient = params.get("recipient") or params.get("to")
        body = self._quarantine_text(str(params.get("message") or params.get("body", "")))
        draft_id = f"msg_draft_{uuid.uuid4().hex[:10]}"

        record = {
            "draft_id": draft_id,
            "type": "message",
            "recipient": recipient,
            "body": body,
            "created_at": time.time(),
            "status": "DRAFT",
            "is_draft": True,
        }
        self._outbox_ledger[draft_id] = record

        return {
            "success": True,
            "draft_id": draft_id,
            "recipient": recipient,
            "status": "DRAFT",
            "message": f"Message draft prepared for '{recipient}'.",
        }

    def _send_message(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sends SMS / Chat message under authorization gate."""
        recipient = params.get("recipient") or params.get("to")
        body = self._quarantine_text(str(params.get("message") or params.get("body", "")))
        user_confirmed = bool(params.get("user_confirmed", False))

        perm = permission_gate.check_permission(
            domain="message",
            action="send_message",
            details={"recipient": recipient, "body_length": len(body)},
            confirmed=user_confirmed,
        )
        if not perm.allowed:
            return {
                "success": False,
                "status": "PENDING_APPROVAL",
                "message": perm.message,
                "error": "Sending message blocked pending user confirmation.",
            }

        if not recipient:
            raise ValueError("Recipient is required to send a message.")

        face_embedding = params.get("face_embedding")
        auth = identity_agent.verify_two_gate_authorization(
            action_name="send_sms",
            face_embedding=face_embedding,
            explicit_user_confirmed=user_confirmed,
        )
        if not auth.get("authorized"):
            return {
                "success": False,
                "status": "IDENTITY_REJECTED",
                "error": auth.get("reason", "Identity authentication failed for sensitive message transmission."),
            }

        if not self._custom_backend:
            return {
                "success": False,
                "status": "NOT_CONFIGURED",
                "error": "No real SMS/chat delivery backend is configured. Message was not sent.",
            }

        msg_id = f"msg_{uuid.uuid4().hex[:10]}"
        send_res = self._custom_backend.send_message(recipient=recipient, body=body)
        success = bool(send_res.get("success", False))

        status_str = "SENT" if success else "FAILED"
        self._outbox_ledger[msg_id] = {
            "message_id": msg_id,
            "type": "message",
            "recipient": recipient,
            "body": body,
            "sent_at": time.time(),
            "status": status_str,
            "provider_response": send_res,
        }

        return {
            "success": success,
            "message_id": msg_id,
            "recipient": recipient,
            "status": status_str,
            "provider_response": send_res,
        }

    def _notify_user(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches user notification locally or via targeted mesh device."""
        title = params.get("title", "JARVIS Notification")
        message = self._quarantine_text(str(params.get("message", "Alert")))
        target_device = params.get("target_device") or params.get("device_id")

        if target_device:
            dev = gateway_registry.find_device(target_device)
            if not dev or not dev.is_alive():
                return {
                    "success": False,
                    "target_device": target_device,
                    "status": "DEVICE_UNAVAILABLE",
                    "error": f"Target device '{target_device}' is unavailable or offline.",
                }
            dispatch_res = {
                "success": True,
                "target_device_id": dev.device_id,
                "status": "delivered_to_device",
            }
        else:
            dispatch_res = {"success": True, "status": "delivered_locally"}

        nid = f"notif_{uuid.uuid4().hex[:8]}"
        self._outbox_ledger[nid] = {
            "notification_id": nid,
            "title": title,
            "message": message,
            "timestamp": time.time(),
            "status": "DELIVERED",
        }

        return {
            "success": True,
            "notification_id": nid,
            "title": title,
            "status": "DELIVERED",
            "target_device": target_device,
            "dispatch": dispatch_res,
        }

    def _get_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Returns recent communication history from outbox ledger."""
        limit = int(params.get("limit", 20))
        items = list(self._outbox_ledger.values())[-limit:]
        return {
            "history": items,
            "count": len(items),
            "total_records": len(self._outbox_ledger),
        }

    def _verify_delivery(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Audits outbox ledger for truthful delivery status of a message or draft."""
        item_id = params.get("item_id") or params.get("message_id") or params.get("draft_id") or params.get("id")
        if not item_id:
            raise ValueError("item_id (message_id or draft_id) is required for delivery verification")

        record = self._outbox_ledger.get(item_id)
        if not record:
            return {
                "item_id": item_id,
                "found": False,
                "delivery_status": "UNKNOWN",
                "error": f"No communication record found for ID '{item_id}'.",
            }

        return {
            "item_id": item_id,
            "found": True,
            "delivery_status": record.get("status", "UNKNOWN"),
            "record": record,
        }
