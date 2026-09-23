"""JARVIS Goal Engine (Cognitive Kernel - Stage 4).

Decomposes top-level goals into subgoals, manages dependency DAGs,
and tracks completion criteria.
"""

from dataclasses import dataclass, field
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("JARVIS.Cognitive.GoalEngine")


@dataclass
class SubGoal:
    goal_id: str
    description: str
    domain: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    completed: bool = False
    result: Optional[Any] = None


@dataclass
class GoalTree:
    root_goal: str
    subgoals: List[SubGoal] = field(default_factory=list)
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    created_at: float = field(default_factory=time.time)


import re


class GoalEngine:
    """Manages hierarchical goal decomposition and completion."""

    def __init__(self):
        self._active_goals: Dict[str, GoalTree] = {}

    def create_atomic_goal(self, goal_text: str, domain: str, action: str, params: Dict[str, Any]) -> GoalTree:
        """Creates an atomic single-subgoal tree for System 1 fast actions."""
        sub = SubGoal(
            goal_id=f"g_{int(time.time()*1000)}",
            description=goal_text,
            domain=domain,
            action=action,
            parameters=params,
        )
        tree = GoalTree(root_goal=goal_text, subgoals=[sub], status="IN_PROGRESS")
        return tree

    def decompose(self, goal_text: str) -> GoalTree:
        """Decomposes a multi-step request into a GoalTree with subgoals and dependency DAG."""
        tree = GoalTree(root_goal=goal_text)
        low = goal_text.lower().strip()

        # 1. Multi-Telemetry request: "Give me CPU usage, RAM usage, network status, and current time"
        telemetry_intents = []
        if "cpu" in low:
            telemetry_intents.append(("cpu_usage", "Inspect CPU utilization"))
        if "ram" in low or "memory" in low:
            telemetry_intents.append(("ram_usage", "Inspect RAM utilization"))
        if "network" in low or "wifi" in low or "ping" in low:
            telemetry_intents.append(("network_status", "Inspect network connectivity"))
        if "time" in low or "current time" in low:
            telemetry_intents.append(("current_time", "Query current system time"))

        if len(telemetry_intents) >= 2:
            for idx, (act, desc) in enumerate(telemetry_intents):
                tree.subgoals.append(
                    SubGoal(
                        goal_id=f"g_telemetry_{idx+1}",
                        description=desc,
                        domain="os",
                        action="multi_telemetry",
                        parameters={"metric": act},
                        dependencies=[],  # Independent, can run concurrently
                    )
                )
            return tree

        # 2. Sequential compound workflows (e.g. "Open Chrome, search GitHub for Python, and tell me what page is currently open")
        if any(sep in low for sep in [" and ", ", then ", " then ", ";", ","]):
            raw_clauses = [c.strip() for c in re.split(r"[,;]|\band\b|\bthen\b", goal_text) if len(c.strip()) > 3]
            if len(raw_clauses) >= 2:
                prev_id = None
                for idx, clause in enumerate(raw_clauses):
                    c_low = clause.lower()
                    domain = "browser" if any(w in c_low for w in ["chrome", "github", "search", "page", "browser", "url"]) else (
                        "file" if any(w in c_low for w in ["file", "folder", "directory"]) else "system"
                    )
                    action = "navigate" if any(w in c_low for w in ["open chrome", "launch browser", "navigate"]) else (
                        "search" if "search" in c_low else (
                            "inspect_page" if any(w in c_low for w in ["what page", "tell me", "inspect"]) else "execute"
                        )
                    )
                    gid = f"g_step_{idx+1}"
                    deps = [prev_id] if prev_id else []
                    tree.subgoals.append(
                        SubGoal(
                            goal_id=gid,
                            description=clause,
                            domain=domain,
                            action=action,
                            parameters={"raw_clause": clause},
                            dependencies=deps,
                        )
                    )
                    prev_id = gid
                return tree

        # Default atomic task
        sub = SubGoal(
            goal_id=f"sub_{int(time.time()*1000)}",
            description=goal_text,
            domain="auto",
            action="execute",
        )
        tree.subgoals.append(sub)
        return tree


goal_engine = GoalEngine()
