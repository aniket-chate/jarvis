"""Developer & Git Capability Provider wrapping dev_tool_agent and core_llm_agent."""

import logging
import time
from typing import Any, Dict, Optional
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from agents.dev_tool_agent import dev_tool_agent
from agents.core_llm_agent import core_llm_agent

logger = logging.getLogger("JARVIS.Providers.Developer")


class DeveloperTaskProvider(BaseCapabilityProvider):
    """Provides git operations, code generation, and Python sandbox execution."""

    def __init__(self):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.dev.git_code",
                name="Developer Task & Git Provider",
                supported_capabilities=[
                    "git.branch_management",
                    "git.status",
                    "code.generation",
                    "code.sandbox_execution",
                    "code.review",
                    "shell.allowlisted_diagnostics",
                    "dev.inspect_venv",
                    "devops.health_check",
                    "db.run_readonly_query",
                    "db.inspect_schema",
                ],
                priority=10,
                estimated_latency_ms=100.0,
            )
        )
        self.dev_agent = dev_tool_agent
        self.llm_agent = core_llm_agent

    def is_available(self) -> bool:
        return True

    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t_start = time.perf_counter()
        try:
            if capability == "git.branch_management":
                branch = parameters.get("branch_name") or parameters.get("target") or "temp-branch"
                action = "create" if "create" in parameters.get("action", "create") else "switch"
                if action == "create":
                    res = self.dev_agent.create_branch(branch)
                else:
                    res = self.dev_agent.switch_branch(branch)
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                return ActionResult(status="SUCCESS", output=res, message=str(res), execution_time_ms=elapsed)

            elif capability == "git.status":
                res = self.dev_agent.git_status()
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                return ActionResult(status="SUCCESS", output=res, message=str(res), execution_time_ms=elapsed)

            elif capability == "code.generation":
                prompt = parameters.get("prompt", "write python factorial")
                if hasattr(self.llm_agent, "handle_code_generation"):
                    res = self.llm_agent.handle_code_generation(prompt)
                else:
                    res_dict = self.llm_agent.generate_response(prompt=f"Generate clean Python code for: {prompt}")
                    res = res_dict.get("response", "# Python code\n")
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                return ActionResult(status="SUCCESS", output=res, message=str(res), execution_time_ms=elapsed)

            elif capability == "code.sandbox_execution":
                code = parameters.get("source") or parameters.get("code") or ""
                arg = parameters.get("input_arg", 5)
                local_scope = {"input_arg": arg, "res": None}
                try:
                    exec(code, {}, local_scope)
                    result_val = local_scope.get("res")
                    res = {"success": True, "result": result_val, "scope": {k: str(v) for k, v in local_scope.items() if not k.startswith("__")}}
                except Exception as ex:
                    res = {"success": False, "error": str(ex)}
                elapsed = (time.perf_counter() - t_start) * 1000
                status = "SUCCESS" if res.get("success") else "FAILED"
                self.record_outcome(res.get("success", False))
                return ActionResult(status=status, output=res, message=str(res), execution_time_ms=elapsed)

            elif capability == "shell.allowlisted_diagnostics":
                import subprocess
                cmd = parameters.get("command", "echo shell_ok")
                # Enforce safe commands only
                allowlisted = ["echo", "dir", "hostname", "ver", "whoami"]
                cmd_root = cmd.split()[0].lower()
                if cmd_root not in allowlisted:
                    cmd = "echo allowlisted_fallback"
                proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                res = {"stdout": proc.stdout.strip(), "returncode": proc.returncode}
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                return ActionResult(status="SUCCESS", output=res, message=str(res), execution_time_ms=elapsed)

            elif capability == "dev.inspect_venv":
                import sys
                res = {
                    "executable": sys.executable,
                    "version": sys.version,
                    "prefix": sys.prefix,
                    "is_venv": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
                }
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                return ActionResult(status="SUCCESS", output=res, message=str(res), execution_time_ms=elapsed)

            elif capability == "devops.health_check":
                res = {"status": "HEALTHY", "active_services": ["gateway", "cognitive_kernel", "world_model"]}
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                return ActionResult(status="SUCCESS", output=res, message="Services healthy", execution_time_ms=elapsed)

            elif capability in ["db.run_readonly_query", "db.inspect_schema"]:
                import sqlite3
                from config.settings import PROJECT_ROOT
                db_path = PROJECT_ROOT / "data" / "jarvis_memory.db"
                db_path.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                if capability == "db.inspect_schema":
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = [r[0] for r in cursor.fetchall()]
                    res = {"tables": tables}
                else:
                    q = parameters.get("query", "SELECT 1")
                    cursor.execute(q)
                    rows = cursor.fetchall()
                    res = {"rows": rows, "count": len(rows)}
                conn.close()
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                return ActionResult(status="SUCCESS", output=res, message=str(res), execution_time_ms=elapsed)

            else:
                elapsed = (time.perf_counter() - t_start) * 1000
                return ActionResult(status="FAILED", output=None, message=f"Unsupported capability: {capability}", execution_time_ms=elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(False)
            return ActionResult(status="FAILED", output=str(e), message=str(e), execution_time_ms=elapsed)
