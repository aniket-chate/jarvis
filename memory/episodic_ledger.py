"""Episodic Action Ledger for JARVIS.

Maintains a structured, chronological record of all physical actions and tasks
executed by JARVIS agents during the session. Enables truthful session recall
and eliminates hallucinations on session summary queries ("what did we do?").
"""

import time
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger("JARVIS.EpisodicLedger")


@dataclass
class ActionEntry:
    timestamp: float
    request_id: str
    persona: str
    domain: str
    action: str
    target: str
    status: str  # "VERIFIED", "EXECUTED", "REQUESTED", "FAILED", "CANCELLED", "BLOCKED"
    summary: str
    error_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EpisodicActionLedger:
    """Session ledger tracking all executed physical actions and tool invocations."""

    def __init__(self):
        self._entries: List[ActionEntry] = []

    def record(
        self,
        request_id: str,
        persona: str,
        domain: str,
        action: str,
        target: str,
        status: str,
        summary: str,
        error_reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ActionEntry:
        """Records an action with its verified lifecycle status into the episodic ledger."""
        norm_status = status.upper().strip()
        if norm_status in ["SUCCESS", "COMPLETED"]:
            norm_status = "VERIFIED"
        elif norm_status in ["BLOCKED", "REFUSED"]:
            norm_status = "BLOCKED"
        elif norm_status not in ["REQUESTED", "EXECUTED", "VERIFIED", "FAILED", "CANCELLED", "BLOCKED"]:
            norm_status = "EXECUTED"

        entry = ActionEntry(
            timestamp=time.time(),
            request_id=request_id or "",
            persona=persona or "Jarvis",
            domain=domain or "system",
            action=action or "execute",
            target=target or "",
            status=norm_status,
            summary=summary or "",
            error_reason=error_reason,
            metadata=metadata or {},
        )
        self._entries.append(entry)
        logger.info(
            "[EpisodicLedger] Recorded action [%s/%s]: %s -> %s (%s)",
            domain,
            action,
            target,
            norm_status,
            summary[:60] if summary else "",
        )
        return entry

    def query_action(self, action_keyword: str, target_keyword: str = "") -> Optional[ActionEntry]:
        """Finds the most recent matching action entry."""
        for e in reversed(self._entries):
            if action_keyword.lower() in e.action.lower():
                if not target_keyword or target_keyword.lower() in e.target.lower():
                    return e
        return None

    def get_failures(self) -> List[ActionEntry]:
        """Returns all recorded failed or blocked actions."""
        return [e for e in self._entries if e.status in ["FAILED", "BLOCKED", "CANCELLED"]]

    def get_recent(self, limit: int = 10) -> List[ActionEntry]:
        """Returns the most recent actions in chronological order."""
        return self._entries[-limit:]

    def get_all(self) -> List[ActionEntry]:
        """Returns all entries for the active session."""
        return list(self._entries)

    def summarize_session(self) -> str:
        """Generates a truthful, grounded natural-language summary of session activity."""
        if not self._entries:
            return "In this session, we have had a conversational discussion and answered questions, but no physical tasks or tools have been executed yet."

        action_counts = {}
        highlights = []
        for e in self._entries:
            domain_key = e.domain
            action_counts[domain_key] = action_counts.get(domain_key, 0) + 1
            if e.action in ["play_youtube", "play_youtube_song", "browse_site", "youtube_search", "browser.playback"]:
                highlights.append(f"navigated browser/YouTube to '{e.target}'")
            elif e.action in ["create_file", "write_file"]:
                highlights.append(f"created file '{e.target}'")
            elif e.action in ["move_file"]:
                highlights.append(f"moved file '{e.target}'")
            elif e.action in ["git_status"]:
                highlights.append("checked repository git status")
            elif e.action in ["git_create_branch"]:
                highlights.append(f"created git branch '{e.target}'")
            elif e.action in ["triage_notifications"]:
                highlights.append("checked and triaged recent desktop notifications")
            elif e.action in ["set_reminder"]:
                highlights.append(f"scheduled a reminder for '{e.target}'")
            elif e.action in ["scan_document"]:
                highlights.append(f"performed OCR text extraction on '{e.target}'")
            elif e.action in ["snap_window_left", "snap_window_right"]:
                highlights.append("managed desktop window snapping")
            elif e.action in ["pause_media", "resume_media"]:
                highlights.append(f"{e.action.replace('_', ' ')} in browser")

        # Deduplicate highlights while preserving order
        seen = set()
        deduped = []
        for h in highlights:
            if h not in seen:
                seen.add(h)
                deduped.append(h)

        if not deduped:
            return f"In this session, we performed {len(self._entries)} system and conversational operations."

        summary_text = "In this session, we actually performed the following actions:\n"
        for i, h in enumerate(deduped[:8], 1):
            summary_text += f"{i}. We {h}.\n"
        return summary_text.strip()

    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns recent actions as dicts."""
        return [e.to_dict() for e in self._entries[-limit:]]

    def get_session_summary(self) -> str:
        """Alias for summarize_session."""
        return self.summarize_session()

    def clear(self) -> None:
        """Clears the session ledger."""
        self._entries.clear()


episodic_ledger = EpisodicActionLedger()
