"""JARVIS Experience-Driven Learning Architecture.

Separates:
1. Experience Collection (Recording raw execution outcomes & verification data)
2. Evaluation (Analyzing reliability, latency, failure patterns)
3. Deployment of Learned Policies (Gated updates to provider ranking & routing confidence)
"""

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("JARVIS.LearningSystem")


@dataclass
class ExperienceRecord:
    record_id: str
    request_id: str
    goal: str
    capability: str
    provider_id: str
    verification_status: str     # "SUCCESS", "PARTIAL", "FAILED"
    latency_ms: float
    reward: float                # -1.0 to 1.0
    user_feedback: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class ExperienceStore:
    """Collects and persists raw interaction experiences without immediately mutating behavior."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path(r"d:\assignment\JARVIS\memory\experience_ledger.json")
        self._records: List[ExperienceRecord] = []
        self._load()

    def _load(self):
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for d in data[-200:]:  # Keep last 200 in memory
                    self._records.append(ExperienceRecord(**d))
            except Exception as e:
                logger.debug("[ExperienceStore] Load error: %s", e)

    def record_experience(
        self,
        request_id: str,
        goal: str,
        capability: str,
        provider_id: str,
        verification_status: str,
        latency_ms: float,
        reward: float,
        user_feedback: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExperienceRecord:
        record = ExperienceRecord(
            record_id=f"exp_{int(time.time()*1000)}",
            request_id=request_id,
            goal=goal,
            capability=capability,
            provider_id=provider_id,
            verification_status=verification_status,
            latency_ms=latency_ms,
            reward=reward,
            user_feedback=user_feedback,
            context=context or {},
        )
        self._records.append(record)
        logger.info(
            "[ExperienceStore] Collected experience: capability='%s', provider='%s', status='%s', reward=%.2f",
            capability,
            provider_id,
            verification_status,
            reward,
        )
        self._persist()
        return record

    def _persist(self):
        try:
            raw = [r.__dict__ for r in self._records[-300:]]
            self.storage_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug("[ExperienceStore] Persist error: %s", e)

    def get_recent(self, limit: int = 20) -> List[ExperienceRecord]:
        return self._records[-limit:]


class ExperienceEvaluator:
    """Analyzes collected experiences to evaluate provider reliability and planning quality."""

    def __init__(self, store: ExperienceStore):
        self.store = store

    def evaluate_provider_performance(self, provider_id: str) -> Dict[str, Any]:
        """Calculates success rate, average latency, and health for a provider."""
        matching = [r for r in self.store._records if r.provider_id == provider_id]
        if not matching:
            return {"provider_id": provider_id, "sample_count": 0, "reliability": 1.0, "avg_latency_ms": 0.0}

        successes = sum(1 for r in matching if r.verification_status == "SUCCESS")
        total = len(matching)
        avg_latency = sum(r.latency_ms for r in matching) / total
        reliability = successes / total

        return {
            "provider_id": provider_id,
            "sample_count": total,
            "reliability": round(reliability, 3),
            "avg_latency_ms": round(avg_latency, 1),
            "recommended_priority_adjustment": 0 if reliability > 0.8 else +10,
        }


experience_store = ExperienceStore()
experience_evaluator = ExperienceEvaluator(experience_store)
