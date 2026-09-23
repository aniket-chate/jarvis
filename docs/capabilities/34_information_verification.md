# Capability 34: Information Verification

**Capability ID:** `34_information_verification`  
**Classification:** `CORE_VERIFICATION`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `verification`  
**Primary Provider:** `provider.verification.information`  
**Provider Operations:** `verification.information`, `verification.cross_reference_claims`, `verification.observe_reality`  

---

## 1. Capability Purpose & Scope

Capability 34 evaluates, cross-references, and validates information before it is accepted as reliable evidence. It is fundamentally distinct from Capability 31 (Web Research): while Capability 31 finds external information, Capability 34 determines whether retrieved information—from personal records, web sources, or real-time feeds—is grounded, coherent, fresh, and free from contradictions.

---

## 2. Verification Dimensions

The verification engine evaluates evidence across 6 objective dimensions:

1. **Source Provenance**: Verifies source identity, type, and attribution integrity.
2. **Source Authority**: Distinguishes authoritative personal records, verified real-time feeds, and external web citations.
3. **Freshness & Temporal Validity**: Enforces strict timestamp checking; flags stale evidence when real-time state is required.
4. **Cross-Source Consistency**: Compares multiple independent sources to identify numerical, factual, or polarity contradictions.
5. **Content Grounding**: Evaluates token overlap and claim entailment against source snippets.
6. **Data Completeness**: Identifies missing attributes, empty payloads, and unsupported assumptions.

---

## 3. Explicit Truthful Verification States

Capability 34 never collapses verification into an ambiguous boolean. It reports explicit, structured states:

| State | Definition | Confidence Range |
| :--- | :--- | :--- |
| `VERIFIED` | Corroborated by multiple authoritative sources or single authoritative source with high grounding and freshness | 0.80 – 0.98 |
| `SUPPORTED` | Grounded in a credible single source without contradictions | 0.60 – 0.79 |
| `UNCERTAIN` | Weak, ambiguous, or incomplete evidence | 0.35 – 0.55 |
| `CONTRADICTED` | Direct disagreement detected between sources (e.g. 8000 vs 9000) or conflict with physical reality | 0.20 – 0.35 |
| `NOT_VERIFIABLE` | Claim cannot be substantiated with available evidence (no sources or unsupported assertion) | 0.00 – 0.25 |
| `STALE` | Evidence exceeds acceptable age threshold for a time-sensitive/current assertion | 0.30 – 0.45 |
| `FAILED` | Malformed inputs, missing claim and sources, or evaluation error | 0.00 |

---

## 4. Conflict Detection & Non-Arbitrary Resolution

When multiple sources disagree (e.g., Source A states "port 8000" while Source B states "port 9000"):
- The verification provider produces a structured conflict object:
  ```json
  {
    "conflict_detected": true,
    "dimension": "value_mismatch",
    "source_a": "Specification Alpha",
    "source_b": "Specification Beta",
    "explanation": "Numeric or property divergence detected between Specification Alpha (['8000']) and Specification Beta (['9000'])."
  }
  ```
- The engine does **NOT** guess or pick one arbitrarily. It preserves both sources and flags the contradiction to the Knowledge Synthesis layer.

---

## 5. Supported Operations

| Operation | Description | Inputs | Expected Output |
| :--- | :--- | :--- | :--- |
| `verification.information` | Multi-dimensional verification of a claim against evidence sources | `claim: str`, `sources: List[Dict]`, `require_fresh: bool = False` | `state: str`, `verified: bool`, `confidence: float`, `support_score: float`, `provenance: List[str]` |
| `verification.cross_reference_claims` | Cross-source consistency analysis and contradiction detection | `sources: List[Dict]` | `conflict_detected: bool`, `conflict: Optional[Dict]`, `sources_count: int` |
| `verification.observe_reality` | Physical reality grounding check via World Model (files on disk, windows, processes) | `target_type: str`, `target_name: str` | `state: str`, `is_grounded: bool`, `detail: str` |
