# JARVIS Regional Localization: India (en_IN)

## 1. Overview
JARVIS is customized for an India-centric operational context. All temporal, monetary, communication, and search layers adhere to Indian regional defaults.

---

## 2. Core Localization Specifications

### A. Timezone & Temporal State
- **Timezone:** `Asia/Kolkata` (`IST` - Indian Standard Time, `UTC+5:30`).
- **Date Format:** `DD-MM-YYYY` (e.g. `10-09-2026`).
- **Clock Format:** 12-hour AM/PM with explicit `IST` designation.
- **Implementation:** Embedded directly in `perception.processing.context_awareness.ContextAwarenessEngine` and reflected across all persona system prompts.

### B. Currency & Monetary Values
- **Default Currency:** Indian Rupee (`INR` / `₹` / `Rs.`).
- **Policy:** The Assistant must never default to USD (`$`) or EUR (`€`) for prices, hotel rates, shopping estimates, or subscriptions unless the user explicitly asks for an international currency.
- **Implementation:** Enforced in `config/config.yaml`, `config/settings.py`, and `llm/personas.py`.

### C. Search & News Regional Biasing
- **Default Search Region:** India (`in`).
- **Location-Sensitive Biasing:** Queries lacking an explicit geographic entity (e.g., *"weather"*, *"news"*, *"best hotels near me"*, *"petrol price"*, *"nifty"*, *"stock market"*) are automatically biased toward India rather than defaulting to US-centric results.
- **Implementation:** Built into `agents.web_agent.WebAgent._localize_query` and `agents.news_agent.NewsAgent.fetch_news`.

### D. Telephony & Messaging (SMS)
- **Default Country Code:** `+91` (India).
- **Behavior:** 10-digit mobile numbers or numbers starting with `0` entered without country codes are automatically normalized to `+91XXXXXXXXXX` before generating Android SMS intents or dispatching communication tasks.
- **Implementation:** `agents.communication_agent.CommunicationAgent._normalize_phone_number`.

---

## 3. Speech Synthesis (TTS) Known Limitation & Resolution

### Known Limitation
- In the official Piper TTS neural voice dataset (`rhasspy/piper-voices`), there is currently **no native `en_IN` (Indian English) voice model**.
- While Indian regional languages (e.g., Hindi `hi_IN`, Marathi `mr_IN`) exist in experimental branches, a production-grade English Indian-accented model is not published.

### Architectural Resolution
- Rather than defaulting to General American (`en_US`) or generating an unconvincing synthetic accent, JARVIS defaults to **`en_GB` (British English - `en_GB-alan-medium`)**.
- Phonetically, British English shares non-rhotic vowel pronunciation and lexical stress closer to Indian English than American English.
- Once a community or official `en_IN` Piper ONNX model is published, it can be dropped directly into `models/piper/` with zero architectural refactoring.
