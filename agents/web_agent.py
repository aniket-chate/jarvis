"""Web Agent for JARVIS Layer 3 (Group 1).

Performs real web search using Tavily or Brave Search API.
Provides page fetch capabilities to retrieve and clean web page text.
Passes all outgoing queries through PrivacyProtection gate.
"""

import re
import logging
from typing import Dict, Any, Optional
import httpx

from config.settings import settings
from agents.privacy_protection import privacy_protection
from skills.web_skills import duckduckgo_skill, wikipedia_skill

logger = logging.getLogger("JARVIS.WebAgent")


class WebAgent:
    """Live web search and URL page fetching agent."""

    def __init__(self):
        self.tavily_key = settings.tavily_api_key
        self.brave_key = settings.brave_api_key
        self.provider = settings.search_provider
        self.is_available = settings.search_available

    def _localize_query(self, query: str) -> str:
        """Biases search queries lacking a specific country/city toward India."""
        q_lower = query.lower()

        # Check if a geographic location or country is already mentioned
        geo_terms = [
            "india", "delhi", "mumbai", "bengaluru", "bangalore", "hyderabad", "chennai", "kolkata",
            "pune", "ahmedabad", "jaipur", "kerala", "goa", "noida", "gurgaon",
            "us", "usa", "uk", "america", "london", "europe", "canada", "australia", "japan", "china",
            "singapore", "dubai", "france", "germany"
        ]
        has_geo = any(re.search(rf"\b{term}\b", q_lower) for term in geo_terms)
        if has_geo:
            return query

        # Location-sensitive search categories requiring regional bias
        location_sensitive = [
            "weather", "news", "hotel", "hotels", "restaurant", "restaurants",
            "flight", "flights", "train", "trains", "near me", "petrol", "diesel", "fuel",
            "gold rate", "gold price", "silver", "stock", "nifty", "sensex", "market", "movies",
            "cinema", "hospitals", "traffic", "election", "elections", "cricket"
        ]
        is_sensitive = any(term in q_lower for term in location_sensitive)
        if is_sensitive:
            localized = f"{query} India"
            logger.info("[WebAgent] Localized query to India: '%s' -> '%s'", query, localized)
            return localized

        return query

    def search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Executes real web search with privacy sanitization and India localization."""
        # Sanitize query to prevent PII/secret leaks
        clean_query = privacy_protection.sanitize_external_query(query, "web_search")
        target_query = self._localize_query(clean_query)
        logger.info("[WebAgent] Initiating search for query: '%s' (Provider: %s)", target_query, self.provider)

        # 1. Try Tavily (if key configured)
        if self.tavily_key:
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": self.tavily_key,
                            "query": target_query,
                            "max_results": max_results,
                            "search_depth": "basic",
                            "include_answer": True
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        results = [
                            {
                                "title": r.get("title", "No Title"),
                                "url": r.get("url", ""),
                                "content": r.get("content", "")
                            }
                            for r in data.get("results", [])
                        ]
                        return {
                            "success": True,
                            "provider": "tavily",
                            "answer": data.get("answer"),
                            "query": target_query,
                            "results": results
                        }
                    else:
                        logger.warning("[WebAgent] Tavily HTTP %d: %s", resp.status_code, resp.text)
            except Exception as e:
                logger.error("[WebAgent] Tavily search error: %s", str(e))

        # 2. Try Brave fallback (if key configured)
        if self.brave_key:
            try:
                headers = {"Accept": "application/json", "X-Subscription-Token": self.brave_key}
                with httpx.Client(timeout=10.0) as client:
                    resp = client.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        params={"q": clean_query, "count": max_results},
                        headers=headers
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_web = data.get("web", {}).get("results", [])
                        results = [
                            {
                                "title": r.get("title", ""),
                                "url": r.get("url", ""),
                                "content": r.get("description", "")
                            }
                            for r in raw_web
                        ]
                        return {
                            "success": True,
                            "provider": "brave",
                            "query": clean_query,
                            "results": results
                        }
            except Exception as e:
                logger.error("[WebAgent] Brave search error: %s", str(e))

        # 3. Free Web Fallback: DuckDuckGo Instant Answer Search
        logger.info("[WebAgent] Falling back to free DuckDuckGo search for '%s'", target_query)
        ddg_res = duckduckgo_skill.search(query=target_query, max_results=max_results)
        if ddg_res.get("success") and ddg_res.get("results"):
            return {
                "success": True,
                "provider": "duckduckgo_fallback",
                "query": target_query,
                "answer": ddg_res.get("summary"),
                "results": ddg_res.get("results", [])
            }

        return {
            "success": False,
            "provider": "none",
            "error": "Web search could not be completed with active providers.",
            "results": []
        }

    def fetch_page(self, url: str, max_chars: int = 4000) -> Dict[str, Any]:
        """Fetches web page content, stripping HTML tags to extract clean text."""
        logger.info("[WebAgent] Fetching URL: %s", url)
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JARVIS/1.0"}
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    html = resp.text
                    # Strip script/style tags
                    cleaned = re.sub(r"<(script|style).*?>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
                    # Strip tags
                    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
                    # Collapse whitespace
                    text = " ".join(cleaned.split())[:max_chars]
                    return {
                        "success": True,
                        "url": url,
                        "content": text,
                        "status_code": 200
                    }
                return {
                    "success": False,
                    "url": url,
                    "error": f"HTTP status {resp.status_code}",
                    "status_code": resp.status_code
                }
        except Exception as e:
            logger.error("[WebAgent] Fetch error for %s: %s", url, str(e))
            return {
                "success": False,
                "url": url,
                "error": str(e)
            }

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator Agent Router."""
        action = inputs.get("action", "search")
        if action == "fetch" or "url" in inputs:
            res = self.fetch_page(inputs["url"])
            res["response"] = res.get("content", "")[:500]
            res["output"] = res["response"]
            return res
        else:
            query = inputs.get("query", inputs.get("search_query", ""))
            res = self.search(query, max_results=inputs.get("max_results", 5))
            results = res.get("results", [])
            provider = res.get("provider", "live web search")
            if results:
                items_summary = []
                for idx, r in enumerate(results[:4], 1):
                    t = r.get("title", "").strip()
                    u = r.get("url", "").strip()
                    c = r.get("content", "").strip()
                    snippet = f"{idx}. {t} ({u})\n   {c[:140]}" if u else f"{idx}. {t}\n   {c[:140]}"
                    items_summary.append(snippet)
                formatted = f"[Source: Live Web Search via {provider.capitalize()}]\nHere are current real-world search results for '{query}':\n\n" + "\n\n".join(items_summary)
            else:
                formatted = f"[Source: Live Web Search]\nNo live search results found for '{query}'."
            res["response"] = formatted
            res["output"] = formatted
            res["message"] = formatted
            return res


web_agent = WebAgent()
