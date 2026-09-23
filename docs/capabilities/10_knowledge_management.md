# Capability 10: Knowledge Management

**Capability ID:** `10_knowledge_management`  
**Classification:** `EXISTING_WRAPPED`  
**Safety Classification:** `READ_ONLY` (Queries & Audits) / `MODIFYING` (Ingest & Deletion within data/knowledge_base/)  
**Domain:** `knowledge`  
**Primary Provider:** `provider.knowledge.rag_store`  
**Fallback Provider:** `provider.file.scoped`  

---

## 1. Capability Purpose & Scope

Capability 10 manages JARVIS's personal, structured, and unstructured long-term knowledge repository. Unlike conversational memory (which stores transient interaction turns and personal preferences in `memory/user_profile.json`), Knowledge Management stores standalone documents, engineering specifications, research notes, and personal reference knowledge.

The capability enforces dense semantic vector search, deduplication via SHA-256 content hashing, versioned updates, empirical existence verification, and strict data containment against prompt injections.

---

## 2. Supported Operations

| Operation | Description | Inputs | Expected Output | Safety / Verification |
| :--- | :--- | :--- | :--- | :--- |
| `knowledge.ingest` | Ingests, validates, hashes, versions, and indexes personal notes/documents | `title`, `content`, `tags`, `source`, `namespace`, `force_overwrite` | `note_id`, `version`, `deduplicated`, `provenance` | Empirically verified via physical JSON file and index entry presence |
| `knowledge.index` | Re-indexes disk documents and synchronizes the local SQLite dense vector store | `force: bool` | `indexed_count`, `cleaned_count`, `total_in_index` | Confirms vector index integrity |
| `knowledge.query` | Dense semantic retrieval with truthful match status and data isolation | `query: str`, `top_k: int`, `namespace: Optional[str]`, `max_age_days: float` | `results: List[Dict]`, `count`, `has_grounded_match` | Evaluates cosine similarity; distinguishes `found`, `uncertain`, `not_found`, and `stale` |
| `knowledge.audit_freshness` | Audits age, staleness, and physical file existence of indexed knowledge | `max_age_days: float`, `namespace: Optional[str]` | `total_notes`, `fresh_count`, `stale_count`, `missing_files_count` | Flags notes older than threshold and any missing physical files |
| `knowledge.delete` | Deletes note from index, physical disk, and vector store | `note_id: str` | `deleted: bool`, `verified: bool` | Empirically verified that file and index entry are absent |

---

## 3. Provider Architecture

```
Cognitive Core (Kernel)
         ↓
Capability Intelligence (Registry & Discovery)
         ↓
Capability 10 (Knowledge Management Contract)
         ↓
KnowledgeProvider (provider.knowledge.rag_store)
         ↓
PersonalKnowledgeBase & LocalVectorStore
         ↓
Physical Storage (data/knowledge_base/*.json & vector_index.db)
```

The Cognitive Core never directly touches SQLite or JSON files. Provider selection is resolved dynamically through `capability_intelligence.select_provider("knowledge.query")`. Alternate providers (e.g. cloud embeddings, Qdrant, Milvus) can be swapped at runtime with zero changes to Cognitive Core logic.

---

## 4. Truthful Retrieval States

Knowledge retrieval explicitly avoids fabricating answers or hallucinating non-existent knowledge:

- **`found` (Score $\ge 0.35$):** High-confidence semantic or lexical match. Grounded answer provided.
- **`uncertain` ($0.20 \le \text{Score} < 0.35$):** Low-confidence semantic match. Clarification or caution flagged.
- **`not_found` (Score $< 0.20$):** Zero hallucination. Grounded message stating no records were found.
- **`stale` (Age $>$ `max_age_days`):** Record retrieved but flagged as potentially outdated for user awareness.

---

## 5. Security & Untrusted Data Invariant

Retrieved knowledge is strictly treated as **INERT DATA**, never as executable instructions:

1. **Quarantine Envelope:** Raw document content is wrapped in `<UNTRUSTED_KNOWLEDGE_DATA doc_id="...">` blocks.
2. **Policy Gate Guard:** Prompt injections inside documents (e.g. `cmd /c whoami`, `format c:`, system overrides) are blocked by `PolicyKernel` and refused if execution is attempted.
3. **Privilege Isolation:** Documents cannot alter JARVIS system persona, override safety policies, or trigger arbitrary code execution.

---

## 6. Empirical Verification

Every knowledge operation participates in the Observation & Verification loop:

- **Ingest Verification:** Verifies physical JSON note file exists on disk and note ID exists in `index.json`.
- **Delete Verification:** Verifies physical file is deleted and note ID is removed from index and vector database.
- **Freshness Verification:** Audits physical file existence for every index entry, detecting orphaned or corrupted records.

---

## 7. Concurrency & Durability

- Thread-safe access via SQLite connection timeouts and serialized index file updates.
- Tested and verified under simultaneous multi-threaded reads and writes without database deadlocks.
- Crash recovery: vector index and index.json can be completely rebuilt from on-disk JSON files via `knowledge.index`.

---

## 8. Final Operational Verification Classifications

| Major Operation | Verification Classification | Implementation & Runtime Reality |
| :--- | :--- | :--- |
| `ingest` | **VERIFIED END-TO-END** | Full request -> intent -> plan -> provider -> physical disk `.json` persistence -> empirical verifier -> episodic memory ledger. |
| `index` | **VERIFIED END-TO-END** | Rebuilds & synchronizes dense SQLite vector store from disk JSON notes with dangling document cleanup. |
| `query` | **VERIFIED END-TO-END** | Dense cosine vector retrieval via Cognitive Core; truthful status (`found`, `uncertain`, `not_found`); grounded verification. |
| `freshness` | **VERIFIED END-TO-END** | Computes age in days, staleness against threshold, and identifies missing on-disk physical files. |
| `update` | **VERIFIED END-TO-END** | In-place version incrementing (v1 -> v2) with SHA-256 hash recalculation and verified re-query of updated values. |
| `deletion` | **VERIFIED END-TO-END** | Verified physical unlinking on disk, index purge, vector database deletion, and confirmed exclusion from subsequent queries. |
| `deduplication` | **VERIFIED END-TO-END** | Deterministic SHA-256 content hashing prevents duplicate entries in identical namespace; reuses existing note ID. |
| `contextual retrieval` | **VERIFIED END-TO-END** | Disambiguates pronouns and conversational references using WorldModel snapshot without hallucinations. |
| `provider replacement` | **VERIFIED END-TO-END** | Dynamic runtime swapping via Capability Intelligence with priority routing and zero Cognitive Core code modification. |
| `security/injection handling` | **VERIFIED END-TO-END** | Untrusted data isolation via `<UNTRUSTED_KNOWLEDGE_DATA>` containment; PolicyKernel prohibits shell command execution attempts. |
| `concurrency/recovery` | **VERIFIED END-TO-END** | Multi-threaded simultaneous ingestion and concurrent query during re-indexing without locks; complete state reload from disk. |
