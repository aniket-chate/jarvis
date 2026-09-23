"""Adaptive Learning & Reinforcement Learning (RL) Module for JARVIS Layer 2.

Implements:
1. Epsilon-Greedy Exploration/Exploitation Policy with mathematical decay.
2. Statistical Evidence Tracking with Bayesian confidence estimation.
3. Feedback Classification and Reward Propagation.
4. Behavioral Personalization (Agent choice, persona preference, proactive suggestions).

HARD ARCHITECTURAL INVARIANT:
"Jarvis learns behavior, but the user remains the authority."
The learning engine may optimize rankings, phrasing, and agent selection, but
is ARCHITECTURALLY PROHIBITED from modifying, weakening, or bypassing permission
gates (PermissionManager, Two-Independent-Gates, or SafetyGuardrails).
Any attempt by the learning engine to alter permission states raises an explicit
SafetyBoundaryViolation.
"""

from __future__ import annotations

import json
import logging
import math
import random
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings import PROJECT_ROOT
from orchestrator.memory import memory_manager

logger = logging.getLogger("JARVIS.ContinuousLearning")

LEARNING_DATA_PATH = PROJECT_ROOT / "memory" / "learning_state.json"


class SafetyBoundaryViolation(PermissionError):
    """Raised when the learning engine attempts to touch or weaken permission gates."""
    pass


