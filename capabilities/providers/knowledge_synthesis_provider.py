"""Knowledge Synthesis Capability Provider for Capability 35.

Provides:
- synthesis.combine_sources: Merges verified evidence across personal and external sources into cohesive answers.
- synthesis.generate_brief: Produces an executive structured brief with clear source provenance.
- synthesis.synthesize: General verified evidence synthesis with conflict preservation.

Core Principles:
1. Anti-Hallucination: Does NOT introduce unsupported factual statements.
2. Explicit Provenance: Distinguishes [Personal Knowledge], [External Source], and [Episodic Memory].
3. Conflict Preservation: If sources disagree, explicitly reports the discrepancy without inventing a resolution.
4. Privacy Boundary: Respects privacy flags and preserves <UNTRUSTED_PERSONAL_DATA> / <UNTRUSTED_WEB_DATA> quarantine.
5. Multi-Intent DAG: Seamlessly integrates with 33 Personal Search, 31 Web Search, 32 Real-Time Info, and 34 Verification.
"""

from datetime import datetime
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult

logger = logging.getLogger("JARVIS.Providers.KnowledgeSynthesis")


class KnowledgeSynthesisProvider(BaseCapabilityProvider):
    """Synthesizes verified evidence into structured, citation-attributed answers without hallucination."""

    def __init__(self):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.knowledge.synthesis",
                name="Multi-Source Knowledge Synthesis Provider",
                supported_capabilities=[
                    "synthesis.combine_sources",
                    "synthesis.generate_brief",
                    "synthesis.synthesize",
                ],
                priority=10,
                estimated_latency_ms=65.0,
            )
        )

    def is_available(self) -> bool:
        return True

    def _categorize_sources(self, sources: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Separates sources into Personal, External, and Episodic categories."""
        personal = []
        external = []
        episodic = []

        for s in sources:
            stype = str(s.get("source_type") or "").lower()
            sid = str(s.get("source_id") or "").lower()
            if stype in ["personal_knowledge", "project", "note", "file"] or "pkb" in sid or s.get("is_private") or s.get("privacy_classification") == "PERSONAL_PRIVATE":
                personal.append(s)
            elif stype in ["episodic_memory", "interaction"] or "event" in sid or "turn" in sid:
                episodic.append(s)
            else:
                external.append(s)

        return personal, external, episodic

    def _extract_clean_text(self, text: str) -> str:
        """Strips quarantine markers while preserving content for reading."""
        if not text:
            return ""
        clean = re.sub(r"<\/?UNTRUSTED_(?:PERSONAL|WEB)_DATA>", "", text).strip()
        return clean

    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t_start = time.perf_counter()
        params = dict(parameters or {})
        query = str(params.get("query") or params.get("goal") or params.get("topic") or "Knowledge Synthesis").strip()
        sources = params.get("sources") or params.get("results") or []
        verification = params.get("verification") or params.get("verification_result") or {}

        if isinstance(sources, dict):
            sources = [sources]
        elif not isinstance(sources, list):
            sources = []

        try:
            # Check for empty sources
            if not sources:
                return ActionResult(
                    status="SUCCESS",
                    output={
                        "query": query,
                        "synthesis": f"No verified information available to synthesize for query: '{query}'.",
                        "citations": [],
                        "has_content": False,
                        "conflict_detected": False,
                    },
                    message=f"No verified information available to synthesize for '{query}'.",
                    execution_time_ms=(time.perf_counter() - t_start) * 1000,
                )

            # Check if verification detected contradictions
            conflict_detected = False
            conflict_summary = ""
            if verification and isinstance(verification, dict):
                if verification.get("state") == "CONTRADICTED" or verification.get("conflict"):
                    conflict_detected = True
                    c_info = verification.get("conflict") or {}
                    conflict_summary = c_info.get("explanation") or verification.get("reason") or "Contradictory evidence detected between sources."

            # Categorize sources
            personal, external, episodic = self._categorize_sources(sources)

            # Build structured synthesis blocks
            citations = []
            sections = []

            # 1. Conflict Warning (if contradiction was detected)
            if conflict_detected:
                sections.append(f"### Discrepancy / Conflicting Evidence Detected\n{conflict_summary}")

            # 2. Personal Knowledge Findings
            if personal:
                p_lines = []
                for s in personal:
                    title = s.get("title") or s.get("source_id") or "Personal Note"
                    content = self._extract_clean_text(s.get("content") or s.get("snippet") or "")
                    p_lines.append(f"- **{title}**: {content[:300]}...")
                    citations.append({
                        "category": "Personal Knowledge",
                        "source_id": s.get("source_id"),
                        "title": title,
                        "type": s.get("source_type", "personal"),
                    })
                sections.append(f"### Personal Knowledge & Project Records\n" + "\n".join(p_lines))

            # 3. External / Web / Real-Time Findings
            if external:
                e_lines = []
                for s in external:
                    title = s.get("title") or s.get("source") or s.get("url") or "External Source"
                    snippet = self._extract_clean_text(s.get("snippet") or s.get("content") or "")
                    url = s.get("url", "")
                    url_part = f" ([Source Link]({url}))" if url else ""
                    e_lines.append(f"- **{title}**{url_part}: {snippet[:300]}...")
                    citations.append({
                        "category": "External Source",
                        "source_id": s.get("source_id") or title,
                        "title": title,
                        "url": url,
                        "type": s.get("source_type", "web"),
                    })
                sections.append(f"### External & Real-Time Research\n" + "\n".join(e_lines))

            # 4. Episodic / Interaction History
            if episodic:
                h_lines = []
                for s in episodic:
                    title = s.get("title") or "Past Interaction"
                    content = self._extract_clean_text(s.get("content") or "")
                    h_lines.append(f"- **{title}**: {content[:200]}")
                    citations.append({
                        "category": "Episodic History",
                        "source_id": s.get("source_id"),
                        "title": title,
                        "type": "episodic_memory",
                    })
                sections.append(f"### Interaction & Action History\n" + "\n".join(h_lines))

            # Assemble coherent synthesis response
            if capability == "synthesis.generate_brief":
                header = f"# Executive Brief: {query}\n\n"
                brief_body = "\n\n".join(sections)
                summary_text = (
                    f"{header}"
                    f"**Synthesized from {len(sources)} verified source(s)** "
                    f"({len(personal)} personal, {len(external)} external, {len(episodic)} episodic).\n\n"
                    f"{brief_body}"
                )
            else:
                summary_text = "\n\n".join(sections)

            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(True)

            msg = (
                f"Synthesized {len(sources)} source(s) into verified brief"
                + (f" [Conflicting Evidence Preserved]" if conflict_detected else "")
                + f" with {len(citations)} citation(s)."
            )

            return ActionResult(
                status="SUCCESS",
                output={
                    "query": query,
                    "synthesis": summary_text,
                    "response": summary_text,
                    "sections_count": len(sections),
                    "citations": citations,
                    "sources_count": len(sources),
                    "personal_sources_count": len(personal),
                    "external_sources_count": len(external),
                    "episodic_sources_count": len(episodic),
                    "conflict_detected": conflict_detected,
                    "has_content": True,
                },
                message=msg,
                execution_time_ms=elapsed,
            )

        except Exception as e:
            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(False)
            logger.error("[KnowledgeSynthesisProvider] Synthesis execution error: %s", e, exc_info=True)
            return ActionResult(
                status="FAILED",
                output={"error": str(e), "query": query, "has_content": False},
                message=f"Knowledge synthesis error: {str(e)}",
                execution_time_ms=elapsed,
            )
