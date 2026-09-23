# JARVIS Fine-Tuning Datasets

This directory hosts training datasets used for QLoRA fine-tuning of JARVIS's on-device foundation models (e.g. Qwen 2.5 3B).

---

## 1. Dataset Architecture & Pipeline Design

JARVIS employs a hybrid dual-stream dataset architecture:

### A. Synthetic Cold-Start Dataset (`synthetic_dataset.jsonl`)
- **Role**: Synthetic "cold-start" seed dataset.
- **Generation Method**: Synthesized using teacher models (Llama 3.3 70B / curated structured schemas) to bootstrap model capabilities across 4 critical failure modes identified during manual testing:
  1. **Structured Parameter Extraction**: Natural language mapping directly to rigorous JSON parameters (`action`, `target`, `contact`, `app`, `query`, etc.) across file operations, messaging, app opening, and web searches.
  2. **Persona Consistency**: Multi-turn and single-turn conversations maintaining distinct identities across `Jarvis`, `Friday`, `Ultron`, and `Omi` using the `{assistant_name}` template convention.
  3. **Grounded Self-Description**: System identity questions answered strictly from the real agent registry (20 specialized local agents, running on Intel Core i5-12450H & NVIDIA RTX 2050 4GB, created by Aniket), eliminating hallucinations.
  4. **Honest Uncertainty & Safety Refusals**: Explicitly recognizing physical hardware limits (e.g., cannot place direct cellular phone calls without an external VoIP/SIM bridge, can only place WhatsApp calls via Web automation) and hard refusals of destructive shell commands (`rm -rf /`, `del /s /q C:\`, format drive, etc.).
- **Head Start, Not a Replacement**: Synthetic data provides an initial inductive bias for zero-shot accuracy. It is **not** a replacement for real user interaction data.

### B. Organic Interaction Dataset (`logs/interactions.jsonl`)
- **Role**: Continual organic real-world telemetry collected via `InteractionAuditStore`.
- **Pipeline**: Logs every live user prompt, task classification, provider cascade execution, parameters extracted, and outcome.
- **Merge Strategy**: On periodic re-fine-tune cycles, high-quality filtered organic interactions from `logs/interactions.jsonl` are de-duplicated and merged with `synthetic_dataset.jsonl` to continuously specialize the model to the user's specific habits, contacts, and workflow.

---

## 2. Dataset Format

All datasets adhere to standard ShareGPT/OpenAI chat JSONL formatting:

```json
{
  "messages": [
    {"role": "system", "content": "You are JARVIS..."},
    {"role": "user", "content": "Send a WhatsApp message to Rahul saying I will be late"},
    {"role": "assistant", "content": "{\"action\": \"send_message\", \"platform\": \"whatsapp\", \"recipient\": \"Rahul\", \"message\": \"I will be late\"}"}
  ],
  "metadata": {
    "category": "parameter_extraction",
    "sub_category": "messaging",
    "source": "synthetic_cold_start"
  }
}
```

---

## 3. Dataset Statistics

- **Total Examples**: 400
- **Line Count**: 400 lines
- **Byte Count**: ~227 KB
- **Review Sample**: `sample_review_30.json` (30 balanced examples across all 4 categories for human evaluation and sign-off before training).