@dataclass
class EvidenceRecord:
    """Statistical evidence tracking for candidate strategies or agent choices."""
    candidate: str
    success_count: int = 0
    failure_count: int = 0
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def record_outcome(self, success: bool) -> None:
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.last_updated = datetime.now(timezone.utc).isoformat()

    @property
    def successes(self) -> int:
        return self.success_count

    @property
    def failures(self) -> int:
        return self.failure_count

    @property
    def total_evidence(self) -> int:
        return self.success_count + self.failure_count

    @property
    def bayesian_confidence(self) -> float:
        """Laplace-smoothed Bayesian confidence estimate."""
        return round((self.success_count + 1.0) / (self.total_evidence + 2.0), 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate": self.candidate,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "total_evidence": self.total_evidence,
            "confidence": self.bayesian_confidence,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceRecord:
        return cls(
            candidate=data.get("candidate", ""),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            last_updated=data.get("last_updated", datetime.now(timezone.utc).isoformat()),
        )


PROHIBITED_RL_ACTIONS = {
    "persona", "persona_switch", "switch_persona", "identity",
    "jarvis", "friday", "ultron", "omi", "active_persona", "persona_preference"
}


class EpsilonGreedyPolicy:
    """Epsilon-greedy adaptive policy balancing exploration and exploitation."""

    def __init__(
        self,
        exploration_rate: float = 0.40,
        min_exploration: float = 0.05,
        decay_rate: float = 0.98,
    ):
        self.exploration_rate = float(exploration_rate)
        self.min_exploration = float(min_exploration)
        self.decay_rate = float(decay_rate)
        self.action_values: Dict[str, float] = {}
        self.action_counts: Dict[str, int] = {}

    def select_action(self, candidates: List[str], explore_override: Optional[bool] = None) -> Tuple[str, str]:
        """Selects candidate via exploration (random) or exploitation (argmax Q-value).

        HARD ARCHITECTURAL INVARIANT: Persona and identity are strictly excluded
        from candidate exploration. Persona changes only from explicit user intent.
        Returns: (selected_action, mode: 'exploration' | 'exploitation')
        """
        # Hard filter out any persona/identity actions
        safe_candidates = [c for c in candidates if c.lower() not in PROHIBITED_RL_ACTIONS]
        if not safe_candidates:
            return "", "exploitation"

        # Determine mode
        is_exploring = (
            explore_override
            if explore_override is not None
            else (random.random() < self.exploration_rate)
        )

        if is_exploring:
            chosen = random.choice(safe_candidates)
            return chosen, "exploration"

        # Exploitation: argmax action value
        best_candidate = safe_candidates[0]
        best_value = self.action_values.get(best_candidate, 0.0)
        for cand in safe_candidates[1:]:
            val = self.action_values.get(cand, 0.0)
            if val > best_value:
                best_value = val
                best_candidate = cand

        return best_candidate, "exploitation"

    def update(self, action: str, reward: float) -> None:
        """Incremental sample-average Q-value update: Q_{n+1} = Q_n + (R - Q_n) / n."""
        # Clamp reward to [-1.0, 1.0]
        r = max(-1.0, min(1.0, float(reward)))
        count = self.action_counts.get(action, 0) + 1
        self.action_counts[action] = count
        old_val = self.action_values.get(action, 0.0)
        new_val = old_val + (r - old_val) / count
        self.action_values[action] = round(new_val, 4)

        # Decay exploration rate
        self.exploration_rate = round(
            max(self.min_exploration, self.exploration_rate * self.decay_rate),
            4,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exploration_rate": self.exploration_rate,
            "min_exploration": self.min_exploration,
            "decay_rate": self.decay_rate,
            "action_values": self.action_values,
            "action_counts": self.action_counts,
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        self.exploration_rate = float(data.get("exploration_rate", 0.40))
        self.min_exploration = float(data.get("min_exploration", 0.05))
        self.decay_rate = float(data.get("decay_rate", 0.98))
        self.action_values = {k: float(v) for k, v in data.get("action_values", {}).items()}
        self.action_counts = {k: int(v) for k, v in data.get("action_counts", {}).items()}


class ContinuousLearningEngine:
    """Adaptive learning engine coordinating RL policy updates, evidence tracking, and behavioral tuning."""

    def __init__(self, storage_path: Path = LEARNING_DATA_PATH):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        self.policy = EpsilonGreedyPolicy()
        self.evidence: Dict[str, EvidenceRecord] = {}
        self.feedback_history: List[Dict[str, Any]] = []

        self._load_state()

    def _load_state(self) -> None:
        """Loads learned state and evidence from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.policy.from_dict(data.get("policy", {}))
                        self.evidence = {
                            k: EvidenceRecord.from_dict(v)
                            for k, v in data.get("evidence", {}).items()
                            if isinstance(v, dict)
                        }
                        self.feedback_history = data.get("feedback_history", [])[-200:]
                logger.info("[ContinuousLearning] Loaded learning state (%d actions, %d evidence records)", len(self.policy.action_values), len(self.evidence))
            except Exception as e:
                logger.error("[ContinuousLearning] Error loading learning state: %s", str(e))

    def _save_state(self) -> None:
        """Saves learned state and evidence to disk."""
        tmp_path = self.storage_path.with_suffix(".tmp")
        try:
            payload = {
                "policy": self.policy.to_dict(),
                "evidence": {k: v.to_dict() for k, v in self.evidence.items()},
                "feedback_history": self.feedback_history[-200:],
                "last_saved": datetime.now(timezone.utc).isoformat(),
            }
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            tmp_path.replace(self.storage_path)
        except Exception as e:
            logger.error("[ContinuousLearning] Failed saving learning state: %s", str(e))
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    def record_feedback(self, action: str, reward: float, context: Optional[str] = None) -> Dict[str, Any]:
        """Records outcome/feedback and updates RL policy and Bayesian evidence."""
        if action.lower() in PROHIBITED_RL_ACTIONS:
            logger.warning("[ContinuousLearning] Blocked attempt to record RL feedback on immutable persona action '%s'", action)
            return {"action": action, "ignored": True, "reason": "Persona is immutable to RL"}

        with self._lock:
            # 1. Update RL policy
            self.policy.update(action=action, reward=reward)

            # 2. Update statistical evidence
            if action not in self.evidence:
                self.evidence[action] = EvidenceRecord(candidate=action)
            is_success = reward > 0.0
            self.evidence[action].record_outcome(is_success)

            # 3. Append history
            entry = {
                "action": action,
                "reward": reward,
                "success": is_success,
                "context": context or "general",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.feedback_history.append(entry)
            self._save_state()

        logger.info(
            "[ContinuousLearning] Feedback recorded for '%s': reward=%.2f, Q-val=%.4f, confidence=%.4f",
            action,
            reward,
            self.policy.action_values.get(action, 0.0),
            self.evidence[action].bayesian_confidence,
        )
        return {
            "action": action,
            "action_value": self.policy.action_values.get(action, 0.0),
            "confidence": self.evidence[action].bayesian_confidence,
            "exploration_rate": self.policy.exploration_rate,
        }

    def get_status_summary(self) -> Dict[str, Any]:
        """Returns live summary of continuous learning metrics, Q-values, and evidence."""
        with self._lock:
            q_vals = {k: round(v, 4) for k, v in self.policy.action_values.items()}
            ev_summary = {
                k: {"successes": v.successes, "failures": v.failures, "confidence": round(v.bayesian_confidence, 4)}
                for k, v in self.evidence.items()
            }
            return {
                "active": True,
                "total_feedback_events": len(self.feedback_history),
                "action_q_values": q_vals,
                "exploration_rate": round(self.policy.exploration_rate, 4),
                "evidence_count": len(self.evidence),
                "evidence_summary": ev_summary,
                "recent_feedback": self.feedback_history[-5:] if self.feedback_history else []
            }

    def run_learning_cycle(self, target_memory: Optional[Any] = None) -> Dict[str, Any]:
        """Synthesizes learned behavioral preferences and commits them to long-term profile facts."""
        logger.info("[ContinuousLearning] Running adaptive learning review cycle...")

        with self._lock:
            # Determine top-performing actions/agents
            top_action = None
            top_val = -float("inf")
            for act, val in self.policy.action_values.items():
                if val > top_val:
                    top_val = val
                    top_action = act

            top_evidence_action = None
            top_conf = 0.0
            for act, ev in self.evidence.items():
                if ev.bayesian_confidence > top_conf:
                    top_conf = ev.bayesian_confidence
                    top_evidence_action = act

        mem = target_memory if target_memory is not None else memory_manager
        before_memory = dict(mem.get_all_persistent())

        observations = {
            "learned_top_performing_agent": top_action or "web_agent",
            "learned_highest_confidence_agent": top_evidence_action or "web_agent",
            "learned_exploration_rate": self.policy.exploration_rate,
            "learning_cycle_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for k, v in observations.items():
            mem.remember(key=k, value=v, persistent=True)

        after_memory = dict(mem.get_all_persistent())
        logger.info("[ContinuousLearning] Committed %d adaptive observations to persistent memory", len(observations))

        return {
            "success": True,
            "learned_observations": observations,
            "policy_summary": self.policy.to_dict(),
            "before_memory": before_memory,
            "after_memory": after_memory,
        }

    # -------------------------------------------------------------------------
    # HARD ARCHITECTURAL FIREWALL: Learning engine is PROHIBITED from altering
    # permissions, security boundaries, or SafetyGuardrails.
    # -------------------------------------------------------------------------
    def modify_permission_state(self, *args: Any, **kwargs: Any) -> None:
        """Inviolable firewall rejecting any attempt to tamper with permissions."""
        logger.critical("[Security Violation] ContinuousLearningEngine attempted to alter a permission state!")
        raise SafetyBoundaryViolation(
            "Security Boundary Invariant Violated: Continuous learning engine is forbidden from altering permission states."
        )

    def override_security_gate(self, *args: Any, **kwargs: Any) -> None:
        """Inviolable firewall rejecting any attempt to bypass safety gates."""
        logger.critical("[Security Violation] ContinuousLearningEngine attempted to bypass safety gates!")
        raise SafetyBoundaryViolation(
            "Security Boundary Invariant Violated: Continuous learning engine cannot bypass or weaken safety gates."
        )


learning_engine = ContinuousLearningEngine()
