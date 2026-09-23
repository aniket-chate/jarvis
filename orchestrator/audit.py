"""Structured Audit & Interaction Logging for JARVIS Layer 2.

Extends existing JARVIS logging (logs/jarvis.log) by appending structured,
privacy-guaranteed JSONL records to logs/interactions.jsonl.

PRIVACY & SECURITY GUARANTEES:
1. Zero Raw Audio Contract: Never persists raw PCM, audio streams, or binary voice buffers.
2. Credential Redaction: All queries, parameters, and action results pass through MemorySanitizer.
3. Complete Auditability: Records timestamp, persona, intent, agent, permission state, AI provider, and verification status.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import PROJECT_ROOT
from orchestrator.memory_sanitizer import MemorySanitizer

logger = logging.getLogger("JARVIS.Audit")

AUDIT_LOG_PATH = PROJECT_ROOT / "logs" / "interactions.jsonl"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class InteractionRecord:
    """Structured record of a single conversational turn or agent action."""

    query: str
    persona: str = "Jarvis"
    intent: str = "general"
    agent_called: str = "core_llm"
    permission_state: str = "allow"
    provider_used: str = "ollama"
    action_result: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    interaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=_utcnow_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # 1. Zero raw audio contract: strip any audio or binary buffers
        for forbidden in ("audio", "pcm", "raw_audio", "voice_buffer", "audio_bytes"):
            if forbidden in self.action_result:
                del self.action_result[forbidden]
            if forbidden in self.metadata:
                del self.metadata[forbidden]

        # 2. Credential sanitization: strip secrets from text fields
        self.query = MemorySanitizer.sanitize(self.query)
        self.action_result = MemorySanitizer.sanitize(self.action_result)
        self.metadata = MemorySanitizer.sanitize(self.metadata)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> InteractionRecord:
        return cls(
            query=str(data.get("query", "")),
            persona=str(data.get("persona", "Jarvis")),
            intent=str(data.get("intent", "general")),
            agent_called=str(data.get("agent_called", "core_llm")),
            permission_state=str(data.get("permission_state", "allow")),
            provider_used=str(data.get("provider_used", "ollama")),
            action_result=dict(data.get("action_result", {})),
            success=bool(data.get("success", True)),
            interaction_id=str(data.get("interaction_id", str(uuid.uuid4()))),
            timestamp=str(data.get("timestamp", _utcnow_iso())),
            metadata=dict(data.get("metadata", {})),
        )


class InteractionAuditStore:
    """Persists structured interaction records to logs/interactions.jsonl."""

    def __init__(self, log_path: Path = AUDIT_LOG_PATH):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record_interaction(self, record: InteractionRecord) -> None:
        """Appends a structured interaction entry to the JSONL audit file."""
        line = json.dumps(record.to_dict()) + "\n"
        with self._lock:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(line)
                logger.debug("[AuditStore] Logged interaction: id=%s, agent=%s", record.interaction_id, record.agent_called)
            except Exception as e:
                logger.error("[AuditStore] Failed writing interaction audit log: %s", str(e))

    def get_recent_interactions(self, limit: int = 50) -> List[InteractionRecord]:
        """Reads recent interaction records from the JSONL audit file."""
        if not self.log_path.exists():
            return []

        records = []
        with self._lock:
            try:
                with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                for line in lines[-limit:]:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            records.append(InteractionRecord.from_dict(data))
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                logger.error("[AuditStore] Failed reading interaction audit log: %s", str(e))

        return records

    def clear(self) -> None:
        """Clears audit log (for testing cleanup)."""
        with self._lock:
            if self.log_path.exists():
                try:
                    self.log_path.unlink()
                except OSError:
                    pass


audit_store = InteractionAuditStore()
