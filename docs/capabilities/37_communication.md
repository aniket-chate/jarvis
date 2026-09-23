# Capability 37: Communication

## 1. Capability Boundary
Capability 37 (`37_communication`) provides unified, safe, multi-channel messaging (Email, SMS, WhatsApp, and Local/Mesh User Notifications) with a mandatory draft-first safety boundary, dynamic contact lookup and disambiguation, Two-Gate authorization for external transmission, factual delivery verification, and untrusted message content quarantine.

It adheres to the frozen architecture:
- **Draft ≠ Send Boundary**: Creating a message (`comm.draft_email`, `comm.draft_message`) NEVER triggers external network transmission. Drafts exist exclusively as staged, reviewable records.
- **Two-Gate Transmission Gate**: Dispatch operations (`comm.send_email`, `comm.send_message`, `comm.send_whatsapp`) require explicit Two-Gate confirmation (`is_confirmed=True`). Unconfirmed dispatches halt with `STATUS_APPROVAL_REQUIRED` and generate a staged authorization ticket.
- **Dynamic Contact Disambiguation**: Contacts are queried dynamically by name, email, or handle. Ambiguous queries with multiple matches return candidate choices rather than guessing or picking arbitrarily.
- **Untrusted Data Isolation**: Inbound and outbound message contents are encapsulated within `<UNTRUSTED_COMMUNICATION_DATA>` fences to prevent indirect prompt injection. Communication data remains untrusted data unless explicitly parsed through the formal user command boundary.

---

## 2. Capability Contract
- **Capability ID**: `37_communication`
- **Domain**: `comm`
- **Primary Provider**: `provider.comm.communication_hub` (`CommunicationHubProvider`)
- **Fallback Provider**: `provider.comm.smtp_fallback`
- **Safety Classification**: `REQUIRES_APPROVAL` / `EXTERNAL_DISPATCH`
- **Verification Strategy**: `EXTERNAL_RECEIPT_VERIFICATION`
- **Timeout**: `30.0s`

### Supported Operations (10)
1. `comm.lookup_contact`: Queries contacts dynamically by name, email, or phone. Returns candidate list or disambiguation choices when multiple matches occur.
2. `comm.register_contact`: Dynamically registers or updates a contact record into runtime memory.
3. `comm.draft_email`: Creates a draft email message, assigns a draft ID, and stores it in the draft queue without external transmission.
4. `comm.send_email`: Dispatches an email message. Requires explicit Two-Gate confirmation (`is_confirmed=True`); rejects unauthorized transmission.
5. `comm.draft_message`: Creates a draft SMS or instant message without transmission.
6. `comm.send_message`: Dispatches an SMS/instant message. Requires explicit Two-Gate confirmation.
7. `comm.send_whatsapp`: Dispatches a WhatsApp message. Requires explicit Two-Gate confirmation.
8. `comm.notify_user`: Dispatches a real-time notification to the user, either locally or routed to a specific mesh device ID.
9. `comm.get_history`: Retrieves conversation history for a given contact or channel.
10. `comm.verify_delivery`: Checks the factual delivery status of a sent message or email using receipt tracking.

---

## 3. Communication Safety Review Matrix

| Condition | Safety Behavior | Implementation Guarantee |
| :--- | :--- | :--- |
| **Draft Request** | Draft created and stored with unique ID | `draft_first=True`; zero network packets emitted |
| **Unconfirmed Send** | Dispatch blocked | Returns `STATUS_APPROVAL_REQUIRED` with pending ticket |
| **Approved Send** | Dispatch allowed | Executes only when `is_confirmed=True` |
| **Ambiguous Recipient** | Clarification requested | Returns `requires_disambiguation=True` with candidate list |
| **Provider Failure** | Truthful error reported | Returns `status="FAILED"` with diagnostic message |
| **Delivery Verification**| Factual status queried | Returns receipt verification (`DELIVERED`, `PENDING`, `UNKNOWN`) |
| **Prompt Injection** | Strict data quarantine | Encapsulated in `<UNTRUSTED_COMMUNICATION_DATA>` boundary |

---

## 4. Configuration & Anti-Hardcoding
Runtime behavior is driven entirely by `CommunicationConfig`:
```python
@dataclass
class CommunicationConfig:
    draft_first: bool = True
    require_confirmation_for_external: bool = True
    max_history_items: int = 50
    rate_limit_per_minute: int = 20
    quarantine_untrusted: bool = True
    default_channel: str = "email"
```
Zero contact names, email addresses, phone numbers, or domain names are hardcoded in provider logic. All entities are resolved dynamically from configured registries.

---

## 5. Security & Privacy
- **Draft-First Safety Boundary**: Operations creating external messages (`draft_email`, `draft_message`) only generate draft artifacts and never emit network dispatches.
- **Two-Gate Authorization**: Calls to `send_email`, `send_message`, and `send_whatsapp` check `is_confirmed=True`. If unconfirmed, the provider halts with `STATUS_APPROVAL_REQUIRED` and returns a pending authorization ticket.
- **Prompt Injection Quarantine**: External message contents (incoming messages, subject lines, bodies) are wrapped in `<UNTRUSTED_COMMUNICATION_DATA>` fences to prevent LLM execution of embedded instructions.
- **Factual Verification**: The `comm.verify_delivery` operation inspects physical dispatch receipts and delivery status rather than assuming success.

---

## 6. Verification & Tests
- **Independent Suite**: `tests/test_capability_37_communication.py` (7/7 PASS)
  - `test_dynamic_contact_lookup_and_disambiguation`
  - `test_draft_first_safety_boundary`
  - `test_two_gate_authorization_enforcement`
  - `test_multi_channel_dispatch`
  - `test_user_notification_routing`
  - `test_prompt_injection_quarantine`
  - `test_delivery_verification`
- **Anti-Hardcoding Suite**: `tests/test_no_domain_specific_hardcoding_batch_36_38.py` (13/13 PASS)
  - Tests C (Unknown Contact), E (Source Removal), F (Config Change), G (Provider Replacement), and H (Unknown Entity).
- **Live Server Integration**: `tests/test_live_batch_36_37_38.py` (LIVE 3, LIVE 4, LIVE 5 PASS)
