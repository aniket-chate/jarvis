# Capability 06: Memory System

**Capability ID:** `06_memory_system`  
**Classification:** `EXISTING`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `memory`  
**Primary Provider:** `provider.memory.sqlite_vector`  
**Fallback Provider:** `provider.memory.in_memory`  

---

## 1. Capability Purpose & Scope
Orchestrates the 7-tier memory architecture (Working, Episodic, Semantic, Procedural, User, World, and Experience Memory). Enforces truthful recall via an immutable append-only Episodic Action Ledger that records physical tool executions and outcomes.

---

## 2. Supported Operations
- `memory.record_episodic`: Appends an immutable event record with strict lifecycle status (`REQUESTED`, `EXECUTED`, `VERIFIED`, `FAILED`, `CANCELLED`, `BLOCKED`).
- `memory.query_episodic`: Recalls truthful historical actions taken during the session.
- `memory.recall_semantic`: Performs cosine similarity retrieval over semantic vector stores.
- `memory.update_profile`: Persists owner facts and preferences to `memory/user_profile.json`.

---

## 3. Required Context & World Model State
- **Request Envelope:** `request_id`, `session_id`, `timestamp`.
- **Verified Action Result:** Status and evidence emitted by the `ObservationVerificationKernel`.

---

## 4. Provider Implementation & Selection
- **Implementation:** `memory/system.py` (`MemorySystem`) and `memory/episodic_ledger.py` (`EpisodicLedger`).
- **Storage:** Local JSON and SQLite persistence in `d:\assignment\JARVIS\memory\`.
- **Truthfulness Guarantee:** Verified by Audit Suite 7. An action must be marked `VERIFIED` by observation before being cited as a completed historical fact.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED`.
- **Invariant Enforcement:** Invariant 5 (*"Memory cannot convert unverified intentions into verified facts"*).
