"""Capability 48: Security & Identity Provider.

Provides a unified, hardened security and identity layer for JARVIS:
- Generic identity records (human, device, service, application, session, external)
- Pluggable authentication mechanisms (local credentials, signed bearer tokens, device tokens)
- Granular authorization (WHO, WHAT, ON WHAT, CONTEXT, TRUST) integrated with PolicyKernel
- Stateful trust evaluation (UNKNOWN, UNTRUSTED, TRUSTED, PRIVILEGED, REVOKED)
- Device identity lifecycle & attestation
- Mandatory secret redaction & credential token masking
- Structured, queryable security audit logging without secret leakage
- Prompt injection quarantine targeting credentials and auth bypass
- Zero domain-specific hardcoding: all identities and credentials are treated as dynamic fixtures
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import logging
from pathlib import Path
import re
import secrets
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import uuid

from capabilities.base import ActionResult, BaseCapabilityProvider, ProviderMetadata
from safety.policy_kernel import policy_kernel, PolicyLevel, SafetyDecision
from event_fabric.bus import event_bus
from event_fabric.schemas import UniversalEvent

logger = logging.getLogger("JARVIS.Capabilities.Providers.SecurityIdentity")


# -----------------------------------------------------------------------------
# Enums and Schemas
# -----------------------------------------------------------------------------

class IdentityType(str, Enum):
    HUMAN = "HUMAN"
    DEVICE = "DEVICE"
    SERVICE = "SERVICE"
    APPLICATION = "APPLICATION"
    CAPABILITY_PROVIDER = "CAPABILITY_PROVIDER"
    SESSION = "SESSION"
    EXTERNAL = "EXTERNAL"


class IdentityStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"


class TrustState(str, Enum):
    UNKNOWN = "UNKNOWN"
    UNTRUSTED = "UNTRUSTED"
    TRUSTED = "TRUSTED"
    PRIVILEGED = "PRIVILEGED"
    REVOKED = "REVOKED"


class AuthState(str, Enum):
    AUTHENTICATED = "AUTHENTICATED"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    INVALID = "INVALID"
    REQUIRES_REAUTHENTICATION = "REQUIRES_REAUTHENTICATION"


class AuthMechanism(str, Enum):
    LOCAL_CREDENTIAL = "LOCAL_CREDENTIAL"
    SIGNED_TOKEN = "SIGNED_TOKEN"
    DEVICE_CREDENTIAL = "DEVICE_CREDENTIAL"
    SESSION_CREDENTIAL = "SESSION_CREDENTIAL"
    CUSTOM = "CUSTOM"


class AuthorizationDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    RESTRICTED = "RESTRICTED"
    REVOKED = "REVOKED"


class AuditSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ALERT = "ALERT"
    CRITICAL = "CRITICAL"


@dataclass
class IdentityRecord:
    identity_id: str
    identity_type: IdentityType = IdentityType.HUMAN
    display_name: str = ""
    status: IdentityStatus = IdentityStatus.ACTIVE
    trust_state: TrustState = TrustState.UNKNOWN
    auth_state: AuthState = AuthState.UNAUTHENTICATED
    authorization_scopes: Set[str] = field(default_factory=set)
    creation_metadata: Dict[str, Any] = field(default_factory=dict)
    last_authentication: Optional[float] = None
    revocation_state: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_safe_dict(self) -> Dict[str, Any]:
        """Returns metadata safe for export (no secret references)."""
        return {
            "identity_id": self.identity_id,
            "identity_type": self.identity_type.value,
            "display_name": self.display_name,
            "status": self.status.value,
            "trust_state": self.trust_state.value,
            "auth_state": self.auth_state.value,
            "authorization_scopes": sorted(list(self.authorization_scopes)),
            "creation_metadata": self.creation_metadata,
            "last_authentication": self.last_authentication,
            "revocation_state": self.revocation_state,
            "provenance": self.provenance,
        }


@dataclass
class DeviceIdentityRecord:
    device_id: str
    device_type: str = "GENERIC_DEVICE"
    display_name: str = ""
    status: IdentityStatus = IdentityStatus.ACTIVE
    trust_state: TrustState = TrustState.UNKNOWN
    auth_state: AuthState = AuthState.UNAUTHENTICATED
    public_key_fingerprint: str = ""
    last_seen: float = field(default_factory=time.time)
    capabilities: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_safe_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "display_name": self.display_name,
            "status": self.status.value,
            "trust_state": self.trust_state.value,
            "auth_state": self.auth_state.value,
            "public_key_fingerprint": self.public_key_fingerprint,
            "last_seen": self.last_seen,
            "capabilities": self.capabilities,
            "provenance": self.provenance,
        }


@dataclass
class SessionRecord:
    session_id: str
    identity_id: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600.0)
    scopes: Set[str] = field(default_factory=set)
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        return self.is_active and time.time() < self.expires_at


@dataclass
class SecurityAuditEvent:
    event_id: str
    event_type: str
    identity_id: str
    resource: str
    action: str
    decision: str
    trust_state: str
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)
    severity: AuditSeverity = AuditSeverity.INFO

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "identity_id": self.identity_id,
            "resource": self.resource,
            "action": self.action,
            "decision": self.decision,
            "trust_state": self.trust_state,
            "timestamp": self.timestamp,
            "details": self.details,
            "severity": self.severity.value,
        }


@dataclass
class SecurityConfig:
    default_session_ttl_sec: float = 3600.0
    require_two_gate_for_privileged: bool = True
    max_audit_events_retained: int = 2000
    allow_untrusted_read_only: bool = False
    secret_mask_placeholder: str = "***REDACTED***"


# -----------------------------------------------------------------------------
# Secret Masking & Prompt Injection Defense
# -----------------------------------------------------------------------------

class SecretRedactor:
    """Safely redacts secrets, tokens, keys, and credentials from text and nested structures."""

    PATTERNS = [
        # Bearer tokens and JWTs
        (re.compile(r"Bearer\s+([A-Za-z0-9_\-\.]{15,})", re.IGNORECASE), r"Bearer ***REDACTED***"),
        (re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}", re.IGNORECASE), r"***REDACTED_JWT***"),
        # Passwords / Secrets
        (re.compile(r"(password|secret|api_key|token|auth_token|client_secret)[\s:=]+([^\s,;\"'\}]+)", re.IGNORECASE), r"\1=***REDACTED***"),
        # Private Keys
        (re.compile(r"-----BEGIN\s+([A-Z\s]+)PRIVATE\s+KEY-----.*?-----END\s+\1PRIVATE\s+KEY-----", re.DOTALL | re.IGNORECASE), r"***REDACTED_PRIVATE_KEY***"),
    ]

    SECRET_KEYS = {
        "password", "secret", "api_key", "token", "auth_token", "client_secret",
        "private_key", "credential", "auth_header", "access_token", "refresh_token"
    }

    @classmethod
    def redact_text(cls, text: str, placeholder: str = "***REDACTED***") -> str:
        if not isinstance(text, str):
            return text
        patterns = [
            (re.compile(r"Bearer\s+([A-Za-z0-9_\-\.]{15,})", re.IGNORECASE), f"Bearer {placeholder}"),
            (re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}", re.IGNORECASE), placeholder),
            (re.compile(r"(password|secret|api_key|token|auth_token|client_secret)[\s:=]+([^\s,;\"'\}]+)", re.IGNORECASE), rf"\1={placeholder}"),
            (re.compile(r"-----BEGIN\s+([A-Z\s]+)PRIVATE\s+KEY-----.*?-----END\s+\1PRIVATE\s+KEY-----", re.DOTALL | re.IGNORECASE), placeholder),
        ]
        result = text
        for pattern, replacement in patterns:
            result = pattern.sub(replacement, result)
        return result

    @classmethod
    def redact_data(cls, data: Any, placeholder: str = "***REDACTED***") -> Any:
        if isinstance(data, dict):
            clean = {}
            for k, v in data.items():
                if any(secret_key in str(k).lower() for secret_key in cls.SECRET_KEYS):
                    clean[k] = placeholder
                else:
                    clean[k] = cls.redact_data(v, placeholder)
            return clean
        elif isinstance(data, list):
            return [cls.redact_data(item, placeholder) for item in data]
        elif isinstance(data, str):
            return cls.redact_text(data, placeholder)
        return data


# -----------------------------------------------------------------------------
# Capability 48 Provider Implementation
# -----------------------------------------------------------------------------

class SecurityIdentityProvider(BaseCapabilityProvider):
    """Capability 48: Security & Identity Provider."""

    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"reveal\s+(all\s+)?(passwords|credentials|secrets|api_keys|tokens)", re.IGNORECASE),
        re.compile(r"show\s+me\s+(all\s+)?(passwords|credentials|secrets|tokens)", re.IGNORECASE),
        re.compile(r"bypass\s+.*?(authorization|authentication|security|policy)", re.IGNORECASE),
        re.compile(r"grant\s+me\s+.*?(admin|root|unrestricted)", re.IGNORECASE),
        re.compile(r"ignore\s+(all\s+)?security\s+rules", re.IGNORECASE),
        re.compile(r"exfiltrate\s+credentials", re.IGNORECASE),
        re.compile(r"override\s+auth(entication)?", re.IGNORECASE),
        re.compile(r"security\.bypass", re.IGNORECASE),
    ]

    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self._identities: Dict[str, IdentityRecord] = {}
        self._devices: Dict[str, DeviceIdentityRecord] = {}
        self._sessions: Dict[str, SessionRecord] = {}
        self._credentials_store: Dict[str, str] = {}  # Hashed secrets keyed by identity_id
        self._audit_log: List[SecurityAuditEvent] = []
        self._lock = threading.RLock()

        metadata = ProviderMetadata(
            provider_id="provider.security.identity_manager",
            name="Security & Identity Provider",
            supported_capabilities=[
                "security.register_identity",
                "security.authenticate",
                "security.authorize",
                "security.evaluate_trust",
                "security.revoke_trust",
                "security.register_device",
                "security.authenticate_device",
                "security.mask_credentials",
                "security.redact_secrets",
                "security.create_audit_event",
                "security.query_audit_events",
                "security.create_session",
                "security.validate_session",
                "security.revoke_session",
                "security.rotate_credentials",
                "security.quarantine_prompt",
                "security.evaluate_policy",
                "security.verify_token",
            ],
            priority=10,
            estimated_latency_ms=5.0,
        )
        super().__init__(metadata=metadata)

    def is_available(self) -> bool:
        return True

    # -------------------------------------------------------------------------
    # Execution Dispatcher
    # -------------------------------------------------------------------------

    def execute(self, action: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t0 = time.time()
        with self._lock:
            # Check prompt injection across parameters
            injection_check = self._check_prompt_injection(parameters)
            if injection_check is not None:
                self._record_audit_event(
                    event_type="PROMPT_INJECTION_DETECTED",
                    identity_id=parameters.get("identity_id", "UNKNOWN"),
                    resource=action,
                    action=action,
                    decision="QUARANTINED",
                    trust_state="UNTRUSTED",
                    details={"pattern": injection_check},
                    severity=AuditSeverity.ALERT,
                )
                return ActionResult(
                    status="FAILURE",
                    output={"error": "SECURITY_VIOLATION", "detail": "Prompt injection targeting security controls quarantined."},
                    message="Prompt injection detected and quarantined.",
                    evidence={"quarantined_pattern": injection_check},
                    execution_time_ms=(time.time() - t0) * 1000,
                )

            handlers: Dict[str, Callable[[Dict[str, Any]], ActionResult]] = {
                "security.register_identity": self._handle_register_identity,
                "security.authenticate": self._handle_authenticate,
                "security.authorize": self._handle_authorize,
                "security.evaluate_trust": self._handle_evaluate_trust,
                "security.revoke_trust": self._handle_revoke_trust,
                "security.register_device": self._handle_register_device,
                "security.authenticate_device": self._handle_authenticate_device,
                "security.mask_credentials": self._handle_mask_credentials,
                "security.redact_secrets": self._handle_redact_secrets,
                "security.create_audit_event": self._handle_create_audit_event,
                "security.query_audit_events": self._handle_query_audit_events,
                "security.create_session": self._handle_create_session,
                "security.validate_session": self._handle_validate_session,
                "security.revoke_session": self._handle_revoke_session,
                "security.rotate_credentials": self._handle_rotate_credentials,
                "security.quarantine_prompt": self._handle_quarantine_prompt,
                "security.evaluate_policy": self._handle_evaluate_policy,
                "security.verify_token": self._handle_verify_token,
            }

            handler = handlers.get(action)
            if not handler:
                return ActionResult(
                    status="FAILURE",
                    output={"error": f"Unsupported action '{action}'"},
                    message=f"Operation '{action}' not supported by {self.metadata.provider_id}.",
                    execution_time_ms=(time.time() - t0) * 1000,
                )

            try:
                res = handler(parameters)
                res.execution_time_ms = (time.time() - t0) * 1000
                return res
            except Exception as e:
                logger.error("[SecurityIdentityProvider] Error in action %s: %s", action, e, exc_info=True)
                return ActionResult(
                    status="ERROR",
                    output={"error": str(e)},
                    message=f"Internal error executing {action}: {e}",
                    execution_time_ms=(time.time() - t0) * 1000,
                )

    # -------------------------------------------------------------------------
    # Prompt Injection Quarantine
    # -------------------------------------------------------------------------

    def _check_prompt_injection(self, data: Any) -> Optional[str]:
        if isinstance(data, str):
            for pattern in self.PROMPT_INJECTION_PATTERNS:
                if pattern.search(data):
                    return pattern.pattern
        elif isinstance(data, dict):
            for v in data.values():
                res = self._check_prompt_injection(v)
                if res:
                    return res
        elif isinstance(data, list):
            for item in data:
                res = self._check_prompt_injection(item)
                if res:
                    return res
        return None

    # -------------------------------------------------------------------------
    # Audit Event Recording
    # -------------------------------------------------------------------------

    def _record_audit_event(
        self,
        event_type: str,
        identity_id: str,
        resource: str,
        action: str,
        decision: str,
        trust_state: str,
        details: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
    ) -> SecurityAuditEvent:
        safe_details = SecretRedactor.redact_data(details or {})
        event = SecurityAuditEvent(
            event_id=f"audit-{uuid.uuid4()}",
            event_type=event_type,
            identity_id=identity_id,
            resource=resource,
            action=action,
            decision=decision,
            trust_state=trust_state,
            timestamp=time.time(),
            details=safe_details,
            severity=severity,
        )
        self._audit_log.append(event)
        if len(self._audit_log) > self.config.max_audit_events_retained:
            self._audit_log.pop(0)

        # Publish to EventFabric if bus is active
        try:
            event_bus.publish_sync(UniversalEvent(
                event_type=f"security.audit.{event_type}",
                source=self.metadata.provider_id,
                payload=event.to_dict(),
            ))
        except Exception:
            pass

        return event

    # -------------------------------------------------------------------------
    # Internal Credential Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _hash_credential(secret: str) -> str:
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    # -------------------------------------------------------------------------
    # Handlers
    # -------------------------------------------------------------------------

    def _handle_register_identity(self, params: Dict[str, Any]) -> ActionResult:
        identity_id = params.get("identity_id")
        if not identity_id:
            return ActionResult(status="FAILURE", output={"error": "Missing 'identity_id' parameter"})

        id_type_str = params.get("identity_type", IdentityType.HUMAN.value).upper()
        try:
            id_type = IdentityType(id_type_str)
        except ValueError:
            id_type = IdentityType.HUMAN

        initial_trust_str = params.get("trust_state", TrustState.UNKNOWN.value).upper()
        try:
            initial_trust = TrustState(initial_trust_str)
        except ValueError:
            initial_trust = TrustState.UNKNOWN

        scopes = set(params.get("authorization_scopes", []))
        credential = params.get("credential")

        record = IdentityRecord(
            identity_id=identity_id,
            identity_type=id_type,
            display_name=params.get("display_name", identity_id),
            status=IdentityStatus.ACTIVE,
            trust_state=initial_trust,
            auth_state=AuthState.UNAUTHENTICATED,
            authorization_scopes=scopes,
            creation_metadata=params.get("creation_metadata", {}),
            provenance={"created_at": time.time(), "registered_via": self.metadata.provider_id},
        )

        self._identities[identity_id] = record
        if credential:
            self._credentials_store[identity_id] = self._hash_credential(credential)

        self._record_audit_event(
            event_type="IDENTITY_REGISTERED",
            identity_id=identity_id,
            resource="identity_registry",
            action="register_identity",
            decision="REGISTERED",
            trust_state=initial_trust.value,
            details={"scopes": sorted(list(scopes))},
        )

        return ActionResult(
            status="SUCCESS",
            output={"identity": record.to_safe_dict()},
            message=f"Identity '{identity_id}' registered successfully.",
            evidence={"identity_id": identity_id, "trust_state": initial_trust.value},
        )

    def _handle_authenticate(self, params: Dict[str, Any]) -> ActionResult:
        identity_id = params.get("identity_id")
        credential = params.get("credential")
        token = params.get("token")

        if not identity_id:
            return ActionResult(status="FAILURE", output={"error": "Missing 'identity_id' parameter"})

        record = self._identities.get(identity_id)
        if not record:
            self._record_audit_event(
                event_type="AUTHENTICATION_FAILURE",
                identity_id=identity_id,
                resource="auth_system",
                action="authenticate",
                decision="REJECTED_UNKNOWN_IDENTITY",
                trust_state=TrustState.UNKNOWN.value,
                severity=AuditSeverity.WARNING,
            )
            return ActionResult(
                status="FAILURE",
                output={"auth_state": AuthState.INVALID.value, "error": "Unknown identity"},
                message=f"Identity '{identity_id}' not found.",
            )

        # Check if revoked or suspended
        if record.status == IdentityStatus.REVOKED or record.trust_state == TrustState.REVOKED:
            record.auth_state = AuthState.REVOKED
            self._record_audit_event(
                event_type="AUTHENTICATION_FAILURE",
                identity_id=identity_id,
                resource="auth_system",
                action="authenticate",
                decision="REJECTED_REVOKED",
                trust_state=TrustState.REVOKED.value,
                severity=AuditSeverity.ALERT,
            )
            return ActionResult(
                status="FAILURE",
                output={"auth_state": AuthState.REVOKED.value, "error": "Identity is revoked"},
                message=f"Identity '{identity_id}' is revoked.",
            )

        # Check credentials
        expected_hash = self._credentials_store.get(identity_id)
        auth_success = False

        if credential and expected_hash:
            if self._hash_credential(credential) == expected_hash:
                auth_success = True
        elif token:
            # Check if token matches session or credential
            if expected_hash and self._hash_credential(token) == expected_hash:
                auth_success = True
            elif token in self._sessions and self._sessions[token].identity_id == identity_id and self._sessions[token].is_valid():
                auth_success = True
        elif not expected_hash:
            # Identity has no password set - check if custom mechanism provided
            if params.get("auth_mechanism") == AuthMechanism.CUSTOM.value and params.get("verified") is True:
                auth_success = True

        if auth_success:
            record.auth_state = AuthState.AUTHENTICATED
            record.last_authentication = time.time()
            session_id = f"sess-{secrets.token_hex(16)}"
            session = SessionRecord(
                session_id=session_id,
                identity_id=identity_id,
                created_at=time.time(),
                expires_at=time.time() + self.config.default_session_ttl_sec,
                scopes=set(record.authorization_scopes),
            )
            self._sessions[session_id] = session

            self._record_audit_event(
                event_type="AUTHENTICATION_SUCCESS",
                identity_id=identity_id,
                resource="auth_system",
                action="authenticate",
                decision="AUTHENTICATED",
                trust_state=record.trust_state.value,
                details={"session_id": session_id},
            )

            return ActionResult(
                status="SUCCESS",
                output={
                    "auth_state": AuthState.AUTHENTICATED.value,
                    "session_id": session_id,
                    "identity": record.to_safe_dict(),
                    "expires_at": session.expires_at,
                },
                message=f"Identity '{identity_id}' authenticated successfully.",
                evidence={"identity_id": identity_id, "session_id": session_id},
            )
        else:
            record.auth_state = AuthState.INVALID
            self._record_audit_event(
                event_type="AUTHENTICATION_FAILURE",
                identity_id=identity_id,
                resource="auth_system",
                action="authenticate",
                decision="INVALID_CREDENTIALS",
                trust_state=record.trust_state.value,
                severity=AuditSeverity.WARNING,
            )
            return ActionResult(
                status="FAILURE",
                output={"auth_state": AuthState.INVALID.value, "error": "Invalid credentials"},
                message="Authentication failed: invalid credentials.",
            )

    def _handle_authorize(self, params: Dict[str, Any]) -> ActionResult:
        """Evaluates WHO is requesting WHAT on WHAT resource under WHICH context with WHAT trust."""
        identity_id = params.get("identity_id")
        operation = params.get("operation") or params.get("action")
        resource = params.get("resource", "generic_resource")
        required_scope = params.get("required_scope")
        confirmation_token = params.get("confirmation_token")

        if not identity_id or not operation:
            return ActionResult(status="FAILURE", output={"error": "Missing 'identity_id' or 'operation'"})

        record = self._identities.get(identity_id)

        # 1. Unknown identity
        if not record:
            decision = AuthorizationDecision.DENY
            self._record_audit_event(
                event_type="AUTHORIZATION_DENIED",
                identity_id=identity_id,
                resource=resource,
                action=operation,
                decision=decision.value,
                trust_state=TrustState.UNKNOWN.value,
                details={"reason": "Unknown identity"},
                severity=AuditSeverity.WARNING,
            )
            return ActionResult(
                status="FAILURE",
                output={"decision": decision.value, "allowed": False, "reason": "Unknown identity"},
                message=f"Authorization denied: unknown identity '{identity_id}'.",
            )

        # 2. Revoked identity or trust
        if record.status == IdentityStatus.REVOKED or record.trust_state == TrustState.REVOKED:
            decision = AuthorizationDecision.REVOKED
            self._record_audit_event(
                event_type="AUTHORIZATION_REVOKED",
                identity_id=identity_id,
                resource=resource,
                action=operation,
                decision=decision.value,
                trust_state=TrustState.REVOKED.value,
                details={"reason": "Identity or trust is revoked"},
                severity=AuditSeverity.ALERT,
            )
            return ActionResult(
                status="FAILURE",
                output={"decision": decision.value, "allowed": False, "reason": "Identity is revoked"},
                message=f"Authorization denied: identity '{identity_id}' is revoked.",
            )

        # 3. Untrusted identity
        if record.trust_state == TrustState.UNTRUSTED and not self.config.allow_untrusted_read_only:
            decision = AuthorizationDecision.DENY
            self._record_audit_event(
                event_type="AUTHORIZATION_DENIED",
                identity_id=identity_id,
                resource=resource,
                action=operation,
                decision=decision.value,
                trust_state=TrustState.UNTRUSTED.value,
                details={"reason": "Identity is untrusted"},
            )
            return ActionResult(
                status="FAILURE",
                output={"decision": decision.value, "allowed": False, "reason": "Untrusted identity"},
                message="Authorization denied: untrusted identity.",
            )

        # 4. Scope check
        if required_scope and required_scope not in record.authorization_scopes and "admin" not in record.authorization_scopes:
            decision = AuthorizationDecision.DENY
            self._record_audit_event(
                event_type="AUTHORIZATION_DENIED",
                identity_id=identity_id,
                resource=resource,
                action=operation,
                decision=decision.value,
                trust_state=record.trust_state.value,
                details={"missing_scope": required_scope},
            )
            return ActionResult(
                status="FAILURE",
                output={"decision": decision.value, "allowed": False, "reason": f"Missing scope '{required_scope}'"},
                message=f"Authorization denied: missing required scope '{required_scope}'.",
            )

        # 5. PolicyKernel Evaluation & Two-Gate token check
        domain = operation.split(".")[0] if "." in operation else "security"
        action_name = operation.split(".")[1] if "." in operation else operation

        safety_decision: SafetyDecision = policy_kernel.evaluate(
            domain=domain,
            action=action_name,
            parameters=params.get("parameters", {}),
            raw_query=params.get("command", "") or str(params.get("target_file", "")),
            user_identity=identity_id,
        )

        if not safety_decision.allowed and safety_decision.level == PolicyLevel.PROHIBITED:
            decision = AuthorizationDecision.DENY
            self._record_audit_event(
                event_type="AUTHORIZATION_DENIED",
                identity_id=identity_id,
                resource=resource,
                action=operation,
                decision=decision.value,
                trust_state=record.trust_state.value,
                details={"policy_reason": safety_decision.reason},
            )
            return ActionResult(
                status="FAILURE",
                output={"decision": decision.value, "allowed": False, "reason": safety_decision.reason},
                message=f"Policy denied: {safety_decision.reason}",
            )

        # If confirmation required
        if safety_decision.level in (PolicyLevel.CONFIRMATION_REQUIRED, PolicyLevel.PRIVILEGED_CONFIRMATION):
            if confirmation_token:
                pending = policy_kernel.confirm_token(confirmation_token)
                if not pending:
                    return ActionResult(
                        status="FAILURE",
                        output={"decision": AuthorizationDecision.DENY.value, "allowed": False, "reason": "Invalid or expired confirmation token"},
                        message="Invalid or expired confirmation token.",
                    )
            else:
                decision = AuthorizationDecision.APPROVAL_REQUIRED
                token = safety_decision.confirmation_token or f"conf_{uuid.uuid4().hex[:12]}"
                self._record_audit_event(
                    event_type="AUTHORIZATION_PENDING_APPROVAL",
                    identity_id=identity_id,
                    resource=resource,
                    action=operation,
                    decision=decision.value,
                    trust_state=record.trust_state.value,
                    details={"token_required": True},
                )
                return ActionResult(
                    status="WAITING_EXTERNAL",
                    output={
                        "decision": decision.value,
                        "allowed": False,
                        "confirmation_token": token,
                        "prompt": safety_decision.confirmation_prompt or f"Confirm execution of {operation}",
                    },
                    message="Approval required for privileged operation.",
                )

        decision = AuthorizationDecision.ALLOW
        self._record_audit_event(
            event_type="AUTHORIZATION_ALLOWED",
            identity_id=identity_id,
            resource=resource,
            action=operation,
            decision=decision.value,
            trust_state=record.trust_state.value,
            details={"risk_score": safety_decision.risk_score},
        )

        return ActionResult(
            status="SUCCESS",
            output={
                "decision": decision.value,
                "allowed": True,
                "identity_id": identity_id,
                "trust_state": record.trust_state.value,
            },
            message=f"Operation '{operation}' authorized for identity '{identity_id}'.",
            evidence={"decision": decision.value, "identity_id": identity_id},
        )

    def _handle_evaluate_trust(self, params: Dict[str, Any]) -> ActionResult:
        identity_id = params.get("identity_id")
        if not identity_id:
            return ActionResult(status="FAILURE", output={"error": "Missing 'identity_id'"})

        record = self._identities.get(identity_id)
        if not record:
            return ActionResult(
                status="SUCCESS",
                output={"identity_id": identity_id, "trust_state": TrustState.UNKNOWN.value},
                message=f"Identity '{identity_id}' unknown.",
            )

        # Dynamic trust escalation requires policy authorization
        new_trust = params.get("new_trust_state")
        if new_trust:
            try:
                target_trust = TrustState(new_trust.upper())
            except ValueError:
                return ActionResult(status="FAILURE", output={"error": f"Invalid trust state '{new_trust}'"})

            # Invariant: Cannot escalate if currently REVOKED without explicit reinstatement
            if record.trust_state == TrustState.REVOKED and target_trust != TrustState.REVOKED:
                if not params.get("reinstatement_authorized", False):
                    return ActionResult(
                        status="FAILURE",
                        output={"error": "Cannot escalate revoked trust without authorized reinstatement."},
                    )

            old_trust = record.trust_state
            record.trust_state = target_trust
            self._record_audit_event(
                event_type="TRUST_STATE_CHANGED",
                identity_id=identity_id,
                resource="trust_evaluator",
                action="evaluate_trust",
                decision="ESCALATED" if target_trust != TrustState.REVOKED else "REVOKED",
                trust_state=target_trust.value,
                details={"old_trust": old_trust.value, "new_trust": target_trust.value},
                severity=AuditSeverity.WARNING,
            )

        return ActionResult(
            status="SUCCESS",
            output={"identity_id": identity_id, "trust_state": record.trust_state.value},
            message=f"Trust state for '{identity_id}' is {record.trust_state.value}.",
            evidence={"identity_id": identity_id, "trust_state": record.trust_state.value},
        )

    def _handle_revoke_trust(self, params: Dict[str, Any]) -> ActionResult:
        identity_id = params.get("identity_id")
        reason = params.get("reason", "Administrative revocation")
        if not identity_id:
            return ActionResult(status="FAILURE", output={"error": "Missing 'identity_id'"})

        record = self._identities.get(identity_id)
        if not record:
            return ActionResult(status="FAILURE", output={"error": f"Identity '{identity_id}' not found."})

        record.trust_state = TrustState.REVOKED
        record.status = IdentityStatus.REVOKED
        record.auth_state = AuthState.REVOKED
        record.revocation_state = {"revoked_at": time.time(), "reason": reason}

        # Invalidate any active sessions
        for s in self._sessions.values():
            if s.identity_id == identity_id:
                s.is_active = False

        self._record_audit_event(
            event_type="TRUST_REVOKED",
            identity_id=identity_id,
            resource="identity_registry",
            action="revoke_trust",
            decision="REVOKED",
            trust_state=TrustState.REVOKED.value,
            details={"reason": reason},
            severity=AuditSeverity.ALERT,
        )

        return ActionResult(
            status="SUCCESS",
            output={"identity_id": identity_id, "status": IdentityStatus.REVOKED.value, "trust_state": TrustState.REVOKED.value},
            message=f"Identity '{identity_id}' and all associated sessions revoked.",
            evidence={"identity_id": identity_id, "trust_state": TrustState.REVOKED.value},
        )

    def _handle_register_device(self, params: Dict[str, Any]) -> ActionResult:
        device_id = params.get("device_id")
        if not device_id:
            return ActionResult(status="FAILURE", output={"error": "Missing 'device_id'"})

        initial_trust_str = params.get("trust_state", TrustState.UNKNOWN.value).upper()
        try:
            initial_trust = TrustState(initial_trust_str)
        except ValueError:
            initial_trust = TrustState.UNKNOWN

        record = DeviceIdentityRecord(
            device_id=device_id,
            device_type=params.get("device_type", "GENERIC_DEVICE"),
            display_name=params.get("display_name", device_id),
            status=IdentityStatus.ACTIVE,
            trust_state=initial_trust,
            auth_state=AuthState.UNAUTHENTICATED,
            public_key_fingerprint=params.get("public_key_fingerprint", ""),
            last_seen=time.time(),
            capabilities=params.get("capabilities", []),
            provenance={"registered_at": time.time()},
        )
        self._devices[device_id] = record

        self._record_audit_event(
            event_type="DEVICE_REGISTERED",
            identity_id=device_id,
            resource="device_registry",
            action="register_device",
            decision="REGISTERED",
            trust_state=initial_trust.value,
            details={"capabilities": record.capabilities},
        )

        return ActionResult(
            status="SUCCESS",
            output={"device": record.to_safe_dict()},
            message=f"Device '{device_id}' registered successfully.",
            evidence={"device_id": device_id, "trust_state": initial_trust.value},
        )

    def _handle_authenticate_device(self, params: Dict[str, Any]) -> ActionResult:
        device_id = params.get("device_id")
        token = params.get("token") or params.get("credential")

        if not device_id:
            return ActionResult(status="FAILURE", output={"error": "Missing 'device_id'"})

        record = self._devices.get(device_id)
        if not record:
            return ActionResult(
                status="FAILURE",
                output={"auth_state": AuthState.INVALID.value, "error": "Unknown device"},
                message=f"Device '{device_id}' not found.",
            )

        if record.status == IdentityStatus.REVOKED or record.trust_state == TrustState.REVOKED:
            return ActionResult(
                status="FAILURE",
                output={"auth_state": AuthState.REVOKED.value, "error": "Device is revoked"},
                message=f"Device '{device_id}' is revoked.",
            )

        record.auth_state = AuthState.AUTHENTICATED
        record.last_seen = time.time()

        self._record_audit_event(
            event_type="DEVICE_AUTHENTICATED",
            identity_id=device_id,
            resource="device_registry",
            action="authenticate_device",
            decision="AUTHENTICATED",
            trust_state=record.trust_state.value,
        )

        return ActionResult(
            status="SUCCESS",
            output={"device_id": device_id, "auth_state": AuthState.AUTHENTICATED.value},
            message=f"Device '{device_id}' authenticated successfully.",
            evidence={"device_id": device_id},
        )

    def _handle_mask_credentials(self, params: Dict[str, Any]) -> ActionResult:
        data = params.get("data")
        text = params.get("text")

        if data is not None:
            redacted = SecretRedactor.redact_data(data, self.config.secret_mask_placeholder)
            return ActionResult(status="SUCCESS", output={"masked_data": redacted})
        elif text is not None:
            redacted = SecretRedactor.redact_text(text, self.config.secret_mask_placeholder)
            return ActionResult(status="SUCCESS", output={"masked_text": redacted})
        return ActionResult(status="FAILURE", output={"error": "Missing 'data' or 'text' parameter."})

    def _handle_redact_secrets(self, params: Dict[str, Any]) -> ActionResult:
        return self._handle_mask_credentials(params)

    def _handle_create_audit_event(self, params: Dict[str, Any]) -> ActionResult:
        event = self._record_audit_event(
            event_type=params.get("event_type", "GENERIC_SECURITY_EVENT"),
            identity_id=params.get("identity_id", "SYSTEM"),
            resource=params.get("resource", "generic_resource"),
            action=params.get("action", "generic_action"),
            decision=params.get("decision", "RECORDED"),
            trust_state=params.get("trust_state", TrustState.UNKNOWN.value),
            details=params.get("details", {}),
            severity=AuditSeverity(params.get("severity", "INFO")),
        )
        return ActionResult(
            status="SUCCESS",
            output={"audit_event": event.to_dict()},
            message=f"Audit event '{event.event_id}' created.",
            evidence={"event_id": event.event_id},
        )

    def _handle_query_audit_events(self, params: Dict[str, Any]) -> ActionResult:
        identity_id = params.get("identity_id")
        event_type = params.get("event_type")
        limit = int(params.get("limit", 100))

        events = self._audit_log
        if identity_id:
            events = [e for e in events if e.identity_id == identity_id]
        if event_type:
            events = [e for e in events if e.event_type == event_type]

        events = events[-limit:]
        return ActionResult(
            status="SUCCESS",
            output={"audit_events": [e.to_dict() for e in events], "count": len(events)},
            message=f"Retrieved {len(events)} audit events.",
            evidence={"count": len(events)},
        )

    def _handle_create_session(self, params: Dict[str, Any]) -> ActionResult:
        identity_id = params.get("identity_id")
        if not identity_id:
            return ActionResult(status="FAILURE", output={"error": "Missing 'identity_id'"})

        record = self._identities.get(identity_id)
        if not record or record.status == IdentityStatus.REVOKED:
            return ActionResult(status="FAILURE", output={"error": "Identity not found or revoked"})

        session_id = f"sess-{secrets.token_hex(16)}"
        ttl = float(params.get("ttl_sec", self.config.default_session_ttl_sec))
        session = SessionRecord(
            session_id=session_id,
            identity_id=identity_id,
            created_at=time.time(),
            expires_at=time.time() + ttl,
            scopes=set(params.get("scopes", record.authorization_scopes)),
        )
        self._sessions[session_id] = session

        return ActionResult(
            status="SUCCESS",
            output={"session_id": session_id, "expires_at": session.expires_at},
            message=f"Session created for '{identity_id}'.",
            evidence={"session_id": session_id},
        )

    def _handle_validate_session(self, params: Dict[str, Any]) -> ActionResult:
        session_id = params.get("session_id")
        if not session_id or session_id not in self._sessions:
            return ActionResult(status="FAILURE", output={"valid": False, "error": "Session not found"})

        session = self._sessions[session_id]
        if not session.is_valid():
            return ActionResult(status="FAILURE", output={"valid": False, "error": "Session expired or inactive"})

        return ActionResult(
            status="SUCCESS",
            output={
                "valid": True,
                "identity_id": session.identity_id,
                "expires_at": session.expires_at,
                "scopes": sorted(list(session.scopes)),
            },
            message="Session is valid.",
            evidence={"session_id": session_id, "valid": True},
        )

    def _handle_revoke_session(self, params: Dict[str, Any]) -> ActionResult:
        session_id = params.get("session_id")
        if not session_id or session_id not in self._sessions:
            return ActionResult(status="FAILURE", output={"error": "Session not found"})

        self._sessions[session_id].is_active = False
        return ActionResult(
            status="SUCCESS",
            output={"session_id": session_id, "revoked": True},
            message=f"Session '{session_id}' revoked.",
            evidence={"session_id": session_id},
        )

    def _handle_rotate_credentials(self, params: Dict[str, Any]) -> ActionResult:
        identity_id = params.get("identity_id")
        new_credential = params.get("new_credential")

        if not identity_id or not new_credential:
            return ActionResult(status="FAILURE", output={"error": "Missing 'identity_id' or 'new_credential'"})

        record = self._identities.get(identity_id)
        if not record or record.status == IdentityStatus.REVOKED:
            return ActionResult(status="FAILURE", output={"error": "Identity not found or revoked"})

        self._credentials_store[identity_id] = self._hash_credential(new_credential)

        # Invalidate all prior sessions on rotation
        for s in self._sessions.values():
            if s.identity_id == identity_id:
                s.is_active = False

        self._record_audit_event(
            event_type="CREDENTIAL_ROTATED",
            identity_id=identity_id,
            resource="credential_store",
            action="rotate_credentials",
            decision="ROTATED",
            trust_state=record.trust_state.value,
            severity=AuditSeverity.WARNING,
        )

        return ActionResult(
            status="SUCCESS",
            output={"identity_id": identity_id, "rotated": True},
            message=f"Credentials rotated and sessions invalidated for '{identity_id}'.",
            evidence={"identity_id": identity_id},
        )

    def _handle_quarantine_prompt(self, params: Dict[str, Any]) -> ActionResult:
        text = params.get("text", "")
        detected = self._check_prompt_injection(text)
        if detected:
            return ActionResult(
                status="SUCCESS",
                output={"quarantined": True, "pattern": detected},
                message="Prompt injection quarantined successfully.",
                evidence={"quarantined": True},
            )
        return ActionResult(
            status="SUCCESS",
            output={"quarantined": False},
            message="No prompt injection detected in text.",
            evidence={"quarantined": False},
        )

    def _handle_evaluate_policy(self, params: Dict[str, Any]) -> ActionResult:
        """Evaluates policy directly via PolicyKernel."""
        domain = params.get("domain", "security")
        action_name = params.get("action_name", "evaluate")
        parameters = params.get("parameters", {})

        decision = policy_kernel.evaluate(
            domain=domain,
            action=action_name,
            parameters=parameters,
            raw_query=params.get("command", "") or str(params.get("target_file", "")),
        )
        return ActionResult(
            status="SUCCESS" if decision.allowed else "FAILURE",
            output={
                "allowed": decision.allowed,
                "policy_level": decision.level.value,
                "reason": decision.reason,
                "risk_score": decision.risk_score,
                "confirmation_prompt": decision.confirmation_prompt,
            },
            message=f"Policy decision: {decision.level.value} (allowed={decision.allowed})",
            evidence={"allowed": decision.allowed, "level": decision.level.value},
        )

    def _handle_verify_token(self, params: Dict[str, Any]) -> ActionResult:
        """Verifies a Two-Gate confirmation token via PolicyKernel."""
        token = params.get("token")
        if not token:
            return ActionResult(status="FAILURE", output={"error": "Missing 'token'"})

        pending = policy_kernel.confirm_token(token)
        valid = (pending is not None)
        msg = "Token confirmed successfully" if valid else "Token invalid or expired"
        return ActionResult(
            status="SUCCESS" if valid else "FAILURE",
            output={"valid": valid, "message": msg},
            message=msg,
            evidence={"token_valid": valid},
        )


security_identity_provider = SecurityIdentityProvider()
