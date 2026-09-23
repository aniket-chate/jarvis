"""Knowledge Management Capability Provider wrapping PersonalKnowledgeBase and Semantic RAG.

Provides:
- knowledge.ingest: Ingest and deduplicate personal notes and documents
- knowledge.index: Index and synchronize physical files and dense vector index
- knowledge.query: Dense semantic retrieval with truthful status and data quarantine
- knowledge.audit_freshness: Audit knowledge staleness, age, and file integrity
- knowledge.delete: Verified deletion from index, disk file, and vector store
"""

import logging
import time
from typing import Any, Dict, Optional

from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from agents.personal_knowledge_base import personal_knowledge_base, PersonalKnowledgeBase

logger = logging.getLogger("JARVIS.Providers.Knowledge")


class KnowledgeProvider(BaseCapabilityProvider):
    """Provides personal knowledge management with provenance, truthful retrieval, and empirical verification."""

    def __init__(self, pkb: Optional[PersonalKnowledgeBase] = None):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.knowledge.rag_store",
                name="Personal Knowledge Base & Semantic RAG Provider",
                supported_capabilities=[
                    "knowledge.ingest",
                    "knowledge.index",
                    "knowledge.query",
                    "knowledge.audit_freshness",
                    "knowledge.delete",
                ],
                priority=10,
                estimated_latency_ms=25.0,
            )
        )
        self.pkb = pkb or personal_knowledge_base

    def is_available(self) -> bool:
        """Returns True if the knowledge base directory and vector store are accessible."""
        try:
            return self.pkb.storage_dir.exists() and self.pkb.vector_store is not None
        except Exception:
            return False

    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t_start = time.perf_counter()
        try:
            params = dict(parameters or {})

            if capability == "knowledge.ingest":
                title = params.get("title", "Untitled Note")
                content = params.get("content", "")
                tags = params.get("tags", [])
                source = params.get("source", "manual")
                note_id = params.get("note_id") or params.get("id")
                namespace = params.get("namespace", "general")
                category = params.get("category")
                confidence = params.get("confidence", "high")
                source_type = params.get("source_type")
                force_overwrite = params.get("force_overwrite", False)

                res = self.pkb.add_note(
                    title=title,
                    content=content,
                    tags=tags,
                    source=source,
                    note_id=note_id,
                    namespace=namespace,
                    category=category,
                    confidence=confidence,
                    source_type=source_type,
                    force_overwrite=force_overwrite,
                )

                elapsed = (time.perf_counter() - t_start) * 1000
                success = res.get("success", False)
                self.record_outcome(success)

                dedup_str = " (deduplicated)" if res.get("deduplicated") else ""
                msg = f"Knowledge note '{res.get('title')}' successfully ingested{dedup_str} (ID: {res.get('note_id')}, Version: {res.get('version', 1)})."
                return ActionResult(
                    status="SUCCESS" if success else "FAILED",
                    output=res,
                    message=msg,
                    execution_time_ms=elapsed,
                )

            elif capability == "knowledge.index":
                force = bool(params.get("force", False))
                res = self.pkb.reindex(force=force)

                elapsed = (time.perf_counter() - t_start) * 1000
                success = res.get("success", False)
                self.record_outcome(success)

                msg = f"Knowledge store re-indexed: {res.get('indexed_count')} documents indexed, {res.get('cleaned_count')} dangling records cleaned."
                return ActionResult(
                    status="SUCCESS" if success else "FAILED",
                    output=res,
                    message=msg,
                    execution_time_ms=elapsed,
                )

            elif capability == "knowledge.query":
                query = str(params.get("query") or params.get("text") or "").strip()
                top_k = int(params.get("top_k", 3))
                namespace = params.get("namespace")
                max_age_days = float(params.get("max_age_days", 30.0))

                results = self.pkb.semantic_search(
                    query=query,
                    top_k=top_k,
                    namespace=namespace,
                    max_age_days=max_age_days,
                )

                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)

                has_grounded = any(r.get("retrieval_status") == "found" for r in results)
                if not results or not has_grounded:
                    if results and results[0].get("retrieval_status") == "uncertain":
                        msg = f"Uncertain match for '{query}': '{results[0].get('title')}' (Score: {results[0].get('score')})."
                    else:
                        msg = f"No grounded knowledge records found matching query: '{query}'."
                else:
                    top = results[0]
                    fresh_flag = f" [{top.get('freshness', 'fresh').upper()}]" if top.get("freshness") == "stale" else ""
                    msg = f"Retrieved knowledge: '{top.get('title')}' (Score: {top.get('score')}, Status: {top.get('retrieval_status')}{fresh_flag})."

                return ActionResult(
                    status="SUCCESS",
                    output={
                        "query": query,
                        "results": results,
                        "count": len(results),
                        "has_grounded_match": has_grounded,
                    },
                    message=msg,
                    execution_time_ms=elapsed,
                )

            elif capability == "knowledge.audit_freshness":
                max_age_days = float(params.get("max_age_days", 30.0))
                namespace = params.get("namespace")
                res = self.pkb.audit_freshness(max_age_days=max_age_days, namespace=namespace)

                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)

                msg = (
                    f"Knowledge Freshness Audit: {res.get('total_notes')} total notes, "
                    f"{res.get('fresh_count')} fresh, {res.get('stale_count')} stale, "
                    f"{res.get('missing_files_count')} missing physical source files."
                )
                return ActionResult(
                    status="SUCCESS",
                    output=res,
                    message=msg,
                    execution_time_ms=elapsed,
                )

            elif capability == "knowledge.delete":
                note_id = str(params.get("note_id") or params.get("id") or "").strip()
                if not note_id:
                    return ActionResult(
                        status="FAILED",
                        output={"error": "Missing note_id"},
                        message="Missing note_id for knowledge deletion",
                    )

                res = self.pkb.delete_note(note_id)
                elapsed = (time.perf_counter() - t_start) * 1000
                verified = res.get("verified", False)
                self.record_outcome(verified)
                msg = f"Knowledge note '{note_id}' deleted and verified: {verified}."
                return ActionResult(
                    status="SUCCESS" if verified else "FAILED",
                    output=res,
                    message=msg,
                    execution_time_ms=elapsed,
                )

            else:
                return ActionResult(
                    status="FAILED",
                    output={"error": f"Capability '{capability}' not supported by KnowledgeProvider"},
                    message=f"Unsupported capability: {capability}",
                )

        except Exception as e:
            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(False)
            logger.error("[KnowledgeProvider] Execution failed for '%s': %s", capability, e)
            return ActionResult(
                status="FAILED",
                output={"error": str(e)},
                message=f"Knowledge operation failed: {str(e)}",
                execution_time_ms=elapsed,
            )
