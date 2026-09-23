"""Web Search Skill for JARVIS.

Primary provider: Tavily (free tier).
Backup provider: Brave Search API.
Graceful degradation: If neither key is present in .env, disables itself with a clear log
and returns an informative message rather than crashing.
"""

import logging
from typing import Dict, List, Any
import httpx
from config.settings import settings

logger = logging.getLogger("JARVIS.Skills.Search")


class WebSearchSkill:
    def __init__(self):
        self.provider = settings.search_provider
        self.is_available = settings.search_available
        self.tavily_key = settings.tavily_api_key
        self.brave_key = settings.brave_api_key

        if not self.is_available:
            logger.warning("[Search Skill] Disabled: No search API key configured in .env")

    async def search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Executes a web search query and returns structured results."""
        if not self.is_available:
            return {
                "success": False,
                "provider": "none",
                "error": "Web search is disabled because neither TAVILY_API_KEY nor BRAVE_API_KEY is configured.",
                "results": [],
            }

        # 1. Primary: Tavily
        if self.tavily_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": self.tavily_key,
                            "query": query,
                            "max_results": max_results,
                            "search_depth": "basic",
                            "include_answer": True,
                        },
                    )
                    if res.status_code == 200:
                        data = res.json()
                        results = [
                            {
                                "title": r.get("title"),
                                "url": r.get("url"),
                                "content": r.get("content"),
                            }
                            for r in data.get("results", [])
                        ]
                        return {
                            "success": True,
                            "provider": "tavily",
                            "answer": data.get("answer"),
                            "results": results,
                        }
                    else:
                        logger.warning("[Tavily] Search failed with status %d: %s", res.status_code, res.text)
            except Exception as e:
                logger.error("[Tavily Error] %s", str(e))

        # 2. Backup: Brave Search
        if self.brave_key:
            try:
                headers = {"Accept": "application/json", "X-Subscription-Token": self.brave_key}
                params = {"q": query, "count": max_results}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.get("https://api.search.brave.com/res/v1/web/search", headers=headers, params=params)
                    if res.status_code == 200:
                        data = res.json()
                        web_results = data.get("web", {}).get("results", [])
                        results = [
                            {
                                "title": r.get("title"),
                                "url": r.get("url"),
                                "content": r.get("description"),
                            }
                            for r in web_results
                        ]
                        return {
                            "success": True,
                            "provider": "brave",
                            "answer": None,
                            "results": results,
                        }
            except Exception as e:
                logger.error("[Brave Search Error] %s", str(e))

        return {
            "success": False,
            "provider": self.provider,
            "error": "Web search request could not be completed.",
            "results": [],
        }


# Global instance
search_skill = WebSearchSkill()
