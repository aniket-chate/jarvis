# Capability 25: Shell & System Administration

**Capability ID:** `25_shell_sysadmin`  
**Classification:** `EXISTING`  
**Safety Classification:** `PRIVILEGED`  
**Domain:** `shell`  
**Primary Provider:** `provider.dev.allowlisted_cli`  
**Fallback Provider:** N/A (Strict Security Policy)  

---

## 1. Capability Purpose & Scope
Provides controlled, strictly allowlisted system diagnostic command execution (e.g. `netstat -ano`, service status checks, environment inspection) while unconditionally prohibiting arbitrary shell commands (`whoami`, `ipconfig`, `rmdir /s /q`, raw `powershell.exe`).

---

## 2. Supported Operations
- `shell.allowlisted_diagnostics`: Executes allowlisted diagnostic inspection commands.
- `shell.network_status`: Checks port bindings and network interface states.
- `shell.service_status`: Inspects active system daemon statuses.

---

## 3. Required Context & World Model State
- **Security Policy Context:** Must pass `policy_kernel.evaluate()` checks with strict allowlist matching.

---

## 4. Provider Implementation & Selection
- **Implementation:** `capabilities/providers/developer_provider.py` and `safety/policy_kernel.py`.
- **Zero-Arbitrary-Shell Invariant:** Any request containing unverified shell execution triggers immediate `PolicyLevel.PROHIBITED`.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 3: PROHIBITED` for arbitrary commands; `Level 2: PRIVILEGED` for safe diagnostics.
- **Verification Strategy:** Returncode analysis and stderr inspection within isolated subprocess environments.
