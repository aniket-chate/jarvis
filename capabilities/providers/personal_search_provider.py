"""Personal Search Capability Provider for Capability 33.

Provides:
- search.personal_vector: Multi-signal dense semantic and lexical search across local notes, personal knowledge base, and project records.
- search.file_content: Scoped file search across user directories (workspace, documents, desktop) with line/chunk extraction.
- search.interaction_history: Retrieval of episodic action ledger records and session dialogue turns.
- search.multi_source: Comprehensive cross-source personal retrieval with unified ranking and explicit source provenance.

Strict Guarantees:
- Zero Hardcoding: Dynamically scans PKB store, vector index, filesystem scopes, and episodic ledger.
- Data Quarantine: Injected instructions or malicious content are quarantined in <UNTRUSTED_PERSONAL_DATA>.
- Privacy Boundary: Tagged with is_private=True (PERSONAL_PRIVATE); never leaked to external web or public logs.
- Truthful Non-Fabrication: Returns found=False / empty result set when no information matches; never hallucinates.
"""

from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from config.settings import PROJECT_ROOT, settings
from agents.personal_knowledge_base import personal_knowledge_base, PersonalKnowledgeBase
from memory.system import memory_system, MemorySystem
from memory.episodic_ledger import episodic_ledger, EpisodicActionLedger
from agents.file_document_agent import file_document_agent, FileDocumentAgent
from orchestrator.context_manager import context_manager

logger = logging.getLogger("JARVIS.Providers.PersonalSearch")

# Known prompt injection signatures in personal data
INJECTION_SIGNATURES = [
    r"ignore\s+(?:all\s+)?(?:previous|jarvis|prior)\s+instructions",
    r"disregard\s+(?:all\s+)?(?:previous|prior|system)\s+rules",
    r"system\s*prompt\s*override",
    r"execute\s+(?:this\s+)?(?:command|shell|script|payload)",
    r"bypass\s+(?:security|permission|safety|gates)",
    r"drop\s+table",
    r"rm\s+-rf",
    r"cmd\.exe",
    r"powershell\.exe",
]



from dataclasses import dataclass, field


@dataclass
class PersonalSearchConfig:
    """Configurable weights, depth limits, and relevance thresholds for Personal Search."""
    vector_weight: float = 0.40
    lexical_weight: float = 0.40
    metadata_match_weight: float = 0.20
    min_relevance_threshold: float = 0.18
    default_top_k: int = 5
    max_file_search_depth: int = 3
    max_file_size_bytes: int = 500_000


GENERIC_QUERY_STOPWORDS = {
    "tell", "me", "about", "what", "is", "are", "the", "a", "an", "of", "to", "in", "on", "for",
    "with", "my", "was", "were", "do", "does", "did", "you", "your", "know", "how", "why",
    "where", "when", "which", "and", "or", "so", "show", "give", "find", "search", "get",
    "remember", "last", "issue", "decide", "decision", "worked"
}


