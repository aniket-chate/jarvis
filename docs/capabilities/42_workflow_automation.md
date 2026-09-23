# Capability 42 — Workflow Automation

## 1. Overview & Architecture

Capability 42 implements multi-step DAG (Directed Acyclic Graph) workflow automation for JARVIS. It provides structured, deterministic composition of existing capabilities without introducing a redundant secondary execution runtime or hardcoded orchestration logic.

Workflows are treated strictly as **data definitions**. Zero domain-specific tasks, pipelines, or entities are embedded into the engine.

```
[Workflow Request]
       │
       ▼
[Policy Kernel Safety Check]
       │  (Quarantine prompt injections / Verify authorization)
       ▼
[Workflow Automation Provider]
       ├── Topological Sorter & Graph Validator
       ├── Step Dependency Resolver
       ├── Conditional Branch Evaluator
       ├── Approval Gate Interlock (Two-Gate)
       ├── Checkpointing Store (data/checkpoints/workflows/)
       └── Compensation & Rollback Engine
       │
       ▼
[Capability Intelligence & Dispatch]
       │
       ├── File / OS / System Operations
       ├── Productivity / Calendar Actions
       ├── IoT & Device Commands
       └── Verification & Observation Engine
```

---

## 2. Contract Specification

- **Capability ID**: `42_workflow_automation`
- **Domain**: `workflow`
- **Primary Provider**: `provider.workflow.runtime_kernel`
- **Fallback Provider**: `provider.workflow.dag_engine`
- **Safety Classification**: `MODIFYING`
- **Checkpoint Required**: `True`
- **Verification Strategy**: `DISK_CHECKPOINT_VERIFICATION`
- **Timeout**: `60.0s`

### Supported Operations

| Operation | Description | Safety Level |
|---|---|---|
| `workflow.define` | Registers a reusable DAG workflow schema | `READ_ONLY` |
| `workflow.execute_dag` | Executes a DAG workflow instance | `MODIFYING` |
| `workflow.pause` | Pauses an active workflow execution | `MODIFYING` |
| `workflow.resume` | Resumes a paused execution from last checkpoint | `MODIFYING` |
| `workflow.cancel` | Terminates execution cleanly | `MODIFYING` |
| `workflow.get_status` | Retrieves status and graph progress | `READ_ONLY` |
| `workflow.persist_checkpoint` | Persists durable snapshot to disk | `MODIFYING` |
| `workflow.resume_checkpoint` | Recovers execution from disk after crash | `MODIFYING` |
| `workflow.approve_gate` | Delivers human approval token to suspended gate | `PRIVILEGED` |
| `workflow.compensate` | Triggers rollback of completed steps on fatal failure | `MODIFYING` |
| `workflow.history` | Returns execution audit ledger | `READ_ONLY` |

---

## 3. Core Engine Mechanics

### A. Topological Sorting & Dependency Graphs
Steps define explicit dependencies via `depends_on: ["step_1", "step_2"]`. The provider constructs the dependency graph, validates the absence of cycles, and calculates the topological execution waves. Independent steps can be evaluated concurrently.

### B. Dynamic Branching & Conditions
Steps can specify conditional predicates based on prior step outputs:
```json
{
  "step_id": "branch_action",
  "capability": "iot.control_device",
  "depends_on": ["sensor_read"],
  "condition": {
    "variable": "steps.sensor_read.result.temperature",
    "operator": ">",
    "value": 28.0
  }
}
```
If the condition evaluates to `False`, the step is marked `SKIPPED`, and downstream dependent steps follow configured branch-skipping rules.

### C. Checkpointing & Crash Recovery
Every workflow execution maintains a durable state file in `data/checkpoints/workflows/{execution_id}.json`. State is snapshotted at:
- `STARTED`
- `STEP_STARTED_{step_id}`
- `STEP_COMPLETED_{step_id}`
- `APPROVAL_REQUIRED_{step_id}`
- `COMPENSATED`
- `COMPLETED` / `FAILED`

If the JARVIS process restarts, calling `workflow.resume_checkpoint` restores all in-flight outputs and resumes remaining pending steps.

### D. Human Approval Gates
High-risk steps (e.g. financial, credential, or physical impact) can declare `requires_approval: True`. When reached:
1. Workflow state transitions to `WAITING_APPROVAL`.
2. A single-use cryptographically random token is generated (`gate_<uuid>`).
3. Checkpoint is written to disk.
4. Execution halts safely until the user confirms the token via `workflow.approve_gate`.

### E. Compensation & Rollback
When a step encounters an unrecoverable failure (exceeding `max_retries`), the engine executes compensation actions in reverse topological order for all previously completed steps that declared a `compensation_capability`.

### F. Prompt Injection Defense
All workflow definitions, parameters, and input variables pass through the `PolicyKernel` and prompt injection scanner. Known evasion signatures (e.g. `ignore previous instructions`, `system prompt override`) are rejected with `Security policy refusal`.

---

## 4. Verification Evidence

Capability 42 was verified against:
- Arbitrary multi-node DAG execution
- Dynamic conditional branching and selective branch skipping
- Idempotency key deduplication
- Human approval gate suspension and release
- Pause and resume lifecycle transitions
- Disk checkpoint persistence and crash recovery
- Prompt injection quarantine
- Cyclic dependency detection
