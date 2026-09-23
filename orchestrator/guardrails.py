"""Safety Guardrail Hook for JARVIS Layer 2.

Rule-based safety validator intercepting TaskSteps before execution.
Blocks dangerous, destructive, or unauthorized actions (disk formatting,
system file wiping, core process termination) and logs violations.
"""

import re
import logging
from typing import Dict, Any, Tuple
from orchestrator.planner import TaskStep

logger = logging.getLogger("JARVIS.Guardrails")

# Dangerous patterns strictly blocked from execution
DANGEROUS_PATTERNS = [
    (r"\bformat\s+[a-zA-Z]:", "Destructive disk formatting command"),
    (r"\brmdir\s+/[sS]", "Recursive directory deletion"),
    (r"\bdel\s+/[fF]\s+/[sS]", "Forceful recursive file deletion"),
    (r"\brm\s+-rf\s+/", "Root filesystem deletion"),
    (r"\bdiskpart\b", "Low-level disk partitioning tool"),
    (r"\b(kill|terminate|stop)\s+(svchost|csrss|lsass|smss|services)\b", "Core Windows system service termination"),
    (r"\bdrop\s+database\b", "Database dropping command"),
]


class SafetyGuardrail:
    """Validates steps against safety policies before execution."""

    def evaluate_step(self, step: TaskStep, persona: str) -> Tuple[bool, str]:
        """Evaluates a single TaskStep for safety risks.

        Returns (is_allowed, reason).
        """
        # Inspect description and input payloads
        inspected_texts = [step.description]
        for k, v in step.inputs.items():
            inspected_texts.append(f"{k}: {v}")
        combined_text = " ".join(inspected_texts)

        # Integrate Policy & Safety Kernel checks (Two-Gate confirmation & shell/file policy)
        try:
            from safety.policy_kernel import policy_kernel
            raw_target = str(step.inputs.get("target") or step.inputs.get("path") or step.description or "")
            step_action = step.inputs.get("action") or getattr(step, "action_type", "execute") or "execute"
            safety_dec = policy_kernel.evaluate(
                domain=step.required_agent_type or "system",
                action=step_action,
                parameters=step.inputs,
                raw_query=combined_text,
            )
            if not safety_dec.allowed:
                logger.warning("[Guardrail BLOCKED via PolicyKernel] Step '%s': %s", step.step_id, safety_dec.reason)
                if safety_dec.confirmation_token:
                    from orchestrator.memory import memory_manager
                    memory_manager.set_pending_action({
                        "action": step_action,
                        "required_agent_type": step.required_agent_type,
                        "inputs": {**step.inputs, "user_confirmed": True, "confirmed": True, "confirmation_token": safety_dec.confirmation_token},
                        "token": safety_dec.confirmation_token,
                    })
                return False, safety_dec.reason
        except Exception as pk_err:
            logger.debug("[Guardrail] Policy kernel evaluation warning: %s", pk_err)

        for pattern, description in DANGEROUS_PATTERNS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                violation_msg = f"Safety Guardrail Alert: Action '{step.description}' BLOCKED ({description})"
                logger.critical(
                    "[Guardrail BLOCKED] [%s] Step '%s' violated safety rule: %s",
                    persona,
                    step.step_id,
                    description,
                )
                return False, violation_msg

        # 2. Check granular policy permissions (ALLOW / ASK / DENY)
        try:
            from agents.permission_checks import permission_manager, PermissionState

            action_name = getattr(step, "action_name", "") or getattr(step, "agent_type", "")
            domain = getattr(step, "action_type", "") or action_name
            eval_res = permission_manager.evaluate_action(
                domain=domain,
                action=action_name,
                details=step.inputs,
                is_approved=getattr(step, "confirmed", False),
                persona=persona,
            )
            if eval_res.get("status") == "denied":
                reason = eval_res.get("reason", "Action denied by permission policy")
                logger.warning("[Guardrail DENIED] [%s] Step '%s': %s", persona, step.step_id, reason)
                return False, f"Permission Policy Denied: {reason}"
        except Exception as e:
            logger.debug("[Guardrail] Permission manager evaluation error: %s", e)

        logger.debug("[Guardrail PASS] [%s] Step '%s' approved", persona, step.step_id)
        return True, "Step verified safe."


safety_guardrail = SafetyGuardrail()
