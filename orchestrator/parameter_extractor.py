"""Structured Parameter Extraction Layer for JARVIS Layer 2.

Parses natural language requests into strict JSON schemas before executing
file, communication, scheduling, or web actions. Logs extracted parameters
explicitly to eliminate ambiguity bugs (such as naming a file 'called').
Uses fast regex-backed heuristics combined with structured parsing.
"""

import re
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger("JARVIS.ParameterExtractor")


class ParameterExtractor:
    """Extracts typed, structured parameters from natural language instructions."""

    @classmethod
    def extract_file_params(cls, text: str) -> Dict[str, Any]:
        """Extracts file operation parameters (action, filename, destination, directory, content)."""
        lower = text.strip().lower()
        action = "read"
        filename = ""
        destination = ""
        directory = "documents"
        content = ""

        requires_clarification = False
        clarification_prompt = ""

        # 1. Determine primary imperative action with word boundaries and grammar precedence
        is_list_search_op = bool(re.search(r"\b(?:list|browse|inspect|search|find|show|view|check)\s+(?:recent\s+)?(?:files|documents|docs|records|workspace|directory)\b", lower)) or bool(re.search(r"\b(?:recent\s+(?:files|documents|docs))\b", lower))

        # Destructive actions take highest semantic precedence
        if re.search(r"\b(delete|remove|erase|trash)\b", lower):
            action = "delete"
        elif re.search(r"\b(rename)\b", lower):
            action = "rename"
        elif re.search(r"\b(move|transfer|relocate)\b", lower):
            action = "move"
        elif is_list_search_op or re.search(r"\b(search|find|locate|grep)\b", lower):
            action = "search"
        elif re.search(r"\b(read|open|view|show|cat|inspect)\b", lower):
            action = "read"
        elif re.search(r"\b(create|make|write|save)\b", lower) and not re.search(r"\b(?:created|saved)\s+file\b", lower):
            action = "create"

        # Detect directory scope
        for d in ["workspace", "desktop", "downloads", "documents"]:
            if (
                f"in {d}" in lower
                or f"in my {d}" in lower
                or f"from {d}" in lower
                or f"from my {d}" in lower
                or f"in the {d}" in lower
                or f"in the authorized {d}" in lower
                or f"{d} scope" in lower
                or f"the authorized {d}" in lower
                or f"{d}" in lower.split()
            ):
                directory = d
                break

        # Check anaphoric references: "the created file", "the one I just created", "the file you created", "that file", "it"
        is_referential = bool(re.search(
            r"\b(?:the\s+)?(?:created\s+file|file\s+(?:you|i)\s+(?:just\s+)?(?:created|made)|(?:one|file)\s+(?:you|i)\s+(?:just\s+)?(?:created|made)|the\s+one\s+(?:i|you)\s+(?:just\s+)?(?:created|made)|that\s+file|this\s+file|the\s+file|that\s+one|this\s+one|it|that)\b",
            lower
        ))

        # 2. Extract action-specific parameters
        if action == "delete":
            # Direct pattern: delete [the file] [called/named] X.ext
            m_del = re.search(
                r"\b(?:delete|remove|erase)\s+(?:the\s+)?(?:file\s+)?(?:called|named)?\s*['\"]?([a-zA-Z0-9_.-]+\.[a-zA-Z0-9]+)['\"]?",
                text,
                re.IGNORECASE
            )
            if m_del:
                filename = m_del.group(1).strip()
            elif is_referential:
                # Anaphoric resolution via WorldModel
                try:
                    from cognitive.world_model import world_model
                    ref = world_model.resolve_reference(text)
                    if ref.get("file_path"):
                        filename = ref["file_path"]
                        logger.info("[ParameterExtractor] Resolved referential target for delete: '%s'", filename)
                except Exception as ref_err:
                    logger.debug("[ParameterExtractor] Reference resolution error: %s", ref_err)

            if not filename and not is_referential:
                # General token extraction
                m_del_gen = re.search(
                    r"\b(?:delete|remove|erase)\s+(?:the\s+)?(?:file\s+)?(?:called|named)?\s*['\"]?([a-zA-Z0-9_.-]+)['\"]?",
                    text,
                    re.IGNORECASE
                )
                if m_del_gen:
                    cand = m_del_gen.group(1).strip()
                    if cand.lower() not in ["the", "file", "created", "it", "that", "this"]:
                        filename = cand

            if not filename:
                requires_clarification = True
                clarification_prompt = "Which file would you like me to delete?"

        elif action == "rename":
            m_ren = re.search(
                r"\brename\s+(?:the\s+)?(?:file\s+)?(?:called\s+)?['\"]?([a-zA-Z0-9_.-]+)['\"]?\s+(?:to|as)\s+['\"]?([a-zA-Z0-9_.-]+)['\"]?",
                text,
                re.IGNORECASE
            )
            if m_ren:
                filename = m_ren.group(1).strip()
                destination = m_ren.group(2).strip()
            elif is_referential:
                try:
                    from cognitive.world_model import world_model
                    ref = world_model.resolve_reference(text)
                    if ref.get("file_path"):
                        filename = ref["file_path"]
                except Exception:
                    pass
                m_to = re.search(r"\b(?:to|as)\s+['\"]?([a-zA-Z0-9_.-]+)['\"]?", text, re.IGNORECASE)
                if m_to:
                    destination = m_to.group(1).strip()
            if not filename:
                requires_clarification = True
                clarification_prompt = "Which file would you like me to rename?"

        elif action == "move":
            m_move = re.search(
                r"\bmove\s+(?:the\s+)?(?:file\s+)?(?:called\s+)?['\"]?([a-zA-Z0-9_.-]+)['\"]?\s+(?:to|into)\s+['\"]?([a-zA-Z0-9_./\\-]+)['\"]?",
                text,
                re.IGNORECASE
            )
            if m_move:
                filename = m_move.group(1).strip()
                destination = m_move.group(2).strip()
            elif is_referential:
                try:
                    from cognitive.world_model import world_model
                    ref = world_model.resolve_reference(text)
                    if ref.get("file_path"):
                        filename = ref["file_path"]
                except Exception:
                    pass
                if not filename:
                    try:
                        from orchestrator.context_manager import context_manager
                        ctx_f = context_manager.get_file()
                        if ctx_f and ctx_f.path:
                            filename = ctx_f.path
                    except Exception:
                        pass
                m_dest = re.search(r"\b(?:to|into)\s+(?:my\s+)?(documents|downloads|desktop|workspace)\b", lower)
                if m_dest:
                    destination = m_dest.group(1).strip()
            if not filename:
                requires_clarification = True
                clarification_prompt = "Which file would you like me to move?"

        elif action == "create":
            # 1. Explicit inline content extraction
            explicit_content_patterns = [
                r"(?:and\s+)?(?:put|write|save)\s+(?:all\s+)?(?:this|the\s+following)?\s*(?:information|content|text|details|data)?\s*(?:inside|in|into)\s*(?:it|the\s+file)?\s*[:\"']\s*(.+)$",
                r"\b(?:with\s+(?:the\s+following\s+)?(?:content|text|information)|saying|containing|with\s+body)\s*[:\"']?\s*(.+)$",
                r"\b(?:with\s+content|with\s+text)\s*['\"]([^'\"]+)['\"]",
            ]
            content_m = None
            for cp in explicit_content_patterns:
                m = re.search(cp, text, re.IGNORECASE | re.DOTALL)
                if m:
                    content_m = m
                    break

            content_ref_m = re.search(r"\b(?:save\s+)?(?:all\s+this\s+information|this\s+information|all\s+the\s+information|these\s+details|these\s+notes|the\s+summary|the\s+search\s+results)\b", lower)

            if content_m:
                content = content_m.group(1).strip().strip('"\'')
                text_clean = text[:content_m.start()].strip()
            elif content_ref_m:
                # Resolve content from WorldModel / Memory
                text_clean = text
                try:
                    from cognitive.world_model import world_model
                    ref = world_model.resolve_reference(text)
                    if ref.get("content"):
                        content = ref["content"]
                        logger.info("[ParameterExtractor] Resolved contextual content for file (%d chars)", len(content))
                except Exception:
                    pass

                if not content:
                    try:
                        from orchestrator.memory import memory_manager
                        last_resp = memory_manager.recall("last_response") or memory_manager.recall("last_tool_output")
                        if last_resp and isinstance(last_resp, str) and len(last_resp.strip()) > 5:
                            content = last_resp.strip()
                            logger.info("[ParameterExtractor] Resolved file content from memory (%d chars)", len(content))
                    except Exception:
                        pass

                if not content:
                    requires_clarification = True
                    clarification_prompt = "What information or content would you like me to save in the file?"
            else:
                text_clean = text

            # Check if user explicitly asked to put/write content, but content remained empty:
            user_demanded_content = bool(re.search(r"\b(?:with\s+content|put\s+.*inside|with\s+text|saying|containing)\b", lower))
            if user_demanded_content and not content:
                requires_clarification = True
                clarification_prompt = "What content would you like me to put in the file?"

            # Filename extraction
            m_name = re.search(
                r"\b(?:create|make|write|save)\s+(?:a\s+)?(?:new\s+)?(?:file\s+)?(?:called|named)?\s*['\"]?([a-zA-Z0-9_.-]+\.[a-zA-Z0-9]+)['\"]?",
                text_clean,
                re.IGNORECASE
            )
            if m_name:
                filename = m_name.group(1).strip()
            else:
                ext_m = re.search(r"\b([a-zA-Z0-9_.-]+\.[a-zA-Z0-9]{1,5})\b", text_clean)
                if ext_m:
                    filename = ext_m.group(1).strip()

        elif action == "search":
            m_search = re.search(
                r"\b(?:search|find)\s+(?:for\s+)?(?:a\s+)?(?:file\s+)?(?:called|named)?\s*['\"]?([a-zA-Z0-9_*.-]+)['\"]?\s+(?:in|under)\s+(documents|downloads|desktop|workspace)",
                text,
                re.IGNORECASE
            )
            if m_search:
                filename = m_search.group(1).strip()
                directory = m_search.group(2).strip().lower()
            else:
                m_search2 = re.search(r"\b(?:search|find)\s+(?:for\s+)?(?:a\s+file\s+called\s+|a\s+file\s+named\s+|file\s+)?['\"]?([^'\"]+?)['\"]?\s+(?:in|under)\s+(?:my\s+)?(documents|downloads|desktop|workspace)", text, re.IGNORECASE)
                if m_search2:
                    filename = m_search2.group(1).strip().replace("called ", "").replace("named ", "").strip()
                    directory = m_search2.group(2).strip().lower()
                else:
                    filename = "*"
            requires_clarification = False

        elif action == "read":
            m_read = re.search(
                r"\b(?:read|open|view|show|cat|inspect)\s+(?:the\s+)?(?:file\s+)?(?:called|named)?\s*['\"]?([a-zA-Z0-9_.-]+\.[a-zA-Z0-9]+)['\"]?",
                text,
                re.IGNORECASE
            )
            if m_read:
                filename = m_read.group(1).strip()
            elif is_referential:
                try:
                    from cognitive.world_model import world_model
                    ref = world_model.resolve_reference(text)
                    if ref.get("file_path"):
                        filename = ref["file_path"]
                        logger.info("[ParameterExtractor] Resolved referential target for read: '%s'", filename)
                except Exception:
                    pass
                if not filename:
                    try:
                        from orchestrator.context_manager import context_manager
                        ctx_f = context_manager.get_file()
                        if ctx_f and ctx_f.path:
                            filename = ctx_f.path
                    except Exception:
                        pass

            if not filename and not is_referential:
                ext_m = re.search(r"\b([a-zA-Z0-9_.-]+\.[a-zA-Z0-9]{1,5})\b", text)
                if ext_m:
                    filename = ext_m.group(1).strip()

            if not filename:
                requires_clarification = True
                clarification_prompt = "Which file would you like me to read?"


        params = {
            "action": action,
            "filename": filename,
            "destination": destination,
            "directory": directory,
            "content": content,
            "requires_clarification": requires_clarification,
            "clarification_prompt": clarification_prompt,
            "raw_query": text,
        }
        logger.info("[Structured Extraction] Extracted file parameters: %s", json.dumps(params))
        return params

    @classmethod
    def extract_communication_params(cls, text: str) -> Dict[str, Any]:
        """Extracts messaging parameters (channel, recipient, message)."""
        lower = text.strip().lower()
        channel = "whatsapp" if "whatsapp" in lower else ("email" if "email" in lower or "mail" in lower else "sms")
        recipient = "Contact"
        message = "Hello from JARVIS"

        # WhatsApp extraction
        if channel == "whatsapp":
            # Recipient
            recip_m = re.search(r"\bto\s+([a-zA-Z0-9_]+)", text, re.IGNORECASE)
            if recip_m:
                recipient = recip_m.group(1).strip().capitalize()

            # Message content
            body_m = re.search(r"\b(?:saying|that|with text|message)\s*[:\"']?(.+?)[\"']?$", text, re.IGNORECASE)
            if body_m:
                message = body_m.group(1).strip().strip('"\'')
            else:
                # Quoted text anywhere
                quote_m = re.search(r"['\"](.+?)['\"]", text)
                if quote_m:
                    message = quote_m.group(1).strip()

        params = {
            "channel": channel,
            "recipient": recipient,
            "message": message,
            "raw_query": text,
        }
        logger.info("[Structured Extraction] Extracted communication parameters: %s", json.dumps(params))
        return params

    @classmethod
    def extract_schedule_params(cls, text: str) -> Dict[str, Any]:
        """Extracts timer/alarm parameters (delay_seconds, message, fire_time)."""
        from datetime import datetime, timedelta
        lower = text.strip().lower()
        now = datetime.now()
        delay_sec = 60
        target_dt = None
        matched_time_span = ""

        # 1. Match relative durations: "in 2 minutes", "for 30 seconds", "1 hour"
        time_rel = re.search(r"\b(\d+)\s*(minutes?|mins?|seconds?|secs?|hours?|hrs?)\b", lower)
        if time_rel:
            val = int(time_rel.group(1))
            unit = time_rel.group(2)
            matched_time_span = time_rel.group(0)
            if "sec" in unit:
                delay_sec = val
            elif "hour" in unit or "hr" in unit:
                delay_sec = val * 3600
            else:
                delay_sec = val * 60
            target_dt = now + timedelta(seconds=delay_sec)
        else:
            # 2. Match clock times
            # Pattern A: 9.50pm, 9:50pm, 9.50 pm, 9:50 AM, 9.50, 9:50, 21:50
            m_time = re.search(r"\b(\d{1,2})[:.](\d{2})\s*(am|pm)?\b", lower)
            hour = None
            minute = 0
            meridiem = None

            if m_time:
                hour = int(m_time.group(1))
                minute = int(m_time.group(2))
                meridiem = m_time.group(3)
                matched_time_span = m_time.group(0)
            else:
                # Pattern B: 9pm, 9 pm, 7am, 7 am
                m_ampm = re.search(r"\b(\d{1,2})\s*(am|pm)\b", lower)
                if m_ampm:
                    hour = int(m_ampm.group(1))
                    minute = 0
                    meridiem = m_ampm.group(2)
                    matched_time_span = m_ampm.group(0)
                else:
                    # Pattern C: at 9, at 9 o'clock, of 9
                    m_at = re.search(r"\b(?:at|for|of)\s+(\d{1,2})\s*(?:o'?clock)?\b", lower)
                    if m_at:
                        hour = int(m_at.group(1))
                        minute = 0
                        matched_time_span = m_at.group(0)

            if hour is not None and 0 <= hour <= 24 and 0 <= minute < 60:
                if meridiem == "pm" and hour < 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0
                elif meridiem is None and hour < 12:
                    cand_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if cand_today <= now and (hour + 12) < 24:
                        hour += 12

                target_dt = now.replace(hour=hour % 24, minute=minute, second=0, microsecond=0)
                if target_dt <= now:
                    target_dt += timedelta(days=1)
                delay_sec = max(1, int((target_dt - now).total_seconds()))

        if target_dt is None:
            target_dt = now + timedelta(seconds=delay_sec)

        # Message extraction
        message = ""
        cleaned = text
        if matched_time_span:
            cleaned = re.sub(re.escape(matched_time_span), "", cleaned, flags=re.IGNORECASE)
        # Strip action trigger words
        cleaned = re.sub(r"\b(?:set|create|schedule)\s+(?:an?\s+)?(?:alarm|timer|reminder)\s*(?:of|at|for|in)?\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bremind\s+me\s*(?:to|about|in|at)?\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bwake\s+me\s+(?:up\s+)?(?:at|for|in)?\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip(" :,-.")

        if cleaned:
            cleaned = re.sub(r"^(?:to|about|for)\s+", "", cleaned, flags=re.IGNORECASE).strip()
            if cleaned:
                message = cleaned

        if not message:
            time_str = target_dt.strftime("%H:%M:%S")
            message = f"Scheduled alarm for {time_str}"

        params = {
            "delay_seconds": delay_sec,
            "message": message,
            "fire_time": target_dt.strftime("%H:%M:%S"),
            "fire_time_iso": target_dt.isoformat(),
            "raw_query": text,
        }
        logger.info("[Structured Extraction] Extracted schedule parameters: %s", json.dumps(params))
        return params

    # Aliases
    extract_file_parameters = extract_file_params
    extract_communication_parameters = extract_communication_params
    extract_schedule_parameters = extract_schedule_params


parameter_extractor = ParameterExtractor()
