# Capability 01: Natural Language & Conversation

**Capability ID:** `01_natural_language`  
**Classification:** `EXISTING`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `chat`  
**Primary Provider:** `provider.llm.ollama_local`  
**Fallback Provider:** `provider.llm.cloud_gemini`  

---

## 1. Capability Purpose & Scope
Provides fluent, natural multimodal dialogue, greeting interactions, contextual clarification, response style selection (concise vs. detailed), and multilingual capabilities with full support for Marathi, English, and Marathi-English code-switching (*Hinglish/Minglish*).

---

## 2. Supported Operations
- `chat.conversation`: Multi-turn conversational dialogue grounded in current context.
- `chat.greeting`: Natural, persona-aligned salutations and status reports.
- `chat.clarification`: Interactive disambiguation when queries are underspecified.
- `chat.multilingual`: Native Marathi, English, and mixed-code conversational processing.

---

## 3. Required Context & World Model State
- **Active Persona:** Sticky persona (`Jarvis`, `Friday`, `Ultron`) from `WorldModel.state.active_persona`.
- **Working Memory:** Recent turns and resolved entity referents.
- **User Profile:** Owner identity and language preferences from `memory/user_profile.json`.

---

## 4. Provider Implementation & Selection
- **Local Ollama (`qwen2.5:3b`):** Primary local provider running on `http://127.0.0.1:11434` for sub-second, air-gapped conversational responses.
- **Cloud Fallback (`Gemini`):** Automatic failover if local inference times out (>30s) or crashes.
- **System 1 vs System 2:**
  - Simple greetings and single-turn factual queries route via System 1 fast path.
  - Ambiguous queries, corrections, and complex synthesis route via System 2 deliberative path.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED`. No side effects on the host OS.
- **Untrusted Input Quarantine:** External content injected into conversation is wrapped in `<UNTRUSTED_EXTERNAL_DATA>` tags.
- **Verification Method:** Deductive response coherence and absence of hallucinated action commitments.
- **Failure Mode:** If LLM is unreachable, falls back to deterministic rule-based conversational templates.
