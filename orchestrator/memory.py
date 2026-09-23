"""Memory Manager for JARVIS Layer 2.

Provides dual-tier memory with:
1. Short-Term Memory: Fast, volatile in-session working context.
2. Long-Term Memory: Persistent user profile and preferences saved to disk.
3. Memory Sanitization: Automatic redaction of credentials, Wi-Fi keys, and tokens.
4. Exponential Half-Life Decay: Mathematical recency weighting of stored facts over time.

Preserves exact existing signatures:
- remember(key: str, value: Any, persistent: bool = False, persona: Optional[str] = None) -> None
- store(key: str, value: Any, persistent: bool = False, persona: Optional[str] = None) -> None (alias)
- recall(key: str, persona: Optional[str] = None) -> Optional[Any]
- forget(key: str, persistent: bool = False, persona: Optional[str] = None) -> bool
- clear_session() -> None
- get_all_persistent() -> Dict[str, Any]
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import PROJECT_ROOT, settings
from orchestrator.memory_sanitizer import MemorySanitizer

logger = logging.getLogger("JARVIS.Memory")

MEMORY_DIR = PROJECT_ROOT / "memory"
USER_PROFILE_PATH = MEMORY_DIR / "user_profile.json"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


class MemoryDecayEngine:
    """Mathematical decay engine using half-life recency weighting."""

    DEFAULT_HALF_LIFE_DAYS: float = 14.0  # 2 weeks half-life

    @classmethod
    def calculate_confidence(
        cls,
        base_confidence: float,
        updated_at_iso: str,
        half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
        now: Optional[datetime] = None,
    ) -> float:
        """Computes exponential half-life decay: C(t) = C_0 * 2^(-delta_t / t_half)."""
        current = now or _utcnow()
        try:
            # Handle ISO string with or without timezone
            dt_str = updated_at_iso.replace("Z", "+00:00")
            ref_dt = datetime.fromisoformat(dt_str)
            if ref_dt.tzinfo is None:
                ref_dt = ref_dt.replace(tzinfo=timezone.utc)
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)

            delta_days = max(0.0, (current - ref_dt).total_seconds() / 86400.0)
            if half_life_days <= 0:
                return base_confidence
            decay_factor = math.pow(0.5, delta_days / half_life_days)
            return round(base_confidence * decay_factor, 4)
        except Exception as e:
            logger.warning("[MemoryDecay] Could not compute decay: %s", e)
            return base_confidence


class MemoryManager:
    """Manages short-term session state and disk-persisted long-term memories with sanitization and decay."""

    def __init__(self, profile_path: Path = USER_PROFILE_PATH):
        self.profile_path = Path(profile_path)
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path = self.profile_path.with_suffix(".meta.json")

        self.session_memory: Dict[str, Any] = {}
        self.long_term_memory: Dict[str, Any] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}

        self.sanitizer = MemorySanitizer
        self.decay_engine = MemoryDecayEngine

        self._load_persistent()

    def _load_persistent(self) -> None:
        """Loads long-term user profile and metadata from disk."""
        if self.profile_path.exists():
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    self.long_term_memory = json.load(f)
                logger.info(
                    "[MemoryManager] Loaded %d persistent memories from %s",
                    len(self.long_term_memory),
                    self.profile_path,
                )
            except Exception as e:
                logger.error("[MemoryManager] Error loading persistent memory: %s", str(e))
                self.long_term_memory = {}
        else:
            self.long_term_memory = {}

        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
            except Exception as e:
                logger.warning("[MemoryManager] Could not load memory metadata: %s", str(e))
                self.metadata = {}
        else:
            self.metadata = {}

    def _save_persistent(self) -> None:
        """Saves long-term memory and metadata to disk."""
        try:
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(self.long_term_memory, f, indent=2)
            logger.debug("[MemoryManager] Flushed persistent memory to disk.")
        except Exception as e:
            logger.error("[MemoryManager] Failed saving persistent memory: %s", str(e))

        try:
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error("[MemoryManager] Failed saving memory metadata: %s", str(e))

    def remember(
        self,
        key: str,
        value: Any,
        persistent: bool = False,
        persona: Optional[str] = None,
        confidence: float = 1.0,
        half_life_days: float = 14.0,
    ) -> None:
        """Stores a key-value memory item with automatic sanitization and decay metadata."""
        p_name = persona or settings.active_persona_name

        # 1. Automatic credential sanitization
        sanitized_val = self.sanitizer.sanitize(value)
        timestamp = _utcnow_iso()

        if persistent:
            self.long_term_memory[key] = sanitized_val
            self.metadata[key] = {
                "created_at": self.metadata.get(key, {}).get("created_at", timestamp),
                "updated_at": timestamp,
                "confidence": max(0.0, min(1.0, float(confidence))),
                "half_life_days": float(half_life_days),
            }
            self._save_persistent()
            logger.info(
                "[MemoryManager] [%s] Stored LONG-TERM memory: '%s' = '%s' (confidence=%.2f, half_life=%.1fd)",
                p_name,
                key,
                str(sanitized_val)[:30],
                confidence,
                half_life_days,
            )
        else:
            self.session_memory[key] = sanitized_val
            logger.info(
                "[MemoryManager] [%s] Stored SHORT-TERM memory: '%s' = '%s'",
                p_name,
                key,
                str(sanitized_val)[:30],
            )

    def store(
        self,
        key: str,
        value: Any,
        persistent: bool = False,
        persona: Optional[str] = None,
        confidence: float = 1.0,
        half_life_days: float = 14.0,
    ) -> None:
        """Direct alias for remember() conforming to JARVIS Layer 2 conventions."""
        self.remember(
            key=key,
            value=value,
            persistent=persistent,
            persona=persona,
            confidence=confidence,
            half_life_days=half_life_days,
        )

    def recall(self, key: str, persona: Optional[str] = None) -> Optional[Any]:
        """Retrieves a memory item from session memory or long-term persistent memory."""
        p_name = persona or settings.active_persona_name

        # Check short-term first
        if key in self.session_memory:
            logger.debug("[MemoryManager] [%s] Recalled from short-term: '%s'", p_name, key)
            return self.session_memory[key]

        # Check long-term
        if key in self.long_term_memory:
            logger.debug("[MemoryManager] [%s] Recalled from long-term: '%s'", p_name, key)
            return self.long_term_memory[key]

        logger.debug("[MemoryManager] [%s] Memory key not found: '%s'", p_name, key)
        return None

    def retrieve(self, key: str, persona: Optional[str] = None) -> Optional[Any]:
        """Convenience alias for recall."""
        return self.recall(key, persona)

    def get_effective_confidence(self, key: str, now: Optional[datetime] = None) -> float:
        """Returns the mathematically decayed confidence for a long-term memory key."""
        if key not in self.long_term_memory:
            return 0.0

        meta = self.metadata.get(key, {})
        base_confidence = meta.get("confidence", 1.0)
        updated_at = meta.get("updated_at", _utcnow_iso())
        half_life = meta.get("half_life_days", 14.0)

        return self.decay_engine.calculate_confidence(
            base_confidence=base_confidence,
            updated_at_iso=updated_at,
            half_life_days=half_life,
            now=now,
        )

    def forget(self, key: str, persistent: bool = False, persona: Optional[str] = None) -> bool:
        """Removes a key from memory and metadata."""
        p_name = persona or settings.active_persona_name
        deleted = False

        if persistent and key in self.long_term_memory:
            del self.long_term_memory[key]
            if key in self.metadata:
                del self.metadata[key]
            self._save_persistent()
            deleted = True
            logger.info("[MemoryManager] [%s] Deleted from LONG-TERM memory: '%s'", p_name, key)

        if key in self.session_memory:
            del self.session_memory[key]
            deleted = True
            logger.info("[MemoryManager] [%s] Deleted from SHORT-TERM memory: '%s'", p_name, key)

        return deleted

    def clear_session(self) -> None:
        """Wipes temporary session memory while keeping long-term intact."""
        self.session_memory.clear()
        logger.info("[MemoryManager] Short-term session memory cleared.")

    def get_all_persistent(self) -> Dict[str, Any]:
        """Returns all persistent long-term memories."""
        return dict(self.long_term_memory)

    def get_all_memories(self) -> Dict[str, Any]:
        """Returns all persistent long-term memories combined with active session memories."""
        combined = dict(self.long_term_memory)
        combined.update(self.session_memory)
        return combined

    def set_pending_action(self, action_data: Dict[str, Any]) -> None:
        """Stores structured pending action across confirmation gates."""
        self.session_memory["pending_confirmed_action"] = action_data
        logger.info("[MemoryManager] Stored pending action for gate confirmation: %s", action_data.get("action"))

    def get_pending_action(self) -> Optional[Dict[str, Any]]:
        """Retrieves structured pending action awaiting user confirmation."""
        return self.session_memory.get("pending_confirmed_action")

    def clear_pending_action(self) -> None:
        """Clears pending confirmed action once processed or cancelled."""
        if "pending_confirmed_action" in self.session_memory:
            del self.session_memory["pending_confirmed_action"]
            logger.info("[MemoryManager] Cleared pending confirmed action.")


memory_manager = MemoryManager()
