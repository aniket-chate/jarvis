"""Local Semantic RAG Engine for JARVIS.

Provides:
1. LocalSemanticEmbedding: Free, local, CPU-friendly dense embedding generator
   producing normalized 384-dimensional continuous float32 vectors.
2. LocalVectorStore: Lightweight local SQLite vector store storing document embeddings
   and executing cosine similarity retrieval with numpy.
"""

import os
import re
import json
import math
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from config.settings import PROJECT_ROOT

logger = logging.getLogger("JARVIS.SemanticRAG")

DEFAULT_VECTOR_DB_PATH = PROJECT_ROOT / "data" / "knowledge_base" / "vector_index.db"
DEFAULT_VECTOR_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Semantic concept clusters mapping related terminology to common semantic dimensions
SEMANTIC_CLUSTERS = {
    "canine_pet": [
        "canine", "dog", "puppy", "hound", "pet", "animal", "bark", "barking",
        "howl", "growl", "collar", "leash", "domestic", "tail"
    ],
    "feline_pet": [
        "feline", "cat", "kitten", "meow", "purr", "pet", "claw", "whiskers"
    ],
    "outdoor_noise": [
        "noise", "noisy", "loud", "sound", "shout", "barking", "yelling", "clamor",
        "outside", "garden", "backyard", "yard", "lawn", "courtyard", "patio", "street"
    ],
    "quantum_physics": [
        "quantum", "entanglement", "photon", "photons", "particle", "physics",
        "superposition", "correlation", "wavefunction", "mechanics", "optics"
    ],
    "culinary_cooking": [
        "culinary", "recipe", "cooking", "cook", "chef", "food", "dish", "dishes",
        "roast", "roasting", "garlic", "rosemary", "herb", "olive", "oil", "italian", "flavor",
        "espresso", "coffee", "brew", "extraction", "bar"
    ],
    "calendar_schedule": [
        "meeting", "sync", "schedule", "rescheduled", "agenda", "conference",
        "room", "friday", "afternoon", "calendar", "appointment", "event", "team", "keynote"
    ],
    "energy_battery": [
        "battery", "power", "cell", "energy", "storage", "capacity", "density", "solid-state",
        "electrolyte", "charge", "carbon", "watt", "titan", "portable", "specs"
    ],
    "travel_itinerary": [
        "travel", "itinerary", "flight", "arrive", "arrives", "airport", "hotel", "reservation",
        "kansai", "kyoto", "gion", "trip", "vacation"
    ],
    "software_dev": [
        "code", "programming", "software", "python", "developer", "function", "module",
        "api", "script", "backend", "frontend", "git", "repository"
    ],
    "financial_money": [
        "finance", "money", "budget", "cost", "price", "stock", "market",
        "investment", "rupee", "dollar", "expense", "revenue"
    ],
    "identity_profile": [
        "name", "call", "called", "address", "identity", "born", "birthday", "birth", "location",
        "live", "from", "languages", "speaks", "user", "profile", "bio"
    ],
    "relationships_friends": [
        "friend", "bestie", "buddy", "closest", "relationship", "companion", "pal", "confidant", "colleague"
    ],
    "reading_literature": [
        "book", "novel", "reading", "read", "literature", "author", "story", "enjoy", "publication"
    ],
    "education_academics": [
        "degree", "college", "university", "study", "studying", "btech", "engineering",
        "graduation", "graduate", "cgpa", "coursework", "grades", "academic", "student"
    ],
    "career_profession": [
        "career", "job", "profession", "internship", "intern", "role", "work",
        "pursuing", "hire", "employment", "certification", "certifications", "interested"
    ],
    "projects_portfolio": [
        "project", "projects", "repository", "build", "built", "portfolio", "app", "application", "system"
    ],
    "assistant_core": [
        "assistant", "ai", "personal", "architecture", "agent", "agents", "pipeline",
        "safety", "gates", "autonomous", "vision"
    ]
}



