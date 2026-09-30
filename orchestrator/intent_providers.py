"""Capability providers for side-effect-free intent arbitration."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any, Optional, Protocol
from config.settings import settings
from orchestrator.parameter_extractor import parameter_extractor
from orchestrator.intent_types import IntentCandidate, NormalizedQuery, StructuredIntent


class IntentProvider(Protocol):
    name: str
    def detect(self, query: NormalizedQuery, context: Any) -> Optional[IntentCandidate]: ...


class Provider:
    def __init__(self, name: str, detector):
        self.name = name
        self._detector = detector

    def detect(self, query, context):
        return self._detector(query, context)

    @staticmethod
    def make(query, name, domain, action, target="", params=None, confidence=.8, confirmation=False):
        return StructuredIntent(domain, action, target, dict(params or {}), confirmation,
                                confidence, query.text, False, "", name)

    @staticmethod
    def clarify(query, name, domain, prompt, params=None, confidence=.98):
        return StructuredIntent(domain, "clarification", "", {"query": prompt, **(params or {})},
                                False, confidence, query.text, True, prompt, name)


def _candidate(intent, score):
    return IntentCandidate(intent=intent, score=score)


def _confirmation(q, ctx):
    tx = getattr(ctx, "get_pending_confirmation", lambda: None)()
    if not tx or getattr(tx, "is_expired", False):
        return None
    low = q.lower
    if low in {"yes", "yes do it", "do it", "confirm", "proceed", "approve", "approved", "go ahead", "sure", "okay", "ok"}