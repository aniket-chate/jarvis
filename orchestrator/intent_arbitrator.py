"""Semantic Intent Arbitrator for JARVIS Layer 2.

Determines the structured semantic meaning FIRST, eliminating fragile keyword-first
regex collisions and ambiguous pronoun failures.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, Any, Optional, List, Sequence
from pathlib import Path
import copy
import unicodedata
from orchestrator.context_manager import context_manager
from memory.episodic_ledger import episodic_ledger

logger = logging.getLogger("JARVIS.IntentArbitrator")


@dataclass
class StructuredIntent:
    domain: str            # "browser", "scheduler", "code", "file", "git", "system", "ocr", "communication", "chat"
    action: str            # specific action name
    target: str            # primary target/argument
    params: Dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    confidence: float = 1.0
    raw_query: str = ""
    needs_clarification: bool = False
    clarification_prompt: str = ""
    source: str = "legacy"


@dataclass
class IntentCandidate:
    intent: StructuredIntent
    score: float


class IntentProvider:
    def __init__(self, name, detect):
        self.name = name
        self.detect = detect


class IntentArbitrator:
    """Side-effect-free semantic classifier with injectable capability providers."""

    def __init__(self, context=None, providers=None):
        self.context = context or context_manager
        self.providers = list(providers) if providers is not None else [
            IntentProvider("confirmation", self._provider_confirmation),
            IntentProvider("weather", self._provider_weather),
            IntentProvider("git", self._provider_git),
            IntentProvider("communication", self._provider_communication),
            IntentProvider("code_followup", self._provider_code_followup),
            IntentProvider("telemetry", self._provider_telemetry),
            IntentProvider("browser", self._provider_browser),
            IntentProvider("scheduler", self._provider_scheduler),
            IntentProvider("file", self._provider_file),
            IntentProvider("file_reference", self._provider_file_reference),
        ]

    @staticmethod
    def normalize(text):
        return " ".join(unicodedata.normalize("NFKC", str(text or "")).split()).strip()

    @staticmethod
    def _make(text, domain, action, target="", params=None, confidence=.8, confirmation=False, source="provider"):
        return StructuredIntent(domain, action, target, dict(params or {}), confirmation, confidence, text, False, "", source)

    @staticmethod
    def _clarify(text, domain, prompt, params=None, confidence=.98, source="provider"):
        return StructuredIntent(domain, "clarification", "", {"query": prompt, **(params or {})}, False, confidence, text, True, prompt, source)

    def arbitrate(self, text: str) -> StructuredIntent:
        clean = self.normalize(text)
        if not clean:
            return self._clarify(clean, "chat", "What would you like JARVIS to do?", source="normalization")
        candidates = []
        for provider in self.providers:
            try:
                candidate = provider.detect(clean)
                if candidate:
                    candidate.intent.source = provider.name
                    candidates.append(candidate)
            except Exception as exc:
                logger.warning("[IntentArbitrator] Provider %s failed: %s", provider.name, exc)
        if candidates:
            return max(candidates, key=lambda item: (item.score, item.intent.confidence)).intent
        intent = self._legacy_arbitrate(clean)
        if not intent.raw_query:
            intent.raw_query = clean
        if not intent.source:
            intent.source = "legacy"
        return intent

    def _provider_confirmation(self, text):
        tx = getattr(self.context, "get_pending_confirmation", lambda: None)()
        if not tx or getattr(tx, "is_expired", False):
            return None
        low = re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()
        if low in {"yes", "yes do it", "do it", "confirm", "proceed", "sure", "approve", "approved", "go ahead", "ok", "okay"}:
            payload = copy.deepcopy(getattr(tx, "payload", {}) or {})
            payload["_confirmation"] = {"domain": getattr(tx, "domain", ""), "action": getattr(tx, "action", ""), "target": getattr(tx, "target", ""), "payload": copy.deepcopy(payload), "original_request": getattr(tx, "original_request", ""), "resolution": "confirm"}
            return IntentCandidate(self._make(text, getattr(tx, "domain", "") or "system", "confirmed_" + getattr(tx, "action", "action"), getattr(tx, "target", ""), payload, 1.0, source="confirmation"), 1.0)
        if low in {"no", "cancel", "abort", "nevermind", "never mind", "dont", "don't"} or (low == "stop" and (getattr(tx, "payload", {}) or {}).get("allow_stop_cancel")):
            return IntentCandidate(self._make(text, "system", "cancel_action", getattr(tx, "target", ""), {"user_cancelled": True}, 1.0, source="confirmation"), 1.0)
        return None

    def _provider_weather(self, text):
        low = text.lower()
        if "whether" in low and (re.search(r"\bwhether\s+(?:to|or|or not)\b", low) or re.search(r"\b(?:know|wonder|decide|choose|unsure|doubt)\s+whether\b", low)):
            return None
        if not re.search(r"\b(?:weather|forecast|temperature|rain|raining)\b", low):
            return None
        location = ""
        match = re.search(r"\b(?:in|for|at)\s+(.+?)(?:\s+(?:today|tomorrow|tonight|now))?\s*[?!.,]*$", text, re.I)
        if match:
            location = match.group(1).strip(" .,!?'\"")
        if not location:
            ctx = getattr(self.context, "get_weather_context", lambda: {})()
            if ctx.get("active"):
                location = str(ctx.get("location") or "").strip()
        if not location:
            location = str(getattr(self.context, "get_configured_location", lambda: "")() or "").strip()
        when = "tomorrow" if "tomorrow" in low else "tonight" if "tonight" in low else "today" if "today" in low else "now"
        if not location:
            return IntentCandidate(self._clarify(text, "info", "Which location should I check?", {"time_target": when}, source="weather"), .98)
        return IntentCandidate(self._make(text, "info", "get_weather", location, {"location": location, "time_target": when, "action": "get_weather"}, .97, source="weather"), .97)

    def _provider_git(self, text):
        low = text.lower()
        if "git status" in low:
            return IntentCandidate(self._make(text, "git", "status", "local_repo", confidence=.96, source="git"), .96)
        if re.search(r"\b(?:create|make)\s+(?:a\s+)?(?:git\s+)?branch\b", low):
            match = re.search(r"\b(?:called|named)\s+([A-Za-z0-9._/-]+)\b", text, re.I)
            if not match:
                return IntentCandidate(self._clarify(text, "git", "What should I name the new branch?", source="git"), .98)
            branch = match.group(1).strip()
            return IntentCandidate(self._make(text, "git", "create_branch", branch, {"branch_name": branch}, .98, source="git"), .98)
        if re.fullmatch(r"(?:switch|go)\s+back", low):
            previous = getattr(self.context, "get_previous_git_branch", lambda: "")()
            if not previous:
                return IntentCandidate(self._clarify(text, "git", "Which branch should I switch back to?", source="git"), .98)
            return IntentCandidate(self._make(text, "git", "switch_branch", previous, {"branch_name": previous}, .98, source="git"), .98)
        return None

    def _provider_communication(self, text):
        low = text.lower()
        if not re.search(r"\b(?:whatsapp|email|mail|message|sms|text)\b", low):
            return None
        match = re.search(r"\b(?:to|tell|message|contact|email)\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?=\s+(?:saying|with|that|body|message)\b|$)", text, re.I)
        if not match:
            match = re.search(r"\b(?:to|tell|message|contact)\s+((?:[A-Za-z][A-Za-z.'-]*\s+){0,5}[A-Za-z][A-Za-z.'-]*)(?=\s+(?:saying|with|that|body|message)\b|$)", text, re.I)
        recipient = match.group(1).strip(" ,.:;") if match else ""
        if not recipient:
            return IntentCandidate(self._clarify(text, "communication", "Who should receive the message?", source="communication"), .98)
        body = re.search(r"\b(?:saying|message|body|with text|that)\s*[:,-]?\s*[\"'](.+?)[\"']\s*$", text, re.I|re.S)
        if not body:
            body = re.search(r"\b(?:saying|message|body|with text|that)\s*[:,-]?\s*(.+)$", text, re.I|re.S)
        message = body.group(1).strip().strip("\"'") if body else ""
        if not message and "draft" not in low:
            return IntentCandidate(self._clarify(text, "communication", "What message should I send?", source="communication"), .98)
        action = "draft_email" if re.search(r"\b(?:email|mail)\b", low) else "draft_message"
        return IntentCandidate(self._make(text, "communication", action, recipient, {"recipient": recipient, "to": recipient, "message": message, "body": message}, .95, source="communication"), .95)

    def _provider_code_followup(self, text):
        if not re.search(r"\b(?:run|execute|test|try)\s+(?:it|this)\b", text, re.I):
            return None
        code_ctx = getattr(self.context, "get_code", lambda: None)()
        if not code_ctx or not getattr(code_ctx, "code", ""):
            return IntentCandidate(self._clarify(text, "code", "Which code should I run?", source="code_followup"), .96)
        match = re.search(r"\bwith\s+(.+)$", text, re.I)
        params = {"code": code_ctx.code, "query": text}
        if match:
            params["input_arg"] = match.group(1).strip()
        return IntentCandidate(self._make(text, "code", "execute_code", code_ctx.code, params, .96, source="code_followup"), .96)

    def _provider_telemetry(self, text):
        metrics = {"cpu":{"cpu"}, "ram":{"ram"}, "memory":{"memory","mem"}, "disk":{"disk","storage"}, "network":{"network","net"}, "battery":{"battery"}, "temperature":{"temperature","temp"}, "uptime":{"uptime"}, "time":{"time","clock"}}
        found = [key for key, aliases in metrics.items() if any(re.search(r"\b"+re.escape(alias)+r"\b", text.lower()) for alias in aliases)]
        if not found:
            return None
        return IntentCandidate(self._make(text, "system", "multi_telemetry", "system_overview", {"metrics": found}, .9, source="telemetry"), .9)

    def _provider_browser(self, text):
        match = re.search(r"\bsearch\s+(?:on\s+)?github\s+(?:for\s+)?(.+)$", text, re.I)
        if match:
            query = match.group(1).strip(" .?!")
            if query:
                return IntentCandidate(self._make(text, "browser", "github_search", query, {"query": query}, .97, source="browser"), .97)
        match = re.search(r"\b(?:play|listen to)\s+(.+?)(?:\s+on\s+(?:youtube|spotify))?[.!?]*$", text, re.I)
        if match:
            query = match.group(1).strip(" .?!")
            if query:
                return IntentCandidate(self._make(text, "browser", "play_youtube", query, {"song": query, "query": query}, .94, source="browser"), .94)
        match = re.search(r"\b(?:search|look up|find)\s+(?:for\s+)?(.+)$", text, re.I)
        if match and not re.search(r"\b(?:file|contact|calendar)\b", text.lower()):
            query = match.group(1).strip(" .?!")
            if query:
                return IntentCandidate(self._make(text, "browser", "browser_search", query, {"query": query, "site": "google"}, .86, source="browser"), .86)
        match = re.search(r"\b(?:open|launch|navigate to|go to)\s+(.+)$", text, re.I)
        if match:
            target = match.group(1).strip(" .?!")
            if target:
                return IntentCandidate(self._make(text, "browser", "open_url", target, {"url": target}, .88, source="browser"), .88)
        return None

    def _provider_scheduler(self, text):
        low = text.lower()
        if re.search(r"\b(?:show|list|display)\s+(?:my\s+)?(?:active\s+)?alarms?\b", low):
            return IntentCandidate(self._make(text, "scheduler", "list", "active_alarms", {"action": "list"}, .96, source="scheduler"), .96)
        if re.search(r"\b(?:cancel|delete|clear|stop)\s+(?:the\s+)?alarm\b", low):
            return IntentCandidate(self._make(text, "scheduler", "cancel", "alarm", {"action": "cancel"}, .96, source="scheduler"), .96)
        if any(x in low for x in ("calendar", "meeting", "event", "agenda", "free slot", "availability")):
            if re.search(r"\b(?:create|add|book|schedule)\b", low):
                params = parameter_extractor.extract_calendar_params(text)
                missing = params.get("missing_required", [])
                if missing:
                    return IntentCandidate(self._clarify(text, "scheduler", "Please provide " + " and ".join(missing) + ".", {"calendar_request": text, **params}, source="scheduler"), .97)
                return IntentCandidate(self._make(text, "scheduler", "create_calendar_event", params.get("title", ""), {"calendar_request": text, **params}, .97, True, "scheduler"), .97)
            return IntentCandidate(self._make(text, "scheduler", "get_calendar_events", "calendar_events", {"query": text, "calendar_request": text}, .94, source="scheduler"), .94)
        if "schedule" in low and not any(x in low for x in ("calendar", "meeting", "event", "reminder", "remind me", "alarm", "timer")):
            return IntentCandidate(self._clarify(text, "scheduler", "What should I schedule?", source="scheduler"), .98)
        if not any(x in low for x in ("reminder", "remind me", "set an alarm", "set a timer", "wake me")):
            return None
        params = parameter_extractor.extract_schedule_params(text)
        if params.get("delay_seconds") is None:
            return IntentCandidate(self._clarify(text, "scheduler", "When should I schedule it?", params, source="scheduler"), .97)
        if ("remind" in low or "reminder" in low) and not params.get("message"):
            return IntentCandidate(self._clarify(text, "scheduler", "What should I remind you about?", params, source="scheduler"), .97)
        action = "set_reminder" if "remind" in low or "reminder" in low else "set_alarm"
        return IntentCandidate(self._make(text, "scheduler", action, params.get("message", ""), params, .96, source="scheduler"), .96)

    def _provider_file(self, text):
        if re.search(r"\b(?:delete|remove|erase)\b", text, re.I) and not re.search(r"\b(?:file|document|resume|report|notes?|pdf|csv|json|folder|directory)\b", text, re.I):
            return IntentCandidate(self._clarify(text, "file", "Which file should I delete?", source="file"), .98)
        if not re.search(r"\b(?:create|make|write|save|read|open|view|show|delete|remove|move|rename|search|find|locate)\b", text, re.I):
            return None
        if not re.search(r"\b(?:file|document|resume|report|notes?|pdf|csv|json|folder|directory)\b", text, re.I):
            return None
        params = parameter_extractor.extract_file_parameters(text)
        action = params.get("action", "")
        filename = params.get("filename") or ""
        if action == "create" and not filename:
            return IntentCandidate(self._clarify(text, "file", "What filename should I use?", params, source="file"), .98)
        if action == "delete" and not filename:
            return IntentCandidate(self._clarify(text, "file", "Which file should I delete?", params, source="file"), .98)
        if action == "read" and not filename:
            return IntentCandidate(self._clarify(text, "file", "Which file should I read?", params, source="file"), .98)
        if action == "rename" and (not filename or not params.get("destination")):
            return IntentCandidate(self._clarify(text, "file", "Which file should I rename, and what should its new name be?", params, source="file"), .98)
        if action == "move" and (not filename or not params.get("destination")):
            return IntentCandidate(self._clarify(text, "file", "Which file should I move, and where should it go?", params, source="file"), .98)
        if action == "search" and (not filename or filename == "*"):
            return IntentCandidate(self._clarify(text, "file", "What file or text should I search for?", params, source="file"), .98)
        mapped = {"create":"create_file","read":"read_file","delete":"delete_file","move":"move_file","rename":"rename_file","search":"search_file"}.get(action)
        if not mapped:
            return None
        return IntentCandidate(self._make(text, "file", mapped, filename, params, .93, action == "delete", "file"), .93)

    def _provider_file_reference(self, text):
        if not re.search(r"\b(?:read|show|open|delete|remove|move|rename)\b", text, re.I):
            return None
        if not re.search(r"\b(?:that file|the file|it|the one|just created|created)\b", text, re.I):
            return None
        file_ctx = getattr(self.context, "get_file", lambda: None)()
        if not file_ctx or not getattr(file_ctx, "path", ""):
            return IntentCandidate(self._clarify(text, "file", "Which file should I use?", source="file_reference"), .97)
        low = text.lower()
        if "delete" in low or "remove" in low:
            action = "delete_file"
            confirmation = True
        elif "move" in low:
            return IntentCandidate(self._clarify(text, "file", "Where should I move the file?", source="file_reference"), .97)
        elif "rename" in low:
            return IntentCandidate(self._clarify(text, "file", "What should the new filename be?", source="file_reference"), .97)
        else:
            action = "read_file"
            confirmation = False
        path = str(file_ctx.path)
        return IntentCandidate(self._make(text, "file", action, path, {"path": path, "file_path": path, "filename": Path(path).name}, .98, confirmation, "file_reference"), .98)

    def _legacy_arbitrate(self, text: str) -> StructuredIntent:
        clean = text.strip()
        low = clean.lower()

        # 1. Check for Pending Confirmation Response ("yes, do it", "yes", "confirm", "proceed", "no", "cancel")
        if context_manager.has_pending_confirmation():
            if low in ["yes, do it", "yes", "do it", "confirm", "proceed", "sure", "approve", "approved", "go ahead"]:
                tx = context_manager.get_pending_confirmation()
                if tx:
                    logger.info("[IntentArbitrator] Matched confirmed transaction: action='%s', target='%s'", tx.action, tx.target)
                    return StructuredIntent(
                        domain=getattr(tx, "domain", "") or tx.payload.get("_domain", "system"),
                        action=f"confirmed_{tx.action}",
                        target=tx.target,
                        params=tx.payload,
                        requires_confirmation=False,
                    )
            elif any(re.search(r"\b" + re.escape(w) + r"\b", low) for w in ["no", "cancel", "stop", "abort", "don't", "dont", "wait", "nevermind"]):
                tx = context_manager.pop_confirmation()
                logger.info("[IntentArbitrator] Explicitly cancelled pending transaction: %s", getattr(tx, "action", "action"))
                return StructuredIntent(
                    domain="system",
                    action="cancel_action",
                    target=getattr(tx, "target", ""),
                    params={"response": "Action cancelled. The operation was safely aborted.", "user_cancelled": True},
                    requires_confirmation=False,
                )

        # 2. Check Contextual References & Pronouns ("pause it", "continue", "close that tab", "what page...")
        ref = context_manager.resolve_references(clean)
        if ref["is_media_control"]:
            return StructuredIntent(
                domain="browser",
                action=ref["resolved_action"],
                target=ref["resolved_target"] or "",
                params={"action": ref["resolved_action"]},
            )
        if ref["is_browser_op"]:
            return StructuredIntent(
                domain="browser",
                action=ref["resolved_action"],
                target=ref["resolved_target"] or "",
                params={"action": ref["resolved_action"]},
            )
        if ref["is_file_op"]:
            f_act = ref["resolved_action"]
            t_file = ref["resolved_target"]
            if f_act == "move_file":
                dest = "downloads" if "downloads" in low else ""
                return StructuredIntent(
                    domain="file",
                    action="move_file",
                    target=t_file,
                    params={"action": "move", "source": t_file, "path": t_file, "destination": dest},
                )
            elif f_act in ["read_file", "read"]:
                return StructuredIntent(
                    domain="file",
                    action="read_file",
                    target=t_file,
                    params={"action": "read", "path": t_file, "file_path": t_file, "filename": t_file, "directory": ""},
                )
            elif f_act in ["delete_file", "delete"]:
                return StructuredIntent(
                    domain="file",
                    action="delete_file",
                    target=t_file,
                    params={"action": "delete_file", "path": t_file, "file_path": t_file, "directory": ""},
                    requires_confirmation=True,
                )

        # 3. Session Grounding / Recall ("what did we actually do in this conversation?")
        if any(p in low for p in ["what did we actually do", "what did we do in this conversation", "summary of what we did", "what have we done"]):
            return StructuredIntent(
                domain="system",
                action="summarize_session",
                target="session_history",
                params={"summary": episodic_ledger.summarize_session()},
            )

        # 4. Persona Switch Intent ("call yourself Friday", "switch to Friday", "call yourself Jarvis")
        m_persona = re.search(r"\b(?:call yourself|switch to|be|act as)\s+(friday|jarvis|ultron|omi)\b", low)
        if m_persona:
            target_p = m_persona.group(1).capitalize()
            pass
            return StructuredIntent(
                domain="system",
                action="switch_persona",
                target=target_p,
                params={"persona": target_p},
            )

        # 4b. Real-Time Weather Intent & ASR Phonetic Disambiguation (Capability 32)
        is_conjunction = bool(
            re.search(r"\b(?:know|doubt|wonder|unsure|decide|choose|matter|see|tell|ask|care)\s+whether\b", low) or
            re.search(r"\bwhether\s+(?:to|or|not|this|that|it|he|she|they|we|i|you|there)\b", low) or
            re.search(r"\bwhether\b.+\bor\b", low) or
            "whether this is" in low or "whether to" in low or "don't know whether" in low or "dont know whether" in low
        )

        is_weather = False
        weather_loc = None
        weather_time = "now"

        if not is_conjunction:
            # Check explicit weather or phonetic ASR ambiguity
            if any(w in low for w in ["weather", "forecast", "temperature", "will it rain", "rain tonight"]):
                is_weather = True
            elif (
                re.search(r"\b(?:tell\s+me|what\s*'?s|what\s+is|how\s*'?s|how\s+is|check|show\s+me|give\s+me)\s+(?:the\s+|today'?s\s+|tomorrow'?s\s+)?(?:today\s+)?whether\b", low) or
                re.search(r"\b(?:today|tomorrow|tonight|right\s+now|current|outside)\s+whether\b", low) or
                re.search(r"\bwhether\s+(?:today|tomorrow|tonight|right\s+now|outside|forecast|report)\b", low) or
                re.search(r"\bwhether\s+(?:in|for|at)\s+[a-zA-Z\s]+\b", low) or
                low.strip() in ["whether", "today whether", "tell me today whether", "what is whether", "how is whether", "check whether"]
            ):
                is_weather = True
            elif re.search(r"\b(?:what\s+about|how\s+about|and)\s+(tomorrow|today|tonight)\b", low) or low in ["and tomorrow", "and tomorrow?", "tomorrow?"]:
                w_ctx = context_manager.get_weather_context() if hasattr(context_manager, "get_weather_context") else {}
                if w_ctx.get("active"):
                    is_weather = True
                    m_t = re.search(r"\b(tomorrow|today|tonight)\b", low)
                    weather_time = m_t.group(1) if m_t else "tomorrow"
                    weather_loc = w_ctx.get("location")
            elif re.search(r"\b(?:what\s+about|how\s+about|and\s+in)\s+([a-zA-Z\s]+)$", low):
                w_ctx = context_manager.get_weather_context() if hasattr(context_manager, "get_weather_context") else {}
                if w_ctx.get("active"):
                    cand = re.search(r"\b(?:what\s+about|how\s+about|and\s+in)\s+([a-zA-Z\s]+)$", low).group(1).strip().title()
                    if cand not in ["It", "This", "That", "The Company", "Tomorrow", "Tonight", "Yesterday"]:
                        is_weather = True
                        weather_loc = cand
                        weather_time = w_ctx.get("time_target", "now")

        if is_weather:
            clean_text = re.sub(r"[?!.,;]+$", "", clean).strip()
            m_city = re.search(r"\b(?:in|for|at)\s+([a-zA-Z0-9_\-\s]+?)(?:\s+(?:today|tomorrow|tonight|right\s+now|now))?$", clean_text, re.IGNORECASE)
            if not m_city:
                m_city = re.search(r"\b(?:in|for|at)\s+([a-zA-Z0-9_\-\s]+?)(?:\s+(?:today|tomorrow|tonight|right\s+now|now|\?))", clean, re.IGNORECASE)
            if m_city:
                cand = m_city.group(1).strip()
                cand = re.sub(r"\b(?:right\s+now|now|today|tomorrow|tonight)\b", "", cand, flags=re.IGNORECASE).strip().title()
                if cand and cand not in ["The", "A", "An"]:
                    weather_loc = cand
            if not weather_loc:
                w_ctx = context_manager.get_weather_context() if hasattr(context_manager, "get_weather_context") else {}
                weather_loc = w_ctx.get("location")
            if "tomorrow" in low:
                weather_time = "tomorrow"
            elif "tonight" in low:
                weather_time = "tonight"
            elif "today" in low:
                weather_time = "today"

            if hasattr(context_manager, "set_weather_context"):
                pass

            return StructuredIntent(
                domain="info",
                action="get_weather",
                target=weather_loc,
                params={"location": weather_loc, "time_target": weather_time, "action": "get_weather"},
                confidence=0.95,
            )

        # 5. Scheduler Intent (CRITICAL FIX: Overrides developer_task regex)
        # "set a reminder in 90 seconds to check on this test"
        if any(w in low for w in ["reminder", "remind me", "set an alarm", "set a timer"]):
            m_sec = re.search(r"in\s+(\d+)\s+(seconds?|secs?|minutes?|mins?|hours?)", low)
            delay = None
            if m_sec:
                val = int(m_sec.group(1))
                unit = m_sec.group(2)
                delay = val * 60 if "min" in unit else val * 3600 if "hour" in unit else val

            m_msg = re.search(r"(?:to|that|about)\s+(.+)$", low)
            msg = m_msg.group(1).strip() if m_msg else ""
            return StructuredIntent(
                domain="scheduler",
                action="set_reminder",
                target=msg,
                params={"delay_seconds": delay, "message": msg, "target": msg},
            )

        # 6. OCR / Receipt Document Understanding ("read this and save the text", "scan receipt")
        if any(w in low for w in ["read this and save the text", "scan receipt", "read receipt", "ocr receipt", "extract text from document"]):
            return StructuredIntent(
                domain="ocr",
                action="scan_document",
                target=ref["resolved_target"] or "",
                params={"image_path": ref["resolved_target"] or "", "save_to_kb": "save" in low},
            )

        # 7. Code Review & Follow-up & Generation
        if ref["is_code_op"] and ref["resolved_action"] == "execute_code":
            # "run it with 5"
            m_arg = re.search(r"with\s+(\d+)", low)
            arg_val = m_arg.group(1).strip() if m_arg else ""
            return StructuredIntent(
                domain="code",
                action="execute_code",
                target=ref["resolved_target"] or "",
                params={"code": ref["resolved_target"], "input_arg": arg_val} if arg_val else {"code": ref["resolved_target"]},
            )

        if ref["is_code_op"] and ref["resolved_action"] == "code_explanation":
            # "what happens if b is zero?"
            return StructuredIntent(
                domain="code",
                action="explain_code",
                target=ref["resolved_target"] or "",
                params={"code": ref["resolved_target"], "scenario": clean},
            )

        if "review this python code" in low or "review this code" in low:
            m_code = re.search(r":\s*(.+)$", clean, re.DOTALL)
            code_text = m_code.group(1).strip() if m_code else clean
            return StructuredIntent(
                domain="code",
                action="review_code",
                target="code_snippet",
                params={"code": code_text},
            )

        # 8. File Operations & Creation Safety
        file_triggers = [
            "make a note file", "create a file", "make a file", "write a file", "save a file",
            "read the file", "read file", "show the file", "show me the file", "open the file", "open file",
            "delete the file", "delete file", "remove the file", "move the file", "move file", "rename the file", "rename file"
        ]
        is_past_inquiry = bool(re.search(r"^(?:did\s+you|was\s+the|were\s+the|have\s+you|why\s+did\s+you)\b", low))
        if not is_past_inquiry and (any(w in low for w in file_triggers) or (any(k in low for k in ["file", "document", "notes", ".txt", ".json", ".csv", ".md"]) and any(v in low for v in ["create", "write", "make", "read", "show", "open", "delete", "remove", "move", "rename"]))):
            from orchestrator.parameter_extractor import parameter_extractor
            f_params = parameter_extractor.extract_file_parameters(clean)
            if f_params.get("requires_clarification"):
                clarif_p = f_params.get("clarification_prompt", "Could you clarify the file operation details?")
                return StructuredIntent(
                    domain="core_llm_agent",
                    action="clarification",
                    target="",
                    params={"query": clarif_p, "system_extra": clarif_p, "response": clarif_p},
                    requires_confirmation=False,
                )

            f_action = f_params.get("action", "read")
            filename = f_params.get("filename") or ""
            dir_target = f_params.get("directory") or "documents"
            content_txt = f_params.get("content") or ""

            target_path = filename if (filename and (":\\" in filename or ":/" in filename)) else f"{dir_target}:{filename}"

            if f_action == "create":
                is_desktop = (dir_target == "desktop" or "desktop" in low)
                return StructuredIntent(
                    domain="file",
                    action="create_file",
                    target=target_path,
                    params={"directory": dir_target, "filename": filename, "content": content_txt, "path": target_path},
                    requires_confirmation=is_desktop,
                    raw_query=clean,
                    source="legacy",
                )
            elif f_action == "read":
                return StructuredIntent(
                    domain="file",
                    action="read_file",
                    target=target_path,
                    params={"action": "read", "path": target_path, "file_path": target_path, "filename": filename, "directory": dir_target},
                    requires_confirmation=False,
                )
            elif f_action == "delete":
                return StructuredIntent(
                    domain="file",
                    action="delete_file",
                    target=target_path,
                    params={"action": "delete_file", "path": target_path, "file_path": target_path, "directory": dir_target},
                    requires_confirmation=True,
                )
            elif f_action == "move":
                f_dest = f_params.get("destination") or "downloads"
                return StructuredIntent(
                    domain="file",
                    action="move_file",
                    target=target_path,
                    params={"action": "move", "source": target_path, "path": target_path, "destination": f_dest, "directory": dir_target},
                    requires_confirmation=False,
                )
            elif f_action == "rename":
                f_new = f_params.get("destination") or f_params.get("new_name") or ""
                return StructuredIntent(
                    domain="file",
                    action="rename_file",
                    target=target_path,
                    params={"action": "rename", "source": target_path, "path": target_path, "new_name": f_new, "destination": f_new},
                    requires_confirmation=False,
                )

        if any(w in low for w in ["find a file", "search for a file", "locate file"]):
            m_fn = re.search(r"called\s+([a-zA-Z0-9_\-\.]+)", low)
            target_fn = m_fn.group(1).strip() if m_fn else ""
            return StructuredIntent(
                domain="file",
                action="search_file",
                target=target_fn,
                params={"filename": target_fn, "pattern": f"*{target_fn}*"},
            )

        # 9. Git Operations
        if "git status" in low:
            return StructuredIntent(
                domain="git",
                action="status",
                target="local_repo",
                params={},
            )

        if "create branch" in low or "temporary branch" in low:
            m_branch = re.search(r"\b(?:called|named|branch)\s+([A-Za-z0-9._/-]+)\b", clean, re.IGNORECASE)
            branch_name = m_branch.group(1).strip() if m_branch else ""
            if not branch_name:
                return StructuredIntent(
                    domain="git",
                    action="create_branch",
                    target="",
                    params={},
                    needs_clarification=True,
                    clarification_prompt="What should I name the new branch?",
                    raw_query=clean,
                )
            return StructuredIntent(
                domain="git",
                action="create_branch",
                target=branch_name,
                params={"branch_name": branch_name},
                raw_query=clean,
            )

        if low in ["switch back", "go back"]:
            previous = context_manager.get_previous_git_branch()
            if not previous:
                return StructuredIntent(
                    domain="git",
                    action="switch_branch",
                    target="",
                    params={},
                    needs_clarification=True,
                    clarification_prompt="Which branch should I switch back to?",
                    raw_query=clean,
                )
            return StructuredIntent(
                domain="git",
                action="switch_branch",
                target=previous,
                params={"branch_name": previous},
                raw_query=clean,
            )

        # 10. Communication (Email, Messages, WhatsApp)
        if any(w in low for w in ["whats app", "whatsapp", "send email", "draft email", "send message", "draft message", "lookup contact", "find contact"]):
            is_email = "email" in low
            is_contact_lookup = "contact" in low and any(k in low for k in ["lookup", "find", "search", "who is"])
            
            if is_contact_lookup:
                m_c = re.search(r"(?:lookup|find|search|for|who is)\s+(?:contact\s+)?([a-zA-Z0-9_\-\s]+)$", clean, re.IGNORECASE)
                c_name = m_c.group(1).strip() if m_c else clean
                return StructuredIntent(
                    domain="communication",
                    action="lookup_contact",
                    target=c_name,
                    params={"query": c_name},
                )

            m_recip = re.search(r"(?:to|tell|message)\s+([a-zA-Z0-9_\-]+)", clean, re.IGNORECASE)
            recipient = m_recip.group(1).strip() if m_recip else ""
            
            m_body = re.search(r"(?:saying|body|that|message)\s+(.+)$", clean, re.IGNORECASE)
            body = m_body.group(1).strip() if m_body else ""

            action_type = "draft_email" if is_email else "draft_message"
            if not recipient or not body:
                missing = "recipient" if not recipient else "message content"
                prompt = f"What {missing} should I use?"
                return StructuredIntent(
                    domain="communication",
                    action="clarification",
                    target="",
                    params={"query": prompt},
                    raw_query=clean,
                    needs_clarification=True,
                    clarification_prompt=prompt,
                )
            return StructuredIntent(
                domain="communication",
                action=action_type,
                target=recipient,
                params={"recipient": recipient, "to": recipient, "message": body, "body": body},
                requires_confirmation=True,
            )

        # 11. Multi-Intent Telemetry ("tell me cpu, ram, network status and the time")
        if all(k in low for k in ["cpu", "ram", "network", "time"]):
            return StructuredIntent(
                domain="system",
                action="multi_telemetry",
                target="system_overview",
                params={"metrics": ["cpu", "ram", "network", "time"]},
            )

        # 12. Browser Contextual Search ("search for python" while on GitHub)
        browser = context_manager.get_browser()
        if "github.com" in browser.url and low in ["search for python", "search python"]:
            return StructuredIntent(
                domain="browser",
                action="github_search",
                target="",
                params={"query": ""},
            )

        # 13. General Web Navigation & Media
        if "open youtube" in low:
            pass
            return StructuredIntent(domain="browser", action="play_youtube", target="", params={"song": ""})

        if "open github" in low:
            pass
            return StructuredIntent(domain="browser", action="open_url", target="https://github.com/", params={"url": "https://github.com/"})

        # 13b. Cross-Capability Composite Workflow (Calendar + Device Mesh + Notification)
        if "calendar" in low and ("notify" in low or "alert me on" in low or "device" in low):
            return StructuredIntent(
                domain="composite",
                action="calendar_mesh_notify",
                target=clean,
                params={"query": clean},
                confidence=0.95,
            )

        # 13c. Device Mesh Discovery & Selection (Capability 36)
        if any(w in low for w in ["discover devices", "list devices", "show devices", "my devices", "device mesh", "mesh peers", "connected devices"]):
            return StructuredIntent(
                domain="mesh",
                action="discover_peers",
                target="mesh_peers",
                params={"online_only": "online" in low},
                confidence=0.96,
            )

        # 13d. Calendar & Scheduling (Capability 38)
        if any(w in low for w in ["calendar", "schedule", "meeting", "events today", "upcoming events", "free slots", "availability"]):
            if "conflict" in low:
                return StructuredIntent(
                    domain="scheduler",
                    action="check_conflicts",
                    target=clean,
                    params={"query": clean},
                    confidence=0.95,
                )
            if any(k in low for k in ["add event", "create event", "schedule meeting", "schedule event", "new meeting", "new event", "book"]):
                m_t = re.search(r"(?:event|meeting|book)\s+(?:named|titled|for|about)?\s*(.+?)(?:\s+(?:at|on|tomorrow|today)|$)", clean, re.IGNORECASE)
                ev_title = m_t.group(1).strip() if m_t else ""
                return StructuredIntent(
                    domain="scheduler",
                    action="create_calendar_event",
                    target=ev_title,
                    params={"title": ev_title, "raw_query": clean},
                    confidence=0.95,
                )
            return StructuredIntent(
                domain="scheduler",
                action="get_calendar_events",
                target="calendar_events",
                params={"query": clean},
                confidence=0.95,
            )

        # 13e. In-App Alarms, Timers & Reminders (Scheduler Agent)
        if any(w in low for w in ["list alarms", "show alarms", "active alarms", "my alarms", "pending alarms"]):
            return StructuredIntent(
                domain="scheduler",
                action="list",
                target="active_alarms",
                params={"action": "list"},
                confidence=0.98,
            )

        if any(w in low for w in ["cancel alarm", "delete alarm", "stop alarm", "cancel the alarm", "clear alarm"]):
            return StructuredIntent(
                domain="scheduler",
                action="cancel",
                target="alarm",
                params={"action": "cancel"},
                confidence=0.98,
            )

        is_alarm_or_timer = bool(
            re.search(r"\b(?:set|create|schedule)\s+(?:an?\s+)?(?:alarm|timer|reminder)\b", low) or
            re.search(r"\b(?:alarm|timer)\s+(?:of|for|at|in)\b", low) or
            re.search(r"\bwake\s+me\s+(?:up\s+)?(?:at|for|in)\b", low) or
            re.search(r"\bremind\s+me\s+(?:in|at|to)\b", low)
        )
        if is_alarm_or_timer:
            from orchestrator.parameter_extractor import parameter_extractor
            sched_params = parameter_extractor.extract_schedule_params(clean)
            return StructuredIntent(
                domain="scheduler",
                action="set_alarm",
                target=sched_params.get("message", ""),
                params=sched_params,
                confidence=0.98,
            )

        # 14. Multi-Intent Personal + External Synthesis (Capabilities 33, 31, 34, 35)
        synthesis_patterns = [
            r"\bcompare\s+(?:my\s+)?(.+?)\s+(?:with|to|against|and)\s+(.+)",
            r"\b(?:synthesize|differences\s+and\s+summarize|verify\s+the\s+differences|differences\s+between)\s+(?:my\s+)?(.+)",
            r"\bcompare\s+my\s+(?:project|architecture|design|notes|work)\b",
        ]
        is_synthesis = False
        p_q = clean
        e_q = clean
        for spat in synthesis_patterns:
            sm = re.search(spat, low)
            if sm:
                is_synthesis = True
                if len(sm.groups()) >= 2 and sm.group(1) and sm.group(2):
                    p_q = re.sub(r"[.?!]+$", "", sm.group(1).strip())
                    e_q = re.sub(r"[.?!]+$", "", sm.group(2).strip())
                elif len(sm.groups()) >= 1 and sm.group(1):
                    p_q = re.sub(r"[.?!]+$", "", sm.group(1).strip())
                    e_q = f"current {p_q}"
                break

        if is_synthesis:
            return StructuredIntent(
                domain="synthesis",
                action="personal_and_external_synthesis",
                target=clean,
                params={"query": clean, "personal_query": p_q, "external_query": e_q},
                confidence=0.96,
            )

        # 15. Personal Search & Project Records (Capability 33)
        personal_patterns = [
            r"what do you remember about (?:my\s+)?(.+)$",
            r"what was my\s+(.+)$",
            r"what were my\s+(.+)$",
            r"what did i decide about (?:the\s+)?(.+)$",
            r"what was the (?:last\s+)?issue with (?:the\s+)?(.+)$",
            r"what projects have i worked on\b",
            r"show me the project i worked on\b",
            r"search (?:my\s+)?(?:personal\s+)?(?:notes|projects|documents|files|records)\b",
            r"what did we decide to use instead\b",
            r"why did we choose that\b",
            r"tell me about (?:my\s+|our\s+|the\s+project\s+|project\s+)(.+)$",
            r"what do you know about (?:my\s+|our\s+|the\s+project\s+|project\s+)(.+)$",
            r"\bmy\s+(?:internship|project|portfolio|work|notes?|records?|docs?|documents?)\b",
        ]
        is_personal = False
        p_target = clean

        for pat in personal_patterns:
            m_p = re.search(pat, low)
            if m_p:
                is_personal = True
                if m_p.groups() and m_p.group(1):
                    p_target = re.sub(r"[.?!]+$", "", m_p.group(1)).strip()
                break

        if is_personal:
            # Contextual resolution for follow-ups
            if "instead" in low or "why did we choose that" in low:
                prev_proj = context_manager.get_working_memory().get("active_project") or context_manager.get_working_memory().get("last_entity") or ""
                p_target = f"{p_target} {prev_proj}".strip()
            else:
                context_manager.set_working_memory_item("active_project", p_target)

            return StructuredIntent(
                domain="personal_search",
                action="search_personal",
                target=p_target,
                params={"query": p_target, "raw_query": clean, "top_k": 5},
                confidence=0.95,
            )

        # Default: Route to Core LLM / Conversational Agent
        return StructuredIntent(
            domain="chat",
            action="respond",
            target="user_query",
            params={"query": clean},
        )


intent_arbitrator = IntentArbitrator()
