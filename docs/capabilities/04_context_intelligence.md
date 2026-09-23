# Capability 04: Context Intelligence

**Capability ID:** `04_context_intelligence`  
**Classification:** `EXISTING`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `cognitive`  
**Primary Provider:** `provider.cognitive.context_engine`  
**Fallback Provider:** N/A (Foundational Core)  

---

## 1. Capability Purpose & Scope
Maintains short-term conversational and operational working context across multi-turn interactions. Eliminates brittle keyword routing by disambiguating pronouns (*"it"*, *"that"*, *"that tab"*, *"that file"*, *"continue"*, *"the other one"*) against the grounded World Model state machine.

---

## 2. Supported Operations
- `context.resolve_pronoun`: Disambiguates references to active Chrome tabs, code artifacts, or files.
- `context.get_active_referent`: Retrieves the primary entity under active user focus.
- `context.update_state`: Updates working context with newly verified entities.

---

## 3. Required Context & World Model State
- **Active Browser State:** Active CDP tab ID, page URL, and media playback status.
- **Active Code Snippet:** Last generated or inspected source code in working memory.
- **Active Filesystem Target:** Most recently referenced or created file path.

---

## 4. Provider Implementation & Selection
- **Implementation:** `cognitive/understanding.py` (`UnderstandingEngine`) and `cognitive/world_model.py`.
- **System 1 Performance:** Resolves referents in **<0.1 ms** via in-memory regex entity extraction and state binding.
- **Multi-Turn Support:** Tested and verified across 4 multi-turn trees (Browser, Media, Files, Code) in Audit Suite 2.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED`.
- **Ambiguity Detection:** When referents cannot be grounded with confidence, flags `is_ambiguous=True` and populates `clarification_prompt` rather than guessing.
- **Invariant Enforcement:** Invariant 7 (*"Independent requests cannot corrupt each other's context"*).
