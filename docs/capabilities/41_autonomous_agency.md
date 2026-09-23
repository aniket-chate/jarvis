# Capability 41: Autonomous Agency

## 1. Capability Boundary
Capability 41 (`41_autonomous_agency`) is the controlled autonomy and agency layer of JARVIS. It enables the system to observe, detect conditions, evaluate goals, plan, act, and empirically verify outcomes without requiring a new user prompt for every step.

It adheres to the frozen architecture:
- Integrates with the existing **Event Fabric**, **World Model**, **Cognitive Core**, **Memory**, **Capability Intelligence**, **Policy Kernel**, **Execution Kernel**, **Observation & Verification**, and **Scheduler** subsystems.
- **Closed-Loop Autonomous Pipeline**:
  ```text
  EVENT -> OBSERVATION -> CONTEXT -> GOAL/CONDITION -> POLICY -> PLAN -> EXECUTION -> OBSERVATION -> VERIFICATION -> OUTCOME -> EXPERIENCE
  ```
  No open-loop unverified autonomous actions are permitted.
- **Explicit Autonomy State Machine**: Tracks goal lifecycle transitions:
  `CREATED` -> `ARMED` -> `TRIGGERED` -> `PLANNING` -> `WAITING_POLICY` -> `READY` -> `RUNNING` -> `WAITING_EXTERNAL` -> `VERIFYING` -> `COMPLETED` / `FAILED` / `PAUSED` / `CANCELLED`.
- **Strict Two-Gate Protection on High-Risk Operations**:
  Autonomous execution strictly halts and transitions to `WAITING_EXTERNAL` (returning `status="APPROVAL_REQUIRED"`) whenever an action involves unconfirmed external communication, financial transactions, destructive file operations, or irreversible changes.
- **Durable Checkpointing & Crash Recovery**:
  Checkpoints are persisted to disk (`data/checkpoints/autonomy/{goal_id}.json`) at every state boundary (`TRIGGER_ACCEPTED`, `PLAN_GENERATED`, `POLICY_CHECK`, `ACTION_STARTED`, `VERIFICATION_COMPLETED`). Resuming from process restart recovers goal state and prevents duplication.
- **Idempotency Enforcement**: Actions track `idempotency_key` to guarantee exactly-once side-effect execution across retries.
- **Retry Bounds & Bounded Autonomy**: Goals enforce maximum attempts (`max_attempts`). Repeated failures transition explicitly to `FAILED` with diagnostics.
- **Human Overrides**: Provides instantaneous human control (`pause`, `resume`, `cancel`, `get_status`).
- **Safety Boundary**: Capability 41 cannot autonomously alter system policy, security rules, or its own source code.

---

## 2. Capability Contract
- **Capability ID**: `41_autonomous_agency`
- **Domain**: `autonomy`
- **Primary Provider**: `provider.autonomy.agency_runtime` (`AutonomousAgencyProvider`)
- **Fallback Provider**: `provider.autonomy.local_watcher`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `OBSERVATION_VERIFICATION`
- **Timeout**: `30.0s`

### Supported Operations (8)
1. `autonomy.register_rule`: Registers persistent proactive rules with condition criteria, trigger types (event, scheduled, poll), and target capabilities.
2. `autonomy.evaluate_triggers`: Evaluates incoming events or conditions against active rules, firing matching goals.
3. `autonomy.execute_goal`: Runs the closed-loop autonomous execution pipeline from policy checks through observation verification.
4. `autonomy.pause_goal`: Suspends execution of an active goal.
5. `autonomy.resume_goal`: Resumes an armed/paused goal from checkpoint.
6. `autonomy.cancel_goal`: Terminates a goal permanently, preventing future actions.
7. `autonomy.get_goal_status`: Inspects goal state, attempts, checkpoints, errors, and outcomes.
8. `autonomy.recover_goals`: Scans checkpoint directory on startup to restore in-flight goals.

---

## 3. Autonomous State Machine & Checkpoints

```text
               ┌─────────────┐
               │   CREATED   │
               └──────┬──────┘
                      │
                      ▼
               ┌─────────────┐
               │    ARMED    │
               └──────┬──────┘
                      │ (Trigger Fires)
                      ▼
               ┌─────────────┐
               │  TRIGGERED  │
               └──────┬──────┘
                      │
                      ▼
               ┌─────────────┐
               │  PLANNING   │
               └──────┬──────┘
                      │
                      ▼
               ┌─────────────┐
               │WAITING_POL. │
               └──────┬──────┘
                      ├────────────────────────────────────────┐
                      │ High-Risk & Unconfirmed                │ Policy Denied
                      ▼                                        ▼
             ┌──────────────────┐                       ┌─────────────┐
             │ WAITING_EXTERNAL │                       │   FAILED    │
             └────────┬─────────┘                       └─────────────┘
                      │ (User Confirmation)
                      ▼
               ┌─────────────┐
               │    READY    │
               └──────┬──────┘
                      │
                      ▼
               ┌─────────────┐
               │   RUNNING   │
               └──────┬──────┘
                      │
                      ▼
               ┌─────────────┐
               │  VERIFYING  │
               └──────┬──────┘
                      ├────────────────────────┐
                      │ Verified               │ Verification Failed / Retries Exhausted
                      ▼                        ▼
               ┌─────────────┐          ┌─────────────┐
               │  COMPLETED  │          │   FAILED    │
               └─────────────┘          └─────────────┘
```

---

## 4. Configuration & Anti-Hardcoding
```python
@dataclass
class AutonomyConfig:
    default_autonomy_level: int = 3
    enforce_two_gate_for_high_risk: bool = True
    max_attempts: int = 3
    checkpoint_dir: str = "data/checkpoints/autonomy"
    require_verification: bool = True
```
Zero rules, user routines, goals, or targets are hardcoded in the engine. All goals are treated as provider-neutral data.

---

## 5. Verification & Test Evidence
- **Independent Suite**: `tests/test_capability_41_autonomous_agency.py` (8/8 PASS, 2.125s)
- **Universal Anti-Hardcoding**: `tests/test_no_domain_specific_hardcoding_batch_39_41.py` (9/9 PASS, 0.286s)
- **Integration Suite**: `tests/test_capabilities_39_40_41_integration.py` (6/6 PASS, 0.920s)
- **Live Server Test**: `tests/test_live_batch_39_40_41.py` (8/8 PASS, live HTTP)
