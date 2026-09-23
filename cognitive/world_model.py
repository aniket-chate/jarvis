"""JARVIS World Model & Context Management (Cognitive Core - Stage 2).

Maintains the internal objective representation of reality:
- User (Identity, Relationships, Preferences)
- Desktop Environment (Active Window, Process, Display)
- Browser Environment (CDP Tab list, Active URL, Title, Media Playback State)
- Workspace & Code Environment (Active Files, Recent Snippets, Git Branches)
- Active Workflows & Tasks (Pending goals, confirmations, background monitors)
- JIT Reality Sampling (Live Win32 and CDP probes to prevent hallucinated states)
- Deep Reference & Pronoun Resolver ("it", "that tab", "the file", "continue", "switch back")
"""

from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.request

logger = logging.getLogger("JARVIS.Cognitive.WorldModel")


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class WorldState:
    user_name: str = "User"
    active_persona: str = "Jarvis"  # Sticky across LLM inferences
    active_window_title: str = ""
    active_window_process: str = ""
    active_browser_tab_id: Optional[str] = None
    active_browser_url: str = ""
    active_browser_title: str = ""
    is_media_playing: bool = False
    media_player_title: str = ""
    last_file_path: Optional[str] = None
    last_created_file: Optional[str] = None
    last_created_content: Optional[str] = None
    last_code_snippet: Optional[str] = None
    last_code_language: str = "python"
    active_git_branch: str = "main"
    previous_git_branch: Optional[str] = None
    pending_confirmation: Optional[Dict[str, Any]] = None
    social_context: Optional[Dict[str, Any]] = None
    active_tasks: List[Dict[str, Any]] = field(default_factory=list)
    recent_actions: List[Dict[str, Any]] = field(default_factory=list)
    last_location: str = ""
    last_weather_query: Optional[Dict[str, Any]] = None
    last_news_topic: Optional[str] = None
    last_sampled_timestamp: float = 0.0


