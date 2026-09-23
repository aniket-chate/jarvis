"""Wikipedia Agent for JARVIS Layer 3 (Group 1).

Retrieves factual concept lookups, historical overviews, and encyclopedia articles
via Wikipedia REST API (free, no API keys required).
"""

import logging
from typing import Dict, Any

from skills.web_skills import wikipedia_skill

logger = logging.getLogger("JARVIS.WikipediaAgent")


class WikipediaAgent:
    """Agent for encyclopedia knowledge lookups and definitions."""

    def lookup(self, query: str) -> Dict[str, Any]:
        logger.info("[WikipediaAgent] Looking up '%s'", query)
        return wikipedia_skill.lookup(query=query)

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator Agent Router."""
        query = inputs.get("query") or inputs.get("topic") or inputs.get("search_query") or ""
        return self.lookup(query=query)


wikipedia_agent = WikipediaAgent()
