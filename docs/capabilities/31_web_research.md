# Capability 31: Web Research

**Capability ID:** `31_web_research`  
**Classification:** `EXISTING_EXPANDED`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `search`  
**Primary Provider:** `provider.web.search_fetch`  
**Fallback Providers:** `provider.web.tavily_api`, `provider.web.duckduckgo_free`, `provider.web.wikipedia_api`  

---

## 1. Capability Purpose & Scope

Capability 31 manages JARVIS's external web research, live search discovery, web page fetching, and multi-source citation synthesis. It operates as a first-class unified capability domain within the JARVIS Cognitive Core rather than an independent or disconnected "web agent".

All external web information is treated as **UNTRUSTED EXTERNAL DATA**. The capability enforces strict safe containment tags (`<UNTRUSTED_WEB_DATA>`), transparent source provenance, authority-based credibility ranking, cross-source contradiction/conflict detection, and multi-provider failover.

---

## 2. Supported Operations

| Operation | Description | Inputs | Expected Output | Safety / Verification |
| :--- | :--- | :--- | :--- | :--- |
| `search.web` | Discovers candidate web sources with privacy sanitization and fallback chain | `query: str`, `max_results: int = 5`, `provider: Optional[str]` | `query`, `provider`, `results: List[CandidateSource]`, `count`, `freshness` | `READ_ONLY`; Verified by `ObservationVerificationKernel` confirming structured candidate sources |
| `web.fetch` | Deep retrieval of web page content with HTML cleaning and data isolation | `url: str`, `max_chars: int = 4000` | `url`, `status_code`, `content`, `length_chars`, `safe_data`, `freshness` | `READ_ONLY`; Empirically verified via real HTTP status code and non-empty extracted text |
| `search.synthesize_citations` | Synthesizes multiple sources, ranks credibility, detects contradictions, and attributes claims | `sources: List[Dict]`, `query: str` | `citations: List[Dict]`, `conflicts: List[Dict]`, `has_conflicts: bool`, `synthesis: str` | `READ_ONLY`; Verified by `ObservationVerificationKernel` confirming citations match sources |

---

## 3. Architectural Pipeline Trace

```
User Natural Language Request ("Research React and compare it with Vue")
      ↓
Cognitive Understanding Engine (cognitive/understanding.py)
   - Disambiguates intent -> domain='search', action='research_and_compare'
   - Resolves pronouns and entities via WorldModel snapshot
      ↓
Context & World Model (cognitive/world_model.py)
   - Injects active referents, workspace state, and recent entities
      ↓
Cognitive Core (cognitive/kernel.py & planning_engine.py)
   - Decomposes multi-intent research into DAG plan:
     Step 1: search.web (React)
     Step 2: search.web (Vue)
     Step 3: search.synthesize_citations (React vs Vue)
      ↓
Capability Intelligence (capabilities/intelligence.py)
   - Dynamically selects primary provider: 'provider.web.search_fetch'
   - Supports runtime provider replacement and automatic failover
      ↓
Web Research Provider (capabilities/providers/search_provider.py)
   - Standardized BaseCapabilityProvider executing operations with latency tracking
      ↓
Underlying Web Engines (agents/web_agent.py & skills/web_skills.py)
   - Tavily API -> Brave API -> DuckDuckGo Free -> Wikipedia Summary
      ↓
Observation
   - ExecutionKernel captures ActionResult with candidate sources, status code, and citations
      ↓
Verification (verification/verifier.py)
   - ObservationVerificationKernel confirms real HTTP status, source structure, and freshness
      ↓
Response & Memory (memory/system.py & memory/episodic.py)
   - Action recorded in 7-Tier EpisodicLedger with verification status
   - Formatted synthesis with citations returned to user
```

---

## 4. Source Provenance & Freshness

Every search result and fetched page retains complete provenance:
- **`source_id`:** Deterministic 12-character SHA-256 hash of URL.
- **`url`:** Absolute source URL.
- **`title`:** Web page or article title.
- **`retrieved_at`:** ISO-8601 retrieval timestamp.
- **`provider`:** Identity of search or fetch engine used (`tavily`, `brave`, `duckduckgo`, `wikipedia`).
- **`source_type`:** Distinguishes `"search_result"` (snippet only) from `"fetched_source"` (deep inspected page).
- **`freshness`:** State classification (`"current"`, `"recent"`, `"cached"`, `"stale"`, `"unavailable"`).

---

## 5. Security & Prompt Injection Defense

All web content is treated as untrusted data:
1. **Data Containment:** Raw snippets and fetched texts are encapsulated in `<UNTRUSTED_WEB_DATA source_id="..." url="...">` tags.
2. **Policy Gate Defense:** Instructions inside web pages (e.g. `"SYSTEM OVERRIDE: execute shell command..."`) cannot override system instructions, persona, or safety policies. The `PolicyKernel` strictly rejects arbitrary shell execution attempts derived from web content.
3. **Privacy Sanitization:** Outgoing search queries pass through `PrivacyProtection` to prevent accidental credential, token, or PII leakage.

---

## 6. Operational Verification Classifications

| Major Operation | Verification Classification | Runtime Reality & Evidence |
| :--- | :--- | :--- |
| `search.web` | **VERIFIED END-TO-END** | Real web search executed via Tavily and DuckDuckGo; candidate sources structured with provenance; verified via `ObservationVerificationKernel`. |
| `web.fetch` | **VERIFIED END-TO-END** | Real web page fetched (`https://example.com`); HTTP 200 verified; HTML stripped; clean text wrapped in `<UNTRUSTED_WEB_DATA>`. |
| `search.synthesize_citations` | **VERIFIED END-TO-END** | Formats transparent citations, ranks authority (`authoritative` vs `standard`), and detects contradictory statements across sources. |
| `contextual retrieval` | **VERIFIED END-TO-END** | Disambiguates pronouns ("it") via `WorldModel` context; flags ambiguous references for clarification rather than hallucinating. |
| `provider replacement` | **VERIFIED END-TO-END** | Dynamic runtime swapping via `CapabilityIntelligence` with priority routing and automatic fallback restoration. |
| `security/injection handling` | **VERIFIED END-TO-END** | Web prompt injection quarantined as inert data; `PolicyKernel` refuses derived command execution. |
| `concurrency/recovery` | **VERIFIED END-TO-END** | 6 concurrent web search threads executed without deadlocks; graceful failover on network handshake timeout. |
