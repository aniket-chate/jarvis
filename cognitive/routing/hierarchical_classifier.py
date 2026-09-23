"""
JARVIS Hierarchical Classification Engine.

Implements two-stage hierarchical semantic candidate generation:
1. Domain Classification (8 canonical JARVIS domains + UNKNOWN)
2. Capability Candidate Classification (Capabilities 1-50 + UNKNOWN)
3. Confidence Calibration, Ambiguity Detection, and Out-of-Distribution / Unknown Intent Detection.

Adheres strictly to architectural boundaries:
Classifier RESPONSIBILITY: UNDERSTAND & CANDIDATE-GENERATE ONLY.
Execution, planning, and policy decisions are strictly deferred to downstream kernels.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

logger = logging.getLogger("JARVIS.Cognitive.Routing.Classifier")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "models" / "routing"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CandidateScore:
    capability: str
    score: float


@dataclass
class ClassificationResult:
    domain: str
    candidates: List[CandidateScore]
    confidence: float
    unknown: bool
    requires_context: bool
    requires_clarification: bool
    top_k_capabilities: List[str] = field(default_factory=list)
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "candidates": [
                {"capability": c.capability, "score": round(c.score, 4)}
                for c in self.candidates
            ],
            "confidence": round(self.confidence, 4),
            "unknown": self.unknown,
            "requires_context": self.requires_context,
            "requires_clarification": self.requires_clarification,
            "top_k_capabilities": self.top_k_capabilities,
            "latency_ms": round(self.latency_ms, 2),
        }


@dataclass
class ClassifierConfig:
    domain_model_file: str = "domain_classifier.joblib"
    capability_model_file: str = "capability_classifier.joblib"
    unknown_threshold: float = 0.025
    ambiguity_margin: float = 0.015
    top_k: int = 5
    ngram_range: Tuple[int, int] = (1, 2)
    min_df: int = 1
    max_features: int = 8000
    regularization_c: float = 5.0


class BaseHierarchicalClassifier(ABC):
    """Abstract interface guaranteeing provider replaceability for routing models."""

    @abstractmethod
    def fit(self, examples: List[Dict[str, Any]]) -> None:
        """Trains the hierarchical models from structured examples."""
        pass

    @abstractmethod
    def classify(self, text: str) -> ClassificationResult:
        """Generates structured candidates and confidence for an utterance."""
        pass

    @abstractmethod
    def save(self, directory: Path) -> None:
        """Serializes trained weights to disk."""
        pass

    @abstractmethod
    def load(self, directory: Path) -> None:
        """Deserializes weights from disk."""
        pass


class TFIDFCalibratedHierarchicalClassifier(BaseHierarchicalClassifier):
    """Calibrated, sub-millisecond local hierarchical classifier using TF-IDF + Logistic Regression."""

    def __init__(self, config: Optional[ClassifierConfig] = None):
        self.config = config or ClassifierConfig()
        self.domain_pipeline: Optional[Pipeline] = None
        self.capability_pipeline: Optional[Pipeline] = None
        self.is_trained: bool = False

        self._try_autoload()

    def _try_autoload(self):
        dom_file = MODEL_DIR / self.config.domain_model_file
        cap_file = MODEL_DIR / self.config.capability_model_file
        if dom_file.exists() and cap_file.exists():
            try:
                self.load(MODEL_DIR)
            except Exception as e:
                logger.warning("[HierarchicalClassifier] Could not autoload models: %s", e)

    def fit(self, examples: List[Dict[str, Any]]) -> None:
        """Fits Domain and Capability classification pipelines on training dataset."""
        t0 = time.perf_counter()

        if not examples:
            raise ValueError("No training examples provided for training!")

        texts = [ex["text"] for ex in examples]
        domains = [ex["domain"] for ex in examples]
        capabilities = [ex["primary_capability"] for ex in examples]

        # Stage 1: Domain Pipeline
        self.domain_pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                ngram_range=self.config.ngram_range,
                min_df=self.config.min_df,
                max_features=self.config.max_features,
                lowercase=True,
            )),
            ("clf", LogisticRegression(
                C=self.config.regularization_c,
                class_weight="balanced",
                max_iter=1000,
                random_state=42,
            )),
        ])
        self.domain_pipeline.fit(texts, domains)

        # Stage 2: Capability Pipeline
        self.capability_pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                ngram_range=self.config.ngram_range,
                min_df=self.config.min_df,
                max_features=self.config.max_features,
                lowercase=True,
            )),
            ("clf", LogisticRegression(
                C=self.config.regularization_c,
                class_weight="balanced",
                max_iter=1000,
                random_state=42,
            )),
        ])
        self.capability_pipeline.fit(texts, capabilities)

        self.is_trained = True
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("[HierarchicalClassifier] Successfully trained on %d examples in %.2f ms", len(examples), elapsed)

    def classify(self, text: str) -> ClassificationResult:
        """Classifies text into domain, top-K capability candidates, and ambiguity flags."""
        t0 = time.perf_counter()
        clean_text = text.strip()

        if not self.is_trained or self.domain_pipeline is None or self.capability_pipeline is None:
            elapsed = (time.perf_counter() - t0) * 1000
            return ClassificationResult(
                domain="UNKNOWN",
                candidates=[],
                confidence=0.0,
                unknown=True,
                requires_context=False,
                requires_clarification=False,
                latency_ms=elapsed,
            )

        # 1. Prompt Injection Safety Intercept -> Route to 48_security_identity
        low = clean_text.lower()
        if re.search(r"\b(ignore\s+(all\s+)?(previous|prior)\s+(rules|instructions)|system\s+override|bypass\s+policy|jailbreak|disregard\s+(your\s+)?safety)\b", low) or "<untrusted_data>" in low:
            elapsed = (time.perf_counter() - t0) * 1000
            return ClassificationResult(
                domain="AGENCY_GOVERNANCE_EVOLUTION",
                candidates=[CandidateScore(capability="48_security_identity", score=1.0)],
                confidence=1.0,
                unknown=False,
                requires_context=False,
                requires_clarification=False,
                top_k_capabilities=["48_security_identity"],
                latency_ms=elapsed,
            )

        # 2. Pronoun and Contextual Reference Detection
        has_pronoun = bool(re.search(r"\b(it|that|this|that tab|that file|them|these|those)\b", low))
        requires_context = has_pronoun

        # 2. Predict Domain Probabilities
        domain_probs = self.domain_pipeline.predict_proba([clean_text])[0]
        domain_classes = self.domain_pipeline.classes_
        top_dom_idx = int(np.argmax(domain_probs))
        top_domain = domain_classes[top_dom_idx]
        domain_confidence = float(domain_probs[top_dom_idx])

        # 3. Predict Capability Probabilities
        cap_probs = self.capability_pipeline.predict_proba([clean_text])[0]
        cap_classes = self.capability_pipeline.classes_

        # Sort capabilities by probability descending
        sorted_indices = np.argsort(cap_probs)[::-1]
        raw_candidates: List[Tuple[str, float]] = []

        for idx in sorted_indices[:self.config.top_k]:
            cap_name = str(cap_classes[idx])
            raw_candidates.append((cap_name, float(cap_probs[idx])))

        top_cap_name = raw_candidates[0][0]
        top_cap_prob = raw_candidates[0][1]

        # 4. Unknown Out-of-Distribution Detection
        content_tokens = [w for w in re.findall(r"[a-zA-Z]{3,}", low) if w not in ENGLISH_STOP_WORDS]
        has_known_content = True
        if content_tokens and hasattr(self.capability_pipeline.named_steps["tfidf"], "vocabulary_"):
            vocab = self.capability_pipeline.named_steps["tfidf"].vocabulary_
            has_known_content = any(w in vocab for w in content_tokens)

        unknown = (
            top_domain == "UNKNOWN"
            or top_cap_name == "UNKNOWN"
            or top_cap_prob < self.config.unknown_threshold
            or not has_known_content
        )

        if unknown:
            elapsed = (time.perf_counter() - t0) * 1000
            return ClassificationResult(
                domain="UNKNOWN",
                candidates=[],
                confidence=0.0,
                unknown=True,
                requires_context=requires_context,
                requires_clarification=False,
                top_k_capabilities=[],
                latency_ms=elapsed,
            )

        # Filter out 'UNKNOWN' from candidates for known queries and normalize
        filtered_candidates = [c for c in raw_candidates if c[0] != "UNKNOWN"]
        top_k_sum = sum(prob for _, prob in filtered_candidates) or 1.0
        normalized_candidates = [
            CandidateScore(capability=name, score=float(prob / top_k_sum))
            for name, prob in filtered_candidates
        ]

        # 5. Ambiguity Detection (Small margin between top-1 and top-2 candidates)
        requires_clarification = False
        if len(raw_candidates) >= 2:
            raw_margin = raw_candidates[0][1] - raw_candidates[1][1]
            if raw_margin < self.config.ambiguity_margin:
                requires_clarification = True

        # Joint confidence = top capability normalized score * domain confidence
        joint_conf = float(normalized_candidates[0].score * domain_confidence) if normalized_candidates else 0.0

        elapsed = (time.perf_counter() - t0) * 1000
        return ClassificationResult(
            domain=str(top_domain),
            candidates=normalized_candidates,
            confidence=round(joint_conf, 4),
            unknown=False,
            requires_context=requires_context,
            requires_clarification=requires_clarification,
            top_k_capabilities=[c.capability for c in normalized_candidates],
            latency_ms=elapsed,
        )

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.domain_pipeline, directory / self.config.domain_model_file)
        joblib.dump(self.capability_pipeline, directory / self.config.capability_model_file)
        logger.info("[HierarchicalClassifier] Saved models to %s", directory)

    def load(self, directory: Path) -> None:
        self.domain_pipeline = joblib.load(directory / self.config.domain_model_file)
        self.capability_pipeline = joblib.load(directory / self.config.capability_model_file)
        self.is_trained = True
        logger.info("[HierarchicalClassifier] Loaded models from %s", directory)


# Global singleton instance
hierarchical_classifier = TFIDFCalibratedHierarchicalClassifier()