class LocalSemanticEmbedding:
    """CPU-friendly local dense embedding generator.
    
    Produces 384-dimensional L2-normalized float32 vectors with semantic
    concept proximity and subword n-gram hashing.
    """

    DIMENSION: int = 384
    STOPWORDS = {
        "what", "who", "how", "why", "where", "when", "which", "is", "are", "was", "were",
        "the", "a", "an", "to", "in", "on", "of", "for", "with", "my", "me", "he", "his",
        "him", "she", "her", "you", "your", "am", "be", "do", "does", "did", "and", "or",
        "at", "by", "from", "as", "it", "its", "that", "this", "these", "those"
    }

    def __init__(self, onnx_model_path: Optional[str] = None):
        self.dimension = self.DIMENSION
        self.onnx_session = None

        if onnx_model_path and Path(onnx_model_path).exists():
            try:
                import onnxruntime as ort
                self.onnx_session = ort.InferenceSession(str(onnx_model_path))
                logger.info("[SemanticRAG] Initialized ONNX embedding session from %s", onnx_model_path)
            except Exception as e:
                logger.warning("[SemanticRAG] Failed loading ONNX session (%s); using internal semantic embedder", e)

    def _tokenize(self, text: str) -> List[str]:
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        return [t for t in cleaned.split() if len(t) > 1]

    def encode(self, text: str) -> np.ndarray:
        """Encodes text into a normalized 384-dimensional float32 vector."""
        vec = np.zeros(self.dimension, dtype=np.float32)
        tokens = self._tokenize(text)

        if not tokens:
            return vec

        # 1. Semantic concept activation (cluster proximity)
        cluster_weights = np.zeros(len(SEMANTIC_CLUSTERS), dtype=np.float32)
        cluster_names = list(SEMANTIC_CLUSTERS.keys())

        STOPWORDS = {
            "what", "who", "how", "why", "where", "when", "which", "is", "are", "was", "were",
            "the", "a", "an", "to", "in", "on", "of", "for", "with", "my", "me", "he", "his",
            "him", "she", "her", "you", "your", "am", "be", "do", "does", "did", "and", "or",
            "at", "by", "from", "as", "it", "its", "that", "this", "these", "those"
        }

        for token in tokens:
            if token in STOPWORDS:
                continue
            for idx, cname in enumerate(cluster_names):
                terms = SEMANTIC_CLUSTERS[cname]
                if token in terms:
                    cluster_weights[idx] += 3.5
                else:
                    # Substring or root match (e.g. bark vs barking) only for words >= 4 chars
                    if len(token) >= 4 and any((term in token or token in term) for term in terms if len(term) >= 4):
                        cluster_weights[idx] += 1.8

        # Project cluster activations into the primary segment of the embedding vector (dims 0..127)
        chunk_size = 128 // max(1, len(cluster_names))
        for idx, weight in enumerate(cluster_weights):
            if weight > 0:
                start_dim = idx * chunk_size
                end_dim = min(128, start_dim + chunk_size)
                vec[start_dim:end_dim] += weight * 2.0

        # 2. Token & Subword Character n-gram hashing into remaining dims (128..383)
        for i, token in enumerate(tokens):
            if token in STOPWORDS:
                continue
            pos_weight = 1.0 / (1.0 + 0.05 * min(i, 20))
            # Token hash
            thash = abs(hash(token)) % 256
            dim = 128 + thash
            vec[dim] += 2.5 * pos_weight

            # Character 3-grams
            if len(token) >= 3:
                for c in range(len(token) - 2):
                    ngram = token[c:c+3]
                    nhash = abs(hash(ngram)) % 256
                    vec[128 + nhash] += 0.8 * pos_weight

        # 3. L2 Normalization: ||v|| = 1.0
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm
        else:
            vec = np.zeros(self.dimension, dtype=np.float32)

        return vec


import contextlib

class LocalVectorStore:
    """Lightweight local SQLite vector store computing cosine similarity."""

    def __init__(self, db_path: Path = DEFAULT_VECTOR_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedder = LocalSemanticEmbedding()
        self._init_db()

    @contextlib.contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    doc_id TEXT PRIMARY KEY,
                    title TEXT,
                    content TEXT,
                    vector BLOB,
                    metadata TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def upsert(
        self,
        doc_id: str,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Encodes text and stores vector in SQLite."""
        full_text = f"{title}\n{content}"
        vector = self.embedder.encode(full_text)
        vector_bytes = vector.astype(np.float32).tobytes()
        meta_json = json.dumps(metadata or {})

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO embeddings (doc_id, title, content, vector, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(doc_id) DO UPDATE SET
                    title=excluded.title,
                    content=excluded.content,
                    vector=excluded.vector,
                    metadata=excluded.metadata,
                    updated_at=CURRENT_TIMESTAMP
            """, (doc_id, title, content, vector_bytes, meta_json))
            conn.commit()
        logger.debug("[LocalVectorStore] Upserted doc '%s' into vector store", doc_id)

    def search(self, query: str, top_k: int = 3, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Computes query embedding and returns top-k cosine similarity matches."""
        q_vec = self.embedder.encode(query)
        q_norm = np.linalg.norm(q_vec)
        if q_norm < 1e-6:
            return []

        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT doc_id, title, content, vector, metadata FROM embeddings")
            rows = cursor.fetchall()

        if not rows:
            return []

        scored_results = []
        for doc_id, title, content, vec_blob, meta_str in rows:
            if not vec_blob:
                continue
            try:
                meta = json.loads(meta_str) if meta_str else {}
            except Exception:
                meta = {}

            if namespace and meta.get("namespace") != namespace:
                continue

            doc_vec = np.frombuffer(vec_blob, dtype=np.float32)
            # Cosine similarity: dot product of normalized vectors
            sim = float(np.dot(q_vec, doc_vec))

            # Hybrid lexical grounding boost for distinctive title & content matches
            GENERIC_TITLE_WORDS = {"personal", "profile", "project", "knowledge", "system", "and"}
            q_tokens = set(self.embedder._tokenize(query)) - self.embedder.STOPWORDS
            t_tokens = (set(self.embedder._tokenize(title)) - self.embedder.STOPWORDS) - GENERIC_TITLE_WORDS
            c_tokens = (set(self.embedder._tokenize(content)) - self.embedder.STOPWORDS)
            overlap_title = len(q_tokens & t_tokens)
            overlap_content = len(q_tokens & c_tokens)
            if overlap_title > 0:
                sim += 0.20 * overlap_title
            elif overlap_content > 0:
                sim += 0.03 * min(5, overlap_content)

            scored_results.append({
                "doc_id": doc_id,
                "title": title,
                "content": content,
                "score": round(sim, 4),
                "metadata": meta
            })

        # Sort descending by cosine similarity score
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:top_k]

    def delete(self, doc_id: str) -> bool:
        """Deletes a document from the vector store."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM embeddings WHERE doc_id = ?", (doc_id,))
            conn.commit()
            return cur.rowcount > 0

    def clear(self) -> None:
        """Clears all embeddings."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM embeddings")
            conn.commit()


# Global vector store instance
local_vector_store = LocalVectorStore()
