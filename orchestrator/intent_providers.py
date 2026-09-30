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
ØØ][ÛHÜÙ][ÜËØØ[KÙ]
ØØ][ÛJKÝ\

BÚ[HÛ[ÜÝÈYÛ[ÜÝÈ[ÝÈ[ÙHÛYÚYÛYÚ[ÝÈ[ÙHÙ^HYÙ^H[ÝÈ[ÙHÝÈYÝØØ][Û]\ØØ[Y]JÝY\Û\YJKÙX]\[ÈÚXÚØØ][ÛÚÝ[HÚXÚÏÈÈ[YWÝ\Ù]Ú[JKN
B]\ØØ[Y]JÝY\XZÙJKÙX]\[ÈÙ]ÝÙX]\ØØ][ÛÈØØ][ÛØØ][Û[YWÝ\Ù]Ú[XÝ[ÛÙ]ÝÙX]\KMÊKMÊBYÜØÚY[\KÝ
NÝÈHKÝÙ\YKÙX\Ú
ÎÚÝß\Ý\Ü^JWÊÊÎ^WÊÊOÊÎXÝ]WÊÊOØ[\\Ï×ÝÊN]\ØØ[Y]JÝY\XZÙJKØÚY[\ØÚY[\\ÝXÝ]WØ[\\ÈÈXÝ[Û\ÝKMKMBYKÙX\Ú
ÎØ[Ù[[]_ÛX\ÝÜ
WÊÊÎWÊÊOØ[\WÝÊN]\ØØ[Y]JÝY\XZÙJKØÚY[\ØÚY[\Ø[Ù[[\HÈXÝ[ÛØ[Ù[KMKMBY[J[ÝÈÜ[
Ø[[\YY][È][YÙ[HYHÛÝ]Z[X[]HJNYÛÛXÝ[ÝÎ]\ØØ[Y]JÝY\XZÙJKØÚY[\ØÚY[\ÚXÚ×ØÛÛXÝÈK^È]Y\HK^KMJKMJBYKÙX\Ú
ÎÜX]_YÛÚßØÚY[JWÝÊNH\[Y]\Ù^XÝÜ^XÝØØ[[\Ü\[\ÊK^
BZ\ÜÚ[ÈHÙ]
Z\ÜÚ[×Ü\]Z\Y×JBYZ\ÜÚ[Î]\ØØ[Y]JÝY\Û\YJKØÚY[\ØÚY[\X\ÙHÝYH
È[Ú[Z\ÜÚ[ÊH
ÈÈØ[[\Ü\]Y\ÝK^
JKMÊB]\ØØ[Y]JÝY\XZÙJKØÚY[\ØÚY[\ÜX]WØØ[[\Ù][Ù]
]HKÈØ[[\Ü\]Y\ÝK^
KMËYJKMÊB]\ØØ[Y]JÝY\XZÙJKØÚY[\ØÚY[\Ù]ØØ[[\Ù][ÈØ[[\Ù][ÈÈ]Y\HK^Ø[[\Ü\]Y\ÝK^KM
KM
BY[J[ÝÈÜ[
[Z[\[Z[YHÙ][[\HÙ]H[Y\ØZÙHYHJNH\[Y]\Ù^XÝÜ^XÝÜØÚY[WÜ\[\ÊK^
BYÙ]
[          re.search(r"\b(?:know|wonder|decide|choose|unsure|doubt)\s+whether\b", low)):
        return None
    if not (re.search(r"\b(?:weather|forecast|temperature|rain|raining|hot outside|cold outside)\b", low) or
            ("whether" in low and re.search(r"\b(?:today|tomorrow|tonight|outside|forecast|report)\s+whether\b", low))):
        return None
    location = ""
    m = re.search(r"\b(?:in|for|at)\s+(.+?)(?:\s+(?:today|tomorrow|tonight|right now|now))?\s*[?!.,]*$", q.text, re.I)
    if m: location = m.group(1).strip(" .,!?'"")
    if not location:
        w = getattr(ctx, "get_weather_context", lambda: {})()
        if w.get("active"): location = str(w.get("location") or "").strip()
    if not location:
        location = str(settings.config.get("user", {}).get("location") or settings.config.get("location", "") or settings.locale.get("location", "")).strip()
    when = "tomorrow" if "tomorrow" in low else "tonight" if "tonight" in low else "today" if "today" in low else "now"
    if not location:
        return _candidate(Provider.clarify(q, "weather", "info", "Which location should I check?", {"time_target": when}), .98)
    return _candidate(Provider.make(q, "weather", "info", "get_weather", location,
        {"location": location, "time_target": when, "action": "get_weather"}, .97), .97)


def _scheduler(q, ctx):
    low = q.lower
    if re.search(r"\b(?:show|list|display)\s+(?:my\s+)?(?:active\s+)?alarms?\b", low):
        return _candidate(Provider.make(q, "scheduler", "scheduler", "list", "active_alarms", {"action": "list"}, .96), .96)
    if re.search(r"\b(?:cancel|delete|clear|stop)\s+(?:the\s+)?alarm\b", low):
        return _candidate(Provider.make(q, "scheduler", "scheduler", "cancel", "alarm", {"action": "cancel"}, .96), .96)
    if any(x in low for x in ("calendar", "meeting", "event", "agenda", "free slot", "availability")):
        if "conflict" in low:
            return _candidate(Provider.make(q, "scheduler", "scheduler", "check_conflicts", q.text, {"query": q.text}, .95), .95)
        if re.search(r"\b(?:create|add|book|schedule)\b", low):
            p = parameter_extractor.extract_calendar_params(q.text)
            missing = p.get("missing_required", [])
            if missing:
                return _candidate(Provider.clarify(q, "scheduler", "scheduler", "Please provide " + " and ".join(missing) + ".", {"calendar_request": q.text, **p}), .97)
            return _candidate(Provider.make(q, "scheduler", "scheduler", "create_calendar_event", p.get("title", ""),
                {"calendar_request": q.text, **p}, .97, True), .97)
        return _candidate(Provider.make(q, "scheduler", "scheduler", "get_calendar_events", "calendar_events",
                                        {"query": q.text, "calendar_request": q.text}, .94), .94)
    if any(x in low for x in ("reminder", "remind me", "set an alarm", "set a timer", "wake me")):
        p = parameter_extractor.extract_schedule_params(q.text)
        if p.get("dela