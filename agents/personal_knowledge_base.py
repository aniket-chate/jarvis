"""Personal Knowledge Base (PKB) for JARVIS Layer 3 (Group 5).

Provides a local, persistent notes and document repository.
Distinct from Memory Manager's preferences/facts:
- Memory Manager stores short/long-term user attributes and conversational context.
- Personal Knowledge Base stores standalone reference notes, project documents,
  and research articles with full-text search and tagging.
All data is stored locally in data/knowledge_base/.
"""

import hashlib
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.settings import PROJECT_ROOT
from agents.semantic_rag import local_vector_store, LocalVectorStore

logger = logging.getLogger("JARVIS.PKB")

PKB_DIR = PROJECT_ROOT / "data" / "knowledge_base"
PKB_DIR.mkdir(parents=True, exist_ok=True)
INDEX_PATH = PKB_DIR / "index.json"


class PersonalKnowledgeBase:
    """Persistent local knowledge repository with dense semantic vector retrieval."""

    def __init__(self, storage_dir: Path = PKB_DIR, vector_store: Optional[LocalVectorStore] = None):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.storage_dir / "index.json"
        self.vector_store = vector_store or local_vector_store
        self._load_index()
        self._sync_vector_store()

    def _load_index(self) -> None:
        """Loads notes index."""
        if self.index_path.exists():
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    self.index: Dict[str, Dict[str, Any]] = json.load(f)
            except Exception as e:
                logger.error("[PKB] Failed loading index: %s", str(e))
                self.index = {}
        else:
            self.index = {}

    def _save_index(self) -> None:
        """Persists index to disk."""
        try:
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(self.index, f, indent=2)
        except Exception as e:
            logger.error("[PKB] Failed saving index: %s", str(e))

    def _sync_vector_store(self) -> None:
        """Indexes any existing stored notes into the vector store."""
        try:
            for note_id, meta in self.index.items():
                note_file = self.storage_dir / f"{note_id}.json"
                if note_file.exists():
                    with open(note_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.vector_store.upsert(
                        doc_id=note_id,
                        title=data.get("title", meta.get("title", "")),
                        content=data.get("content", ""),
                        metadata=meta,
                    )
        except Exception as e:
            logger.warning("[PKB] Vector store sync warning: %s", e)

    def add_note(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        source: str = "manual",
        note_id: Optional[str] = None,
        namespace: str = "general",
        category: Optional[str] = None,
        confidence: str = "high",
        last_confirmed: Optional[str] = None,
        source_type: Optional[str] = None,
        force_overwrite: bool = False,
    ) -> Dict[str, Any]:
        """Creates or updates a knowledge note, tracks provenance, saves to disk, and indexes in vector store."""
        content_hash = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

        # Deduplication check for identical content in the same namespace
        if not note_id and not force_overwrite:
            for existing_id, meta in self.index.items():
                if meta.get("namespace") == namespace and meta.get("content_hash") == content_hash:
                    logger.info("[PKB] Deduplicated note '%s' matching existing note '%s'", title, existing_id)
                    return {
                        "success": True,
                        "note_id": existing_id,
                        "title": meta.get("title", title),
                        "tags": meta.get("tags", []),
                        "namespace": namespace,
                        "deduplicated": True,
                        "provenance": {
                            "source": meta.get("source", source),
                            "ingested_at": meta.get("created_at"),
                            "updated_at": meta.get("updated_at"),
                            "content_hash": content_hash,
                            "version": meta.get("version", 1),
                        },
                    }

        target_id = note_id or str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()
        clean_tags = [t.strip().lower() for t in (tags or [])]
        existing_meta = self.index.get(target_id, {})
        version = (existing_meta.get("version", 0) + 1) if existing_meta else 1

        note_meta = {
            "id": target_id,
            "title": title,
            "tags": clean_tags,
            "created_at": existing_meta.get("created_at", timestamp),
            "updated_at": timestamp,
            "source": source,
            "source_type": source_type or ("manual" if source == "manual" else "document"),
            "namespace": namespace,
            "category": category or "general",
            "confidence": confidence,
            "last_confirmed": last_confirmed or timestamp,
            "preview": content[:150],
            "content_hash": content_hash,
            "version": version,
        }

        # Write note body
        note_file = self.storage_dir / f"{target_id}.json"
        note_data = {**note_meta, "content": content}
        with open(note_file, "w", encoding="utf-8") as f:
            json.dump(note_data, f, indent=2)

        self.index[target_id] = note_meta
        self._save_index()

        # Index in lightweight local vector store
        try:
            self.vector_store.upsert(
                doc_id=target_id,
                title=title,
                content=content,
                metadata=note_meta,
            )
        except Exception as e:
            logger.warning("[PKB] Failed vector indexing for note %s: %s", target_id, e)

        logger.info("[PKB] Added/updated note '%s' (ID: %s, Namespace: %s, Version: %d)", title, target_id, namespace, version)
        return {
            "success": True,
            "note_id": target_id,
            "title": title,
            "tags": clean_tags,
            "namespace": namespace,
            "version": version,
            "deduplicated": False,
            "provenance": {
                "source": source,
                "ingested_at": note_meta["created_at"],
                "updated_at": timestamp,
                "content_hash": content_hash,
                "version": version,
            },
        }

    def delete_note(self, note_id: str) -> Dict[str, Any]:
        """Deletes a knowledge note from index, disk file, and vector store with verification."""
        existed = note_id in self.index
        note_file = self.storage_dir / f"{note_id}.json"
        file_existed = note_file.exists()

        if note_id in self.index:
            del self.index[note_id]
            self._save_index()

        if file_existed:
            try:
                note_file.unlink()
            except Exception as e:
                logger.error("[PKB] Failed deleting note file %s: %s", note_file, e)

        # Remove from vector store
        try:
            self.vector_store.delete(note_id)
        except Exception as e:
            logger.warning("[PKB] Vector store delete warning for %s: %s", note_id, e)

        # Empirical verification of deletion
        verified_deleted = (note_id not in self.index) and (not note_file.exists())
        logger.info("[PKB] Deleted note '%s' (existed=%s, verified=%s)", note_id, existed or file_existed, verified_deleted)
        return {
            "success": verified_deleted,
            "note_id": note_id,
            "deleted": existed or file_existed,
            "verified": verified_deleted,
        }

    def audit_freshness(self, max_age_days: float = 30.0, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Audits all indexed notes for freshness, staleness, and missing disk files."""
        now = datetime.now()
        fresh_notes = []
        stale_notes = []
        missing_files = []

        for nid, meta in self.index.items():
            if namespace and meta.get("namespace") != namespace:
                continue

            # Verify physical file existence
            note_file = self.storage_dir / f"{nid}.json"
            if not note_file.exists():
                missing_files.append({"id": nid, "title": meta.get("title", ""), "path": str(note_file)})

            upd_str = meta.get("updated_at") or meta.get("created_at")
            age_days = 0.0
            if upd_str:
                try:
                    upd_dt = datetime.fromisoformat(upd_str)
                    age_days = (now - upd_dt).total_seconds() / 86400.0
                except Exception:
                    pass

            item_info = {
                "id": nid,
                "title": meta.get("title", ""),
                "namespace": meta.get("namespace", "general"),
                "age_days": round(age_days, 1),
                "version": meta.get("version", 1),
                "source": meta.get("source", "unknown"),
            }

            if age_days > max_age_days:
                stale_notes.append(item_info)
            else:
                fresh_notes.append(item_info)

        total = len(fresh_notes) + len(stale_notes)
        return {
            "total_notes": total,
            "fresh_count": len(fresh_notes),
            "stale_count": len(stale_notes),
            "missing_files_count": len(missing_files),
            "max_age_days_threshold": max_age_days,
            "fresh": fresh_notes,
            "stale": stale_notes,
            "missing_files": missing_files,
        }

    def reindex(self, force: bool = False) -> Dict[str, Any]:
        """Re-indexes all on-disk notes into the vector store and synchronizes index."""
        indexed_count = 0
        cleaned_count = 0

        # Scan storage_dir for JSON files
        json_files = list(self.storage_dir.glob("*.json"))
        for jf in json_files:
            if jf.name == "index.json":
                continue
            doc_id = jf.stem
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                title = data.get("title", doc_id)
                content = data.get("content", "")
                meta = self.index.get(doc_id, {
                    "id": doc_id,
                    "title": title,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "namespace": data.get("namespace", "general"),
                    "source": data.get("source", "manual"),
                })
                self.vector_store.upsert(
                    doc_id=doc_id,
                    title=title,
                    content=content,
                    metadata=meta,
                )
                if doc_id not in self.index:
                    self.index[doc_id] = meta
                indexed_count += 1
            except Exception as e:
                logger.error("[PKB] Failed reindexing %s: %s", jf, e)

        # If force, remove entries in index whose files are missing
        if force:
            missing = [nid for nid in list(self.index.keys()) if not (self.storage_dir / f"{nid}.json").exists()]
            for nid in missing:
                del self.index[nid]
                self.vector_store.delete(nid)
                cleaned_count += 1

        self._save_index()
        return {
            "success": True,
            "indexed_count": indexed_count,
            "cleaned_count": cleaned_count,
            "total_in_index": len(self.index),
        }

    def semantic_search(
        self,
        query: str,
        top_k: int = 3,
        namespace: Optional[str] = None,
        max_age_days: float = 30.0,
    ) -> List[Dict[str, Any]]:
        """Performs dense vector semantic search across personal knowledge with truthful status."""
        results = self.vector_store.search(query=query, top_k=top_k, namespace=namespace)
        now = datetime.now()
        for r in results:
            full_note = self.get_note(r["doc_id"])
            if full_note:
                r["content"] = full_note.get("content", r["content"])
                r["tags"] = full_note.get("tags", [])
                r["namespace"] = full_note.get("namespace", r.get("metadata", {}).get("namespace", "general"))
                r["category"] = full_note.get("category", r.get("metadata", {}).get("category", "general"))
                r["version"] = full_note.get("version", 1)
                r["source"] = full_note.get("source", "unknown")
                r["updated_at"] = full_note.get("updated_at", "")
                r["content_hash"] = full_note.get("content_hash", "")
            else:
                r["version"] = r.get("metadata", {}).get("version", 1)
                r["source"] = r.get("metadata", {}).get("source", "unknown")
                r["updated_at"] = r.get("metadata", {}).get("updated_at", "")
                r["content_hash"] = r.get("metadata", {}).get("content_hash", "")

            score = r.get("score", 0.0)
            # Truthful retrieval state classification
            if score >= 0.35:
                r["retrieval_status"] = "found"
            elif score >= 0.20:
                r["retrieval_status"] = "uncertain"
            else:
                r["retrieval_status"] = "not_found"

            # Check freshness
            upd_str = r.get("updated_at")
            if upd_str:
                try:
                    upd_dt = datetime.fromisoformat(upd_str)
                    age_days = (now - upd_dt).total_seconds() / 86400.0
                    r["age_days"] = round(age_days, 1)
                    r["freshness"] = "stale" if age_days > max_age_days else "fresh"
                except Exception:
                    r["freshness"] = "unknown"
                    r["age_days"] = 0.0
            else:
                r["freshness"] = "fresh"
                r["age_days"] = 0.0

            # Safe data containment for retrieved knowledge text
            raw_content = r.get("content", "")
            r["safe_data"] = f"<UNTRUSTED_KNOWLEDGE_DATA doc_id='{r['doc_id']}'>\n{raw_content}\n</UNTRUSTED_KNOWLEDGE_DATA>"

        return results

    def search_notes(self, query: str, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """Searches notes by title, tag, or content."""
        query_lower = query.lower()
        tag_lower = tag.lower() if tag else None
        matches: List[Dict[str, Any]] = []

        for note_id, meta in self.index.items():
            # Check tag filter
            if tag_lower and tag_lower not in meta.get("tags", []):
                continue

            # Check title or preview match
            if query_lower in meta.get("title", "").lower() or query_lower in meta.get("preview", "").lower():
                matches.append(meta)
                continue

            # Check full content
            note_file = self.storage_dir / f"{note_id}.json"
            if note_file.exists():
                try:
                    with open(note_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if query_lower in data.get("content", "").lower():
                        matches.append(meta)
                except Exception:
                    pass

        logger.info("[PKB] Search for '%s' returned %d matches", query, len(matches))
        return matches

    def get_note(self, note_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves full content of a note by its ID."""
        note_file = self.storage_dir / f"{note_id}.json"
        if not note_file.exists():
            return None
        try:
            with open(note_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("[PKB] Error reading note %s: %s", note_id, str(e))
            return None

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator and Capability Providers."""
        action = inputs.get("action", "search")
        if action in ["add", "ingest"]:
            return self.add_note(
                title=inputs.get("title", "Untitled Note"),
                content=inputs.get("content", ""),
                tags=inputs.get("tags", []),
                source=inputs.get("source", "manual"),
                note_id=inputs.get("note_id") or inputs.get("id"),
                namespace=inputs.get("namespace", "general"),
                category=inputs.get("category"),
                confidence=inputs.get("confidence", "high"),
                source_type=inputs.get("source_type"),
                force_overwrite=inputs.get("force_overwrite", False),
            )
        elif action in ["get", "read"]:
            note_id = inputs.get("id") or inputs.get("note_id", "")
            note = self.get_note(note_id)
            return {"success": bool(note), "note": note}
        elif action in ["delete", "remove", "forget"]:
            note_id = inputs.get("id") or inputs.get("note_id", "")
            return self.delete_note(note_id)
        elif action in ["audit", "audit_freshness", "freshness"]:
            max_age = float(inputs.get("max_age_days", 30.0))
            namespace = inputs.get("namespace")
            return self.audit_freshness(max_age_days=max_age, namespace=namespace)
        elif action in ["reindex", "sync"]:
            force = bool(inputs.get("force", False))
            return self.reindex(force=force)
        elif action in ["search_semantic", "semantic_search", "rag", "query"]:
            query = inputs.get("query", "")
            namespace = inputs.get("namespace")
            top_k = int(inputs.get("top_k", 3))
            max_age = float(inputs.get("max_age_days", 30.0))
            results = self.semantic_search(query=query, top_k=top_k, namespace=namespace, max_age_days=max_age)
            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results),
                "has_grounded_match": any(r.get("retrieval_status") == "found" for r in results),
            }
        else:
            query = inputs.get("query", "")
            results = self.search_notes(query=query, tag=inputs.get("tag"))
            return {"success": True, "query": query, "results": results, "count": len(results)}


personal_knowledge_base = PersonalKnowledgeBase()


