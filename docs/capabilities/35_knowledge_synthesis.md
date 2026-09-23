# Capability 35: Knowledge Synthesis

**Capability ID:** `35_knowledge_synthesis`  
**Classification:** `CORE_SYNTHESIS`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `synthesis`  
**Primary Provider:** `provider.knowledge.synthesis`  
**Provider Operations:** `synthesis.combine_sources`, `synthesis.generate_brief`, `synthesis.synthesize`  

---

## 1. Capability Purpose & Scope

Capability 35 combines verified evidence from heterogeneous sources into coherent, well-structured answers and executive briefs. It is **not** a simple text concatenator or ungrounded text generation loop.

### Strict Synthesis Invariants:
1. **Anti-Hallucination Invariant**: Every factual statement is strictly grounded in verified personal evidence, external citations, or explicitly stated uncertainty. The synthesizer never manufactures unsupported facts.
2. **Conflict Preservation**: If the verification stage identifies contradictions between sources, the synthesis explicitly presents the conflict (e.g. "Source A states X whereas Source B states Y") rather than silently resolving it.
3. **Personal vs External Clean Boundary**: In heterogeneous queries, synthesis maintains transparent categorization between **Personal Knowledge** (private user records, projects, files) and **External Information** (web sources, real-time data).
4. **Transparent Citation**: All claims are traceable to source identity and provenance metadata.

---

## 2. Multi-Step Synthesis Pipeline

The standard synthesis pipeline coordinates Capabilities 33, 34, and 35 without conflating them into a single monolithic call:

```
[Retrieve]      Capability 33 (Personal Search) / Capability 31 (Web) / Capability 32 (Real-Time)
       ↓
[Verify]        Capability 34 (Information Verification)
       ↓
[Structure]     Group evidence by category (Personal, External, Episodic)
       ↓
[Resolve]       Detect and preserve conflicts & uncertainties
       ↓
[Synthesize]    Capability 35 (Knowledge Synthesis)
       ↓
[Attribution]   Attach transparent source citations & verification badges
```

---

## 3. Supported Operations

| Operation | Description | Inputs | Expected Output |
| :--- | :--- | :--- | :--- |
| `synthesis.combine_sources` | Combines verified evidence into categorized sections with source attribution | `query: str`, `sources: List[Dict]`, `verification: Optional[Dict]` | `synthesis: str`, `sources_count: int`, `personal_sources_count: int`, `external_sources_count: int`, `citations: List[Dict]` |
| `synthesis.generate_brief` | Produces an executive multi-section brief from evidence | `topic: str`, `evidence: List[Dict]`, `include_recommendations: bool = True` | `brief: str`, `topic: str`, `sections: List[str]` |
| `synthesis.synthesize` | Direct claim synthesis adhering to strict factual containment | `prompt: str`, `data: Any` | `output: str`, `status: "SUCCESS"` |

---

## 4. Personal + External Executive Brief Structure

When comparing personal project records with external web research (e.g., *"Compare my previous Jarvis architecture decision with current external information"*), Capability 35 formats the result as a structured brief:

```markdown
# Executive Synthesis: [Query]

## 1. Verified Personal Knowledge
- [Personal Fact 1] (Source: [Doc Name])
- [Personal Fact 2] (Source: [Project Record])

## 2. External Research & Real-Time Context
- [External Fact 1] (Source: [Web Citation])
- [External Fact 2] (Source: [API Feed])

## 3. Comparative Analysis & Key Differences
- Personal architecture specifies modular capability intelligence.
- External standards align with modular provider abstraction.

## 4. Verified Conflicts & Uncertainties
- [None detected | Disagreement between Source A and Source B]

## 5. Citations & Provenance
- [1] Personal Source: [doc_id]
- [2] External Source: [url]
```
