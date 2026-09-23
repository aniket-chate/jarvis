# Capability 03: World Model

**Capability ID:** `03_world_model`  
**Classification:** `EXISTING`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `cognitive`  
**Primary Provider:** `provider.cognitive.world_model`  
**Fallback Provider:** N/A (Foundational Core)  

---

## 1. Capability Purpose & Scope
Represents and continuously updates the physical ground truth state of the host computer, open applications, windows, browser tabs, files, git repositories, and operating system processes. Enforces the invariant that the system must never claim a world state merely because an action was requested.

---

## 2. Supported Operations
- `world.probe_window`: Enumerates visible desktop windows, foreground HWND, and window geometry.
- `world.probe_browser`: Queries Google Chrome CDP (port 9222) for active tab URL, title, and session state.
- `world.probe_file`: Evaluates physical file existence, size in bytes, and exact SHA-256 hash.
- `world.probe_git`: Traverses repository tree to find `.git` root, resolving active branch and HEAD commit.
- `world.probe_process`: Interrogates Win32 OS APIs for running process PID, name, and telemetry.

---

## 3. Required Context & World Model State
- Grounded in live Win32 APIs, CDP JSON-RPC, and OS filesystem syscalls.
- Operates Just-In-Time (JIT) before every cognitive planning turn.

---

## 4. Provider Implementation & Selection
- **Implementation:** `cognitive/world_model.py` (`WorldModel`).
- **Parent Directory Traversal:** Enabled recursive upward directory traversal to locate repo root at `d:\assignment\.git`.
- **Headless Fallback:** Visible window enumeration fallback handles headless and background testing contexts.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED`. Purely observational.
- **Verification Method:** Direct syscall and API return verification.
- **Invariant Enforcement:** Invariant 3 (*"No important action is considered successful without verification"*).