class WorldModel:
    """Live internal model of the user's world, context, and environment."""

    def __init__(self):
        self.state = WorldState()
        self._load_user_profile()

    def _load_user_profile(self):
        profile_path = PROJECT_ROOT / "memory" / "user_profile.json"
        if profile_path.exists():
            try:
                data = json.loads(profile_path.read_text(encoding="utf-8"))
                self.state.user_name = data.get("owner_name", "User")
            except Exception as e:
                logger.debug("[WorldModel] User profile read error: %s", e)

    def update_social_context(self, context_data: Dict[str, Any]):
        """Integrates perceptual emotion and social context without overriding intent."""
        self.state.social_context = context_data
        logger.info(
            "[WorldModel] Updated social context: sentiment='%s', urgent=%s, conf=%.2f",
            context_data.get("sentiment"),
            context_data.get("is_urgent"),
            context_data.get("confidence", 0.0),
        )

    def set_persona(self, persona_name: str):
        """Sets sticky persona across all session boundaries."""
        clean = "Friday" if "friday" in persona_name.lower() else "Jarvis"
        self.state.active_persona = clean
        logger.info("[WorldModel] Active persona sticky set to: '%s'", clean)

    def get_persona(self) -> str:
        return self.state.active_persona

    def update_code_context(self, snippet: str, language: str = "python"):
        self.state.last_code_snippet = snippet
        self.state.last_code_language = language
        logger.info("[WorldModel] Updated active code context (%d chars)", len(snippet))

    def update_file_context(self, file_path: str, content: Optional[str] = None, is_creation: bool = False):
        self.state.last_file_path = file_path
        if is_creation:
            self.state.last_created_file = file_path
            if content:
                self.state.last_created_content = content
        logger.info("[WorldModel] Updated active file context: %s (created=%s)", file_path, is_creation)
        try:
            from orchestrator.context_manager import context_manager
            context_manager.set_file(file_path, action="create" if is_creation else "touch", content=content or "")
        except Exception:
            pass

    def update_media_state(self, is_playing: bool, title: str = ""):
        self.state.is_media_playing = is_playing
        if title:
            self.state.media_player_title = title
        logger.info("[WorldModel] Media state updated: playing=%s, title='%s'", is_playing, title)

    def update_git_branch(self, branch_name: str):
        if self.state.active_git_branch != branch_name:
            self.state.previous_git_branch = self.state.active_git_branch
            self.state.active_git_branch = branch_name
            logger.info("[WorldModel] Git branch updated: active='%s', previous='%s'", branch_name, self.state.previous_git_branch)

    def stage_confirmation(self, transaction: Dict[str, Any]):
        self.state.pending_confirmation = transaction

    def clear_confirmation(self):
        self.state.pending_confirmation = None

    def record_action_digest(self, action_digest: Dict[str, Any]):
        self.state.recent_actions.append(action_digest)
        if len(self.state.recent_actions) > 10:
            self.state.recent_actions = self.state.recent_actions[-10:]

    def sample_jit_reality(self):
        """Just-In-Time Reality Sampling to ensure internal model matches ground truth."""
        t_now = time.time()
        if t_now - self.state.last_sampled_timestamp < 1.5:
            return

        self.state.last_sampled_timestamp = t_now

        # 1. Sample Chrome CDP state (Port 9222)
        try:
            req = urllib.request.Request("http://127.0.0.1:9222/json/list", headers={"User-Agent": "JARVIS-WorldModel"})
            with urllib.request.urlopen(req, timeout=0.8) as resp:
                tabs = json.loads(resp.read().decode("utf-8"))
                pages = [t for t in tabs if t.get("type") == "page"]
                if pages:
                    active = pages[-1]
                    self.state.active_browser_tab_id = active.get("id")
                    self.state.active_browser_url = active.get("url", "")
                    self.state.active_browser_title = active.get("title", "")
        except Exception:
            pass

        # 3. Sample Real Git Branch (from filesystem .git/HEAD)
        try:
            curr = Path(r"d:\assignment\JARVIS")
            git_head = None
            for p in [curr] + list(curr.parents):
                candidate = p / ".git" / "HEAD"
                if candidate.exists():
                    git_head = candidate
                    break
            if git_head and git_head.exists():
                head_content = git_head.read_text(encoding="utf-8").strip()
                if head_content.startswith("ref: refs/heads/"):
                    self.state.active_git_branch = head_content.replace("ref: refs/heads/", "").strip()
        except Exception:
            pass

    def probe_file(self, file_path: str) -> Dict[str, Any]:
        """Empirically probes file existence, size, and modification state on disk."""
        p = Path(file_path)
        if not p.is_absolute():
            p = (Path(r"d:\assignment\JARVIS\workspace") / file_path).resolve()
        exists = p.exists() and p.is_file()
        if not exists:
            return {"path": str(p), "exists": False, "size_bytes": 0, "mtime": 0.0, "sha256": None}
        import hashlib
        stat = p.stat()
        hasher = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return {
            "path": str(p),
            "exists": True,
            "size_bytes": stat.st_size,
            "mtime": stat.st_mtime,
            "sha256": hasher.hexdigest(),
        }

    def probe_git(self, repo_path: Optional[str] = None) -> Dict[str, Any]:
        """Empirically probes repository branch, HEAD commit, and working tree."""
        root = Path(repo_path) if repo_path else Path(r"d:\assignment\JARVIS")
        git_head = None
        for p in [root] + list(root.parents):
            candidate = p / ".git" / "HEAD"
            if candidate.exists():
                git_head = candidate
                root = p
                break
        if not git_head or not git_head.exists():
            return {"is_git_repo": False, "branch": "unknown", "head_commit": None}
        content = git_head.read_text(encoding="utf-8").strip()
        branch = "detached"
        if content.startswith("ref: refs/heads/"):
            branch = content.replace("ref: refs/heads/", "").strip()
        return {
            "is_git_repo": True,
            "branch": branch,
            "head_ref": content,
            "repo_root": str(root),
        }

    def probe_process(self, process_name: str) -> Dict[str, Any]:
        """Empirically probes whether a process is running on the host OS."""
        import psutil
        p_lower = process_name.lower()
        matched = []
        for p in psutil.process_iter(['pid', 'name']):
            try:
                name = (p.info.get('name') or '').lower()
                if p_lower in name:
                    matched.append({"pid": p.info['pid'], "name": p.info['name']})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return {
            "process_name": process_name,
            "is_running": len(matched) > 0,
            "instances": matched,
            "count": len(matched),
        }

    def probe_browser(self) -> Dict[str, Any]:
        """Empirically probes Chrome CDP state on port 9222."""
        try:
            req = urllib.request.Request("http://127.0.0.1:9222/json/list", headers={"User-Agent": "JARVIS-WorldModel"})
            with urllib.request.urlopen(req, timeout=1.2) as resp:
                tabs = json.loads(resp.read().decode("utf-8"))
                pages = [t for t in tabs if t.get("type") == "page"]
                active = pages[-1] if pages else None
                return {
                    "connected": True,
                    "total_tabs": len(pages),
                    "active_tab": {
                        "id": active.get("id") if active else None,
                        "url": active.get("url") if active else None,
                        "title": active.get("title") if active else None,
                    } if active else None,
                }
        except Exception as e:
            return {"connected": False, "total_tabs": 0, "active_tab": None, "error": str(e)}

    def probe_window(self) -> Dict[str, Any]:
        """Empirically probes the active Win32 foreground or prominent desktop window."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            title = ""
            if hwnd:
                length = user32.GetWindowTextLengthW(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value

            # If foreground is 0 or untitled (e.g. background execution context), inspect active desktop windows
            if not hwnd or not title.strip():
                from agents.system_control_agent import system_control_agent
                wins = system_control_agent.list_windows()
                if wins:
                    cand = None
                    for w in wins:
                        if any(k in w["title"].lower() for k in ["chrome", "assignment", "antigravity", "code", "notepad", "terminal"]):
                            cand = w
                            break
                    if not cand:
                        cand = wins[0]
                    hwnd = cand["hwnd"]
                    title = cand["title"]

            if hwnd and title:
                return {
                    "has_window": True,
                    "hwnd": hwnd,
                    "title": title,
                }
            return {"has_window": False, "title": "", "hwnd": 0}
        except Exception as e:
            return {"has_window": False, "title": "", "error": str(e)}


    def resolve_reference(self, utterance: str) -> Dict[str, Any]:
        """Resolves pronouns and references ('it', 'that tab', 'the file', 'run it with 5') to concrete entities."""
        self.sample_jit_reality()
        low = utterance.lower().strip()
        resolved = {}


        # Tab references ("that tab", "the tab", "close that tab")
        if re.search(r"\b(that\s+tab|this\s+tab|the\s+tab)\b", low):
            resolved["tab_id"] = self.state.active_browser_tab_id
            resolved["tab_url"] = self.state.active_browser_url
            resolved["tab_title"] = self.state.active_browser_title

        # Code execution references ("run it with 5", "run it", "explain it")
        if "run it" in low or any(k in low for k in ["execute it", "run this", "explain it"]):
            if self.state.last_code_snippet:
                resolved["code_snippet"] = self.state.last_code_snippet
                resolved["code_language"] = self.state.last_code_language

                # Check for arguments e.g. "with 5"
                m_arg = re.search(r"with\s+([a-zA-Z0-9_\.\-]+)", low)
                if m_arg:
                    resolved["code_arg"] = m_arg.group(1).strip()

        # Media playback references ("pause it", "resume it", "continue", "switch to the other one")
        if any(phrase in low for phrase in ["pause it", "hold on, pause", "continue", "resume it", "resume playback", "pause the video"]):
            resolved["media_target"] = "active_browser_player"
            resolved["tab_id"] = self.state.active_browser_tab_id

        if "the other one" in low or "switch to the other" in low:
            resolved["target_context"] = "alternate_tab_or_window"
            resolved["tab_id"] = self.state.active_browser_tab_id

        # Branch references ("switch back", "delete that temporary branch")
        if "switch back" in low and self.state.previous_git_branch:
            resolved["git_target_branch"] = self.state.previous_git_branch
        elif "that temporary branch" in low:
            resolved["git_target_branch"] = "temp-test-branch"

        # File references ("the created file", "the one I just created", "the file you created", "that file", "the file", "it")
        file_ref_match = re.search(
            r"\b(?:the\s+)?(?:created\s+file|file\s+(?:you|i)\s+(?:just\s+)?(?:created|made)|(?:one|file)\s+(?:you|i)\s+(?:just\s+)?(?:created|made)|the\s+one\s+(?:i|you)\s+(?:just\s+)?(?:created|made)|that\s+file|this\s+file|the\s+file|that\s+one|this\s+one)\b",
            low,
        )
        verb_file_ref = bool(
            re.search(r"\b(?:open|read|view|show|cat|inspect|examine|summarize|move|transfer|delete|remove|erase)\s+(?:it|that|this)\b", low)
        ) or any(k in low for k in ["delete the file", "remove the file", "open the file", "read the file", "check the file"])
        
        if (file_ref_match or verb_file_ref):
            target_f = self.state.last_created_file or self.state.last_file_path
            if target_f:
                resolved["file_path"] = target_f

        # Content references ("save all this information inside it", "with this information", "these notes")
        if re.search(r"\b(?:all\s+this\s+information|this\s+information|all\s+the\s+information|these\s+notes|the\s+summary|the\s+search\s+results)\b", low):
            if self.state.last_created_content:
                resolved["content"] = self.state.last_created_content
            elif self.state.recent_actions:
                for act in reversed(self.state.recent_actions):
                    res = act.get("result") or act.get("response") or ""
                    if isinstance(res, str) and len(res.strip()) > 10:
                        resolved["content"] = res.strip()
                        break

        # Code references ("fix it", "run it again", "what happens if the input is")
        if any(k in low for k in ["fix it", "run it again", "input is", "if the input is"]):
            if self.state.last_code_snippet:
                resolved["code_snippet"] = self.state.last_code_snippet
                resolved["code_language"] = self.state.last_code_language

        # Real-time Weather Context follow-ups ("what about tomorrow", "will it rain tonight", "what about mumbai")
        if re.search(r"\b(?:what\s+about|how\s+about)\s+tomorrow\b", low) or "weather tomorrow" in low:
            resolved["weather_location"] = self.state.last_location
            resolved["weather_time_target"] = "tomorrow"
        elif re.search(r"\b(?:will\s+it\s+rain\s+tonight|what\s+about\s+tonight)\b", low):
            resolved["weather_location"] = self.state.last_location
            resolved["weather_time_target"] = "tonight"
        elif re.search(r"\b(?:what\s+about|how\s+about)\s+([a-zA-Z\s]+)\b", low):
            m_city = re.search(r"\b(?:what\s+about|how\s+about)\s+([a-zA-Z\s]+)$", low)
            if m_city:
                cand = m_city.group(1).strip().title()
                if cand not in ["It", "This", "That", "Tomorrow", "Tonight", "Yesterday"]:
                    resolved["weather_location"] = cand

        # Real-time News Context follow-ups ("what changed since this morning", "give me the latest news")
        if "what changed since this morning" in low or "since this morning" in low:
            resolved["news_topic"] = self.state.last_news_topic or "general"
            resolved["news_time_filter"] = "today"

        return resolved

    resolve_pronoun = resolve_reference

    def get_observation(self) -> Dict[str, Any]:
        """Returns observation snapshot of physical and cognitive reality."""
        return self.get_context_snapshot()

    def get_context_snapshot(self) -> Dict[str, Any]:
        """Returns normalized context snapshot for Cognition."""
        self.sample_jit_reality()
        return {
            "user": self.state.user_name,
            "persona": self.state.active_persona,
            "active_window": {
                "title": self.state.active_window_title,
                "process": self.state.active_window_process,
            },
            "active_browser": {
                "tab_id": self.state.active_browser_tab_id,
                "url": self.state.active_browser_url,
                "title": self.state.active_browser_title,
                "is_playing": self.state.is_media_playing,
                "media_title": getattr(self.state, "media_player_title", ""),
            },
            "last_file": self.state.last_file_path,
            "last_code": {
                "snippet": self.state.last_code_snippet,
                "language": self.state.last_code_language,
            } if self.state.last_code_snippet else None,
            "git": {
                "active_branch": self.state.active_git_branch,
                "previous_branch": self.state.previous_git_branch,
            },
            "last_location": self.state.last_location,
            "last_news_topic": self.state.last_news_topic,
            "last_weather_query": self.state.last_weather_query,
            "pending_confirmation": self.state.pending_confirmation,
            "social_context": self.state.social_context,
            "recent_actions": self.state.recent_actions[-5:],
        }


world_model = WorldModel()
