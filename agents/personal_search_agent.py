"""Personal Search & Knowledge Synthesis Agent for JARVIS Layer 3.

Routes personal retrieval, cross-source verification, and knowledge synthesis queries
through Capability Intelligence providers:
- Capability 33 (Personal Search: provider.search.personal_vector)
- Capability 34 (Information Verification: provider.verification.information)
- Capability 35 (Knowledge Synthesis: provider.knowledge.synthesis)
"""

import logging
from typing import Any, Dict, Optional

from capabilities.intelligence import capability_intelligence

logger = logging.getLogger("JARVIS.PersonalSearchAgent")


class PersonalSearchAgent:
    """Agent bridging Orchestrator requests to Personal Search and Synthesis capability providers."""

    def search_personal(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Retrieves personal information from Capability 33 provider."""
        logger.info("[PersonalSearchAgent] Executing personal search for '%s'", query)
        provider = capability_intelligence.select_provider("search.personal_vector")
        if not provider:
            return {"success": False, "error": "No provider registered for 'search.personal_vector'"}

        action_res = provider.execute("search.personal_vector", {"query": query, "top_k": top_k})
        out = dict(action_res.output) if isinstance(action_res.output, dict) else {"output": action_res.output}
        msg = action_res.message or out.get("message")
        out["success"] = (action_res.status == "SUCCESS")
        out["message"] = msg
        out["status"] = "success" if out["success"] else "failed"

        results = out.get("results") or []
        if out["success"] and results:
            lines = [f"Found {len(results)} personal information record(s) for '{query}':"]
            for idx, r in enumerate(results[:3], 1):
                t = r.get("title") or f"Record {idx}"
                c = (r.get("content") or "").strip().replace("\n", " ")
                if len(c) > 220:
                    c = c[:217] + "..."
                lines.append(f"{idx}. {t}: {c}")
            out["response"] = "\n".join(lines)
        else:
            out["response"] = msg
        return out

    def synthesize(self, query: str, sources: list, verification: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Synthesizes verified evidence via Capability 35 provider."""
        logger.info("[PersonalSearchAgent] Executing knowledge synthesis for '%s'", query)
        provider = capability_intelligence.select_provider("synthesis.combine_sources")
        if not provider:
            return {"success": False, "error": "No provider registered for 'synthesis.combine_sources'"}

        action_res = provider.execute("synthesis.combine_sources", {
            "query": query,
            "sources": sources,
            "verification": verification,
        })
        out = dict(action_res.output) if isinstance(action_res.output, dict) else {"output": action_res.output}
        msg = action_res.message or out.get("synthesis")
        out["success"] = (action_res.status == "SUCCESS")
        out["message"] = msg
        out["response"] = out.get("synthesis", msg)
        out["status"] = "success" if out["success"] else "failed"
        return out

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standard interface for Orchestrator Agent Router."""
        action = inputs.get("action", "search_personal")
        query = str(inputs.get("query") or inputs.get("prompt") or inputs.get("text") or "").strip()

        if action in ["synthesize", "synthesis", "combine_sources"]:
            sources = inputs.get("sources") or []
            verification = inputs.get("verification")
            return self.synthesize(query=query, sources=sources, verification=verification)
        else:
            top_k = int(inputs.get("top_k", 5))
            return self.search_personal(query=query, top_k=top_k)


personal_search_agent = PersonalSearchAgent()
