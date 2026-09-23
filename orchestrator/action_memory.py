"""Session Action Memory Manager for JARVIS Layer 2.

Tracks the most recent actions, active browser tabs, media playback sessions,
and created artifacts across conversational turns. Enables symmetric follow-up
commands ("stop it", "pause that", "resume", "play again", "close it", "undo that")
by maintaining live references to active browser pages without requiring
hardcoded per-app stop phrase lists.
"""

import time
import logging
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger("JARVIS.ActionMemory")


class ActionMemoryManager:
    """Manages active session context, live browser page references, and recent actions for symmetrical start/stop/resume/undo."""

    def __init__(self):
        self._last_action: Optional[Dict[str, Any]] = None
        self._active_web_session: Optional[Dict[str, Any]] = None
        self._active_media_session: Optional[Dict[str, Any]] = None
        self._live_page_ref: Optional[Any] = None
        self._live_browser_agent: Optional[Any] = None

    def record_action(
        self,
        action_type: str,
        target: str,
        agent: str,
        details: Optional[Dict[str, Any]] = None,
        undo_handler: Optional[Callable[[], Any]] = None,
    ) -> None:
        """Records an action in short-term session memory."""
        record = {
            "action_type": action_type,
            "target": target,
            "agent": agent,
            "details": details or {},
            "timestamp": time.time(),
        }
        self._last_action = record

        if action_type in ["web_navigation", "browser_task", "open_site", "web_action"]:
            self._active_web_session = record
        elif action_type in ["media_playback", "song_playback", "video_playback", "chained_play"]:
            self._active_media_session = record
            self._active_web_session = record

        logger.info(
            "[ActionMemory] Recorded action: type='%s', target='%s', agent='%s'",
            action_type, target, agent
        )

    def set_live_page(
        self,
        page: Any,
        agent: Optional[Any] = None,
        title: str = "",
        url: str = "",
        is_media: bool = False,
        query: str = "",
        action_type: str = "web_action"
    ) -> None:
        """Stores a live reference to an active browser Page object and its controlling agent."""
        self._live_page_ref = page
        if agent is not None:
            self._live_browser_agent = agent

        rec = {
            "url": url or (getattr(page, "url", "") if page else ""),
            "title": title,
            "action_type": "media_playback" if is_media else action_type,
            "query": query,
            "is_playing": is_media,
            "has_live_page": page is not None,
            "timestamp": time.time(),
        }
        self._active_web_session = rec
        if is_media:
            self._active_media_session = rec
        self._last_action = rec

        logger.info(
            "[ActionMemory] Registered LIVE browser page reference (title='%s', is_media=%s)",
            title, is_media
        )

    def get_live_page(self) -> Optional[Any]:
        """Returns the active live Playwright Page instance if still open."""
        if self._live_page_ref is not None:
            try:
                if hasattr(self._live_page_ref, "is_closed") and self._live_page_ref.is_closed():
                    self._live_page_ref = None
                    return None
                return self._live_page_ref
            except Exception:
                self._live_page_ref = None
                return None
        return None

    def has_live_page(self) -> bool:
        """Checks whether an active, unclosed browser page is currently referenced."""
        return self.get_live_page() is not None

    def get_last_action(self) -> Optional[Dict[str, Any]]:
        """Returns the most recent action record."""
        return self._last_action

    def get_active_media_session(self) -> Optional[Dict[str, Any]]:
        """Returns the active media playback session if recent (< 15 minutes)."""
        if self._active_media_session:
            if time.time() - self._active_media_session.get("timestamp", 0) < 900:
                return self._active_media_session
        return None

    def get_active_web_session(self) -> Optional[Dict[str, Any]]:
        """Returns the active web session if recent (< 15 minutes)."""
        if self._active_web_session:
            if time.time() - self._active_web_session.get("timestamp", 0) < 900:
                return self._active_web_session
        return None

    def record_web_session(
        self,
        url: str,
        title: str,
        site: str = "web",
        action_type: str = "web_action",
        query: str = "",
        screenshot_path: Optional[str] = None,
        page: Optional[Any] = None,
        agent: Optional[Any] = None,
    ) -> None:
        """Records an active web session with optional live page reference."""
        is_playing = action_type in ["media_playback", "youtube_playback", "chained_play"] or "youtube" in site
        if page is not None:
            self._live_page_ref = page
        if agent is not None:
            self._live_browser_agent = agent

        rec = {
            "url": url,
            "title": title,
            "site": site,
            "action_type": action_type,
            "query": query,
            "screenshot_path": screenshot_path,
            "is_playing": is_playing,
            "has_live_page": self._live_page_ref is not None,
            "timestamp": time.time(),
        }
        self._active_web_session = rec
        if is_playing:
            self._active_media_session = rec
        self._last_action = rec

    def update_media_playback_state(self, is_playing: bool) -> None:
        """Updates playing state of the active media session."""
        if self._active_media_session:
            self._active_media_session["is_playing"] = is_playing
            self._active_media_session["timestamp"] = time.time()
        if self._active_web_session:
            self._active_web_session["is_playing"] = is_playing

    def pause_active_media(self) -> Dict[str, Any]:
        """Dispatches pause directly to the live page reference or controlling agent."""
        page = self.get_live_page()
        stopped_count = 0

        # Method 1: Execute on live page reference directly
        if page is not None:
            try:
                res = page.evaluate("""() => {
                    let stopped = 0;
                    const vids = document.querySelectorAll('video, audio');
                    for (const v of vids) {
                        if (!v.paused) {
                            v.pause();
                            stopped++;
                        }
                    }
                    const yt = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
                    if (yt && typeof yt.pauseVideo === 'function') {
                        yt.pauseVideo();
                        stopped++;
                    }
                    return stopped;
                }""")
                stopped_count = res or 0
                logger.info("[ActionMemory] Dispatched pause directly to live page (stopped_count=%d)", stopped_count)
            except Exception as e:
                logger.warning("[ActionMemory] Direct pause on live page failed: %s", e)

        # Method 2: Delegate to live browser agent if direct page evaluation did not execute
        if stopped_count == 0 and self._live_browser_agent and hasattr(self._live_browser_agent, "stop_active_media"):
            try:
                agent_res = self._live_browser_agent.stop_active_media()
                stopped_count = agent_res.get("stopped_count", 1)
            except Exception as e:
                logger.warning("[ActionMemory] Agent stop_active_media failed: %s", e)

        self.update_media_playback_state(is_playing=False)
        msg = f"Paused playback in active session." if stopped_count > 0 else "Paused active media."
        return {
            "success": True,
            "action": "pause_media",
            "stopped_count": stopped_count,
            "response": msg,
            "output": msg
        }

    def resume_active_media(self) -> Dict[str, Any]:
        """Dispatches resume/play directly to the live page reference or controlling agent."""
        page = self.get_live_page()
        resumed_count = 0

        # Method 1: Execute on live page reference directly
        if page is not None:
            try:
                res = page.evaluate("""() => {
                    let resumed = 0;
                    const yt = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
                    if (yt && typeof yt.playVideo === 'function') {
                        try { yt.unMute(); } catch(e){}
                        yt.playVideo();
                        resumed++;
                    }
                    const vids = document.querySelectorAll('video, audio');
                    for (const v of vids) {
                        if (v.paused) {
                            v.muted = false;
                            v.play().catch(() => {});
                            resumed++;
                        }
                    }
                    return resumed;
                }""")
                resumed_count = res or 0
                logger.info("[ActionMemory] Dispatched resume directly to live page (resumed_count=%d)", resumed_count)
            except Exception as e:
                logger.warning("[ActionMemory] Direct resume on live page failed: %s", e)

        # Method 2: Delegate to live browser agent if available
        if resumed_count == 0 and self._live_browser_agent and hasattr(self._live_browser_agent, "resume_active_media"):
            try:
                agent_res = self._live_browser_agent.resume_active_media()
                resumed_count = agent_res.get("resumed_count", 1)
            except Exception as e:
                logger.warning("[ActionMemory] Agent resume_active_media failed: %s", e)

        self.update_media_playback_state(is_playing=True)
        msg = "Resumed playback in active session." if resumed_count > 0 else "Resumed playback."
        return {
            "success": True,
            "action": "resume_media",
            "resumed_count": resumed_count,
            "response": msg,
            "output": msg
        }

    def close_active_page(self) -> Dict[str, Any]:
        """Dispatches close directly to the live page reference."""
        page = self.get_live_page()
        closed = False

        if page is not None:
            try:
                page.close()
                closed = True
                logger.info("[ActionMemory] Closed active live page reference.")
            except Exception as e:
                logger.warning("[ActionMemory] Error closing live page: %s", e)

        if not closed and self._live_browser_agent and hasattr(self._live_browser_agent, "close_active_page"):
            try:
                self._live_browser_agent.close_active_page()
                closed = True
            except Exception as e:
                logger.warning("[ActionMemory] Agent close_active_page failed: %s", e)

        self.clear_active_session()
        msg = "Closed active browser tab." if closed else "No active browser tab was open."
        return {
            "success": True,
            "action": "close_page",
            "response": msg,
            "output": msg
        }

    def get_active_session(self) -> Optional[Dict[str, Any]]:
        """Returns the active media or web session if active within the last 15 minutes."""
        now = time.time()
        if self._active_media_session and (now - self._active_media_session.get("timestamp", 0) < 900):
            return self._active_media_session
        if self._active_web_session and (now - self._active_web_session.get("timestamp", 0) < 900):
            return self._active_web_session
        return self._last_action

    def clear_active_session(self) -> None:
        """Clears both media and web active sessions and drops live page reference."""
        self._active_media_session = None
        self._active_web_session = None
        self._live_page_ref = None

    def clear_active_media(self) -> None:
        """Clears the active media state after stopping."""
        self._active_media_session = None

    def clear_active_web(self) -> None:
        """Clears the active web session after closing."""
        self._active_web_session = None
        self._live_page_ref = None


# Global singleton instance
action_memory = ActionMemoryManager()
action_memory_manager = action_memory
