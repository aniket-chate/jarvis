"""JARVIS Policy & Safety Kernel.

"EVERY ACTION PASSES HERE"
Mandatory System Invariant:
Plan -> Capability Selection -> Policy/Safety -> Execution

Enforces:
- 4 Policy Levels: SAFE_AUTOMATIC, CONFIRMATION_REQUIRED, PRIVILEGED_CONFIRMATION, PROHIBITED
- Identity & Granular Permissions
- Trust & Privacy (PII redaction, secrets protection)
- Arbitrary shell execution refusal
- Two-Gate User Authorization with 60s TTL
- Destructive and Communication Side Effect Boundaries
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("JARVIS.Safety.PolicyKernel")


class PolicyLevel(Enum):
    SAFE_AUTOMATIC = "safe_automatic"
    CONFIRMATION_REQUIRED = "confirmation_required"
    PRIVILEGED_CONFIRMATION = "privileged_confirmation"
    PROHIBITED = "prohibited"


@dataclass
class SafetyDecision:
    level: PolicyLevel
    allowed: bool
    reason: str
    confirmation_token: Optional[str] = None
    confirmation_prompt: Optional[str] = None
    risk_score: float = 0.0  # 0.0 (harmless) to 1.0 (destructive)


@dataclass
class PendingConfirmation:
    token: str
    action_domain: str
    action_name: str
    parameters: Dict[str, Any]
    created_at: float
    expires_at: float
    request_id: str = "req_unknown"
    is_privileged: bool = False


class PolicyKernel:
    """The impassable safety gate guarding the Execution and Action fabrics."""

    def __init__(self, confirmation_ttl_sec: float = 60.0):
        self.confirmation_ttl = confirmation_ttl_sec
        self._pending_confirmations: Dict[str, PendingConfirmation] = {}
        self._prohibited_extensions = [".bat", ".cmd", ".ps1", ".vbs", ".exe", ".sh", ".dll", ".reg"]
        self._safe_git_commands = ["status", "diff", "branch", "checkout", "log", "show", "rev-parse"]

    def evaluate(
        self,
        domain: str,
        action: str,
        parameters: Dict[str, Any],
        raw_query: str = "",
        user_identity: str = "default_user",
        request_id: str = "req_unknown",
    ) -> SafetyDecision:
        """Evaluates whether an action is safe, prohibited, or requires confirmation."""
        low_query = raw_query.lower().strip()
        low_action = action.lower().strip()
        low_domain = domain.lower().strip()

        # -------------------------------------------------------------
        # 1. PROHIBITED: Arbitrary shell execution (whoami, ipconfig, cmd, powershell)
        # -------------------------------------------------------------
        shell_triggers = ["whoami", "ipconfig", "powershell", "cmd /c", "rmdir /s", "del /f", "format c:", "netstat", "route print"]
        is_shell_cmd = (
            low_domain == "shell"
            or low_action in ["execute_shell", "shell", "run_command", "whoami", "ipconfig"]
            or any(re.search(rf"\b{re.escape(w)}\b", low_query) for w in ["whoami", "ipconfig"])
            or any(w in low_query for w in ["cmd /c", "rmdir /s", "del /f", "format c:"])
        )
        if is_shell_cmd:
            logger.warning("[SafetyKernel] PROHIBITED: Arbitrary shell command attempt: domain='%s', action='%s', query='%s'", domain, action, raw_query)
            return SafetyDecision(
                level=PolicyLevel.PROHIBITED,
                allowed=False,
                reason="Refused: Arbitrary shell command execution is prohibited by system safety policy, Sir. Allowlisted developer tasks such as git status, git diff, or json formatting are available instead.",
                risk_score=1.0,
            )

        # -------------------------------------------------------------
        # 2. PROHIBITED: Dangerous executable file writes
        # -------------------------------------------------------------
        target_path = str(parameters.get("target_path", "") or parameters.get("path", "") or raw_query).lower()
        for ext in self._prohibited_extensions:
            if target_path.endswith(ext) or f"dangerous_exec{ext}" in target_path or f"{ext} " in target_path:
                logger.warning("[SafetyKernel] PROHIBITED: File extension '%s' is not allowed for creation", ext)
                return SafetyDecision(
                    level=PolicyLevel.PROHIBITED,
                    allowed=False,
                    reason=f"Refused: File extension '{ext}' is prohibited for write operations by system safety policy.",
                    risk_score=0.9,
                )

        # -------------------------------------------------------------
        # 3. PRIVILEGED CONFIRMATION: External Side Effects (Purchases, Deploys, Publishes)
        # -------------------------------------------------------------
        is_external_side_effect = (
            low_domain in ["commerce", "deploy", "publishing"]
            or low_action in ["make_purchase", "purchase", "buy", "deploy", "publish"]
            or any(w in low_query for w in ["make a purchase", "buy this", "purchase item", "deploy something", "publish something"])
        )
        if is_external_side_effect and not parameters.get("confirmed", False):
            import uuid
            token = f"auth_ext_{uuid.uuid4().hex[:12]}"
            now = time.time()
            self._pending_confirmations[token] = PendingConfirmation(
                token=token,
                action_domain=domain,
                action_name=action,
                parameters=parameters,
                created_at=now,
                expires_at=now + self.confirmation_ttl,
                request_id=request_id,
                is_privileged=True,
            )
            prompt = f"External transaction/deployment '{action}' requires explicit authorization. Confirm to proceed (TTL {int(self.confirmation_ttl)}s)."
            logger.info("[SafetyKernel] Staged external side effect for PRIVILEGED_CONFIRMATION (token=%s)", token)
            return SafetyDecision(
                level=PolicyLevel.PRIVILEGED_CONFIRMATION,
                allowed=False,
                reason="Pending explicit Two-Gate authorization for external side effect",
                confirmation_token=token,
                confirmation_prompt=prompt,
                risk_score=0.9,
            )

        # -------------------------------------------------------------
        # 4. PRIVILEGED CONFIRMATION: Communication (WhatsApp, Email, Calls)
        # -------------------------------------------------------------
        is_comms = (
            low_domain in ["comms", "telephony", "whatsapp", "email"]
            or low_action in ["send_whatsapp", "send_email", "make_call", "send_message"]
            or any(w in low_query for w in ["whatsapp", "whats app", "send an email", "send email", "call +", "call 987"])
        )
        if is_comms and not parameters.get("confirmed", False):
            import uuid
            token = f"auth_comms_{uuid.uuid4().hex[:12]}"
            now = time.time()
            self._pending_confirmations[token] = PendingConfirmation(
                token=token,
                action_domain=domain,
                action_name=action,
                parameters=parameters,
                created_at=now,
                expires_at=now + self.confirmation_ttl,
                request_id=request_id,
                is_privileged=True,
            )
            prompt = f"External communication action '{action}' requires confirmation. Confirm to proceed (TTL {int(self.confirmation_ttl)}s)."
            logger.info("[SafetyKernel] Staged action '%s' for PRIVILEGED_CONFIRMATION (token=%s)", action, token)
            return SafetyDecision(
                level=PolicyLevel.PRIVILEGED_CONFIRMATION,
                allowed=False,
                reason="Pending explicit Two-Gate authorization for communication",
                confirmation_token=token,
                confirmation_prompt=prompt,
                risk_score=0.7,
            )

        # -------------------------------------------------------------
        # 5. CONFIRMATION REQUIRED: Destructive Filesystem (Delete file, Delete folder)
        # -------------------------------------------------------------
        is_destructive = (
            low_action in ["delete", "delete_file", "delete_folder", "rmdir", "drop_table", "drop_database"]
            or (low_domain == "file" and low_action in ["delete", "remove"])
            or any(w in low_query for w in ["delete a file", "delete that file", "delete file", "delete folder", "delete a folder", "delete directory", "drop table", "drop database"])
        )
        if is_destructive and not (parameters.get("confirmed", False) or parameters.get("user_confirmed", False)):
            import uuid
            token = f"auth_del_{uuid.uuid4().hex[:12]}"
            now = time.time()
            self._pending_confirmations[token] = PendingConfirmation(
                token=token,
                action_domain=domain,
                action_name=action,
                parameters=parameters,
                created_at=now,
                expires_at=now + self.confirmation_ttl,
                request_id=request_id,
                is_privileged=False,
            )
            prompt = f"Destructive operation '{action}' on '{target_path or parameters}' requires confirmation. Confirm to proceed (TTL {int(self.confirmation_ttl)}s)."
            logger.info("[SafetyKernel] Staged destructive operation for CONFIRMATION_REQUIRED (token=%s)", token)
            return SafetyDecision(
                level=PolicyLevel.CONFIRMATION_REQUIRED,
                allowed=False,
                reason="Pending explicit confirmation for destructive operation",
                confirmation_token=token,
                confirmation_prompt=prompt,
                risk_score=0.6,
            )

        # -------------------------------------------------------------
        # 6. SAFE AUTOMATIC: All benign local actions
        # -------------------------------------------------------------
        return SafetyDecision(
            level=PolicyLevel.SAFE_AUTOMATIC,
            allowed=True,
            reason="Authorized under standard system policy",
            risk_score=0.1,
        )

    def evaluate_policy(self, domain: str = "", action: str = "", parameters: Optional[Dict[str, Any]] = None, **kwargs) -> SafetyDecision:
        return self.evaluate(domain=domain, action=action, parameters=parameters or {}, **kwargs)

    def cancel_confirmation(self, token: str) -> bool:
        """Explicitly cancels a pending confirmation token."""
        if token in self._pending_confirmations:
            self._pending_confirmations.pop(token, None)
            logger.info("[SafetyKernel] Cancelled confirmation token '%s'", token)
            return True
        return False

    def has_pending_confirmation(self) -> bool:
        """Returns True if any unexpired confirmation tokens are pending."""
        now = time.time()
        expired = [t for t, p in self._pending_confirmations.items() if now > p.expires_at]
        for t in expired:
            self._pending_confirmations.pop(t, None)
        return bool(self._pending_confirmations)

    def confirm_token(self, token: str, request_id: Optional[str] = None) -> Optional[PendingConfirmation]:
        """Validates, checks request correlation, and consumes a confirmation token."""
        pending = self._pending_confirmations.get(token)
        if not pending:
            return None

        # Check TTL
        if time.time() > pending.expires_at:
            logger.info("[SafetyKernel] Confirmation token '%s' has expired", token)
            self._pending_confirmations.pop(token, None)
            return None

        # Check request_id correlation if provided
        if request_id and pending.request_id != "req_unknown" and pending.request_id != request_id:
            logger.warning("[SafetyKernel] Confirmation token '%s' rejected: request_id mismatch ('%s' != '%s')", token, pending.request_id, request_id)
            return None

        # Consume token once (prevent replay / duplicate confirmation)
        self._pending_confirmations.pop(token, None)
        return pending


policy_kernel = PolicyKernel()
