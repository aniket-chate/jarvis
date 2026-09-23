"""Identity & Security Agent for JARVIS Layer 3 (Group 4).

Performs face-embedding verification against the stored owner profile.
Enforces the Two-Independent-Gates Rule for sensitive actions:
Gate 1: Successful identity match (confidence >= 0.85)
Gate 2: Explicit user confirmation
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from config.settings import PROJECT_ROOT, settings

logger = logging.getLogger("JARVIS.Agents.Identity")

OWNER_PROFILE_PATH = PROJECT_ROOT / "memory" / "owner_profile.json"
SENSITIVE_ACTIONS = {
    "send_email",
    "send_sms",
    "delete_file",
    "format_disk",
    "book_reservation",
    "financial_transaction",
    "lock_system",
    "power_off",
}


class IdentityAgent:
    """Matches biometrics and enforces two-gate security policies."""

    def __init__(self, profile_path: Path = OWNER_PROFILE_PATH):
        self.profile_path = profile_path
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.owner_profile: Dict[str, Any] = {}
        self.threshold = 0.85
        self._load_or_init_profile()

    def _load_or_init_profile(self) -> None:
        """Loads owner embedding or initializes baseline profile."""
        if self.profile_path.exists():
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    self.owner_profile = json.load(f)
                logger.info("[IdentityAgent] Loaded owner profile: '%s'", self.owner_profile.get("name", "Owner"))
                return
            except Exception as e:
                logger.error("[IdentityAgent] Error loading profile: %s", str(e))

        # Fail closed. A synthetic embedding is not biometric enrollment and must
        # never be accepted as an owner identity.
        self.owner_profile = {
            "name": None,
            "registered": False,
            "embedding_dim": 128,
            "face_embedding": [],
        }
        logger.warning(
            "[IdentityAgent] No enrolled owner profile found. Sensitive actions requiring "
            "biometric identity will remain locked until real enrollment is completed."
        )

    def match_face(self, query_embedding: List[float]) -> Tuple[bool, float]:
        """Calculates cosine similarity between query embedding and owner embedding.

        Returns (is_match, similarity_score).
        """
        stored = np.array(self.owner_profile.get("face_embedding", []), dtype=np.float32)
        query = np.array(query_embedding, dtype=np.float32)

        if len(stored) == 0 or len(query) == 0 or len(stored) != len(query):
            logger.warning("[IdentityAgent] Dimension mismatch or empty embedding")
            return False, 0.0

        dot_prod = np.dot(stored, query)
        norm_stored = np.linalg.norm(stored)
        norm_query = np.linalg.norm(query)

        if norm_stored == 0 or norm_query == 0:
            return False, 0.0

        similarity = float(dot_prod / (norm_stored * norm_query))
        similarity = max(0.0, min(1.0, similarity))
        is_match = similarity >= self.threshold

        logger.info("[IdentityAgent] Face match check: similarity=%.4f (Threshold=%.2f) -> Match=%s", similarity, self.threshold, is_match)
        return is_match, similarity

    def verify_two_gate_authorization(
        self,
        action: str = "sensitive_action",
        action_name: Optional[str] = None,
        face_embedding: Optional[List[float]] = None,
        user_confirmed: bool = False,
        explicit_user_confirmed: Optional[bool] = None,
        persona: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enforces Two-Independent-Gates Rule for sensitive actions.

        Gate 1: Identity Match (Biometric verification)
        Gate 2: Explicit Confirmation (User intent approval)
        """
        act = action_name or action
        confirmed = explicit_user_confirmed if explicit_user_confirmed is not None else user_confirmed
        p_name = persona or settings.active_persona_name
        is_sensitive = act.lower() in SENSITIVE_ACTIONS or any(s in act.lower() for s in ["send", "kill", "delete", "format", "pay"])

        # Gate 1: Biometrics
        gate_1_passed = False
        similarity_score = 0.0
        if face_embedding:
            gate_1_passed, similarity_score = self.match_face(face_embedding)
        else:
            logger.warning("[IdentityAgent] [%s] Gate 1 failed: No face embedding provided", p_name)

        # Gate 2: Explicit user confirmation
        gate_2_passed = bool(confirmed)

        authorized = (gate_1_passed and gate_2_passed) if is_sensitive else True

        result = {
            "action": act,
            "is_sensitive": is_sensitive,
            "gate_1_identity": {
                "passed": gate_1_passed,
                "similarity_score": round(similarity_score, 4),
            },
            "gate_2_confirmation": {
                "passed": gate_2_passed,
            },
            "authorized": authorized,
            "active_persona": p_name,
        }

        if not authorized:
            reasons = []
            if not gate_1_passed:
                reasons.append("Identity verification failed (Gate 1)")
            if not gate_2_passed:
                reasons.append("Explicit confirmation pending (Gate 2)")
            reason_str = "; ".join(reasons)
            result["denial_reason"] = reason_str
            result["reason"] = reason_str
            logger.warning("[IdentityAgent] [%s] Action '%s' DENIED: %s", p_name, act, reason_str)
        else:
            logger.info("[IdentityAgent] [%s] Action '%s' APPROVED through security gates", p_name, act)

        return result

    def verify_face(self, query_embedding: List[float]) -> Dict[str, Any]:
        """Convenience method returning match dictionary."""
        is_match, sim = self.match_face(query_embedding)
        return {
            "match": is_match,
            "similarity": sim,
            "threshold": self.threshold
        }

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator Agent Router."""
        action = inputs.get("action", "verify_gate")
        if action == "match_face":
            return self.verify_face(inputs.get("face_embedding", []))
        return self.verify_two_gate_authorization(
            action=inputs.get("target_action", "sensitive_action"),
            face_embedding=inputs.get("face_embedding"),
            user_confirmed=inputs.get("user_confirmed", False)
        )


identity_agent = IdentityAgent()

