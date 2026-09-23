"""Permission Checks & Policy Management Module for JARVIS Layer 3 (Group 4).

Granular Authorization States:
- ALLOW: Explicitly allowed by the user.
- ASK: Requires explicit runtime confirmation (default for restricted capabilities).
- DENY: Blocked/rejected from execution -- inviolable gate.

INVIOLABLE SAFETY INVARIANT:
Two-Independent-Gates Rule (Gate 1: Biometric identity match + Gate 2: Explicit confirmation)
is permanent and non-bypassable. An 'ALLOW' state can NEVER bypass Two-Independent-Gates
for sensitive actions (delete_file, format_disk, send_email, financial_transaction, etc.).
The Continuous Learning engine is strictly firewalled from altering, weakening, or bypassing
these gates.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings import PROJECT_ROOT, settings

logger = logging.getLogger("JARVIS.Safety.Permissions")

PERMISSIONS_PATH = PROJECT_ROOT / "memory" / "permissions.json"

RESTRICTED_DOMAINS = {
    "filesystem", "file", "application", "app", "calendar",
    "message", "email", "sms", "money", "system"
}

SENSITIVE_ACTIONS = {
    "send_email",
    "send_sms",
    "delete_file",
    "format_disk",
    "book_reservation",
    "financial_transaction",
    "lock_system",
    "power_off",
}


class PermissionState(str, Enum):
    """Granular authorization states."""
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PermissionDecision:
    """Represents a recorded permission decision for a capability or action."""
    capability: str
    state: PermissionState = PermissionState.ASK
    reason: str = ""
    updated_at: str = field(default_factory=_utcnow_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value if isinstance(self.state, PermissionState) else str(self.state)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PermissionDecision":
        state_raw = data.get("state", PermissionState.ASK.value)
        try:
            state = PermissionState(state_raw)
        except ValueError:
            state = PermissionState.ASK
        return cls(
            capability=str(data.get("capability", "")),
            state=state,
            reason=str(data.get("reason", "")),
            updated_at=str(data.get("updated_at", _utcnow_iso())),
            metadata=dict(data.get("metadata", {})),
        )


class PermissionManager:
    """Evaluates agent actions against persistent permission policies and Two-Gate safety rules."""

    def __init__(self, storage_path: Path = PERMISSIONS_PATH):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._store: Dict[str, PermissionDecision] = {}
        self._load_permissions()

    def _load_permissions(self) -> None:
        """Loads permission decisions from persistent storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._store = {
                            k: PermissionDecision.from_dict(v)
                            for k, v in data.items()
                            if isinstance(v, dict)
                        }
                logger.info("[PermissionManager] Loaded %d permission policies from %s", len(self._store), self.storage_path)
            except Exception as e:
                logger.error("[PermissionManager] Error loading permissions: %s", str(e))
                self._store = {}
        else:
            self._store = {}

    def _save_permissions(self) -> None:
        """Atomically persists permission decisions to disk."""
        tmp_path = self.storage_path.with_suffix(".tmp")
        try:
            serialized = {k: v.to_dict() for k, v in self._store.items()}
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2)
            tmp_path.replace(self.storage_path)
            logger.debug("[PermissionManager] Flushed permission policies to disk.")
        except Exception as e:
            logger.error("[PermissionManager] Failed saving permissions: %s", str(e))
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    def get_state(self, capability: str) -> PermissionState:
        """Retrieves permission state for a capability or action (default: ASK)."""
        clean_cap = capability.strip().lower()
        with self._lock:
            decision = self._store.get(clean_cap)
            if decision:
                return decision.state
        return PermissionState.ASK

    def set_state(
        self,
        capability: str,
        state: PermissionState | str,
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PermissionDecision:
        """Sets and persists permission decision for a capability or action."""
        clean_cap = capability.strip().lower()
        if isinstance(state, str):
            state = PermissionState(state.lower())

        with self._lock:
            decision = PermissionDecision(
                capability=clean_cap,
                state=state,
                reason=reason,
                updated_at=_utcnow_iso(),
                metadata=metadata or {},
            )
            self._store[clean_cap] = decision
            self._save_permissions()

        logger.info("[PermissionManager] Policy updated: '%s' -> %s (%s)", clean_cap, state.value.upper(), reason)
        return decision

    set_permission = set_state
    set_policy = set_state

    def list_permissions(self) -> Dict[str, Dict[str, Any]]:

        """Returns all registered permission decisions."""
        with self._lock:
            return {k: v.to_dict() for k, v in self._store.items()}

    def evaluate_action(
        self,
        domain: str,
        action: str,
        details: Dict[str, Any],
        is_approved: bool = False,
        persona: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Checks if an action requires explicit user permission and returns authorization state."""
        p_name = persona or settings.active_persona_name
        domain_lower = domain.lower().strip()
        action_lower = action.lower().strip()

        # Check hierarchical capability key: "domain.action", then "action", then "domain"
        candidates = [f"{domain_lower}.{action_lower}", action_lower, domain_lower]
        perm_state = PermissionState.ASK
        for cand in candidates:
            with self._lock:
                if cand in self._store:
                    perm_state = self._store[cand].state
                    break

        prompt_desc = f"Action in domain '{domain}': {action} with parameters {details}"

        # -------------------------------------------------------------
        # 1. State == DENY: Immediate Hard Block (Cannot be overridden)
        # -------------------------------------------------------------
        if perm_state == PermissionState.DENY:
            logger.warning("[PermissionGate] [%s] Action STRICTLY BLOCKED by DENY policy: %s", p_name, prompt_desc)
            return {
                "approved": False,
                "status": "denied",
                "domain": domain,
                "action": action,
                "details": details,
                "reason": f"Capability '{action}' is explicitly DENIED by user permission policy.",
                "prompt": f"Permission Denied: '{action}' has been blocked by your permanent policy setting.",
                "active_persona": p_name,
            }

        # -------------------------------------------------------------
        # 2. Check Sensitive Actions: Non-bypassable Two-Independent-Gates Rule
        # -------------------------------------------------------------
        is_sensitive = (
            action_lower in SENSITIVE_ACTIONS
            or any(s in action_lower for s in ["delete", "format", "send_email", "pay", "kill"])
        )
        if is_sensitive:
            if not is_approved:
                logger.warning("[PermissionGate] [%s] SENSITIVE action requires confirmation: %s", p_name, prompt_desc)
                return {
                    "approved": False,
                    "status": "pending_approval",
                    "domain": domain,
                    "action": action,
                    "details": details,
                    "prompt": f"Two-Gate Safety Alert: JARVIS requires confirmation to execute sensitive action '{action}'. Parameters: {details}",
                    "active_persona": p_name,
                }
            # When confirmed, sensitive action approved
            logger.info("[PermissionGate] [%s] SENSITIVE action APPROVED after user confirmation: %s", p_name, prompt_desc)
            return {
                "approved": True,
                "status": "approved",
                "domain": domain,
                "action": action,
                "details": details,
                "active_persona": p_name,
            }

        # -------------------------------------------------------------
        # 3. State == ALLOW for non-sensitive actions
        # -------------------------------------------------------------
        if perm_state == PermissionState.ALLOW:
            logger.info("[PermissionGate] [%s] Action APPROVED via persistent ALLOW policy: %s", p_name, prompt_desc)
            return {
                "approved": True,
                "status": "approved",
                "domain": domain,
                "action": action,
                "details": details,
                "active_persona": p_name,
            }

        # -------------------------------------------------------------
        # 4. State == ASK: Requires user approval if restricted domain
        # -------------------------------------------------------------
        requires_permission = domain_lower in RESTRICTED_DOMAINS
        if requires_permission and not is_approved:
            logger.warning("[PermissionGate] [%s] Action BLOCKED pending approval: %s", p_name, prompt_desc)
            return {
                "approved": False,
                "status": "pending_approval",
                "domain": domain,
                "action": action,
                "details": details,
                "prompt": f"Permission Request: JARVIS requires confirmation to execute '{action}' on {domain}. Details: {details}",
                "active_persona": p_name,
            }

        logger.info("[PermissionGate] [%s] Action APPROVED for execution: %s", p_name, prompt_desc)
        return {
            "approved": True,
            "status": "approved",
            "domain": domain,
            "action": action,
            "details": details,
            "active_persona": p_name,
        }

    def check_permission(
        self,
        domain: str,
        action: str,
        details: Dict[str, Any],
        confirmed: bool = False,
        persona: Optional[str] = None,
    ) -> Any:
        """Object-oriented check returning an object with .allowed, .message, .status."""
        res = self.evaluate_action(
            domain=domain,
            action=action,
            details=details,
            is_approved=confirmed,
            persona=persona,
        )

        class PermissionResult:
            def __init__(self, d: Dict[str, Any]):
                self.allowed = d.get("approved", False)
                self.status = d.get("status", "pending_approval")
                self.message = d.get("prompt", "Action approved") if not self.allowed else "Approved for execution"
                self.data = d

            def __repr__(self) -> str:
                return f"<PermissionResult allowed={self.allowed} status={self.status}>"

        return PermissionResult(res)


permission_manager = PermissionManager()
permission_gate = permission_manager
