"""Unified Working Context Manager for JARVIS Layer 2.

Maintains live short-term working context across conversational turns:
- Session-sticky active persona (preserves "Friday" across LLM boundaries)
- Active browser context (current URL, page title, media playback state)
- Active window context (focused desktop application)
- Last code snippet context (for follow-up questions and execution)
- Last file operation context (for pronoun and file chaining)
- Pending confirmation transaction (for Two-Gate safety)
- Semantic pronoun & reference resolution
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger("JARVIS.ContextManager")


@dataclass
class BrowserState:
    url: str = ""
    title: str = ""
    media_state: str = "stopped"  # "playing", "paused", "stopped"
    media_target: str = ""
    last_updated: float = field(default_factory=time.time)


@dataclass
class CodeContext:
    code: str = ""
    language: str = "python"
    function_name: str = ""
    variables: List[str] = field(default_factory=list)
    last_updated: float = field(default_factory=time.time)


@dataclass
class FileContext:
    path: str = ""
    name: str = ""
    directory: str = ""
    action: str = ""
    content: str = ""
    last_updated: float = field(default_factory=time.time)


@dataclass
class ConfirmationTransaction:
    action: str
    target: str
    payload: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = 90.0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds


class WorkingContextManager:
    """Central working memory and pronoun resolution engine for JARVIS."""

    def __init__(self):
        self._active_persona: str = "Jarvis"
        self._browser: BrowserState = BrowserState()
        self._code: Optional[CodeContext] = None
        self._file: Optional[FileContext] = None
        self._pending_confirmation: Optional[ConfirmationTransaction] = None
        self._last_git_branch: str = "master"
        self._active_window_title: str = ""
        self._history: List[Dict[str, Any]] = []

    # Persona Stickiness
    @property
    def active_persona(self) -> str:
        return self._active_persona

    def set_persona(self, persona_name: str) -> None:
        if persona_name:
            self._active_persona = persona_name.strip().capitalize()
            logger.info("[ContextManager] Bound session-sticky persona to '%s'", self._active_persona)

    # Browser Tracking
    def update_browser(
        self,
        url: Optional[str] = None,
        title: Optional[str] = None,
        media_state: Optional[str] = None,
        media_target: Optional[str] = None,
    ) -> None:
        if url is not None:
            self._browser.url = url
        if title is not None:
            self._browser.title = title
        if media_state is not None:
            self._browser.media_state = media_state
        if media_target is not None:
            self._browser.media_target = media_target
        self._browser.last_updated = time.time()
        logger.info(
            "[ContextManager] Updated browser context: URL='%s', Title='%s', Media='%s' (%s)",
            self._browser.url,
            self._browser.title,
            self._browser.media_state,
            self._browser.media_target,
        )

    def get_browser(self) -> BrowserState:
        return self._browser

    # Code Tracking
    def set_code(self, code: str, language: str = "python", function_name: str = "", variables: Optional[List[str]] = None) -> None:
        self._code = CodeContext(
            code=code,
            language=language,
            function_name=function_name,
            variables=variables or ["a", "b"],
            last_updated=time.time(),
        )
        logger.info("[ContextManager] Stored working code context: func='%s', len=%d", function_name, len(code))

    def get_code(self) -> Optional[CodeContext]:
        return self._code

    # File Tracking
    def set_file(self, path: str, action: str = "create", content: str = "") -> None:
        p = Path(path)
        self._file = FileContext(
            path=str(p.resolve()),
            name=p.name,
            directory=str(p.parent),
            action=action,
            content=content,
            last_updated=time.time(),
        )
        logger.info("[ContextManager] Stored working file context: '%s' (%s)", p.name, action)

    # Weather Tracking
    def set_weather_context(self, location: str, time_target: str = "now") -> None:
        self._weather_context = {
            "active": True,
            "location": location,
            "time_target": time_target,
            "timestamp": time.time(),
        }
        logger.info("[ContextManager] Stored working weather context: location='%s', time='%s'", location, time_target)

    def get_weather_context(self) -> Dict[str, Any]:
        ctx = getattr(self, "_weather_context", None)
        if not ctx:
            return {"active": False, "location": "Delhi", "time_target": "now"}
        if time.time() - ctx.get("timestamp", 0) > 900:
            ctx["active"] = False
        return ctx

    def clear_file(self) -> None:
        self._file = None

    def get_file(self) -> Optional[FileContext]:
        try:
            from cognitive.world_model import world_model
            wm_target = world_model.state.last_created_file or world_model.state.last_file_path
            if wm_target and Path(wm_target).exists():
                p = Path(wm_target)
                self._file = FileContext(
                    path=str(p.resolve()) if p.is_absolute() else str(p),
                    name=p.name,
                    directory=str(p.parent),
                    action="create" if world_model.state.last_created_file == wm_target else "touch",
                    content=world_model.state.last_created_content or "",
                    last_updated=time.time(),
                )
            elif not wm_target:
                self._file = None
        except Exception:
            pass
        return self._file

    # Confirmation Transaction Management
    def stage_confirmation(self, action: str, target: str, payload: Dict[str, Any]) -> ConfirmationTransaction:
        tx = ConfirmationTransaction(action=action, target=target, payload=payload)
        self._pending_confirmation = tx
        logger.info("[ContextManager] Staged pending confirmation: action='%s', target='%s'", action, target)
        return tx

    def pop_confirmation(self) -> Optional[ConfirmationTransaction]:
        tx = self._pending_confirmation
        if tx and not tx.is_expired:
            self._pending_confirmation = None
            return tx
        self._pending_confirmation = None
        return None

    def has_pending_confirmation(self) -> bool:
        return self._pending_confirmation is not None and not self._pending_confirmation.is_expired

    # Git State
    def set_git_branch(self, branch: str) -> None:
        self._last_git_branch = branch

    def get_git_branch(self) -> str:
        return self._last_git_branch

    # Pronoun & Contextual Reference Resolution
    def resolve_references(self, query: str) -> Dict[str, Any]:
        """Resolves ambiguous pronouns like 'it', 'that file', 'that tab', 'continue' from context."""
        low = query.strip().lower()
        resolved = {
            "is_media_control": False,
            "is_file_op": False,
            "is_code_op": False,
            "is_browser_op": False,
            "resolved_target": None,
            "resolved_action": None,
        }

        # 1. Media Pronoun Resolution ("pause it", "hold on, pause it", "continue", "resume it")
        if any(w in low for w in ["pause it", "hold on, pause", "pause the video", "pause the song", "stop playing"]):
            resolved["is_media_control"] = True
            resolved["resolved_action"] = "pause_media"
            resolved["resolved_target"] = self._browser.media_target or "current video"
            return resolved

        if any(w in low for w in ["continue", "resume", "play it", "go ahead, continue", "unpause"]):
            resolved["is_media_control"] = True
            resolved["resolved_action"] = "resume_media"
            resolved["resolved_target"] = self._browser.media_target or "current video"
            return resolved

        # 2. Browser Tab References ("close that tab", "close this tab", "what page am i looking at")
        if "close that tab" in low or "close this tab" in low or "close tab" in low:
            resolved["is_browser_op"] = True
            resolved["resolved_action"] = "close_tab"
            resolved["resolved_target"] = self._browser.url or "active_tab"
            return resolved

        if "what page" in low or "which page" in low:
            resolved["is_browser_op"] = True
            resolved["resolved_action"] = "query_page"
            resolved["resolved_target"] = self._browser.title or self._browser.url
            return resolved

        # 3. File Context References ("move that file", "delete it", "open that file", "read the file I just created", "show me the file you just created")
        file_target = None
        try:
            from cognitive.world_model import world_model
            wm_target = world_model.state.last_created_file or world_model.state.last_file_path
            if wm_target and Path(wm_target).exists():
                file_target = str(Path(wm_target).resolve())
            elif not wm_target:
                self._file = None
        except Exception:
            pass

        if not file_target:
            ctx_f = self.get_file()
            if ctx_f and ctx_f.path and Path(ctx_f.path).exists():
                file_target = ctx_f.path

        if file_target and any(p in low for p in ["that file", "this file", "the file", "move it", "delete it", "open it", "read it", "show it", "just created", "you created", "i created", "just made", "you made"]):
            resolved["is_file_op"] = True
            resolved["resolved_target"] = file_target
            if any(w in low for w in ["move", "transfer", "relocate"]):
                resolved["resolved_action"] = "move_file"
            elif any(w in low for w in ["delete", "remove", "erase", "trash"]):
                resolved["resolved_action"] = "delete_file"
            elif any(w in low for w in ["read", "open", "show", "view", "cat", "inspect"]):
                resolved["resolved_action"] = "read_file"
            return resolved

        # 4. Code Follow-Up & Execution References ("what happens if b is zero?", "run it with 5")
        if self._code and ("run it" in low or "execute it" in low):
            resolved["is_code_op"] = True
            resolved["resolved_action"] = "execute_code"
            resolved["resolved_target"] = self._code.code
            return resolved

        if self._code and any(k in low for k in ["if b is zero", "b is 0", "if a is zero", "what if b is"]):
            resolved["is_code_op"] = True
            resolved["resolved_action"] = "code_explanation"
            resolved["resolved_target"] = self._code.code
            return resolved

        return resolved

    def set_working_memory_item(self, key: str, value: Any) -> None:
        if not hasattr(self, "_working_memory"):
            self._working_memory = {}
        self._working_memory[key] = value

    def get_working_memory(self) -> Dict[str, Any]:
        if not hasattr(self, "_working_memory"):
            self._working_memory = {}
        return self._working_memory

    def clear_session(self) -> None:
        """Clears all session and working context."""
        self._browser = BrowserState()
        self._code = None
        self._file = None
        self._active_window = ""
        self._pending_confirmation = None
        self._last_weather_context = {}
        self._working_memory = {}
        logger.info("[ContextManager] Working session context cleared.")


context_manager = WorkingContextManager()
