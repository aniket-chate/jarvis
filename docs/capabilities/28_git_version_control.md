# Capability 28: Git & Version Control

**Capability ID:** `28_git_version_control`  
**Classification:** `EXISTING`  
**Safety Classification:** `MODIFYING`  
**Domain:** `git`  
**Primary Provider:** `provider.dev.git_code`  
**Fallback Provider:** `provider.dev.git_cli`  

---

## 1. Capability Purpose & Scope
Provides version control operations over local Git repositories: branch creation, branch switching, status checking, diff inspection, commit creation, and stash management. Verifies Git state changes by inspecting real Git repository metadata.

---

## 2. Supported Operations
- `git.branch_management`: Creates and switches temporary or feature branches.
- `git.status`: Evaluates working tree status and untracked / modified files.
- `git.diff`: Inspects unstaged or staged diff hunks.
- `git.commit`: Commits verified changes with clean semantic messages.
- `git.stash`: Stashes and pops working tree modifications.

---

## 3. Required Context & World Model State
- **Git HEAD State:** Branch name, HEAD commit hash, and root path resolved in `WorldModel.state.git_head`.

---

## 4. Provider Implementation & Selection
- **Implementation:** `capabilities/providers/developer_provider.py` (`DeveloperTaskProvider`), backed by `agents/dev_tool_agent.py`.
- **Parent Traversal:** Upward parent directory resolution finds `.git` at `d:\assignment\.git`.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED` for read/status/diff; `Level 1: MODIFYING` for branch switch.
- **Verification Strategy:** Physical execution of `git rev-parse --abbrev-ref HEAD` verifies branch switch.
