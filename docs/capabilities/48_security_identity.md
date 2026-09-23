# Capability 48: Security & Identity

## 1. Overview & Purpose
Capability 48 establishes JARVIS's unified security, identity, and trust architecture. It protects the entire JARVIS runtime, API surface, execution kernel, and memory fabrics through:
- Generic, unhardcoded identity modeling (`HUMAN`, `DEVICE`, `SERVICE`, `APPLICATION`, `CAPABILITY_PROVIDER`, `SESSION`, `EXTERNAL`).
- Pluggable authentication mechanisms (`LOCAL_CREDENTIAL`, `BEARER_TOKEN`, `SIGNED_TOKEN`, `DEVICE_KEY`, `SESSION_TOKEN`, `EXTERNAL_IDP`).
- Multi-tier authorization decisions (`ALLOW`, `DENY`, `APPROVAL_REQUIRED`, `RESTRICTED`, `REVOKED`).
- Stateful trust evaluation (`UNKNOWN`, `UNTRUSTED`, `MONITORED`, `TRUSTED`, `REVOKED`) where unknown identities are never treated as trusted.
- Device identity management with cryptographic fingerprinting, trust tracking, and revocation.
- Universal secret redaction and credential masking across all logs, telemetry, and outputs.
- Comprehensive, tamper-evident audit logging for all authentication attempts, authorization decisions, trust escalations, and security-sensitive actions.
- Defensive quarantining against prompt injection attempts aimed at exfiltrating credentials or bypassing security policies.

---

## 2. Architecture & Flow
```
Client / Agent / Subsystem Request
        ↓
Identity / Credential Ingestion
        ↓
Authentication Provider (Pluggable Auth Mechanisms)
        ↓
Identity Context Construction
        ↓
Stateful Trust Evaluation (Unknown / Untrusted / Monitored / Trusted / Revoked)
        ↓
Authorization Evaluation (Scope & Role Checking)
        ↓
PolicyKernel (Two-Gate Safety & Confirmation)
        ↓
Capability Intelligence & Execution
        ↓
Secret Redactor (Dynamic Masking of Secrets & Tokens)
        ↓
Structured Audit Event Generation
        ↓
Observation & Verification Feedback Loop
```

---

## 3. Generic Data Schemas & Abstractions

### 3.1 Identity & Device Records
- **`GenericIdentity`**:
  - `identity_id`: Arbitrary unique string identifier.
  - `identity_type`: `IdentityType` enum (`HUMAN`, `DEVICE`, `SERVICE`, `APPLICATION`, `CAPABILITY_PROVIDER`, `SESSION`, `EXTERNAL`).
  - `display_name`: Human-readable label.
  - `status`: `IdentityStatus` enum (`ACTIVE`, `SUSPENDED`, `REVOKED`, `EXPIRED`).
  - `trust_state`: `TrustState` enum (`UNKNOWN`, `UNTRUSTED`, `MONITORED`, `TRUSTED`, `REVOKED`).
  - `authentication_state`: `AuthenticationState` enum (`UNAUTHENTICATED`, `AUTHENTICATED`, `EXPIRED`, `REVOKED`, `INVALID`, `REQUIRES_REAUTHENTICATION`).
  - `authorization_scopes`: Set of allowed action/resource scopes.
  - `roles`: Assigned RBAC roles.
  - `metadata`: Arbitrary generic attributes (secrets are strictly excluded).
  - `provenance`: Origin/issuer metadata.
- **`GenericDeviceIdentity`**:
  - `device_id`: Arbitrary unique device identifier.
  - `device_name`: Human-readable name.
  - `hardware_fingerprint`: Cryptographic/hash fingerprint.
  - `status`: `IdentityStatus`.
  - `trust_state`: `TrustState`.
  - `ip_address`: Last-seen IP.
  - `zone`: Deployment zone.
  - `last_seen`: Timestamp of most recent telemetry/heartbeat.
  - `metadata`: Arbitrary hardware/software attributes.

### 3.2 Authorization & Trust
- **`AuthorizationDecision`**:
  - `decision`: `ALLOW`, `DENY`, `APPROVAL_REQUIRED`, `RESTRICTED`, `REVOKED`.
  - `allowed`: Boolean convenience flag.
  - `identity_id`: Evaluated subject.
  - `operation`: Requested action.
  - `resource`: Target resource.
  - `reason`: Structured explanation.
  - `trust_state`: Subject's trust level at decision time.
  - `confirmation_token`: Optional two-gate confirmation token if approval is required.

### 3.3 Secret Redaction & Audit
- **`SecretRedactor`**: Configurable regular expression patterns detecting JWTs, API keys, passwords, bearer tokens, private keys, and authorization headers, substituting them with configurable mask indicators (e.g., `***REDACTED***`).
- **`SecurityAuditEvent`**: Structured log record with `event_id`, `timestamp`, `event_type`, `identity_id`, `actor`, `operation`, `resource`, `decision`, `trust_state`, and sanitized `details`.

---

## 4. Supported Operations & Capability Contracts

| Capability Operation | Description | Safety Level |
| :--- | :--- | :--- |
| `security.register_identity` | Registers generic identity and initializes trust state | Read/Write |
| `security.authenticate` | Authenticates credentials via registered pluggable mechanism | Authenticated |
| `security.authorize` | Evaluates who, what, on what resource, under which trust | Authorization Gate |
| `security.escalate_trust` | Explicit policy-gated promotion of subject trust | Privileged |
| `security.revoke_identity` | Immediately revokes identity and voids active authorizations | Privileged |
| `security.register_device` | Registers a generic hardware/compute device | Read/Write |
| `security.mask_credentials` | Recursively sanitizes data structures to mask secrets | Safe |
| `security.query_audit_events`| Queries security audit log by identity, type, or timerange | Read-Only |

---

## 5. Universal Anti-Hardcoding Invariant
Capability 48 contains **zero domain-specific hardcoding**:
- No hardcoded usernames, system admins, passwords, or API keys.
- No fixture-based security shortcuts or bypasses.
- All authentications, trust states, and authorizations dynamically evaluate incoming metadata against registered policies.
- Full AST and dynamic test suite verification (`tests/test_no_domain_specific_hardcoding_batch_48_50.py`).
