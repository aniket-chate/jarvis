# JARVIS Security & Privacy Architecture

This document formalizes the **data privacy boundaries**, **hardware security guarantees**, and **sandboxing architecture** of JARVIS.

---

## 1. Data Privacy Boundary: What Stays Local vs. What Leaves the Machine

JARVIS adheres to a strict **Local-First Privacy Architecture**. All continuous background sensors, neural model weights, conversational memories, and biometrics execute entirely on the local workstation.

### What Stays Strictly Local (Never Leaves the Workstation)

| Data Type | Processing Engine | Storage / Execution Location | Network Access |
| :--- | :--- | :--- | :--- |
| **Wake Word Audio** | openWakeWord | Local CPU RAM buffer (discarded immediately) | None |
| **Speech-to-Text (ASR)** | faster-whisper | Local CPU (base model weights) | None |
| **Text-to-Speech (TTS)** | piper-tts | Local CPU (ONNX model weights) | None |
| **Core Reasoning** | Ollama (Qwen2.5 3B) | Local GPU (RTX 2050 4GB VRAM) | None |
| **Vision Understanding** | Ollama (Moondream 1.6B) | Local GPU (RTX 2050 4GB VRAM) | None |
| **Biometric Face Embeddings** | OpenCV + Cosine Similarity | `memory/owner_profile.json` | None |
| **User Memory & Profile** | MemoryManager | `memory/user_profile.json` | None |
| **Personal Knowledge Base**| PKB Repository | `data/knowledge_base/` | None |
| **Workspace Files** | Sandboxed Agent | `workspace/` | None |

---

### What Leaves the Machine (Strictly Gated Outbound Calls)

The only data that ever leaves the local workstation consists of external web queries explicitly initiated by the user. Every outbound call is sanitized and gated:

1. **Web Search Queries (Tavily / Brave)**:
   - Outgoing query strings are passed through `PrivacyProtection.sanitize_external_query()`.
   - Any accidentally included API keys, credentials, email addresses, phone numbers, or private memory keys are automatically redacted before network transmission.
2. **Google Cloud Services (Calendar & Gmail)**:
   - Uses user-authorized OAuth tokens saved locally in `credentials/`.
   - **Draft-First Rule**: Email sending always creates a local draft first.
   - **Two-Gate Rule**: Actually dispatching an email requires **both** biometric identity confirmation (Gate 1) and explicit user approval (Gate 2).
3. **Browser Automation (Playwright)**:
   - Navigates directly to requested public websites (e.g. YouTube, Wikipedia).
   - Never shares internal memory, authentication tokens, or profile vectors with visited pages.

---

## 2. Filesystem Sandboxing & Path-Traversal Defense

All filesystem interactions performed by `file_document_agent` are strictly restricted to the workspace root:

```text
D:\assignment\JARVIS\workspace\
```

### Path Traversal Defense Mechanisms

1. **Normalization & Traversal Stripping**: All relative paths are normalized using `os.path.normpath` and checked for `..` parent directory traversal tokens.
2. **Boundary Containment Check**:
   ```python
   target_path = (sandbox_root / relative_path).resolve()
   if not str(target_path).startswith(str(sandbox_root)):
       raise PermissionError("Access denied: Path traversal outside sandbox is forbidden")
   ```
3. **Permission Gate**: All file write and deletion operations are routed through `PermissionManager.evaluate_action(domain='filesystem')`.
