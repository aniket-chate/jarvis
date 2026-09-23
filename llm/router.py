"""Skill & Persona Intent Router for JARVIS.

Analyzes user queries, handles persona switching commands, dispatches to
appropriate skills, and routes synthesis to the Core LLM (Qwen2.5 3B).
"""

import re
import logging
from typing import Dict, Any, Optional
from config.settings import settings
from llm.ollama_client import OllamaClient
from skills.tavily_search import search_skill
from skills.system_control import system_skill
from skills.google_calendar import calendar_skill
from skills.google_gmail import gmail_skill
from skills.cast_skill import cast_skill
from skills.home_assistant import home_assistant_skill
from skills.identity_gate import identity_gate

logger = logging.getLogger("JARVIS.Router")


class IntentRouter:
    def __init__(self):
        self.llm = OllamaClient()

    async def handle_input(self, text: str, persona_override: Optional[str] = None) -> Dict[str, Any]:
        """Routes text input to persona management, tools, or Core LLM."""
        query = text.strip()
        active_persona = persona_override or settings.active_persona_name

        # 1. Explicit Persona Switching Intent
        switch_match = self._check_persona_switch(query)
        if switch_match:
            settings.set_active_persona(switch_match)
            new_persona = settings.get_persona()
            prompt = f"The user just switched to you. Introduce yourself briefly in your exact tone: '{new_persona.tone}'."
            response_text = await self.llm.generate_response(prompt, persona=new_persona.name)
            return {
                "type": "persona_switch",
                "active_persona": new_persona.name,
                "response": response_text,
            }

        # 2. System Diagnostics (Time, Storage, Battery)
        query_lower = query.lower()
        if any(w in query_lower for w in ["what time", "current time", "what date", "today's date"]):
            time_data = system_skill.get_time()
            return {
                "type": "system",
                "active_persona": active_persona,
                "response": f"It is currently {time_data['time']} on {time_data['date']}.",
            }

        if any(w in query_lower for w in ["disk space", "storage status", "free space"]):
            storage = system_skill.get_storage_status("C:")
            return {
                "type": "system",
                "active_persona": active_persona,
                "response": f"Drive {storage.get('drive', 'C:')} has {storage.get('free_gb')} GB free out of {storage.get('total_gb')} GB ({storage.get('free_percent')}% available).",
            }

        # 3. Calendar & Email Queries
        if any(w in query_lower for w in ["calendar", "my schedule", "upcoming events"]):
            cal_res = calendar_skill.list_upcoming_events()
            if not cal_res.get("success"):
                return {
                    "type": "skill",
                    "active_persona": active_persona,
                    "response": cal_res.get("error"),
                }
            events = cal_res.get("events", [])
            if not events:
                return {
                    "type": "skill",
                    "active_persona": active_persona,
                    "response": "You have no upcoming events on your primary calendar.",
                }
            event_summary = ", ".join(f"'{e['summary']}' at {e['start']}" for e in events)
            return {
                "type": "skill",
                "active_persona": active_persona,
                "response": f"Here are your upcoming events: {event_summary}.",
            }

        if any(w in query_lower for w in ["unread emails", "check my email", "check inbox"]):
            gmail_res = gmail_skill.list_unread_messages()
            if not gmail_res.get("success"):
                return {
                    "type": "skill",
                    "active_persona": active_persona,
                    "response": gmail_res.get("error"),
                }
            messages = gmail_res.get("messages", [])
            if not messages:
                return {
                    "type": "skill",
                    "active_persona": active_persona,
                    "response": "You have no unread messages in your inbox.",
                }
            return {
                "type": "skill",
                "active_persona": active_persona,
                "response": f"You have {len(messages)} unread messages. First snippet: {messages[0]['snippet']}",
            }

        # 4. Chromecast Discovery
        if any(w in query_lower for w in ["find chromecasts", "discover cast", "list cast devices"]):
            devices = cast_skill.discover_devices()
            if devices:
                return {
                    "type": "skill",
                    "active_persona": active_persona,
                    "response": f"Found {len(devices)} Google Cast devices: {', '.join(devices)}.",
                }
            return {
                "type": "skill",
                "active_persona": active_persona,
                "response": "No Google Cast devices found on the local subnet.",
            }

        # 5. Web Search Intent (Explicit request or real-time query)
        search_triggers = ["search for", "google", "look up", "who is", "latest news on", "weather in"]
        needs_search = any(query_lower.startswith(t) or t in query_lower for t in search_triggers)

        context_prompt = query
        if needs_search and settings.search_available:
            logger.info("[Router] Dispatching query to web search: %s", query)
            search_res = await search_skill.search(query)
            if search_res.get("success") and search_res.get("results"):
                snippets = [f"- {r['title']}: {r['content'][:250]}" for r in search_res["results"][:3]]
                combined_context = "\n".join(snippets)
                context_prompt = (
                    f"User Query: {query}\n\n"
                    f"Live Web Search Results:\n{combined_context}\n\n"
                    f"Please formulate a concise, helpful response synthesizing the above facts in your assigned persona tone."
                )

        # 6. Route to Core LLM (Qwen2.5 3B)
        response_text = await self.llm.generate_response(context_prompt, persona=active_persona)
        return {
            "type": "llm",
            "active_persona": active_persona,
            "response": response_text,
        }

    def _check_persona_switch(self, query: str) -> Optional[str]:
        """Detects if user asked to switch persona."""
        q = query.lower()
        patterns = {
            "jarvis": [r"\bswitch to jarvis\b", r"\bactivate jarvis\b", r"\bjarvis take over\b"],
            "friday": [r"\bswitch to friday\b", r"\bactivate friday\b", r"\bfriday take over\b"],
            "ultron": [r"\bswitch to ultron\b", r"\bactivate ultron\b", r"\bultron take over\b"],
            "omi": [r"\bswitch to omi\b", r"\bactivate omi\b", r"\bomi take over\b"],
        }
        for persona_key, pattern_list in patterns.items():
            for pat in pattern_list:
                if re.search(pat, q):
                    return settings.personas[persona_key].name
        return None


# Global instance
router = IntentRouter()
