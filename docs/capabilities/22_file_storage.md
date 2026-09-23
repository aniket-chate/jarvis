# Capability 22: File & Storage Intelligence

**Capability ID:** `22_file_storage`  
**Classification:** `EXISTING`  
**Safety Classification:** `DESTRUCTIVE`  
**Domain:** `file`  
**Primary Provider:** `provider.file.scoped`  
**Fallback Provider:** `provider.file.python_shutil`  

---

## 1. Capability Purpose & Scope
Provides safe, scoped filesystem manipulation (creation, atomic moves, renaming, read, search, deletion, archive inspection, and SHA-256 hashing) constrained strictly to the allowed project and user workspace boundaries.

---

## 2. Supported Operations
- `file.read`: Reads text and binary content from authorized paths.
- `file.create`: Writes content to new files within workspace boundaries.
- `file.search`: Performs recursive file discovery matching globs or content keywords.
- `file.move`: Atomically relocates files, verifying source absence and destination presence.
- `file.rename`: Renames existing files with path collision checks.
- `file.delete`: Deletes designated files or folders under Two-Gate confirmation.
- `file.compress` & `file.extract`: Creates and unpacks zip archives.

---

## 3. Required Context & World Model State
- **Workspace Root:** Confined to `d:\assignment\JARVIS\workspace` and project root.
- **Active File Referent:** Pinned in `WorldModel.state.last_file_path`.

---

## 4. Provider Implementation & Selection
- **Implementation:** `capabilities/providers/file_provider.py` (`FileDocumentProvider`), backed by `agents/file_document_agent.py`.
- **Path Traversal Protection:** All paths are sanitized against directory traversal attacks (`..`).

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:**
  - Read/Search: `Level 0: ALLOWED`.
  - Create/Move: `Level 1: LOW_RISK`.
  - Delete/Purge: `Level 2: DESTRUCTIVE` (requires explicit cryptographic Two-Gate confirmation token).
- **Verification Strategy:** Physical `Path.exists()`, byte length, and SHA-256 content hash check.
