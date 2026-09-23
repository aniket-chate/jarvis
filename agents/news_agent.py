"""News Agent for JARVIS Layer 3 (Group 1).

Fetches latest topic-based news using web_agent search.
Extracts headlines, source summaries, and links.
"""

import logging
from typing import Dict, Any, List

from agents.web_agent import web_agent

logger = logging.getLogger("JARVIS.NewsAgent")


class NewsAgent:
    """Agent for topic and category-based news summarization."""

    def fetch_news(self, topic: str = "technology", count: int = 5) -> Dict[str, Any]:
        """Queries web_agent for recent news headlines on the given topic (localized to India)."""
        geo_terms = ["india", "delhi", "mumbai", "bengaluru", "us", "uk", "global", "world", "america", "europe"]
        has_geo = any(term in topic.lower() for term in geo_terms)
        query = f"latest {topic} news in India today" if not has_geo else f"latest {topic} news today"
        logger.info("[NewsAgent] Fetching news for topic: '%s' (Query: '%s')", topic, query)

        search_result = web_agent.search(query=query, max_results=count)
        if not search_result.get("success"):
            return {
                "success": False,
                "topic": topic,
                "error": search_result.get("error", "Failed to retrieve news."),
                "articles": []
            }

        articles: List[Dict[str, str]] = []
        for r in search_result.get("results", []):
            articles.append({
                "headline": r.get("title", "Untitled"),
                "summary": r.get("content", ""),
                "source_url": r.get("url", "")
            })

        return {
            "success": True,
            "topic": topic,
            "count": len(articles),
            "articles": articles
        }

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator Agent Router."""
        topic = inputs.get("topic", inputs.get("query", "technology"))
        count = inputs.get("count", inputs.get("max_results", 5))

        try:
            from capabilities.intelligence import capability_intelligence
            provider = capability_intelligence.select_provider("info.get_news")
            if provider:
                action_res = provider.execute("info.get_news", {"topic": topic, "count": count})
                if action_res.status == "SUCCESS" and action_res.output:
                    out = dict(action_res.output)
                    msg = action_res.message
                    if not msg and out.get("articles"):
                        lines = [f"Here are the latest news items on {topic}:"]
                        for idx, a in enumerate(out["articles"][:4], 1):
                            lines.append(f"{idx}. {a.get('headline')}\n   {a.get('summary', '')[:140]}")
                        msg = "\n\n".join(lines)
                    out["message"] = msg
                    out["response"] = msg
                    out["output"] = msg
                    out["success"] = True
                    return out
        except Exception as prov_err:
            logger.debug("[NewsAgent] Capability provider route fallback: %s", prov_err)

        res = self.fetch_news(topic=topic, count=count)
        if res.get("success") and res.get("articles"):
            lines = [f"Here are the latest news items on {topic}:"]
            for idx, a in enumerate(res["articles"][:4], 1):
                lines.append(f"{idx}. {a.get('headline')}\n   {a.get('summary', '')[:140]}")
            formatted = "\n\n".join(lines)
            res["message"] = formatted
            res["response"] = formatted
            res["output"] = formatted
        return res


news_agent = NewsAgent()
