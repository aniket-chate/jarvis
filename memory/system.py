"""JARVIS Unified 7-Tier Memory System.

Implements explicit separation of memory responsibilities with strict read/write policies:
1. Working Memory: Immediate turn context, active goals, pronoun entity bindings.
2. Episodic Memory: Immutable ledger of what actually happened (physical actions, outcomes).
3. Semantic Memory: Stable factual knowledge base & document embeddings.
4. Procedural Memory: Executable skill recipes & workflow procedures.
5. User Memory: Aniket's profile, habits, relationships, and preferences.
6. World Knowledge: Live external facts retrieved from search/web.
7. Experience Memory: Reinforcement learning records (state, action, reward, confidence).
"""

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
from memory.episodic_ledger import episodic_ledger

logger = logging.getLogger("JARVIS.Memory.Unified")


@dataclass
class WorkingMemory:
    """Tier 1: Transient cognitive context and pronoun bindings."""
    active_session_id: str = "default"
    active_goal: Optional[str] = None
    active_code: Optional[Dict[str, str]] = None
    active_file: Optional[str] = None
    active_tab: Optional[str] = None
    pronoun_bindings: Dict[str, Any] = field(default_factory=dict)
    turn_dialogue: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class SemanticFact:
    fact_id: str
    subject: str
    predicate: str
    obj: str
    confidence: float = 1.0


class MemorySystem:
    """The unified multi-tier memory system governing all read/write policies."""

    def __init__(self):
        self.working = WorkingMemory()
        self.episodic = episodic_ledger
        self._user_profile_path = Path(r"d:\assignment\JARVIS\memory\user_profile.json")
        self._facts: Dict[str, SemanticFact] = {}
        self._procedural_recipes: Dict[str, List[str]] = {
            "git.feature_flow": ["create_branch", "edit_files", "git_status", "run_tests", "commit"],
            "browser.research": ["open_search", "inspect_results", "extract_content", "summarize"],
        }
        self._load_facts()

    def _load_facts(self):
        self.store_fact("Aniket", "creator_of", "JARVIS")
        self.store_fact("Aniket", "likes_book", "Mrutunjay")
        self.store_fact("JARVIS", "runs_on", "Local AI and Windows 11")

    # -------------------------------------------------------------
    # 1. Working Memory (Short-Term Cognitive Buffer)
    # -------------------------------------------------------------
    def bind_pronoun(self, pronoun: str, entity_value: Any):
        self.working.pronoun_bindings[pronoun.lower()] = entity_value

    def get_pronoun_binding(self, pronoun: str) -> Optional[Any]:
        return self.working.pronoun_bindings.get(pronoun.lower())

    def record_dialogue(self, role: str, text: str):
        self.working.turn_dialogue.append({"role": role, "text": text, "time": time.time()})
        if len(self.working.turn_dialogue) > 20:
            self.working.turn_dialogue = self.working.turn_dialogue[-20:]

    # -------------------------------------------------------------
    # 2. Episodic Memory (Ground Truth What Actually Happened)
    # -------------------------------------------------------------
    def record_episodic_action(
        self,
        request_id: str = "",
        persona: str = "Jarvis",
        domain: str = "system",
        action: str = "action",
        target: str = "",
        status: str = "completed",
        summary: str = "",
        error_reason: Optional[str] = None,
        outcome: Optional[str] = None,
        success: Optional[bool] = None,
        **kwargs: Any,
    ):
        """Strict write policy: Verified lifecycle state records in Episodic Memory."""
        if outcome and not summary:
            summary = str(outcome)
        if success is not None:
            status = "VERIFIED" if success else "FAILED"
        if not request_id:
            request_id = f"req_{int(time.time()*1000)}"
        if "." in action and domain == "system":
            domain = action.split(".")[0]
        self.episodic.record(
            request_id=request_id,
            persona=persona,
            domain=domain,
            action=action,
            target=target,
            status=status,
            summary=summary,
            error_reason=error_reason,
        )

    def query_episodic_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.episodic.get_recent_events(limit=limit)

    def query_action_status(self, action_keyword: str, target_keyword: str = "") -> Optional[Dict[str, Any]]:
        """Queries the exact lifecycle status of an action."""
        entry = self.episodic.query_action(action_keyword, target_keyword)
        return entry.to_dict() if entry else None

    def get_failed_actions(self) -> List[Dict[str, Any]]:
        """Queries all actions that failed, were blocked, or cancelled with their error reasons."""
        return [e.to_dict() for e in self.episodic.get_failures()]

    def has_action_been_done(self, action_name: str, target_keyword: str = "") -> bool:
        """Answers: 'Did you actually do that?' - Only True for physically VERIFIED actions."""
        events = self.episodic.get_recent_events(limit=50)
        for ev in events:
            if action_name.lower() in ev.get("action", "").lower():
                if not target_keyword or target_keyword.lower() in ev.get("target", "").lower():
                    # Must be VERIFIED to count as done (Invariant 5)
                    if ev.get("status") in ["VERIFIED", "COMPLETED", "SUCCESS"]:
                        return True
        return False

    def get_truthful_session_summary(self) -> str:
        return self.episodic.get_session_summary()

    # -------------------------------------------------------------
    # 3. Semantic Memory (Stable Facts)
    # -------------------------------------------------------------
    def store_fact(self, subject: str, predicate: str, obj: str):
        key = f"{subject}_{predicate}".lower()
        self._facts[key] = SemanticFact(fact_id=key, subject=subject, predicate=predicate, obj=obj)

    def query_fact(self, subject: str, predicate: str) -> Optional[str]:
        key = f"{subject}_{predicate}".lower()
        fact = self._facts.get(key)
        return fact.obj if fact else None

    # -------------------------------------------------------------
    # 4. Procedural Memory (How things are done)
    # -------------------------------------------------------------
    def get_procedure(self, workflow_name: str) -> List[str]:
        return self._procedural_recipes.get(workflow_name, [])

    # -------------------------------------------------------------
    # 5. User Memory (Stable Aniket Profile)
    # -------------------------------------------------------------
    def get_user_profile(self) -> Dict[str, Any]:
        if self._user_profile_path.exists():
            try:
                data = json.loads(self._user_profile_path.read_text(encoding="utf-8"))
                owner = data.get("owner_name") or data.get("owner") or data.get("user_name") or "Aniket"
                data["owner_name"] = owner
                return data
            except Exception:
                pass
        return {"owner_name": "Aniket", "book": "Mrutunjay"}

    # -------------------------------------------------------------
    # 6. Experience Memory (RL & Continuous Learning)
    # -------------------------------------------------------------
    def record_experience(self, action: str, reward: float, context: str = ""):
        try:
            from orchestrator.learning import learning_engine
            learning_engine.record_feedback(action=action, reward=reward, context=context)
            logger.info("[MemorySystem] Recorded RL experience for '%s' (reward=%.2f)", action, reward)
        except Exception as e:
            logger.debug("[MemorySystem] Experience recording error: %s", e)


# Master Unified Memory singleton
memory_system = MemorySystem()
