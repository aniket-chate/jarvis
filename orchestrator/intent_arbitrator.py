"""Semantic Intent Arbitrator for JARVIS Layer 2.

Determines the structured semantic meaning FIRST, eliminating fragile keyword-first
regex collisions and ambiguous pronoun failures.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
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


class IntentArbitrator:
    """Classifies user intent through semantic decomposition and active context binding."""

    def arbitrate(self, text: str) -> StructuredIntent:
        intent = self._arbitrate(text)
        if not intent.raw_query:
            intent.raw_query = text.strip()
        if intent.action == "clarification":
            prompt = intent.clarification_prompt or (intent.params or {}).get("response") or (intent.params or {}).get("query") or ""
            intent.needs_clarification = True
            intent.clarification_prompt = prompt
        return intent

    def _arbitrate(self, text: str) -> StructuredIntent:
        clean = text.strip()
        low = clean.lower()

        # Front-door normalization for unambiguous commands. These are parameterized
        # patterns only; values always come from the user's request.
        m_media = re.fullmatch(r"play\s+(.+?)(?:\s+on\s+youtube)?[.!?]?", clean, re.IGNORECASE)
        if m_media and ("youtube" in low or low.startswith("play ")):
            media_query = re.sub(r"\s+on\s+youtube\s*$", "", m_media.group(1).strip(), flags=re.IGNORECASE).rstrip(".!?").strip()
            excluded_media = {"a song", "a music", "song", "music", "it", "that", "it again", "that again"}
            if media_query.lower() not in excluded_media or ("youtube" in low and media_query.lower() in {"music", "a music"}):
                return StructuredIntent(domain="browser", action="play_youtube", target=media_query, params={"song": media_query})

        m_open = re.fullmatch(r"(?:open|go to|navigate to)\s+(.+?)[.!?]?", clean, re.IGNORECASE)
        if m_open:
            target = m_open.group(1).strip()
            if target.lower() in {"github", "youtube"} or re.match(r"^https?://", target, re.IGNORECASE) or target.lower().startswith("www."):
                return StructuredIntent(domain="browser", action="open_url", target=target, params={"url": target})

        m_branch = re.fullmatch(r"create\s+(?:a\s+)?branch\s+(?:called|named)\s+([A-Za-z0-9._/-]+)[.!?]?", clean, re.IGNORECASE)
        if m_branch:
            return StructuredIntent(domain="git", action="create_branch", target=m_branch.group(1), params={"branch_name": m_branch.group(1)})

        m_comm = re.fullmatch(r"(message|email|text)\s+(.+?)\s+(?:saying|that|body|with)\s+(.+?)[.!?]?", clean, re.IGNORECASE)
        if m_comm:
            kind, recipient, body = m_comm.groups()
            return StructuredIntent(
                domain="communication",
                action="draft_email" if kind.lower() == "email" else "draft_message",
                target=recipient.strip(),
                params={"recipient": recipient.strip(), "to": recipient.strip(), "message": body.strip(), "body": body.strip()},
                requires_confirmation=True,
            )

        m_meeting = re.fullmatch(r"schedule\s+(?:a\s+)?meeting\s+(.+)", clean, re.IGNORECASE)
        if m_meeting:
            request = clean
            if not re.search(r"\bfor\s+\d+\s*(?:minutes?|mins?|hours?|hrs?)\b", low):
                prompt = "What duration should the meeting have?"
                return StructuredIntent(domain="scheduler", action="clarification", target="", params={"query": prompt, "calendar_request": request, "response": prompt}, needs_clarification=True, clarification_prompt=prompt)
            return StructuredIntent(domain="scheduler", action="create_calendar_event", target=m_meeting.group(1).strip(), params={"title": m_meeting.group(1).strip(), "raw_query": request, "calendar_request": request})

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
                        params={**tx.payload, "_confirmation": {"original_request": getattr(tx, "original_request", ""), "domain": getattr(tx, "domain", ""), "action": getattr(tx, "action", ""), "target": getattr(tx, "target", ""), "resolution": "confirm"}},
                        requires_confirmation=False,
                    )
            elif any(re.search(r"\b" + re.escape(w) + r"\b", low) for w in ["no", "cancel", "stop", "abort", "don't", "dont", "wait", "nevermind"]):
                tx = context_manager.pop_confirmation()
                if tx and getattr(tx, "action", "") == "create_file":
                    try:
                        from orchestrator.memory import memory_manager
                        pending = memory_manager.get_pending_action() or {}
                        pending_inputs = pending.get("inputs", {})
                        if (
                            pending.get("action") == "create_file"
                            and pending_inputs.get("path") == getattr(tx, "target", "")
                        ):
                            memory_manager.clear_pending_action()
                    except Exception:
                        logger.debug("Unable to clear cancelled create_file memory action", exc_info=True)
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
        explicit_file_search = (
            bool(re.search(r"\b(?:search|find|locate)\b", low))
            and bool(re.search(r"\b(?:file|files|document|documents)\b", low))
        )
        if ref["is_browser_op"] and not explicit_file_search:
            return StructuredIntent(
                domain="browser",
                action=ref["resolved_action"],
                target=ref["resolved_target"] or "",
                params={"action": ref["resolved_action"]},
            )
        if ref["is_file_op"] and not explicit_file_search:
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

        # Explicit UI/file navigation must not be mistaken for document operations.
        if re.fullmatch(r"(?:open|launch)\s+(?:file\s+explorer|explorer)[.!?]?", low):
            return StructuredIntent(
                domain="system",
                action="open_application",
                target="explorer",
                params={"app_name": "explorer", "query": clean},
            )

        # Explicit scoped project-folder navigation is an OS action, not personal search.
        if re.search(r"\b(?:open|go to|navigate to)\b", low) and re.search(r"\b(?:project folder|jarvis project|backend folder|backend directory)\b", low):
            target = "JARVIS project" if "project" in low else "backend"
            return StructuredIntent(
                domain="system",
                action="open_application",
                target=target,
                params={"app_name": target, "query": clean},
            )

        # Explicit local-file search: use word boundaries so 'documentation' is not treated as 'document'.
        m_scoped_search = re.search(
            r"\b(?:search|find|locate)\s+(?:for\s+)?(?:my\s+)?(.+?)\s+in\s+(?:my\s+)?(documents|downloads|desktop|workspace)\b",
            clean,
            re.IGNORECASE,
        )
        if m_scoped_search:
            requested = m_scoped_search.group(1).strip(" .?!")
            scope = m_scoped_search.group(2).lower()
            if re.search(r"\bpython\s+files?\b", requested, re.IGNORECASE):
                pattern = "*.py"
            elif re.search(r"\b(?:pdf|pdfs)\b", requested, re.IGNORECASE):
                pattern = "*.pdf"
            else:
                pattern = f"*{requested}*"
            return StructuredIntent(
                domain="file",
                action="search_file",
                target=requested,
                params={"action": "search", "pattern": pattern, "directory": scope, "filename": requested},
            )

        # Preserve explicit GitHub destination before the generic web-search rule.
        if re.search(r"\bsearch\s+(?:github|on\s+github)\b", low):
            m_g = re.search(r"\bsearch\s+(?:github|on\s+github)\s+(?:for\s+)?(.+)$", clean, re.IGNORECASE)
            query_g = m_g.group(1).strip(" .?!") if m_g else clean
            return StructuredIntent(
                domain="browser",
                action="github_search",
                target=query_g,
                params={"query": query_g},
            )

        # Specialized search destinations must outrank generic web search.
        if re.search(r"\bsearch\s+(?:for\s+)?(?:cats|.+?)\s+on\s+google\b", low) or re.search(r"\bsearch\s+(?:for\s+)?(.+?)\s+on\s+google\b", low):
            m_google = re.search(r"\bsearch\s+(?:for\s+)?(.+?)\s+on\s+google\b", clean, re.IGNORECASE)
            query_google = m_google.group(1).strip(" .?!") if m_google else clean
            return StructuredIntent(
                domain="browser",
                action="web_search",
                target=query_google,
                params={"query": query_google, "engine": "google"},
            )

        # Personal/notes search must outrank generic web search.
        if re.search(r"\bsearch\s+(?:my\s+)?(?:notes?|personal\s+(?:notes?|files?|data))\b", low):
            m_personal_search = re.search(r"\bsearch\s+(?:my\s+)?(.+)$", clean, re.IGNORECASE)
            query_personal = m_personal_search.group(1).strip(" .?!") if m_personal_search else clean
            return StructuredIntent(
                domain="personal_search",
                action="search_personal",
                target=query_personal,
                params={"query": query_personal, "raw_query": clean, "top_k": 5},
                confidence=0.95,
            )

        # General web research/search must outrank the generic chat fallback.
        if re.search(r"\b(?:search|find|look\s+up|research|browse)\b", low):
            has_local_scope = bool(re.search(r"\b(?:file|files|document|documents|downloads|desktop|workspace)\b", low))
            if not has_local_scope:
                return StructuredIntent(
                    domain="browser",
                    action="web_search",
                    target=clean,
                    params={"query": clean},
                )

        # Broad folder/directory deletion is still a file-agent destructive operation.
        if re.search(r"\b(?:delete|remove|erase)\b", low) and re.search(r"\b(?:folder|directory)\b", low):
            return StructuredIntent(
                domain="file",
                action="delete_file",
                target="",
                params={"action": "delete_file", "path": "", "file_path": "", "directory": ""},
                requires_confirmation=True,
                needs_clarification=True,
                clarification_prompt="Which folder or directory should I delete?",
            )

        # Reminder cancellation must outrank generic reminder creation.
        if re.search(r"\b(?:stop|cancel|disable|remove)\b.*\b(?:reminder|alarm|timer)\b", low):
            return StructuredIntent(
                domain="scheduler",
                action="cancel",
                target="reminder",
                params={"action": "cancel"},
            )

        # Live system connectivity queries should use telemetry/device state, not generic chat.
        if re.search(r"\b(?:internet|wifi|wi-fi)\b", low):
            return StructuredIntent(
                domain="system",
                action="multi_telemetry",
                target="network",
                params={"metrics": ["network"]},
            )
        if re.search(r"\b(?:phone|android)\b", low) and re.search(r"\b(?:connected|connection|online|reachable)\b", low):
            return StructuredIntent(
                domain="system",
                action="multi_telemetry",
                target="phone",
                params={"metrics": ["phone"]},
            )

        # Explicit browser history navigation. Use the persistent browser session when active.
        if low in {"go back", "back", "go to previous page", "previous page"}:
            browser_ctx = context_manager.get_browser()
            if getattr(browser_ctx, "url", ""):
                return StructuredIntent(domain="browser", action="go_back", target=browser_ctx.url, params={"action": "go_back"})

        # Device-mesh notification requests are routed to a real provider instead of chat.
        m_phone_notice = re.search(r"\b(?:send|push)\s+(?:a\s+)?notification\s+to\s+(?:my\s+)?phone\s+(?:saying|that|with)\s+(.+)$", clean, re.IGNORECASE)
        if m_phone_notice:
            message = m_phone_notice.group(1).strip().strip('"')
            return StructuredIntent(
                domain="capability",
                action="execute",
                target="mesh.route_to_device",
                params={
                    "capability": "mesh.route_to_device",
                    "parameters": {
                        "target_device_id": "phone",
                        "type": "skill_request",
                        "skillId": "send_notification",
                        "requestId": "jarvis_notification",
                        "parameters": {"title": "JARVIS", "message": message},
                        "message": message,
                    },
                },
            )

        # Wake-word management uses the existing local multi-persona provider.
        if re.search(r"\b(?:test|check)\s+(?:the\s+)?wake[- ]?word\s+system\b", low):
            return StructuredIntent(domain="capability", action="execute", target="wakeword.evaluate_false_positives", params={"capability": "wakeword.evaluate_false_positives", "parameters": {"sample_count": 10}})
        if re.search(r"\b(?:change|configure|adjust)\s+(?:my\s+)?wake[- ]?word\b", low):
            return StructuredIntent(domain="capability", action="execute", target="wakeword.configure", params={"capability": "wakeword.configure", "parameters": {}})
        if re.search(r"\b(?:create|add)\s+(?:another|a new)\s+wake[- ]?word\s+profile\b", low):
            return StructuredIntent(domain="capability", action="execute", target="wakeword.configure", params={"capability": "wakeword.configure", "parameters": {"active_personas": ["Jarvis", "Friday", "Ultron"]}})

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
            context_manager.set_persona(target_p)
            return StructuredIntent(
                domain="system",
                action="switch_persona",
                target=target_p,
                params={"persona": target_p},
            )

        # Generic telemetry requests must outrank the word "temperature" as a weather cue.
        if any(re.search(r"\b" + re.escape(k) + r"\b", low) for k in ["cpu", "ram", "memory", "battery", "disk", "storage", "network", "uptime"]) and not any(k in low for k in ["weather", "forecast", "rain"]):
            metrics = [k for k in ["cpu", "ram", "memory", "battery", "disk", "storage", "network", "uptime", "temperature"] if re.search(r"\b" + re.escape(k) + r"\b", low)]
            return StructuredIntent(domain="system", action="multi_telemetry", target="system_overview", params={"metrics": metrics})

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
                context_manager.set_weather_context(weather_loc, weather_time)

            if not weather_loc:
                prompt = "Which location should I use for the weather?"
                return StructuredIntent(domain="info", action="clarification", target="", params={"query": prompt, "response": prompt}, needs_clarification=True, clarification_prompt=prompt)
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
        if not is_past_inquiry and (any(w in low for w in file_triggers) or bool(re.search(r"\b(?:read|open|view|show|inspect)\s+(?:[a-zA-Z]:[\\/]|/|~)", clean, re.IGNORECASE)) or (bool(re.search(r"\b(?:search|find|locate)\b", low)) and bool(re.search(r"\b(?:file|files|document|documents)\b", low))) or (bool(re.search(r"\b(?:file|document|notes)\b|\.(?:txt|json|csv|md|pdf)\b", low)) and any(v in low for v in ["create", "write", "make", "read", "show", "open", "delete", "remove", "move", "rename"]))):
            from orchestrator.parameter_extractor import parameter_extractor
            f_params = parameter_extractor.extract_file_parameters(clean)
            if f_params.get("requires_clarification"):
                clarif_p = f_params.get("clarification_prompt", "Could you clarify the file operation details?")
                return StructuredIntent(
                    domain="file",
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
                if is_desktop:
                    context_manager.stage_confirmation(
                        action="create_file",
                        domain="file",
                        target=target_path,
                        payload={"directory": dir_target, "filename": filename, "content": content_txt, "path": target_path},
                    )
                    return StructuredIntent(
                        domain="file",
                        action="stage_file_creation",
                        target=target_path,
                        params={"directory": dir_target, "filename": filename, "content": content_txt, "path": target_path},
                        requires_confirmation=True,
                    )
                else:
                    return StructuredIntent(
                        domain="file",
                        action="create_file",
                        target=target_path,
                        params={"directory": dir_target, "filename": filename, "content": content_txt, "path": target_path},
                        requires_confirmation=False,
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
            elif f_action == "search":
                pattern = f_params.get("pattern") or f"*{filename}*"
                return StructuredIntent(
                    domain="file",
                    action="search_file",
                    target=filename,
                    params={"action": "search", "pattern": pattern, "directory": dir_target, "filename": filename},
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

        if re.fullmatch(r"(?:switch|go)\s+back(?:\s+to\s+(?:the\s+)?previous(?:\s+git)?\s+branch)?[.!]?", low):
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
        if re.match(r"^(?:message|email|text)\s+\S+", low) or any(w in low for w in ["whats app", "whatsapp", "send email", "send an email", "draft email", "send message", "draft message", "lookup contact", "find contact"]) or ("send" in low and "message" in low) or ("message" in low and " to " in low):
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

            m_recip = re.search(r"(?:message\s+to|to|tell|message)\s+([a-zA-Z0-9_\-]+)", clean, re.IGNORECASE)
            recipient = m_recip.group(1).strip() if m_recip else ""
            ambiguous_recipients = {"someone", "somebody", "a", "an", "person", "them", "him", "her"}
            if recipient.lower() in ambiguous_recipients or re.search(r"\b(?:send|message)\s+(?:a\s+)?message\s+to\s+(?:someone|somebody|a\s+person|them|him|her)\b", low):
                recipient = ""
            
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


        # Explicit local file/document searches outrank contextual browser search.
        m_file_search = re.fullmatch(r"(?:search|find|locate)(?:\s+for)?\s+(.+?)\s+(?:in|under)\s+(documents|downloads|desktop|workspace)[.!?]?", clean, re.IGNORECASE)
        if m_file_search:
            pattern, directory = m_file_search.groups()
            return StructuredIntent(
                domain="file",
                action="search",
                target=pattern.strip(),
                params={"pattern": pattern.strip(), "directory": directory.lower()},
            )

        # 12. Explicit search destinations must be parsed before contextual GitHub search.
        m_google_search = re.fullmatch(r"search(?:\s+for)?\s+(.+?)\s+on\s+google[.!?]?", clean, re.IGNORECASE)
        if m_google_search:
            query = m_google_search.group(1).strip()
            return StructuredIntent(domain="browser", action="web_search", target=query, params={"query": query, "engine": "google"})

        m_github_search = re.fullmatch(r"(?:search|find)(?:\s+on)?\s+github\s+(?:for\s+)?(.+?)[.!?]?", clean, re.IGNORECASE)
        if m_github_search:
            query = m_github_search.group(1).strip()
            return StructuredIntent(domain="browser", action="github_search", target=query, params={"query": query})

        # Contextual GitHub search applies only to unqualified search requests.
        browser = context_manager.get_browser()
        if "github.com" in browser.url and not re.search(r"\b(?:github|google)\b", low):
            search_match = re.fullmatch(r"search(?:\s+for)?\s+(.+)", clean, re.IGNORECASE)
            if search_match:
                query = search_match.group(1).strip()
                return StructuredIntent(domain="browser", action="github_search", target=query, params={"query": query})

        # 13. General Web Navigation & Media
        if re.search(r"\b(?:search|find)\s+(?:on\s+)?github\s+(?:for\s+)?(.+)$", clean, re.IGNORECASE):
            m = re.search(r"\b(?:search|find)\s+(?:on\s+)?github\s+(?:for\s+)?(.+)$", clean, re.IGNORECASE)
            query = m.group(1).strip() if m else ""
            if query:
                return StructuredIntent(domain="browser", action="github_search", target=query, params={"query": query})

        if re.fullmatch(r"\s*play\s+(?:a\s+)?(?:song|music)\s*[.!?]?\s*", low):
            return StructuredIntent(domain="browser", action="clarification", target="", params={"query": "Which song or media would you like me to play?", "response": "Which song or media would you like me to play?"}, needs_clarification=True, clarification_prompt="Which song or media would you like me to play?")

        if re.fullmatch(r"\s*play\s+(?:it|that)(?:\s+again)?[.!?]?\s*", low):
            return StructuredIntent(domain="browser", action="resume_media", target="", params={"query": clean})
        m_youtube_play = re.fullmatch(r"\s*play\s+(.+?)\s+on\s+youtube[.!?]?\s*", clean, re.IGNORECASE)
        m_play = re.fullmatch(r"\s*play\s+(.+?)[.!?]?\s*", clean, re.IGNORECASE)
        if m_youtube_play:
            song = m_youtube_play.group(1).strip()
            if song.lower() not in {"a song", "it", "that"}:
                return StructuredIntent(domain="browser", action="play_youtube", target=song, params={"song": song})
        elif m_play and m_play.group(1).strip().lower() not in {"a song", "music", "it", "that"}:
            song = m_play.group(1).strip()
            return StructuredIntent(domain="browser", action="play_youtube", target=song, params={"song": song})

        if "open youtube" in low:
            context_manager.update_browser(url="https://www.youtube.com", media_state="stopped", media_target="")
            return StructuredIntent(domain="browser", action="open_url", target="https://www.youtube.com", params={"url": "https://www.youtube.com"})

        if "open github" in low:
            context_manager.update_browser(url="https://github.com/", title="GitHub", media_state="stopped")
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
        if low.strip() in {"schedule something", "schedule an event", "schedule a meeting"}:
            prompt = "What should I schedule, and when?"
            return StructuredIntent(domain="scheduler", action="clarification", target="", params={"query": prompt, "response": prompt}, needs_clarification=True, clarification_prompt=prompt)

        if any(w in low for w in ["calendar", "schedule", "meeting", "events today", "upcoming events", "free slots", "availability"]):
            if "conflict" in low:
                return StructuredIntent(
                    domain="scheduler",
                    action="check_conflicts",
                    target=clean,
                    params={"query": clean},
                    confidence=0.95,
                )
            if re.search(r"^schedule\s+", low) and re.search(r"\b(?:for|duration|lasting)\s+\d+\s*(?:minutes?|mins?|hours?|hrs?)\b", low):
                title = re.sub(r"^schedule\s+(?:a\s+)?", "", clean, flags=re.IGNORECASE)
                return StructuredIntent(domain="scheduler", action="create_calendar_event", target=title, params={"title": title, "raw_query": clean, "calendar_request": clean}, confidence=0.95)

            if any(k in low for k in ["add event", "create event", "schedule meeting", "schedule event", "new meeting", "new event", "book"]):
                if "schedule meeting" in low and not re.search(r"\b(?:for|duration|lasting)\s+\d+\s*(?:minutes?|mins?|hours?|hrs?)\b", low):
                    prompt = "How long should the meeting be?"
                    return StructuredIntent(domain="scheduler", action="clarification", target="", params={"query": prompt, "calendar_request": clean, "response": prompt}, needs_clarification=True, clarification_prompt=prompt)
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

        if re.fullmatch(r"delete\s+(?:something|it|that|a file|the file)[.!?]?", low):
            prompt = "Which file would you like me to delete?"
            return StructuredIntent(domain="file", action="clarification", target="", params={"query": prompt, "response": prompt}, requires_confirmation=False, needs_clarification=True, clarification_prompt=prompt)

        # Browser navigation is handled only for explicit URLs or domain-like targets.
        # Desktop application names must continue to the application-control planner.
        m_generic_browser = re.fullmatch(r"(?:open|go to|navigate to)\s+(.+?)[.!?]?", clean, re.IGNORECASE)
        if m_generic_browser:
            target = m_generic_browser.group(1).strip()
            if re.match(r"^https?://", target, re.IGNORECASE) or re.match(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:[/:].*)?$", target):
                return StructuredIntent(domain="browser", action="open_url", target=target, params={"url": target})

        # Default: Route to Core LLM / Conversational Agent
        return StructuredIntent(
            domain="chat",
            action="respond",
            target="user_query",
            params={"query": clean},
        )


intent_arbitrator = IntentArbitrator()
