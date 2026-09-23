# Capability 18: Persona & Social Interaction

**Capability ID:** `18_persona_social`  
**Classification:** `EXISTING`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `system`  
**Primary Provider:** `provider.llm.persona_manager` (wrapping `config.settings.settings` & `llm/personas.py`)  
**Fallback Provider:** `provider.os.win32`  

---

## 1. Capability Purpose & Scope
Manages persistent personality, voice assignment, and conversational demeanor across JARVIS personas:
- **Jarvis:** Crisp, efficient, courteous, and respectful.
- **Friday:** Warm, casual, energetic, and encouraging.
- **Ultron:** Dry, blunt, faintly sardonic, and unapologetically direct.
- **Omi:** Minimal, calm, gentle, and concise.

---

## 2. Supported Operations
- `system.switch_persona`: Hot-swaps the active persona across prompt templates, voice models, and demeanor settings.
- `system.set_tone`: Configures dynamic style/tone modifiers (e.g. "sardonic", "concise", "empathetic") on top of base personas.
- `system.get_persona`: Retrieves the current active persona configuration and system prompt preview.

---

## 3. Required Context & World Model State
- **Active Persona Setting:** Persisted in `config.settings.settings.active_persona_name`.
- **System Prompts:** Registered in `llm/personas.py` (`PERSONA_SYSTEM_PROMPTS`).

---

## 4. Provider Implementation & Selection
- **Implementation:** `capabilities/providers/persona_provider.py` (`PersonaManagerProvider`).
- **Fast-Path Latency:** Instantaneous in-memory state transition in **< 1.0 ms**.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED` (Read-only persona state management).
- **Verification Strategy:** `PERSONA_STATE_ASSERTION` confirms that system prompts and voice IDs correctly update on state transitions.
