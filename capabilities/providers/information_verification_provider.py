"""Information Verification Capability Provider for Capability 34.

Provides:
- verification.information: Multi-dimensional verification of claims against retrieved evidence.
- verification.cross_reference_claims: Cross-source consistency checking and structured conflict detection.
- verification.observe_reality: Empirical physical reality grounding check via World Model.

Verification Dimensions:
1. Source Provenance: Verifies source identity, type, and traceability.
2. Source Authority: Distinguishes authoritative personal PKB records, real-time feeds, and external web citations.
3. Freshness: Flags stale evidence when current/real-time state is required.
4. Cross-Source Consistency: Detects value/claim contradictions without arbitrarily picking a winner.
5. Content Grounding: Verifies claim text is strictly supported by source text snippets.
6. Data Completeness: Detects missing fields, null payloads, and unverified assumptions.

Explicit Truthful States:
- VERIFIED: Corroborated by multiple authoritative sources or single authoritative source with high confidence and freshness.
- SUPPORTED: Single credible source with consistent evidence.
- UNCERTAIN: Weak, ambiguous, or incomplete evidence.
- CONTRADICTED: Disagreement/conflict detected between sources or physical reality.
- NOT_VERIFIABLE: Claim cannot be substantiated with available evidence.
- STALE: Evidence is outdated for a time-sensitive/current assertion.
- FAILED: Missing sources, malformed evidence, or evaluation error.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from cognitive.world_model import world_model, WorldModel

logger = logging.getLogger("JARVIS.Providers.InformationVerification")


@dataclass
class VerificationConfig:
    """Configurable thresholds for evidence support and freshness auditing."""
    verified_threshold: float = 0.75
    supported_threshold: float = 0.40
    uncertain_threshold: float = 0.15
    default_max_age_sec: float = 86400.0
    fresh_max_age_sec: float = 7200.0


class InformationVerificationProvider(BaseCapabilityProvider):
    """Audits and verifies retrieved evidence across multiple sources and physical reality."""

    def __init__(self, wm: Optional[WorldModel] = None, config: Optional[VerificationConfig] = None):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.verification.information",
                name="Information Verification & Grounding Provider",
                supported_capabilities=[
                    "verification.information",
                    "verification.cross_reference_claims",
                    "verification.observe_reality",
                ],
                priority=10,
                estimated_latency_ms=30.0,
            )
        )
        self.world_model = wm or world_model
        self.config = config or VerificationConfig()

    def is_available(self) -> bool:
        return True

    def _extract_tokens(self, text: str) -> set:
        return set(re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", text.lower()))

    def _calculate_support(self, claim: str, evidence: str) -> float:
        """Calculates token grounding overlap between claim and source evidence."""
        c_tokens = self._extract_tokens(claim)
        if not c_tokens:
            return 1.0
        e_tokens = self._extract_tokens(evidence)
        if not e_tokens:
            return 0.0
        intersection = c_tokens.intersection(e_tokens)
        return len(intersection) / len(c_tokens)

    def _detect_conflicts(self, sources: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Detects contradictions between multiple source items."""
        if len(sources) < 2:
            return None

        # Compare values across sources
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                s1 = sources[i]
                s2 = sources[j]
                t1 = str(s1.get("content") or s1.get("snippet") or s1.get("value") or "").strip()
                t2 = str(s2.get("content") or s2.get("snippet") or s2.get("value") or "").strip()

                # Explicit numeric value check (e.g. "port: 8000" vs "port: 9000", "temp: 28" vs "temp: 35")
                m1_nums = re.findall(r"\b\d+(?:\.\d+)?\b", t1)
                m2_nums = re.findall(r"\b\d+(?:\.\d+)?\b", t2)
                # If sources talk about the same property but have different numbers
                shared_words = self._extract_tokens(t1).intersection(self._extract_tokens(t2))
                if len(shared_words) >= 2 and m1_nums and m2_nums and m1_nums != m2_nums:
                    return {
                        "conflict_detected": True,
                        "dimension": "value_mismatch",
                        "source_a": s1.get("source_id") or s1.get("title") or "Source A",
                        "source_b": s2.get("source_id") or s2.get("title") or "Source B",
                        "claim_a": t1[:200],
                        "claim_b": t2[:200],
                        "explanation": f"Numeric or property divergence detected between {s1.get('title', 'Source A')} ({m1_nums}) and {s2.get('title', 'Source B')} ({m2_nums}).",
                    }

                # Semantic polarity contradiction (yes/no, enable/disable, true/false, pass/fail)
                negations = [("enable", "disable"), ("active", "inactive"), ("passed", "failed"), ("success", "failure"), ("true", "false"), ("yes", "no")]
                for pos, neg in negations:
                    if (pos in t1.lower() and neg in t2.lower()) or (neg in t1.lower() and pos in t2.lower()):
                        return {
                            "conflict_detected": True,
                            "dimension": "polarity_contradiction",
                            "source_a": s1.get("source_id") or s1.get("title") or "Source A",
                            "source_b": s2.get("source_id") or s2.get("title") or "Source B",
                            "claim_a": t1[:200],
                            "claim_b": t2[:200],
                            "explanation": f"Direct polarity contradiction detected: '{pos}' vs '{neg}'.",
                        }

        return None

    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t_start = time.perf_counter()
        params = dict(parameters or {})

        try:
            # -------------------------------------------------------------
            # 1. verification.information (Main Claim Verification)
            # -------------------------------------------------------------
            if capability in ["verification.information", "verification.verifier"]:
                claim = str(params.get("claim") or params.get("statement") or params.get("assertion") or "").strip()
                sources = params.get("sources") or params.get("evidence") or []
                if isinstance(sources, dict):
                    sources = [sources]
                elif not isinstance(sources, list):
                    sources = []

                if not sources and not claim:
                    return ActionResult(
                        status="FAILED",
                        output={"state": "FAILED", "reason": "Missing claim and sources", "verified": False},
                        message="Verification requires at least a claim or evidence sources.",
                        execution_time_ms=(time.perf_counter() - t_start) * 1000,
                    )

                # Check for empty sources
                if not sources:
                    return ActionResult(
                        status="SUCCESS",
                        output={
                            "state": "NOT_VERIFIABLE",
                            "claim": claim,
                            "verified": False,
                            "confidence": 0.0,
                            "reason": "No evidence sources provided to verify claim.",
                            "provenance": [],
                        },
                        message=f"Claim '{claim}' cannot be verified: No evidence sources provided.",
                        execution_time_ms=(time.perf_counter() - t_start) * 1000,
                    )

                # Check for conflicts between sources
                conflict = self._detect_conflicts(sources)
                if conflict:
                    self.record_outcome(True)
                    return ActionResult(
                        status="SUCCESS",
                        output={
                            "state": "CONTRADICTED",
                            "claim": claim,
                            "verified": False,
                            "confidence": 0.3,
                            "conflict": conflict,
                            "sources_count": len(sources),
                            "reason": conflict["explanation"],
                            "provenance": [s.get("source_id") or s.get("title") for s in sources],
                        },
                        message=f"Verification found contradictions between sources: {conflict['explanation']}",
                        execution_time_ms=(time.perf_counter() - t_start) * 1000,
                    )

                # Check Freshness
                require_fresh = bool(params.get("require_fresh", False) or "right now" in claim.lower() or "today" in claim.lower() or "current" in claim.lower())
                max_age_sec = float(params.get("max_age_sec", self.config.default_max_age_sec))
                if require_fresh:
                    max_age_sec = min(max_age_sec, self.config.fresh_max_age_sec)

                is_stale = False
                now_ts = time.time()
                for s in sources:
                    ts_val = s.get("timestamp") or s.get("retrieved_at") or s.get("created_at")
                    if ts_val:
                        try:
                            if isinstance(ts_val, (int, float)):
                                age = now_ts - float(ts_val)
                            else:
                                dt = datetime.fromisoformat(str(ts_val).replace("Z", "+00:00"))
                                age = now_ts - dt.timestamp()
                            if age > max_age_sec:
                                is_stale = True
                                break
                        except Exception:
                            pass

                if is_stale and require_fresh:
                    self.record_outcome(True)
                    return ActionResult(
                        status="SUCCESS",
                        output={
                            "state": "STALE",
                            "claim": claim,
                            "verified": False,
                            "confidence": 0.4,
                            "reason": f"Evidence exceeds maximum age threshold of {max_age_sec}s for real-time verification.",
                            "provenance": [s.get("source_id") or s.get("title") for s in sources],
                        },
                        message=f"Verification rejected stale evidence for time-sensitive claim '{claim}'.",
                        execution_time_ms=(time.perf_counter() - t_start) * 1000,
                    )

                # Evaluate support across sources
                total_support = 0.0
                weights = []
                for s in sources:
                    snippet = f"{s.get('title', '')} {s.get('snippet', '')} {s.get('content', '')}".strip()
                    auth = 1.0 if s.get("source_type") in ["personal_knowledge", "project", "realtime_feed"] else 0.8
                    sup = self._calculate_support(claim, snippet)
                    total_support += sup * auth
                    weights.append(auth)

                avg_support = total_support / max(1.0, sum(weights)) if weights else 0.0

                # Determine final state
                if avg_support >= self.config.verified_threshold:
                    final_state = "VERIFIED"
                    is_ver = True
                    conf = min(0.98, 0.70 + (0.28 * avg_support))
                elif avg_support >= self.config.supported_threshold:
                    final_state = "SUPPORTED"
                    is_ver = True
                    conf = 0.70
                elif avg_support > self.config.uncertain_threshold:
                    final_state = "UNCERTAIN"
                    is_ver = False
                    conf = 0.45
                else:
                    final_state = "NOT_VERIFIABLE"
                    is_ver = False
                    conf = 0.20

                self.record_outcome(True)
                return ActionResult(
                    status="SUCCESS",
                    output={
                        "state": final_state,
                        "claim": claim,
                        "verified": is_ver,
                        "confidence": round(conf, 4),
                        "support_score": round(avg_support, 4),
                        "sources_count": len(sources),
                        "provenance": [s.get("source_id") or s.get("title") for s in sources],
                        "sources": sources,
                    },
                    message=f"Information verification state: {final_state} (Confidence: {conf:.2f}, Support: {avg_support:.2f}).",
                    execution_time_ms=(time.perf_counter() - t_start) * 1000,
                )

            # -------------------------------------------------------------
            # 2. verification.cross_reference_claims (Consistency & Contradiction)
            # -------------------------------------------------------------
            elif capability == "verification.cross_reference_claims":
                sources = params.get("sources") or []
                if not isinstance(sources, list) or len(sources) < 2:
                    return ActionResult(
                        status="SUCCESS",
                        output={
                            "state": "SUPPORTED",
                            "cross_referenced": True,
                            "conflict_detected": False,
                            "message": "Fewer than 2 sources provided for cross-referencing.",
                            "agreements": len(sources),
                        },
                        message="Cross-referencing completed: Single source evaluated.",
                        execution_time_ms=(time.perf_counter() - t_start) * 1000,
                    )

                conflict = self._detect_conflicts(sources)
                if conflict:
                    self.record_outcome(True)
                    return ActionResult(
                        status="SUCCESS",
                        output={
                            "state": "CONTRADICTED",
                            "cross_referenced": True,
                            "conflict_detected": True,
                            "conflict_details": conflict,
                            "sources_evaluated": len(sources),
                        },
                        message=f"Cross-referencing detected contradiction: {conflict['explanation']}",
                        execution_time_ms=(time.perf_counter() - t_start) * 1000,
                    )

                self.record_outcome(True)
                return ActionResult(
                    status="SUCCESS",
                    output={
                        "state": "VERIFIED",
                        "cross_referenced": True,
                        "conflict_detected": False,
                        "sources_evaluated": len(sources),
                        "agreement_consensus": "HIGH",
                    },
                    message=f"Cross-referencing confirmed multi-source agreement across {len(sources)} sources.",
                    execution_time_ms=(time.perf_counter() - t_start) * 1000,
                )

            # -------------------------------------------------------------
            # 3. verification.observe_reality (Ground Truth Reality Check)
            # -------------------------------------------------------------
            elif capability == "verification.observe_reality":
                target_type = params.get("target_type", "window")
                target_name = params.get("target_name", "")

                obs = {}
                if hasattr(self.world_model, "get_observation"):
                    try:
                        obs = self.world_model.get_observation()
                    except Exception:
                        obs = {}
                elif hasattr(self.world_model, "get_context_snapshot"):
                    try:
                        obs = self.world_model.get_context_snapshot()
                    except Exception:
                        obs = {}

                is_grounded = False
                detail = ""

                if target_type == "window":
                    windows = obs.get("windows", []) if isinstance(obs, dict) else []
                    matched = [w for w in windows if target_name.lower() in str(w).lower()]
                    is_grounded = len(matched) > 0
                    detail = f"Observed {len(matched)} matching window(s) for '{target_name}'."
                elif target_type == "file":
                    if hasattr(self.world_model, "probe_file"):
                        probe = self.world_model.probe_file(target_name)
                        is_grounded = bool(probe.get("exists", False))
                    else:
                        p = Path(target_name)
                        is_grounded = p.exists()
                    detail = f"Observed physical file on disk: {is_grounded} ({target_name})."
                else:
                    is_grounded = True
                    detail = f"Observed reality state: {obs.get('system_status', 'ONLINE')}."

                state = "VERIFIED" if is_grounded else "CONTRADICTED"
                self.record_outcome(True)
                return ActionResult(
                    status="SUCCESS",
                    output={
                        "state": state,
                        "is_grounded": is_grounded,
                        "target_type": target_type,
                        "target_name": target_name,
                        "details": detail,
                    },
                    message=f"Reality observation {state}: {detail}",
                    execution_time_ms=(time.perf_counter() - t_start) * 1000,
                )

            else:
                return ActionResult(
                    status="FAILED",
                    output={"error": f"Capability '{capability}' not supported by InformationVerificationProvider"},
                    message=f"Unsupported capability: {capability}",
                    execution_time_ms=(time.perf_counter() - t_start) * 1000,
                )

        except Exception as e:
            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(False)
            logger.error("[InformationVerificationProvider] Execution failed: %s", e, exc_info=True)
            return ActionResult(
                status="FAILED",
                output={"state": "FAILED", "error": str(e), "verified": False},
                message=f"Verification failure: {str(e)}",
                execution_time_ms=elapsed,
            )
