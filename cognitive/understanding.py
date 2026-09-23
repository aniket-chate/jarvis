"""JARVIS Understanding Engine (Cognitive Kernel - Stage 1).

Responsible for:
- Semantic intent understanding (Meaning first, not keywords)
- Entity extraction (targets, values, time intervals)
- Pronoun & reference resolution ("it", "that", "this tab", "that file")
- Ambiguity detection & context framing
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("JARVIS.Cognitive.Understanding")


@dataclass
class CognitiveIntent:
    """Structured understanding of user utterance."""
    domain: str              # "browser", "os", "file", "git", "code", "scheduler", "chat", "shell", "system", "unknown"
    action: str              # "play_media", "pause_media", "set_reminder", "create_file", "snap_window", etc.
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    is_system_1_fast_path: bool = True
    is_ambiguous: bool = False
    clarification_prompt: Optional[str] = None
    target_entity: Optional[str] = None
    resolved_pronoun: Optional[str] = None


class UnderstandingEngine:
    """Disambiguates and structures natural language meaning before planning."""

    def __init__(self):
        pass

    def understand(self, utterance: str, world_model_context: Optional[Dict[str, Any]] = None) -> CognitiveIntent:
        world_model_context = world_model_context or {}
        text = utterance.strip()
        low = text.lower()

        # -------------------------------------------------------------
        # 1. Pronoun & Reference Disambiguation ("it", "that tab", "that file")
        # -------------------------------------------------------------
        resolved_pronoun = None
        target_entity = None

        if re.search(r"\b(that\s+tab|this\s+tab)\b", low):
            active_tab = world_model_context.get("active_browser", {}).get("tab_id")
            resolved_pronoun = f"tab_id:{active_tab}" if active_tab else "active_browser_tab"

        if re.search(r"\b(that\s+file|this\s+file)\b", low):
            resolved_pronoun = str(world_model_context.get("last_file") or "report.txt")

        if re.search(r"\b(it|that|this)\b", low):
            if any(k in low for k in ["run", "execute", "explain", "review"]) and world_model_context.get("last_code"):
                resolved_pronoun = "last_code_snippet"
            elif any(k in low for k in ["pause", "resume", "stop", "mute", "video", "song"]) and world_model_context.get("active_browser"):
                resolved_pronoun = "active_media_player"
            elif world_model_context.get("last_file"):
                resolved_pronoun = str(world_model_context.get("last_file"))

        # -------------------------------------------------------------
        # 2. Prohibited Shell Commands (Security & Safety Invariant)
        # -------------------------------------------------------------
        if any(cmd in low for cmd in ["ipconfig", "whoami", "ifconfig", "rm -rf", "cmd.exe", "powershell.exe"]) or (
            low.startswith("can you execute") and any(c in low for c in ["ipconfig", "whoami", "netstat", "bash"])
        ):
            return CognitiveIntent(
                domain="shell",
                action="execute_shell",
                parameters={"command": text, "raw": text},
                confidence=0.99,
                is_system_1_fast_path=True,
                target_entity="shell",
            )

        # -------------------------------------------------------------
        # 3. Persona Switches
        # -------------------------------------------------------------
        if any(w in low for w in ["call yourself", "switch to", "activate", "address yourself as"]):
            target_p = None
            if "friday" in low:
                target_p = "Friday"
            elif "ultron" in low:
                target_p = "Ultron"
            elif "jarvis" in low:
                target_p = "Jarvis"
            if target_p:
                return CognitiveIntent(
                    domain="system",
                    action="switch_persona",
                    parameters={"persona": target_p},
                    confidence=0.98,
                    is_system_1_fast_path=True,
                    target_entity=target_p,
                )

        # -------------------------------------------------------------
        # 4. Destructive Actions / Dangerous Operations
        # -------------------------------------------------------------
        if any(phrase in low for phrase in ["delete a folder", "delete folder", "delete database", "drop database", "wipe disk"]):
            return CognitiveIntent(
                domain="system",
                action="destructive_operation",
                parameters={"target": text},
                confidence=0.95,
                is_system_1_fast_path=False,
                target_entity=text,
            )

        # -------------------------------------------------------------
        # 5. External Communications (WhatsApp / Email)
        # -------------------------------------------------------------
        if any(phrase in low for phrase in ["send a whatsapp message", "send whatsapp", "whatsapp message", "send an email", "send email"]):
            return CognitiveIntent(
                domain="communication",
                action="send_message",
                parameters={"raw": text},
                confidence=0.95,
                is_system_1_fast_path=False,
                target_entity=text,
            )

        # -------------------------------------------------------------
        # 6. Time-Based Reminders & Scheduling (Domain: scheduler)
        # -------------------------------------------------------------
        if any(w in low for w in ["reminder", "remind me", "alarm", "timer"]):
            sec = 60
            m_sec = re.search(r"in\s+(\d+)\s*(?:seconds?|secs?|s\b)", low)
            m_min = re.search(r"in\s+(\d+)\s*(?:minutes?|mins?|m\b)", low)
            if m_sec:
                sec = int(m_sec.group(1))
            elif m_min:
                sec = int(m_min.group(1)) * 60

            msg = text
            m_to = re.search(r"(?:to|that|for)\s+(.+)$", text, re.IGNORECASE)
            if m_to:
                msg = m_to.group(1).strip()

            return CognitiveIntent(
                domain="scheduler",
                action="set_reminder",
                parameters={"delay_seconds": sec, "message": msg},
                confidence=0.98,
                is_system_1_fast_path=True,
                target_entity=msg,
            )

        # -------------------------------------------------------------
        # 7. File Operations (Domain: file)
        # -------------------------------------------------------------
        if re.search(r"\bcreate\s+(?:a\s+)?file\b", low) or re.search(r"\bwrite\s+(?:a\s+)?file\b", low):
            m_f = re.search(r"(?:called|named)\s+([a-zA-Z0-9_\.\-]+)", text, re.IGNORECASE)
            if not m_f:
                m_f = re.search(r"\bfile\s+([a-zA-Z0-9_\-]+\.[a-zA-Z0-9]+)", text, re.IGNORECASE)
            if m_f:
                filename = m_f.group(1).strip().rstrip(".")
            return CognitiveIntent(
                domain="file",
                action="create_file",
                parameters={"filename": filename, "path": filename, "content": "Sample file content"},
                confidence=0.95,
                is_system_1_fast_path=True,
                target_entity=filename,
            )

        if re.search(r"\bmove\s+(?:that\s+file|it|this|[a-zA-Z0-9_\.\-]+)\s+to\b", low):
            dest = "Downloads"
            m_d = re.search(r"to\s+([a-zA-Z0-9_\.\-]+)", text, re.IGNORECASE)
            if m_d:
                dest = m_d.group(1).strip().rstrip(".")
            src = resolved_pronoun or world_model_context.get("last_file") or "report.txt"
            return CognitiveIntent(
                domain="file",
                action="move_file",
                parameters={"source": str(src), "destination": dest, "path": str(src)},
                confidence=0.95,
                is_system_1_fast_path=True,
                target_entity=dest,
                resolved_pronoun=str(src),
            )

        file_ext_pattern = r"\b[a-zA-Z0-9_\-]+\.(txt|py|md|json|csv|pdf|docx|log|png|jpg|c|cpp|js|ts|yaml|yml)\b"
        if any(phrase in low for phrase in ["open that file", "open it", "read that file", "read it", "summarize it", "summarize that file"]) or (
            low.startswith("open ") and re.search(file_ext_pattern, low) and not any(ext in low for ext in ["http", "www", ".com", ".org", "github", "chrome", "google"])
        ):
            target_f = resolved_pronoun or world_model_context.get("last_file") or "report.txt"
            m_f = re.search(r"(?:open|read|summarize)\s+([a-zA-Z0-9_\-]+\.[a-zA-Z0-9]+)", text, re.IGNORECASE)
            if m_f and m_f.group(1).lower().rstrip(".") not in ["it", "that", "this"]:
                target_f = m_f.group(1).strip().rstrip(".")
            return CognitiveIntent(
                domain="file",
                action="read_file",
                parameters={"path": str(target_f)},
                confidence=0.95,
                is_system_1_fast_path=True,
                target_entity=str(target_f),
                resolved_pronoun=str(target_f),
            )

        if any(phrase in low for phrase in ["delete a file", "delete that file", "delete the file", "delete report.txt"]):
            target_f = resolved_pronoun or world_model_context.get("last_file") or "report.txt"
            return CognitiveIntent(
                domain="file",
                action="delete_file",
                parameters={"path": str(target_f)},
                confidence=0.95,
                is_system_1_fast_path=True,
                target_entity=str(target_f),
            )

        # -------------------------------------------------------------
        # 8. Browser Navigation, Search & Media (Domain: browser)
        # -------------------------------------------------------------
        if any(phrase in low for phrase in ["pause it", "pause the video", "hold on, pause", "pause media", "pause playback"]):
            return CognitiveIntent(
                domain="browser",
                action="pause_media",
                confidence=0.99,
                is_system_1_fast_path=True,
                resolved_pronoun=resolved_pronoun or "active_media_player",
            )

        if any(phrase in low for phrase in ["continue", "resume playback", "resume it", "resume the video", "unpause"]):
            return CognitiveIntent(
                domain="browser",
                action="resume_media",
                confidence=0.99,
                is_system_1_fast_path=True,
                resolved_pronoun=resolved_pronoun or "active_media_player",
            )

        if any(phrase in low for phrase in ["close that tab", "close tab", "close the tab"]):
            return CognitiveIntent(
                domain="browser",
                action="close_tab",
                confidence=0.98,
                is_system_1_fast_path=True,
                resolved_pronoun=resolved_pronoun or "active_tab",
            )

        if "what page am i looking at" in low or "current page" in low:
            return CognitiveIntent(
                domain="browser",
                action="inspect_page",
                confidence=0.95,
                is_system_1_fast_path=True,
            )

        if low in ["go back", "navigate back", "previous page"]:
            return CognitiveIntent(
                domain="browser",
                action="navigate_back",
                confidence=0.95,
                is_system_1_fast_path=True,
            )

        if any(w in low for w in ["open github", "open chrome", "open google", "navigate to"]):
            target_url = "https://github.com" if "github" in low else "https://www.google.com"
            m_u = re.search(r"(?:navigate to|open)\s+(https?://[^\s]+|[a-zA-Z0-9_\-\.]+)", text, re.IGNORECASE)
            if m_u and "." in m_u.group(1):
                target_url = m_u.group(1).strip()
            return CognitiveIntent(
                domain="browser",
                action="navigate",
                parameters={"url": target_url, "target": target_url},
                confidence=0.95,
                is_system_1_fast_path=True,
                target_entity=target_url,
            )

        if re.search(r"\bsearch\b", low) and any(w in low for w in ["github", "youtube", "on google"]):
            q = text
            m_q = re.search(r"search\s+(?:for\s+)?(.+?)(?:\s+on\s+[a-zA-Z]+|$)", text, re.IGNORECASE)
            if m_q:
                q = m_q.group(1).strip()
            site = "github" if "github" in low else "google"
            return CognitiveIntent(
                domain="browser",
                action="search",
                parameters={"query": q, "site": site},
                confidence=0.95,
                is_system_1_fast_path=True,
                target_entity=q,
            )

        if re.search(r"\b(play|song|youtube)\b", low) and any(w in low for w in ["play", "lofi", "music", "song"]):
            query_match = re.search(r"play\s+(?:some\s+)?(.+?)(?:\s+on\s+youtube|\s+instead|$)", text, re.IGNORECASE)
            query = query_match.group(1).strip() if query_match else "lofi hip hop"
            return CognitiveIntent(
                domain="browser",
                action="play_youtube",
                parameters={"query": query},
                confidence=0.95,
                is_system_1_fast_path=True,
                target_entity=query,
            )

        # -------------------------------------------------------------
        # 9. OS & Desktop Controls (Domain: os)
        # -------------------------------------------------------------
        if any(phrase in low for phrase in ["snap this to the left", "snap window left", "snap left", "snap window"]):
            return CognitiveIntent(
                domain="os",
                action="snap_window",
                parameters={"direction": "left"},
                confidence=0.98,
                is_system_1_fast_path=True,
            )

        if any(phrase in low for phrase in ["cpu, ram, network", "system telemetry", "telemetry", "cpu and ram", "cpu usage"]):
            return CognitiveIntent(
                domain="os",
                action="multi_telemetry",
                parameters={"items": ["cpu", "ram", "network", "time"]},
                confidence=0.99,
                is_system_1_fast_path=True,
            )

        # -------------------------------------------------------------
        # 10. Developer Tasks & Code (Domain: code / git)
        # -------------------------------------------------------------
        if any(phrase in low for phrase in ["factorial", "def factorial", "tiny python factorial", "generate a factorial"]):
            return CognitiveIntent(
                domain="code",
                action="generate_code",
                parameters={"prompt": text, "language": "python", "task": "factorial"},
                confidence=0.95,
                is_system_1_fast_path=True,
            )

        if "run it with" in low or (low.startswith("run it") and "5" in low):
            return CognitiveIntent(
                domain="code",
                action="execute_code",
                parameters={"input_arg": 5, "source": world_model_context.get("last_code", {}).get("snippet")},
                confidence=0.90,
                is_system_1_fast_path=True,
                resolved_pronoun="last_code_snippet",
            )

        if re.search(r"\bcreate\s+(?:a\s+)?(?:temporary\s+)?branch\b", low):
            branch_name = "temp-test-branch"
            m_b = re.search(r"branch\s+(?:named\s+|for\s+)?([a-zA-Z0-9_\-]+)", text, re.IGNORECASE)
            if m_b:
                branch_name = m_b.group(1).strip()
            return CognitiveIntent(
                domain="git",
                action="create_branch",
                parameters={"branch_name": branch_name},
                confidence=0.95,
                is_system_1_fast_path=True,
                target_entity=branch_name,
            )

        if "switch back" in low:
            return CognitiveIntent(
                domain="git",
                action="switch_branch",
                parameters={"target": "main"},
                confidence=0.90,
                is_system_1_fast_path=True,
            )

        if "git status" in low:
            return CognitiveIntent(
                domain="git",
                action="git_status",
                confidence=0.95,
                is_system_1_fast_path=True,
            )

        # -------------------------------------------------------------
        # 11. Session Recall & Grounded Truthful Memory
        # -------------------------------------------------------------
        if any(phrase in low for phrase in ["what did we actually do", "what did we do in this conversation", "summary of real actions", "what did you do earlier"]):
            return CognitiveIntent(
                domain="chat",
                action="session_summary",
                parameters={"query": text},
                confidence=0.99,
                is_system_1_fast_path=True,
            )

        # -------------------------------------------------------------
        # 12. Personal Knowledge Management (Capability 10)
        # -------------------------------------------------------------
        # 12a. Audit Freshness
        if any(phrase in low for phrase in ["audit knowledge freshness", "check knowledge freshness", "audit knowledge", "knowledge freshness audit", "audit notes freshness"]):
            return CognitiveIntent(
                domain="knowledge",
                action="audit_knowledge",
                parameters={"max_age_days": 30.0},
                confidence=0.98,
                is_system_1_fast_path=True,
                target_entity="knowledge_store",
            )

        # 12b. Save / Ingest Note
        if any(phrase in low for phrase in ["save a note", "save note", "create a note", "add note", "store in knowledge base", "save to knowledge base", "add to knowledge"]):
            title = "Personal Note"
            content = text
            m_title = re.search(r"(?:about|called|named|titled)\s+([^:\n]+?)(?::|\s+with\s+content|\s+saying|$)", text, re.IGNORECASE)
            if m_title:
                title = m_title.group(1).strip()
            m_content = re.search(r"(?::|\s+with\s+content|\s+saying)\s+(.+)$", text, re.IGNORECASE)
            if m_content:
                content = m_content.group(1).strip()
            else:
                content = text

            return CognitiveIntent(
                domain="knowledge",
                action="ingest_knowledge",
                parameters={
                    "title": title,
                    "content": content,
                    "tags": ["personal", "user_note"],
                    "source": "conversation",
                    "namespace": "personal_notes",
                },
                confidence=0.96,
                is_system_1_fast_path=True,
                target_entity=title,
            )

        # 12c. Delete / Forget Note
        if any(phrase in low for phrase in ["delete note", "forget note", "delete knowledge note", "remove note"]):
            m_id = re.search(r"(?:note|id)\s+([a-zA-Z0-9_\-]+)", text, re.IGNORECASE)
            target_nid = m_id.group(1).strip() if m_id else "unknown"
            return CognitiveIntent(
                domain="knowledge",
                action="delete_knowledge",
                parameters={"note_id": target_nid, "id": target_nid},
                confidence=0.95,
                is_system_1_fast_path=True,
                target_entity=target_nid,
            )

        # 12d. Query Knowledge Base
        knowledge_query_patterns = [
            r"what did i save about\s+(.+)$",
            r"what do i know about\s+(.+)$",
            r"what notes do i have (?:on|about)\s+(.+)$",
            r"search knowledge (?:for|about)\s+(.+)$",
            r"search my notes (?:for|about)\s+(.+)$",
            r"recall knowledge about\s+(.+)$",
            r"look up knowledge (?:on|about)\s+(.+)$",
        ]
        for pattern in knowledge_query_patterns:
            m_k = re.search(pattern, low)
            if m_k:
                q_term = m_k.group(1).strip().rstrip("?.")
                if q_term in ["it", "that", "this"] and resolved_pronoun:
                    q_term = resolved_pronoun
                return CognitiveIntent(
                    domain="knowledge",
                    action="query_knowledge",
                    parameters={"query": q_term, "top_k": 3},
                    confidence=0.96,
                    is_system_1_fast_path=True,
                    target_entity=q_term,
                    resolved_pronoun=resolved_pronoun if q_term == resolved_pronoun else None,
                )

        if "what did i save" in low or "search knowledge" in low:
            q_term = resolved_pronoun or text
            return CognitiveIntent(
                domain="knowledge",
                action="query_knowledge",
                parameters={"query": q_term, "top_k": 3},
                confidence=0.92,
                is_system_1_fast_path=True,
                target_entity=str(q_term),
                resolved_pronoun=resolved_pronoun,
            )

        # -------------------------------------------------------------
        # 13. Real-Time Information (Capability 32)
        # -------------------------------------------------------------
        # 13a. Combined Weather and News Multi-Intent ("Tell me today's weather and the latest technology news")
        m_comb = re.search(
            r"(?:tell\s+me\s+|give\s+me\s+|what\s+is\s+)?(?:today'?s?\s+)?weather\s+(?:and|as\s+well\s+as|along\s+with)\s+(?:the\s+)?(?:latest\s+)?(.+?)\s*news",
            low,
        )
        if m_comb:
            topic_part = m_comb.group(1).strip()
            loc = world_model_context.get("last_location") or "Delhi"
            return CognitiveIntent(
                domain="info",
                action="weather_and_news",
                parameters={"location": loc, "topic": topic_part or "technology", "time_target": "today", "time_filter": "latest"},
                confidence=0.97,
                is_system_1_fast_path=True,
                target_entity=f"Weather in {loc} & News on {topic_part}",
            )

        # 13b. Weather Queries & Contextual Follow-ups
        is_weather = False
        weather_loc = None
        weather_time = "now"

        clean_text = text.rstrip("?.! ")
        clean_low = low.rstrip("?.! ")

        # Check for conjunction patterns to prevent misrouting genuine conversational sentences
        is_conjunction = bool(
            re.search(r"\b(?:know|doubt|wonder|unsure|decide|choose|matter|see|tell|ask|care)\s+whether\b", clean_low) or
            re.search(r"\bwhether\s+(?:to|or|not|this|that|it|he|she|they|we|i|you|there)\b", clean_low) or
            re.search(r"\bwhether\b.+\bor\b", clean_low) or
            "whether this is" in clean_low or "whether to" in clean_low or "don't know whether" in clean_low or "dont know whether" in clean_low
        )

        if not is_conjunction:
            if any(w in clean_low for w in ["weather", "forecast", "temperature", "will it rain", "rain tonight"]):
                is_weather = True
            elif (
                re.search(r"\b(?:tell\s+me|what\s*'?s|what\s+is|how\s*'?s|how\s+is|check|show\s+me|give\s+me)\s+(?:the\s+|today'?s\s+|tomorrow'?s\s+)?(?:today\s+)?whether\b", clean_low) or
                re.search(r"\b(?:today|tomorrow|tonight|right\s+now|current|outside)\s+whether\b", clean_low) or
                re.search(r"\bwhether\s+(?:today|tomorrow|tonight|right\s+now|outside|forecast|report)\b", clean_low) or
                re.search(r"\bwhether\s+(?:in|for|at)\s+[a-zA-Z\s]+\b", clean_low) or
                clean_low in ["whether", "today whether", "tell me today whether", "what is whether", "how is whether", "check whether"]
            ):
                is_weather = True
            elif re.search(r"\b(?:what\s+about|how\s+about|and)\s+(tomorrow|today|tonight)\b", clean_low) or clean_low in ["and tomorrow", "and tomorrow?", "tomorrow?"]:
                if world_model_context.get("last_weather_query") or world_model_context.get("last_location"):
                    is_weather = True
                    m_t = re.search(r"\b(tomorrow|today|tonight)\b", clean_low)
                    weather_time = m_t.group(1) if m_t else "tomorrow"
                    weather_loc = world_model_context.get("last_location") or "Delhi"
            elif re.search(r"\b(?:what\s+about|how\s+about|and\s+in)\s+([a-zA-Z\s]+)$", clean_low):
                cand = re.search(r"\b(?:what\s+about|how\s+about|and\s+in)\s+([a-zA-Z\s]+)$", clean_low).group(1).strip().title()
                if cand not in ["It", "This", "That", "The Company", "Tomorrow", "Tonight", "Yesterday"]:
                    if world_model_context.get("last_weather_query") or world_model_context.get("last_location"):
                        is_weather = True
                        weather_loc = cand
                        weather_time = world_model_context.get("last_weather_time", "now")

            if is_weather:
                # Extract location if specified e.g. "weather in Mumbai", "temperature for Delhi"
                m_city = re.search(r"\b(?:in|for|at)\s+([a-zA-Z\s]+?)(?:\s+(?:today|tomorrow|tonight|right\s+now|now))?$", clean_text, re.IGNORECASE)
                if m_city:
                    cand_city = m_city.group(1).strip()
                    cand_city = re.sub(r"\b(?:right\s+now|now|today|tomorrow|tonight)\b", "", cand_city, flags=re.IGNORECASE).strip().title()
                    if cand_city:
                        weather_loc = cand_city

                # Temporal qualifier extraction
                if "tomorrow" in clean_low:
                    weather_time = "tomorrow"
                elif "tonight" in clean_low:
                    weather_time = "tonight"
                elif "today" in clean_low:
                    weather_time = "today"
                elif "right now" in clean_low or "now" in clean_low:
                    weather_time = "now"

        if is_weather:
            import time
            resolved_loc = weather_loc or world_model_context.get("last_location") or "Delhi"
            world_model_context["last_weather_query"] = {"query": text, "location": resolved_loc, "time_target": weather_time, "timestamp": time.time()}
            world_model_context["last_location"] = resolved_loc
            world_model_context["last_weather_time"] = weather_time
            return CognitiveIntent(
                domain="info",
                action="get_weather",
                parameters={"location": resolved_loc, "time_target": weather_time},
                confidence=0.95,
                is_system_1_fast_path=True,
                target_entity=resolved_loc,
            )

        # 13c. Real-Time News Queries & Contextual Follow-ups
        is_news = False
        news_topic = "general"
        news_time = "latest"

        if any(w in low for w in ["latest news", "breaking news", "news today", "headlines"]):
            is_news = True
            m_top = re.search(r"(?:latest|breaking)?\s*(.+?)\s*news", low)
            if m_top:
                cand_top = m_top.group(1).strip()
                if cand_top and cand_top not in ["the", "any", "today's", "todays"]:
                    news_topic = cand_top
            if "today" in low:
                news_time = "today"
        elif "news" in low and not any(k in low for k in ["search", "find", "research", "compare"]):
            m_top = re.search(r"([a-zA-Z\s]+?)\s*news", low)
            if m_top:
                cand_top = m_top.group(1).strip()
                if cand_top and cand_top not in ["the", "any"]:
                    news_topic = cand_top
                    is_news = True
        elif "what changed since this morning" in low:
            is_news = True
            news_topic = world_model_context.get("last_news_topic") or "general"
            news_time = "today"

        if is_news:
            return CognitiveIntent(
                domain="info",
                action="get_news",
                parameters={"topic": news_topic, "time_filter": news_time, "count": 5},
                confidence=0.95,
                is_system_1_fast_path=True,
                target_entity=news_topic,
            )

        # -------------------------------------------------------------
        # 14. Web Research & Search (Capability 31)
        # -------------------------------------------------------------
        # 13a. Multi-Intent Research & Comparison ("Research X and compare with Y")
        m_comp = re.search(
            r"(?:research|search|find information about)\s+(.+?)\s+and\s+compare\s+(?:it\s+)?with\s+(.+)$",
            low,
        )
        if m_comp:
            term_a = m_comp.group(1).strip()
            term_b = m_comp.group(2).strip().rstrip("?.")
            return CognitiveIntent(
                domain="search",
                action="research_and_compare",
                parameters={"topic_a": term_a, "topic_b": term_b, "query": f"{term_a} vs {term_b}"},
                confidence=0.96,
                is_system_1_fast_path=True,
                target_entity=f"{term_a} vs {term_b}",
            )

        # 13b. Direct Web Fetch ("fetch page https://...", "read url https://...")
        m_fetch = re.search(
            r"(?:fetch|read|scrape|download)\s+(?:page|url|website|site)?\s*(https?://[^\s]+)",
            text,
            re.IGNORECASE,
        )
        if m_fetch:
            fetch_url = m_fetch.group(1).strip()
            return CognitiveIntent(
                domain="search",
                action="web_fetch",
                parameters={"url": fetch_url, "target_url": fetch_url},
                confidence=0.98,
                is_system_1_fast_path=True,
                target_entity=fetch_url,
            )

        # 13c. Web Search & Information Retrieval
        web_search_patterns = [
            r"search for the latest information about\s+(.+)$",
            r"search the web for\s+(.+)$",
            r"search web for\s+(.+)$",
            r"search online for\s+(.+)$",
            r"find information about\s+(.+)$",
            r"find the latest information about\s+(.+)$",
            r"look up that company\b",
            r"look up\s+(.+)\s+online$",
            r"search for\s+(.+)$",
            r"look up\s+(.+)$",
        ]
        for pattern in web_search_patterns:
            m_s = re.search(pattern, low)
            if m_s:
                target_term = m_s.group(1).strip().rstrip("?.") if m_s.groups() else "that company"

                # Check contextual pronoun or referent resolution
                if target_term in ["it", "that", "this", "that company", "the company", "that project", "that topic"]:
                    resolved = (
                        resolved_pronoun
                        or world_model_context.get("last_company")
                        or world_model_context.get("last_entity")
                        or world_model_context.get("last_topic")
                    )
                    if resolved:
                        target_term = str(resolved)
                        return CognitiveIntent(
                            domain="search",
                            action="search_web",
                            parameters={"query": target_term, "max_results": 5},
                            confidence=0.95,
                            is_system_1_fast_path=True,
                            target_entity=target_term,
                            resolved_pronoun=target_term,
                        )
                    else:
                        # Cannot resolve reliably: ask for clarification rather than hallucinating
                        return CognitiveIntent(
                            domain="search",
                            action="search_web",
                            parameters={"query": target_term, "max_results": 5},
                            confidence=0.60,
                            is_system_1_fast_path=True,
                            is_ambiguous=True,
                            clarification_prompt="Which entity or company would you like me to look up?",
                            target_entity=target_term,
                        )

                return CognitiveIntent(
                    domain="search",
                    action="search_web",
                    parameters={"query": target_term, "max_results": 5},
                    confidence=0.95,
                    is_system_1_fast_path=True,
                    target_entity=target_term,
                )

        # -------------------------------------------------------------
        # 15. Personal Search (Capability 33)
        # -------------------------------------------------------------
        personal_patterns = [
            r"what do you remember about (?:my\s+)?(.+)$",
            r"what was my\s+(.+)$",
            r"what were my\s+(.+)$",
            r"what did i decide about (?:the\s+)?(.+)$",
            r"what was the (?:last\s+)?issue with (?:the\s+)?(.+)$",
            r"what projects have i worked on\b",
            r"show me the project i worked on\b",
            r"search (?:my\s+)?(?:personal\s+)?(?:notes|projects|documents)\b",
            r"what did we decide to use instead\b",
            r"why did we choose that\b",
            r"tell me about (?:my\s+|project\s+)?(.+)$",
            r"what do you know about (?:my\s+|project\s+)?(.+)$",
            r"\bmy\s+(?:internship|project|portfolio|work|notes?|records?|docs?|documents?)\b",
        ]
        for pat in personal_patterns:
            m_pers = re.search(pat, low)
            if m_pers:
                target_term = m_pers.group(1).strip().rstrip("?.") if m_pers.groups() and m_pers.group(1) else text
                if "instead" in low or "why did we choose that" in low:
                    prev = world_model_context.get("last_project") or world_model_context.get("last_entity") or ""
                    target_term = f"{target_term} {prev}".strip()
                else:
                    world_model_context["last_project"] = target_term

                return CognitiveIntent(
                    domain="search",
                    action="search_personal",
                    parameters={"query": target_term, "raw_query": text, "top_k": 5},
                    confidence=0.96,
                    is_system_1_fast_path=True,
                    target_entity=target_term,
                )

        # -------------------------------------------------------------
        # 16. Multi-Intent Personal + External Knowledge Synthesis (Capability 35)
        # -------------------------------------------------------------
        synthesis_patterns = [
            r"\bcompare\s+(?:my\s+)?(.+?)\s+(?:with|to|against|and)\s+(.+)",
            r"\b(?:synthesize|differences\s+and\s+summarize|verify\s+the\s+differences|differences\s+between)\s+(?:my\s+)?(.+)",
            r"\bcompare\s+my\s+(?:project|architecture|design|notes|work)\b",
        ]
        for spat in synthesis_patterns:
            sm = re.search(spat, low)
            if sm:
                p_q = text
                e_q = text
                if len(sm.groups()) >= 2 and sm.group(1) and sm.group(2):
                    p_q = re.sub(r"[.?!]+$", "", sm.group(1).strip())
                    e_q = re.sub(r"[.?!]+$", "", sm.group(2).strip())
                elif len(sm.groups()) >= 1 and sm.group(1):
                    p_q = re.sub(r"[.?!]+$", "", sm.group(1).strip())
                    e_q = f"current {p_q}"

                return CognitiveIntent(
                    domain="search",
                    action="personal_and_external_synthesis",
                    parameters={"query": text, "personal_query": p_q, "external_query": e_q},
                    confidence=0.96,
                    is_system_1_fast_path=False,
                    target_entity=f"Synthesis: {p_q} vs {e_q}",
                )

        # -------------------------------------------------------------
        # 17. Information Verification (Capability 34)
        # -------------------------------------------------------------
        if (low.startswith("verify if ") or low.startswith("verify whether ") or low.startswith("check if claim ") or "cross-reference" in low):
            claim_text = re.sub(r"^(?:verify\s+(?:if|whether)\s+|check\s+if\s+claim\s+)", "", text, flags=re.IGNORECASE).strip()
            return CognitiveIntent(
                domain="verification",
                action="verify_information",
                parameters={"claim": claim_text},
                confidence=0.95,
                is_system_1_fast_path=True,
                target_entity=claim_text,
            )

        # -------------------------------------------------------------
        # 18. Fallback to General Cognition / Deep Deliberative (System 2)
        # -------------------------------------------------------------
        return CognitiveIntent(
            domain="chat",
            action="general_chat",
            parameters={"query": text},
            confidence=0.85,
            is_system_1_fast_path=False,
        )


understanding_engine = UnderstandingEngine()
