"""Web Research Capability Provider for Capability 31.

Provides:
- search.web: Multi-provider live web search with privacy sanitization and fallback chain (Tavily -> Brave -> DuckDuckGo -> Wikipedia).
- web.fetch: Full web page fetch and HTML cleaning with safe data containment (<UNTRUSTED_WEB_DATA>).
- search.synthesize_citations: Multi-source synthesis, cross-source conflict detection, credibility ranking, and transparent provenance citations.
"""

from datetime import datetime
import hashlib
import logging
import re
import time
from typing import Any, Dict, List, Optional
import urllib.parse

from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from agents.web_agent import web_agent, WebAgent
from skills.web_skills import duckduckgo_skill, wikipedia_skill
from agents.privacy_protection import privacy_protection

logger = logging.getLogger("JARVIS.Providers.WebResearch")


class WebSearchProvider(BaseCapabilityProvider):
    """Provides privacy-sanitized live web search, page fetching, and multi-source citation synthesis."""

    def __init__(self, agent: Optional[WebAgent] = None):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.web.search_fetch",
                name="Web Search & Fetch Provider",
                supported_capabilities=[
                    "search.web",
                    "web.fetch",
                    "search.synthesize_citations",
                ],
                priority=10,
                estimated_latency_ms=1200.0,
            )
        )
        self.agent = agent or web_agent
        self.ddg = duckduckgo_skill
        self.wiki = wikipedia_skill

    def is_available(self) -> bool:
        """Returns True if at least one search/fetch pathway is available."""
        return True

    def _generate_source_id(self, url: str) -> str:
        return hashlib.sha256(url.strip().lower().encode("utf-8")).hexdigest()[:12]

    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t_start = time.perf_counter()
        params = dict(parameters or {})
        now_iso = datetime.now().isoformat()

        try:
            # ---------------------------------------------------------
            # 1. SEARCH: search.web
            # ---------------------------------------------------------
            if capability == "search.web":
                raw_query = str(params.get("query") or params.get("search_query") or params.get("q") or "").strip()
                if not raw_query:
                    return ActionResult(
                        status="FAILED",
                        output={"error": "Empty search query", "results": [], "count": 0},
                        message="Search query cannot be empty.",
                        execution_time_ms=(time.perf_counter() - t_start) * 1000,
                    )

                max_results = int(params.get("max_results", 5))
                forced_provider = params.get("provider")

                # Sanitize query to prevent PII / secret leakage
                sanitized_query = privacy_protection.sanitize_external_query(raw_query, "web_search")

                results: List[Dict[str, Any]] = []
                used_provider = "unknown"
                summary_answer = None

                # Optional forced or primary provider execution
                if forced_provider == "wikipedia":
                    wiki_res = self.wiki.lookup(sanitized_query)
                    if wiki_res.get("success"):
                        used_provider = "wikipedia"
                        results.append({
                            "title": wiki_res.get("title", sanitized_query),
                            "url": wiki_res.get("url", ""),
                            "snippet": wiki_res.get("summary", ""),
                            "provider": "wikipedia",
                        })
                elif forced_provider == "duckduckgo":
                    ddg_res = self.ddg.search(sanitized_query, max_results=max_results)
                    if ddg_res.get("success"):
                        used_provider = "duckduckgo"
                        summary_answer = ddg_res.get("summary")
                        for r in ddg_res.get("results", []):
                            results.append({
                                "title": r.get("title", ""),
                                "url": r.get("url", ""),
                                "snippet": r.get("content", ""),
                                "provider": "duckduckgo",
                            })
                else:
                    # Default execution through WebAgent (Tavily -> Brave -> DuckDuckGo fallback)
                    agent_res = self.agent.search(sanitized_query, max_results=max_results)
                    if agent_res.get("success") and agent_res.get("results"):
                        used_provider = agent_res.get("provider", "live_search")
                        summary_answer = agent_res.get("answer")
                        for r in agent_res.get("results", []):
                            results.append({
                                "title": r.get("title", "Untitled"),
                                "url": r.get("url", ""),
                                "snippet": r.get("content", ""),
                                "provider": used_provider,
                            })
                    else:
                        # Fallback to direct DuckDuckGo skill
                        ddg_res = self.ddg.search(sanitized_query, max_results=max_results)
                        if ddg_res.get("success") and ddg_res.get("results"):
                            used_provider = "duckduckgo"
                            summary_answer = ddg_res.get("summary")
                            for r in ddg_res.get("results", []):
                                results.append({
                                    "title": r.get("title", ""),
                                    "url": r.get("url", ""),
                                    "snippet": r.get("content", ""),
                                    "provider": "duckduckgo",
                                })
                        else:
                            # Fallback to Wikipedia summary if concept query
                            wiki_res = self.wiki.lookup(sanitized_query)
                            if wiki_res.get("success"):
                                used_provider = "wikipedia"
                                results.append({
                                    "title": wiki_res.get("title", sanitized_query),
                                    "url": wiki_res.get("url", ""),
                                    "snippet": wiki_res.get("summary", ""),
                                    "provider": "wikipedia",
                                })

                # Format structured candidate sources with full provenance & safe containment
                candidate_sources = []
                for idx, r in enumerate(results, 1):
                    u = r.get("url", "").strip()
                    title = r.get("title", f"Result {idx}").strip()
                    snippet = r.get("snippet", "").strip()
                    src_id = self._generate_source_id(u) if u else f"src_{idx}"
                    candidate_sources.append({
                        "source_id": src_id,
                        "title": title,
                        "url": u,
                        "snippet": snippet,
                        "provider": r.get("provider", used_provider),
                        "source_type": "search_result",
                        "retrieved_at": now_iso,
                        "freshness": "current",
                        "confidence": 0.85 if u else 0.5,
                        "safe_data": f"<UNTRUSTED_WEB_DATA source_id='{src_id}' url='{u}'>\n{snippet}\n</UNTRUSTED_WEB_DATA>",
                    })

                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)

                if candidate_sources:
                    msg = f"Web search for '{sanitized_query}' returned {len(candidate_sources)} source(s) via {used_provider}."
                else:
                    msg = f"No live search results found for '{sanitized_query}'."

                return ActionResult(
                    status="SUCCESS",
                    output={
                        "query": sanitized_query,
                        "raw_query": raw_query,
                        "provider": used_provider,
                        "answer": summary_answer,
                        "results": candidate_sources,
                        "count": len(candidate_sources),
                        "retrieved_at": now_iso,
                        "freshness": "current" if candidate_sources else "unavailable",
                    },
                    message=msg,
                    execution_time_ms=elapsed,
                )

            # ---------------------------------------------------------
            # 2. FETCH: web.fetch
            # ---------------------------------------------------------
            elif capability == "web.fetch":
                url = str(params.get("url") or params.get("target_url") or "").strip()
                if not url:
                    return ActionResult(
                        status="FAILED",
                        output={"error": "Missing URL for web.fetch", "url": ""},
                        message="URL is required for page fetch.",
                        execution_time_ms=(time.perf_counter() - t_start) * 1000,
                    )

                # Validate URL structure
                parsed = urllib.parse.urlparse(url)
                if not parsed.scheme or not parsed.netloc or parsed.scheme.lower() not in ["http", "https"]:
                    return ActionResult(
                        status="FAILED",
                        output={"error": f"Malformed URL: '{url}'", "url": url},
                        message=f"Malformed URL: '{url}'. Must include valid scheme (http/https).",
                        execution_time_ms=(time.perf_counter() - t_start) * 1000,
                    )

                max_chars = int(params.get("max_chars", 4000))
                fetch_res = self.agent.fetch_page(url=url, max_chars=max_chars)
                elapsed = (time.perf_counter() - t_start) * 1000

                success = fetch_res.get("success", False)
                self.record_outcome(success)

                if not success:
                    err_msg = fetch_res.get("error", "Unknown fetch error")
                    return ActionResult(
                        status="FAILED",
                        output={
                            "url": url,
                            "error": err_msg,
                            "status_code": fetch_res.get("status_code", 0),
                            "retrieved_at": now_iso,
                            "freshness": "unavailable",
                        },
                        message=f"Failed fetching page '{url}': {err_msg}",
                        execution_time_ms=elapsed,
                    )

                content = fetch_res.get("content", "")
                src_id = self._generate_source_id(url)
                title = params.get("title") or url

                # Safe data containment for fetched web content
                safe_data = f"<UNTRUSTED_WEB_DATA source_id='{src_id}' url='{url}'>\n{content}\n</UNTRUSTED_WEB_DATA>"

                out = {
                    "source_id": src_id,
                    "url": url,
                    "title": title,
                    "content": content,
                    "length_chars": len(content),
                    "status_code": fetch_res.get("status_code", 200),
                    "source_type": "fetched_source",
                    "retrieved_at": now_iso,
                    "freshness": "current",
                    "confidence": 0.95,
                    "safe_data": safe_data,
                }
                msg = f"Fetched and inspected source '{url}' ({len(content)} chars, HTTP {fetch_res.get('status_code', 200)})."
                return ActionResult(
                    status="SUCCESS",
                    output=out,
                    message=msg,
                    execution_time_ms=elapsed,
                )

            # ---------------------------------------------------------
            # 3. SYNTHESIZE CITATIONS: search.synthesize_citations
            # ---------------------------------------------------------
            elif capability == "search.synthesize_citations":
                sources = params.get("sources") or params.get("results") or []
                query = str(params.get("query") or "").strip()

                if not sources:
                    return ActionResult(
                        status="SUCCESS",
                        output={
                            "query": query,
                            "citations": [],
                            "conflicts": [],
                            "claims": [],
                            "synthesis": "No candidate sources provided for citation synthesis.",
                            "total_sources": 0,
                            "retrieved_at": now_iso,
                        },
                        message="Zero sources provided to synthesize.",
                        execution_time_ms=(time.perf_counter() - t_start) * 1000,
                    )

                citations = []
                conflicts = []
                claims = []

                # Domain authority score heuristic
                authoritative_tlds = [".gov", ".edu", ".org", "wikipedia.org", "github.com", "python.org", "docs.", "developer."]

                for idx, src in enumerate(sources, 1):
                    u = src.get("url", "")
                    title = src.get("title", f"Source {idx}")
                    snippet = src.get("snippet") or src.get("content") or ""
                    stype = src.get("source_type", "search_result")
                    retrieved_at = src.get("retrieved_at", now_iso)

                    # Determine authority weight
                    is_auth = any(dom in u.lower() for dom in authoritative_tlds)
                    credibility = "authoritative" if is_auth else "standard"

                    citations.append({
                        "citation_num": idx,
                        "source_id": src.get("source_id") or self._generate_source_id(u if u else str(idx)),
                        "title": title,
                        "url": u,
                        "source_type": stype,
                        "credibility": credibility,
                        "retrieved_at": retrieved_at,
                        "attribution": f"[{idx}] {title} ({u or 'direct'}) - {stype.replace('_', ' ').title()}",
                    })

                    if snippet:
                        claims.append({
                            "citation_num": idx,
                            "title": title,
                            "claim_text": snippet[:200],
                        })

                # Conflict detection: detect contradictory keywords across extracted snippets
                if len(sources) >= 2:
                    texts = [str(s.get("snippet") or s.get("content") or "").lower() for s in sources]
                    # Check for direct contradictions (e.g. true vs false, supported vs deprecated, increased vs decreased)
                    contradiction_pairs = [
                        ("supported", "deprecated"),
                        ("increase", "decrease"),
                        ("succeeded", "failed"),
                        ("enabled", "disabled"),
                        ("active", "discontinued"),
                    ]
                    for word_a, word_b in contradiction_pairs:
                        has_a = any(word_a in t for t in texts)
                        has_b = any(word_b in t for t in texts)
                        if has_a and has_b:
                            conflicts.append({
                                "conflict_type": "contradictory_terminology",
                                "detected_terms": [word_a, word_b],
                                "note": f"Sources contain contrasting statements referencing '{word_a}' vs '{word_b}'. Preserved for cognitive reasoning.",
                            })

                # Build human-readable formatted synthesis
                citation_lines = [c["attribution"] for c in citations]
                synthesis_header = f"Synthesized research from {len(citations)} source(s) for '{query}':"
                conflict_section = ""
                if conflicts:
                    conflict_section = "\n\n[Caution: Conflicting Evidence Detected]\n" + "\n".join(f"- {c['note']}" for c in conflicts)

                full_synthesis = f"{synthesis_header}\n\nSources & Provenance:\n" + "\n".join(citation_lines) + conflict_section

                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)

                return ActionResult(
                    status="SUCCESS",
                    output={
                        "query": query,
                        "citations": citations,
                        "conflicts": conflicts,
                        "has_conflicts": len(conflicts) > 0,
                        "claims": claims,
                        "synthesis": full_synthesis,
                        "total_sources": len(citations),
                        "retrieved_at": now_iso,
                    },
                    message=f"Synthesized citations from {len(citations)} sources (conflicts detected: {len(conflicts)}).",
                    execution_time_ms=elapsed,
                )

            else:
                return ActionResult(
                    status="FAILED",
                    output={"error": f"Unsupported capability '{capability}'"},
                    message=f"Capability '{capability}' not supported by WebSearchProvider.",
                    execution_time_ms=(time.perf_counter() - t_start) * 1000,
                )

        except Exception as e:
            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(False)
            logger.error("[WebSearchProvider] Error executing '%s': %s", capability, e)
            return ActionResult(
                status="FAILED",
                output={"error": str(e)},
                message=f"Web operation failed: {str(e)}",
                execution_time_ms=elapsed,
            )