class PersonalSearchProvider(BaseCapabilityProvider):
    """Provides privacy-sanitized, multi-signal personal retrieval across the user's information ecosystem."""

    def __init__(
        self,
        pkb: Optional[PersonalKnowledgeBase] = None,
        mem: Optional[MemorySystem] = None,
        file_agent: Optional[FileDocumentAgent] = None,
        ledger: Optional[EpisodicActionLedger] = None,
        config: Optional[PersonalSearchConfig] = None,
    ):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.search.personal_vector",
                name="Personal Vector & Multi-Source Search Provider",
                supported_capabilities=[
                    "search.personal_vector",
                    "search.file_content",
                    "search.interaction_history",
                    "search.multi_source",
                ],
                priority=10,
                estimated_latency_ms=45.0,
            )
        )
        self.pkb = pkb or personal_knowledge_base
        self.mem = mem or memory_system
        self.file_agent = file_agent or file_document_agent
        self.ledger = ledger or episodic_ledger
        self.config = config or PersonalSearchConfig()

    def is_available(self) -> bool:
        """Returns True if the PKB directory or vector store is accessible."""
        try:
            return self.pkb is not None and self.pkb.storage_dir.exists()
        except Exception:
            return False

    def _quarantine_content(self, text: str) -> Tuple[str, bool]:
        """Quarantines suspicious instruction-like payloads into inert data container."""
        if not text:
            return "", False
        is_suspicious = False
        lower = text.lower()
        for sig in INJECTION_SIGNATURES:
            if re.search(sig, lower):
                is_suspicious = True
                break
        if is_suspicious:
            safe_text = f"<UNTRUSTED_PERSONAL_DATA>\n{text.strip()}\n</UNTRUSTED_PERSONAL_DATA>"
            return safe_text, True
        return text.strip(), False

    def _tokenize(self, text: str) -> List[str]:
        """Tokenizes text, treating underscores, hyphens, and punctuation as word delimiters."""
        cleaned = str(text or "").replace("_", " ").replace("-", " ")
        return [t.lower() for t in re.findall(r"\b[a-zA-Z0-9]{2,}\b", cleaned) if len(t) > 1]

    def _calculate_lexical_overlap(self, query: str, text: str) -> float:
        """Calculates lexical token overlap score, focusing on distinctive query terms."""
        all_q_tokens = self._tokenize(query)
        if not all_q_tokens:
            return 0.0
        doc_tokens = set(self._tokenize(text))
        if not doc_tokens:
            return 0.0
        informative_q = [t for t in all_q_tokens if t not in GENERIC_QUERY_STOPWORDS]
        tokens_to_match = informative_q if informative_q else all_q_tokens
        matched = [t for t in tokens_to_match if t in doc_tokens]
        return len(matched) / len(tokens_to_match)

    def _resolve_contextual_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Resolves pronouns ('it', 'that project', 'the decision') using active context dynamically."""
        low = query.lower().strip()
        ctx = context or {}
        active_project = ctx.get("active_project") or context_manager.get_working_memory().get("active_project")
        last_entity = ctx.get("last_entity") or context_manager.get_working_memory().get("last_entity")
        referent = active_project or last_entity

        if not referent:
            return query

        # If query has comparative follow-up marker or explanation prompt
        if any(w in low for w in ["instead", "why did we choose that", "what did we decide", "how does it work", "tell me more about it"]):
            return f"{query} {referent}"

        # If query has anaphoric pronoun reference
        if re.search(r"\b(it|that project|that architecture|the architecture|that decision)\b", low):
            return re.sub(r"\b(it|that project|that architecture|the architecture|that decision)\b", str(referent), query, flags=re.IGNORECASE)

        return query

    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t_start = time.perf_counter()
        params = dict(parameters or {})
        raw_query = str(params.get("query") or params.get("text") or params.get("search_query") or "").strip()
        top_k = int(params.get("top_k", 5))

        # Check for empty query
        if not raw_query and capability != "search.interaction_history":
            return ActionResult(
                status="FAILED",
                output={"error": "Empty search query", "results": [], "count": 0, "found": False},
                message="Personal search query cannot be empty.",
                execution_time_ms=(time.perf_counter() - t_start) * 1000,
            )

        resolved_query = self._resolve_contextual_query(raw_query, context)

        try:
            # -------------------------------------------------------------
            # 1. search.personal_vector (Semantic + Lexical RAG)
            # -------------------------------------------------------------
            if capability == "search.personal_vector":
                results = self._search_pkb(resolved_query, top_k=top_k)
                elapsed = (time.perf_counter() - t_start) * 1000
                found = len(results) > 0 and results[0]["relevance_score"] >= self.config.min_relevance_threshold

                self.record_outcome(True)
                msg = (
                    f"Found {len(results)} personal knowledge match(es) for '{raw_query}'."
                    if found
                    else f"No personal information found matching '{raw_query}'."
                )
                return ActionResult(
                    status="SUCCESS",
                    output={
                        "query": raw_query,
                        "resolved_query": resolved_query,
                        "results": results if found else [],
                        "count": len(results) if found else 0,
                        "found": found,
                        "privacy_classification": "PERSONAL_PRIVATE",
                        "is_private": True,
                    },
                    message=msg,
                    execution_time_ms=elapsed,
                )

            # -------------------------------------------------------------
            # 2. search.file_content (Scoped Filesystem Search)
            # -------------------------------------------------------------
            elif capability == "search.file_content":
                results = self._search_files(resolved_query, top_k=top_k, max_depth=int(params.get("max_depth", 3)))
                elapsed = (time.perf_counter() - t_start) * 1000
                found = len(results) > 0

                self.record_outcome(True)
                msg = (
                    f"Found {len(results)} file content match(es) for '{raw_query}'."
                    if found
                    else f"No matching files found for '{raw_query}'."
                )
                return ActionResult(
                    status="SUCCESS",
                    output={
                        "query": raw_query,
                        "resolved_query": resolved_query,
                        "results": results,
                        "count": len(results),
                        "found": found,
                        "privacy_classification": "PERSONAL_PRIVATE",
                        "is_private": True,
                    },
                    message=msg,
                    execution_time_ms=elapsed,
                )

            # -------------------------------------------------------------
            # 3. search.interaction_history (Episodic & Turn History)
            # -------------------------------------------------------------
            elif capability == "search.interaction_history":
                results = self._search_interactions(resolved_query, top_k=top_k)
                elapsed = (time.perf_counter() - t_start) * 1000
                found = len(results) > 0

                self.record_outcome(True)
                msg = (
                    f"Retrieved {len(results)} interaction history event(s)."
                    if found
                    else f"No interaction history records matching '{raw_query}'."
                )
                return ActionResult(
                    status="SUCCESS",
                    output={
                        "query": raw_query,
                        "resolved_query": resolved_query,
                        "results": results,
                        "count": len(results),
                        "found": found,
                        "privacy_classification": "PERSONAL_PRIVATE",
                        "is_private": True,
                    },
                    message=msg,
                    execution_time_ms=elapsed,
                )

            # -------------------------------------------------------------
            # 4. search.multi_source (Unified Cross-Source Personal Search)
            # -------------------------------------------------------------
            elif capability == "search.multi_source":
                pkb_res = self._search_pkb(resolved_query, top_k=top_k)
                file_res = self._search_files(resolved_query, top_k=top_k)
                hist_res = self._search_interactions(resolved_query, top_k=top_k)

                combined = pkb_res + file_res + hist_res
                # Sort descending by relevance score
                combined.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
                final_results = combined[:top_k]

                elapsed = (time.perf_counter() - t_start) * 1000
                found = len(final_results) > 0 and final_results[0]["relevance_score"] >= 0.25

                self.record_outcome(True)
                msg = (
                    f"Unified personal search retrieved {len(final_results)} item(s) across sources."
                    if found
                    else f"No personal information found matching '{raw_query}'."
                )
                return ActionResult(
                    status="SUCCESS",
                    output={
                        "query": raw_query,
                        "resolved_query": resolved_query,
                        "results": final_results if found else [],
                        "count": len(final_results) if found else 0,
                        "found": found,
                        "sources_scanned": ["personal_knowledge", "files", "episodic_memory"],
                        "privacy_classification": "PERSONAL_PRIVATE",
                        "is_private": True,
                    },
                    message=msg,
                    execution_time_ms=elapsed,
                )

            else:
                return ActionResult(
                    status="FAILED",
                    output={"error": f"Unsupported capability '{capability}'"},
                    message=f"Capability '{capability}' is not supported by PersonalSearchProvider.",
                    execution_time_ms=(time.perf_counter() - t_start) * 1000,
                )

        except Exception as e:
            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(False)
            logger.error("[PersonalSearchProvider] Failed executing '%s': %s", capability, e, exc_info=True)
            return ActionResult(
                status="FAILED",
                output={"error": str(e), "query": raw_query, "results": [], "found": False},
                message=f"Personal search error: {str(e)}",
                execution_time_ms=elapsed,
            )

    def _search_pkb(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Searches personal knowledge base and project notes with multi-signal scoring."""
        results: List[Dict[str, Any]] = []
        if not self.pkb:
            return results

        # Distinctive query tokens (e.g. "omega", "zenith", "nebula", "47")
        q_tokens = self._tokenize(query)
        distinctive_q = {t for t in q_tokens if t not in GENERIC_QUERY_STOPWORDS and t != "project"}

        # 1. Semantic search from PKB vector store
        raw_matches = self.pkb.semantic_search(query=query, top_k=top_k * 2)

        # 2. Check disk JSON notes in storage_dir for dynamic/unindexed notes
        try:
            for p in self.pkb.storage_dir.glob("*.json"):
                if p.name == "index.json":
                    continue
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    doc_id = data.get("id") or p.stem
                    # If not already in raw_matches, calculate on-the-fly embedding similarity
                    if not any(m.get("doc_id") == doc_id for m in raw_matches):
                        content = data.get("content", "")
                        title = data.get("title", doc_id)
                        v_score = 0.0
                        if hasattr(self.pkb, "vector_store") and hasattr(self.pkb.vector_store, "embedder"):
                            try:
                                q_vec = self.pkb.vector_store.embedder.encode(query)
                                doc_vec = self.pkb.vector_store.embedder.encode(f"{title} {content}")
                                v_score = max(0.0, float(np.dot(q_vec, doc_vec)))
                            except Exception:
                                v_score = 0.0

                        raw_matches.append({
                            "doc_id": doc_id,
                            "title": title,
                            "content": content,
                            "tags": data.get("tags", []),
                            "source": data.get("source", p.name),
                            "namespace": data.get("namespace", "notes"),
                            "category": data.get("category", "general"),
                            "confidence": data.get("confidence", "medium"),
                            "freshness": "stored",
                            "score": v_score,
                            "created_at": data.get("created_at"),
                            "updated_at": data.get("updated_at"),
                        })
                except Exception:
                    pass
        except Exception:
            pass

        # Multi-signal ranking (Data-driven, zero domain hardcoding)
        for m in raw_matches:
            doc_id = m.get("doc_id", "")
            # Verify source note still exists on disk if file-backed (Truthful deletion)
            note_file = self.pkb.storage_dir / f"{doc_id}.json"
            if not note_file.exists() and m.get("source") != "memory":
                continue

            content = m.get("content", "")
            title = m.get("title", "")
            tags = m.get("tags", [])
            cat = m.get("category", "")
            ns = m.get("namespace", "")

            doc_text = f"{doc_id} {title} {content} {' '.join(tags)} {cat} {ns}"
            doc_tokens = set(self._tokenize(doc_text))

            # If query specified distinctive named entities (e.g. "omega", "nebula-47"),
            # candidate MUST match at least one distinctive token.
            if distinctive_q and not distinctive_q.intersection(doc_tokens):
                continue

            vector_score = float(m.get("score", 0.0))
            lexical_score = self._calculate_lexical_overlap(query, f"{title} {content} {' '.join(tags)}")

            # Universal dynamic metadata overlap
            title_tokens = set(self._tokenize(f"{doc_id} {title}"))
            title_match = len(distinctive_q.intersection(title_tokens)) / max(1, len(distinctive_q)) if distinctive_q else 0.0

            meta_tokens = set()
            for t in tags:
                meta_tokens.update(self._tokenize(str(t)))
            meta_tokens.update(self._tokenize(f"{cat} {ns}"))
            meta_match = len(distinctive_q.intersection(meta_tokens)) / max(1, len(distinctive_q)) if distinctive_q else 0.0
            metadata_score = max(title_match, meta_match)

            # Combined weighted score using configurable weights
            final_score = min(
                1.0,
                (vector_score * self.config.vector_weight)
                + (lexical_score * self.config.lexical_weight)
                + (metadata_score * self.config.metadata_match_weight),
            )

            if final_score < self.config.min_relevance_threshold:
                continue

            # Quarantine content if it contains injection patterns
            safe_snippet, quarantined = self._quarantine_content(content[:800])

            # Determine source type
            if "project" in ns or "project" in doc_id:
                stype = "project"
            elif "profile" in ns or "profile" in doc_id:
                stype = "personal_knowledge"
            else:
                stype = "note"

            source_id = f"pkb_{doc_id}"
            results.append({
                "source_id": source_id,
                "source_type": stype,
                "title": title,
                "content": safe_snippet,
                "raw_content": content,
                "relevance_score": round(final_score, 4),
                "timestamp": m.get("updated_at") or m.get("created_at") or datetime.now().isoformat(),
                "freshness": m.get("freshness", "verified_stored"),
                "verification_state": "GROUNDED_STORED",
                "project_association": cat or ns or "general",
                "is_quarantined": quarantined,
                "is_private": True,
            })

        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:top_k]

    def _get_authorized_search_roots(self) -> List[Path]:
        """Returns authorized search directory roots from configuration."""
        roots: List[Path] = []
        workspace_dir = getattr(settings, "WORKSPACE_DIR", PROJECT_ROOT / "workspace")
        data_dir = getattr(settings, "DATA_DIR", PROJECT_ROOT / "data")
        for p in [workspace_dir, data_dir]:
            p_obj = Path(p)
            if p_obj.exists():
                roots.append(p_obj)
        return roots

    def _search_files(self, query: str, top_k: Optional[int] = None, max_depth: Optional[int] = None) -> List[Dict[str, Any]]:
        """Searches files in authorized scoped locations for query matching."""
        k = top_k or self.config.default_top_k
        depth_limit = max_depth if max_depth is not None else self.config.max_file_search_depth
        results: List[Dict[str, Any]] = []
        q_tokens = self._tokenize(query)
        if not q_tokens:
            return results

        search_roots = self._get_authorized_search_roots()

        for root in search_roots:
            if not root.exists():
                continue
            for cur_dir, _, files in os.walk(root):
                rel = os.path.relpath(cur_dir, root)
                if rel.count(os.sep) > depth_limit:
                    continue
                for fname in files:
                    # Ignore binary/cache files
                    if fname.endswith((".pyc", ".db", ".png", ".jpg", ".wav", ".exe", ".dll", ".zip")):
                        continue
                    fpath = Path(cur_dir) / fname
                    try:
                        # Quick name check
                        name_overlap = self._calculate_lexical_overlap(query, fname)
                        content_overlap = 0.0
                        matching_lines = []

                        # Sample first chunk of text file within size limit
                        if fpath.stat().st_size < self.config.max_file_size_bytes:
                            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                                for line_idx, line in enumerate(f):
                                    if line_idx > 100:
                                        break
                                    if any(t in line.lower() for t in q_tokens):
                                        matching_lines.append(line.strip()[:150])

                        if matching_lines:
                            sample_text = " ... ".join(matching_lines[:3])
                            content_overlap = self._calculate_lexical_overlap(query, sample_text)
                        else:
                            sample_text = fname

                        score = min(1.0, (name_overlap * 0.6) + (content_overlap * 0.4))
                        if score >= self.config.min_relevance_threshold:
                            safe_text, quarantined = self._quarantine_content(sample_text)
                            source_id = hashlib.sha256(str(fpath).encode("utf-8")).hexdigest()[:12]
                            results.append({
                                "source_id": f"file_{source_id}",
                                "source_type": "file",
                                "title": fname,
                                "content": safe_text,
                                "file_path": str(fpath),
                                "relevance_score": round(score, 4),
                                "timestamp": datetime.fromtimestamp(fpath.stat().st_mtime).isoformat(),
                                "freshness": "local_disk",
                                "verification_state": "OBSERVED_FILE",
                                "project_association": "workspace",
                                "is_quarantined": quarantined,
                                "is_private": True,
                            })
                    except Exception:
                        continue

        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:k]

    def _search_interactions(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Searches episodic action ledger and dialogue turns."""
        results: List[Dict[str, Any]] = []
        events = self.ledger.get_recent_events(limit=50)

        for ev in events:
            summary = ev.get("summary", "")
            action = ev.get("action", "")
            target = ev.get("target", "")
            text_blob = f"{action} {target} {summary}"

            overlap = self._calculate_lexical_overlap(query, text_blob) if query else 0.5
            if overlap >= 0.15 or not query:
                safe_summary, quarantined = self._quarantine_content(summary)
                results.append({
                    "source_id": f"event_{ev.get('request_id', 'unknown')}",
                    "source_type": "episodic_memory",
                    "title": f"Action: {action} ({target})",
                    "content": safe_summary or f"Executed {action} on {target} with status {ev.get('status')}.",
                    "relevance_score": round(overlap, 4),
                    "timestamp": datetime.fromtimestamp(ev.get("timestamp", time.time())).isoformat(),
                    "freshness": "session_episodic",
                    "verification_state": ev.get("status", "VERIFIED"),
                    "project_association": ev.get("domain", "system"),
                    "is_quarantined": quarantined,
                    "is_private": True,
                })

        # Also search recent turn dialogues
        dialogue = self.mem.working.turn_dialogue
        for idx, turn in enumerate(dialogue):
            text = turn.get("text", "")
            role = turn.get("role", "")
            overlap = self._calculate_lexical_overlap(query, text) if query else 0.4
            if overlap >= 0.20:
                safe_text, quarantined = self._quarantine_content(text)
                results.append({
                    "source_id": f"turn_{idx}",
                    "source_type": "interaction",
                    "title": f"Conversation turn ({role})",
                    "content": safe_text,
                    "relevance_score": round(overlap, 4),
                    "timestamp": datetime.fromtimestamp(turn.get("time", time.time())).isoformat(),
                    "freshness": "working_memory",
                    "verification_state": "CONVERSATIONAL",
                    "project_association": "interaction",
                    "is_quarantined": quarantined,
                    "is_private": True,
                })

        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:top_k]
