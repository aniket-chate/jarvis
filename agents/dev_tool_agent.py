"""Narrow Dev Support Agent for JARVIS Layer 3 (Group 3).

Provides strictly allowlisted developer utilities:
1. Git operations: status, diff, commit, branch list, branch switch
   (executed via targeted subprocess calls to `git` specifically, NEVER an open shell).
2. Pure text & data utilities: Regex generation, JSON formatting/validation.
3. Refusal Gate: Explicitly rejects general shell/terminal/bash/powershell execution
   to preserve system security invariants.
"""

import re
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.settings import PROJECT_ROOT

logger = logging.getLogger("JARVIS.DevToolAgent")


class DevToolAgent:
    """Safely handles allowlisted developer tasks without exposing a general shell."""

    def __init__(self, repo_root: Path = PROJECT_ROOT):
        self.repo_root = repo_root.resolve()

    # --- Allowlisted Git Operations (Group 3) ---
    def _run_git_command(self, args: List[str]) -> Dict[str, Any]:
        """Runs targeted git executable directly without a shell interpreter."""
        # Enforce allowlist of safe git subcommands
        allowed_subcommands = {"status", "diff", "branch", "checkout", "switch", "log", "commit"}
        if not args or args[0] not in allowed_subcommands:
            return {"success": False, "error": f"Git subcommand '{args[0] if args else ''}' is not permitted."}

        full_cmd = ["git"] + args
        try:
            res = subprocess.run(
                full_cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                shell=False,  # CRITICAL SAFETY INVARIANT: No shell execution
                timeout=15
            )
            return {
                "success": res.returncode == 0,
                "action": f"git_{args[0]}",
                "output": res.stdout.strip() if res.returncode == 0 else res.stderr.strip(),
                "returncode": res.returncode,
                "response": res.stdout.strip() if res.returncode == 0 else f"Git error: {res.stderr.strip()}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def git_status(self) -> Dict[str, Any]:
        """Queries repository working tree status."""
        return self._run_git_command(["status", "--short"])

    def git_diff(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        """Inspects current repository unstaged or staged diffs."""
        args = ["diff"]
        if file_path:
            args.extend(["--", file_path])
        return self._run_git_command(args)

    def git_branch(self) -> Dict[str, Any]:
        """Lists repository branches."""
        return self._run_git_command(["branch", "-a"])

    def git_switch_branch(self, branch_name: str) -> Dict[str, Any]:
        """Switches to an existing branch."""
        clean_branch = branch_name.strip()
        return self._run_git_command(["checkout", clean_branch])

    def git_create_branch(self, branch_name: str) -> Dict[str, Any]:
        """Creates and checks out a new branch."""
        clean_branch = branch_name.strip()
        return self._run_git_command(["checkout", "-b", clean_branch])


    def git_commit(self, message: str) -> Dict[str, Any]:
        """Records changes to the repository with a commit message."""
        clean_msg = message.strip()
        if not clean_msg:
            return {"success": False, "error": "Commit message cannot be empty."}
        return self._run_git_command(["commit", "-m", clean_msg])

    # --- Pure Text & Data Utilities (Group 3) ---
    def generate_regex(self, description: str, sample_text: Optional[str] = None) -> Dict[str, Any]:
        """Generates regular expression patterns for common text matching tasks."""
        desc_lower = description.lower()
        pattern = ""
        explanation = ""

        if "email" in desc_lower:
            pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
            explanation = "Matches standard email addresses."
        elif "url" in desc_lower or "link" in desc_lower:
            pattern = r"https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)"
            explanation = "Matches HTTP and HTTPS URLs."
        elif "phone" in desc_lower or "mobile" in desc_lower:
            pattern = r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
            explanation = "Matches 10-digit phone numbers with optional international country codes."
        elif "date" in desc_lower:
            pattern = r"\b\d{4}[-/]\d{2}[-/]\d{2}\b|\b\d{2}[-/]\d{2}[-/]\d{4}\b"
            explanation = "Matches standard YYYY-MM-DD or DD-MM-YYYY dates."
        elif "ip" in desc_lower or "ipv4" in desc_lower:
            pattern = r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"
            explanation = "Matches standard IPv4 addresses."
        elif "hex" in desc_lower or "color" in desc_lower:
            pattern = r"#(?:[0-9a-fA-F]{3}){1,2}\b"
            explanation = "Matches 3 or 6 digit hex color codes."
        else:
            clean_word = re.escape(description.strip())
            pattern = rf"\b{clean_word}\b"
            explanation = f"Matches occurrences of '{description}'."

        matches = []
        if sample_text and pattern:
            try:
                matches = re.findall(pattern, sample_text)
            except Exception:
                pass

        return {
            "success": True,
            "action": "generate_regex",
            "description": description,
            "regex": pattern,
            "explanation": explanation,
            "matches_in_sample": matches,
            "response": f"Generated regex `{pattern}`: {explanation}"
        }

    def format_validate_json(self, json_string: str, indent: int = 2) -> Dict[str, Any]:
        """Validates and pretty-prints JSON strings, providing exact error diagnostics."""
        try:
            parsed = json.loads(json_string)
            formatted = json.dumps(parsed, indent=indent)
            return {
                "success": True,
                "is_valid": True,
                "action": "format_json",
                "formatted_json": formatted,
                "key_count": len(parsed) if isinstance(parsed, (dict, list)) else 1,
                "response": "JSON is valid and formatted successfully."
            }
        except json.JSONDecodeError as err:
            return {
                "success": False,
                "is_valid": False,
                "error": f"JSON syntax error at line {err.lineno}, column {err.colno}: {err.msg}",
                "lineno": err.lineno,
                "colno": err.colno,
                "response": f"Invalid JSON: syntax error at line {err.lineno}, column {err.colno}: {err.msg}"
            }

    # --- Refusal Gate for Arbitrary Shell Execution ---
    def refuse_general_shell(self, command: str) -> Dict[str, Any]:
        """Inviolable refusal gate rejecting arbitrary shell/PowerShell/terminal execution."""
        msg = "Refused: Arbitrary shell command execution is prohibited by system safety policy, Sir. Allowlisted developer tasks such as git status, git diff, or json formatting are available instead."
        logger.warning("[DevToolAgent] Blocked prohibited general shell execution request: '%s'", command)
        return {
            "success": True,
            "status": "success",
            "action": "refuse_general_shell",
            "command": command,
            "message": msg,
            "response": msg,
            "output": msg
        }

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator Agent Router."""
        action = inputs.get("action", "").lower()
        cmd = inputs.get("command", "") or inputs.get("query", "")

        # Check for prohibited general shell execution
        prohibited_phrases = ["run shell", "shell command", "execute bash", "powershell command", "run terminal", "run in cmd", "whoami"]
        if action in ["refuse_general_shell", "refuse", "shell", "bash", "terminal", "run_cmd"] or any(p in cmd.lower() for p in prohibited_phrases):
            return self.refuse_general_shell(cmd)

        if action in ["git_status", "status"]:
            return self.git_status()
        elif action in ["git_diff", "diff"]:
            return self.git_diff(inputs.get("file_path"))
        elif action in ["git_branch", "branches"]:
            return self.git_branch()
        elif action in ["git_create_branch", "create_branch", "branch_create"]:
            return self.git_create_branch(inputs.get("branch", "temp-test-branch"))
        elif action in ["git_switch", "checkout", "switch_branch"]:
            return self.git_switch_branch(inputs.get("branch", inputs.get("target", "main")))

        elif action in ["git_commit", "commit"]:
            return self.git_commit(inputs.get("message", "Commit via JARVIS Dev Tool"))
        elif action in ["generate_regex", "regex"]:
            desc = inputs.get("description", inputs.get("query", ""))
            sample = inputs.get("sample", inputs.get("sample_text"))
            return self.generate_regex(desc, sample)
        elif action in ["format_json", "validate_json", "json"]:
            raw_json = inputs.get("json", inputs.get("text", inputs.get("data", "")))
            return self.format_validate_json(raw_json)
        else:
            return {"success": False, "error": f"Unknown dev tool action: '{action}'"}


dev_tool_agent = DevToolAgent()
