# Capability 43 — Monitoring & Alerts

## 1. Overview & Architecture

Capability 43 provides event-driven and scheduled metric monitoring, anomaly detection, alert deduplication, cooldown suppression, incident lifecycle tracking, and policy-governed automated remediation for JARVIS.

It operates without uncontrolled polling loops, integrating directly with the Event Fabric (`UniversalEvent`) and Cognitive Core.

```
[Incoming Metric Stream / Event]
              │
              ▼
[Monitoring & Alerts Provider]
       ├── Heartbeat & Stale Detector
       ├── Dynamic Condition Evaluator (>, <, ==, !=, in, range)
       ├── Consecutive Breach Filter (False-Positive Dampener)
       ├── Fingerprint-Based Deduplication (SHA-256)
       ├── Cooldown Period Suppressor
       ├── Incident Lifecycle (ACTIVE -> ACKNOWLEDGED -> RESOLVED)
       ├── Time-Based Escalator (INFO -> WARNING -> ERROR -> CRITICAL)
       └── Policy-Gated Remediation Action Dispatcher
              │
              ▼
[Event Fabric / User Notification Channels]
```

---

## 2. Contract Specification

- **Capability ID**: `43_monitoring_alerts`
- **Domain**: `monitor`
- **Primary Provider**: `provider.monitor.event_alerts`
- **Fallback Provider**: `provider.monitor.threshold_poll`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `ALERT_EVENT_LOG_VERIFICATION`
- **Timeout**: `10.0s`

### Supported Operations

| Operation | Description | Safety Level |
|---|---|---|
| `monitor.watch_condition` | Registers a dynamic condition monitoring rule | `READ_ONLY` |
| `monitor.create_rule` | Alias for registering a monitoring rule | `READ_ONLY` |
| `monitor.evaluate_metrics` | Evaluates telemetry batch against active rules | `READ_ONLY` |
| `monitor.emit_alert` | Emits a structured alert with deduplication | `READ_ONLY` |
| `monitor.deduplicate` | Checks whether an alert fingerprint is currently active | `READ_ONLY` |
| `monitor.acknowledge_alert`| Marks an alert acknowledged by an operator | `READ_ONLY` |
| `monitor.resolve_alert` | Manually resolves an active alert | `READ_ONLY` |
| `monitor.get_alerts` | Queries active and historical alert records | `READ_ONLY` |
| `monitor.pause` | Pauses rule evaluation | `READ_ONLY` |
| `monitor.resume` | Resumes rule evaluation | `READ_ONLY` |
| `monitor.detect_stale` | Detects targets that have missed reporting deadlines | `READ_ONLY` |
| `monitor.escalate_alert` | Elevates severity on unacknowledged incidents | `READ_ONLY` |

---

## 3. Core Engine Mechanics

### A. Dynamic Condition Evaluation
Rules evaluate arbitrary targets and metrics using generic comparison operators:
- Numerical: `>`, `<`, `>=`, `<=`, `==`, `!=`
- Set/Collection: `in`
- Range: `range` (min, max bounds)
- Substring: `contains`

### B. Fingerprint-Based Deduplication & Cooldown
Every alert computes a canonical SHA-256 fingerprint:
```python
fingerprint = sha256(f"{rule_id}:{target}:{metric}".encode()).hexdigest()[:16]
```
If an alert with an identical fingerprint is already `ACTIVE` or within its `cooldown_sec` window, recurring emissions are suppressed, preventing notification floods.

### C. Auto-Resolution
When an incoming metric stream returns within normal bounds (the breach condition evaluates to `False`), the provider automatically resolves the associated active alert, recording `Auto-resolved: metric normalized` and releasing the fingerprint lock.

### D. Incident Escalation
If an active alert remains unacknowledged past its `escalation_timeout_sec`, calling `monitor.escalate_alert` increments its severity level:
$$\text{INFO} \longrightarrow \text{WARNING} \longrightarrow \text{ERROR} \longrightarrow \text{CRITICAL}$$
and dispatches high-priority notification events.

### E. Stale Source Detection
Targets reporting metrics update internal heartbeat timestamps. The provider periodically inspects target ages. If $\Delta t > \text{stale\_threshold\_sec}$, a `STALE_TARGET` alert is emitted.

### F. Policy-Governed Remediation
When a monitoring rule defines an `action_capability` to trigger upon an alert, the provider consults `PolicyKernel` before executing the action. Modifying or high-risk actions are blocked unless explicitly authorized.

---

## 4. Verification Evidence

Capability 43 was verified against:
- Normal metrics producing zero false alerts
- Threshold breach and subsequent auto-resolution upon metric normalization
- Repeated event deduplication and cooldown window suppression
- Operator acknowledgement and manual resolution
- Unacknowledged alert escalation to higher severity
- Stale target detection via artificial heartbeat lag
- Rule pause and resume lifecycle
- Novel synthesized metric names and arbitrary targets
- Prompt injection resistance in rule definitions
- Provider hot-swapping via `CapabilityIntelligence`
