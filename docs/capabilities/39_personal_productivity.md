# Capability 39: Personal Productivity

## 1. Capability Boundary
Capability 39 (`39_personal_productivity`) provides generalized, provider-neutral personal productivity intelligence across tasks, to-do items, priorities, focus sessions, deadlines, dependencies, notes, and workflow states.

It adheres to the frozen architecture:
- Operates through the existing **World Model**, **Memory**, **Calendar & Scheduling**, **Execution Kernel**, **Policy Kernel**, and **Observation/Verification** subsystems.
- **Provider-Neutral Data Model**: Uses `ProductivityItem` with explicit fields (`id`, `type`, `title`, `description`, `status`, `priority`, `created_at`, `updated_at`, `due_at`, `timezone`, `dependencies`, `parent_id`, `tags`, `context`, `source`, `metadata`).
- **Explicit Lifecycle State Model**: Explicit state machine transitions (`CREATED`, `READY`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`, `CANCELLED`, `ARCHIVED`).
- **Strict Dependency Evaluation**:
  - If Task B depends on Task A, Task B is set to `BLOCKED` while Task A is incomplete.
  - Completing Task A evaluates dependency satisfaction across all stored items and automatically cascade-unblocks Task B to `READY`.
  - Blocked work is never executed silently.
- **Temporal & Scheduling Separation**: Tasks, calendar events, reminders, and scheduled executions remain strictly distinct entities. Creating a deadline task optionally creates a linked distinct calendar event or scheduler reminder without duplicating calendar infrastructure.
- **Controlled Autonomy Boundary**: Capability 39 exposes productivity condition signals to Capability 41 (e.g. deadline proximity, unblocked dependencies) but does NOT act as an autonomous agent itself.

---

## 2. Capability Contract
- **Capability ID**: `39_personal_productivity`
- **Domain**: `productivity`
- **Primary Provider**: `provider.productivity.local_task` (`PersonalProductivityProvider`)
- **Fallback Provider**: `provider.productivity.file_store`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `EVENT_STATE_QUERY`
- **Timeout**: `10.0s`

### Supported Operations (13)
1. `productivity.create_task` / `productivity.add_task`: Creates a productivity task with arbitrary data attributes, dependencies, priority, tags, and optional calendar/scheduler links.
2. `productivity.get_tasks` / `productivity.list_tasks`: Retrieves stored tasks with filtering by status, priority, or tag.
3. `productivity.update_task`: Mutates fields (title, description, priority, due date, status) with state validation.
4. `productivity.complete_task`: Transitions task to `COMPLETED`, records episodic experience where permitted, and cascades unblocking to downstream dependents.
5. `productivity.cancel_task`: Explicitly cancels a task, preserving state history.
6. `productivity.delete_task`: Permanently removes an item from storage.
7. `productivity.check_dependencies`: Audits the dependency graph for a task or all tasks, identifying missing prerequisites.
8. `productivity.start_focus_session`: Initiates a timed focus interval linked to an active task.
9. `productivity.create_note`: Attaches structured notes/scratchpads to tasks or general context.
10. `productivity.get_notes`: Retrieves notes filtered by task ID or query tag.
11. `productivity.triage_notifications`: Evaluates deadline proximity and priority scores to surface urgent action items.

---

## 3. Data Model & Lifecycle

### Task State Machine
```text
      ┌────────────┐
      │  CREATED   │
      └─────┬──────┘
            │
            ▼ (Evaluate Dependencies)
     ┌──────────────┐      Unsatisfied
     │ Dependencies ├──────────────────────┐
     │  Satisfied?  │                      │
     └──────┬───────┘                      ▼
            │ Yes                    ┌───────────┐
            ▼                        │  BLOCKED  │
       ┌─────────┐                   └─────┬─────┘
       │  READY  │                         │ Prerequisite Completed
       └────┬────┘                         ▼ (Cascade Unblock)
            │                        ┌───────────┐
            ├───────────────────────►│   READY   │
            ▼                        └─────┬─────┘
     ┌─────────────┐                       │
     │ IN_PROGRESS │◄──────────────────────┘
     └──────┬──────┘
            │
      ┌─────┴──────────────────┐
      ▼                        ▼
┌───────────┐            ┌───────────┐
│ COMPLETED │            │ CANCELLED │
└─────┬─────┘            └─────┬─────┘
      ▼                        ▼
┌────────────────────────────────────┐
│              ARCHIVED              │
└────────────────────────────────────┘
```

---

## 4. Configuration & Anti-Hardcoding
All runtime behavior is governed by `ProductivityConfig`:
```python
@dataclass
class ProductivityConfig:
    default_priority: str = "medium"
    auto_schedule_reminders: bool = False
    max_tasks: int = 1000
    focus_session_default_minutes: int = 25
```
Zero project names, task titles, people, companies, or user deadlines are hardcoded. Tests generate dynamic UUID identifiers and verify general contract execution.

---

## 5. Security & Privacy
- **Memory Boundary**: Sensitive productivity details are not dumped indiscriminately into long-term memory. Only completion summaries are recorded in episodic memory via `EpisodicLedger`.
- **Thread Safety**: All state alterations are protected by reentrant threading locks (`threading.RLock`).

---

## 6. Verification & Test Evidence
- **Independent Suite**: `tests/test_capability_39_personal_productivity.py` (8/8 PASS, 0.003s)
- **Universal Anti-Hardcoding**: `tests/test_no_domain_specific_hardcoding_batch_39_41.py` (9/9 PASS, 0.286s)
- **Integration Suite**: `tests/test_capabilities_39_40_41_integration.py` (6/6 PASS, 0.920s)
- **Live Server Test**: `tests/test_live_batch_39_40_41.py` (8/8 PASS, live HTTP)
