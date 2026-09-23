# JARVIS — Autonomous Multimodal AI Assistant

> **Next-Generation Personal AI Operating System** with 50 verified real-world capabilities, hierarchical intent routing, autonomous computer use, voice synthesis, and safety guardrails.

---

## 🌟 Overview

**JARVIS** is an autonomous desktop and web AI companion designed for complex task execution, deep system integration, proactive intelligence, and seamless voice/multimodal interaction.

Unlike traditional chat wrappers, JARVIS operates through an **orchestrated multi-agent cognitive architecture**:
- **Hierarchical Cognitive Routing**: ML-driven two-tier domain and capability classifier ensuring 0% routing collision across 50 distinct capability domains.
- **Multimodal Perception**: Real-time screen analysis, OCR, visual diffing, and Chrome DevTools Protocol (CDP) browser automation.
- **Voice & Speech Engine**: Low-latency local neural TTS (Piper) and high-accuracy ASR with wake-word detection.
- **Autonomous Planner & Verifier**: Closed-loop execution engine that drafts multistep plans, checks preconditions, verifies outcomes, and executes self-healing retries.
- **Deterministic Safety Policy Kernel**: Strict policy enforcement preventing destructive actions, unauthenticated file wipes, and sensitive credential leakage.

---

## 🏗️ Architecture

```
                                  [ User Input ]
                               (Voice / Text / UI)
                                        │
                                        ▼
                         ┌─────────────────────────────┐
                         │   Orchestrator & Router     │
                         │  (Hierarchical Classifier)  │
                         └──────────────┬──────────────┘
                                        │
         ┌──────────────────────────────┼──────────────────────────────┐
         ▼                              ▼                              ▼
┌──────────────────┐           ┌──────────────────┐           ┌──────────────────┐
│ Cognitive Engine │           │ Execution Mesh   │           │ Perception Layer │
│ • World Model    │           │ • Task Planner   │           │ • Vision / OCR   │
│ • Context Mgr    │           │ • Safe Verifier  │           │ • Browser CDP    │
│ • Intent Arbiter │           │ • Skill Dispatch │           │ • Voice/ASR/TTS  │
└──────────────────┘           └──────────────────┘           └──────────────────┘
         │                              │                              │
         └──────────────────────────────┼──────────────────────────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────┐
                         │    Unified Client & API     │
                         │   (FastAPI + WebSockets)    │
                         └─────────────────────────────┘
```

---

## 🚀 Key Capability Domains (1–50 Baseline)

1. **System & Desktop Control**: Application launching, process management, file inspection, and shell automation.
2. **Web & Browser Automation**: Headless and visible Chromium navigation, form interaction, content scraping via CDP.
3. **Personal Search & Information**: Multi-engine web search (Tavily/Brave), live knowledge retrieval, and fact verification.
4. **Communication & Collaboration**: Local email drafting, messaging automation, and contact management.
5. **Productivity & Scheduling**: Calendar appointment scheduling, task tracking, and proactive notifications.
6. **Data Science & Analytics**: Code execution sandbox, data manipulation, and report compilation.
7. **Security & Guardrails**: Path containment, destructive command interception, and secret isolation.

---

## 📁 Repository Structure

```
JARVIS/
├── agents/             # Specialized autonomous agents (communication, search, scheduler, etc.)
├── capabilities/       # Capability contract providers (realtime, voice, developer, system)
├── client/             # Unified web interface (HTML/JS/CSS client)
├── cognitive/          # Cognitive architecture, world model, and hierarchical routing
│   └── routing/        # ML-based domain and capability classifiers
├── config/             # Agent registries, system configurations, and intent schemas
├── data/               # Vector knowledge base and synthetic training datasets
├── docs/               # Architecture specs, capability matrices, and audit reports
├── llm/                # Local LLM integration (Ollama client, AI router, model prompts)
├── models/             # Serialized routing models and wake-word definitions
├── orchestrator/       # Core execution loop, planner, verifier, and parameter extractor
├── perception/         # Screen inspection, camera input, and sensor processing
├── safety/             # Policy kernel, guardrails, and access control
├── scripts/            # Training scripts, system monitors, and verification suites
├── server/             # FastAPI backend server and WebSocket communication hub
├── skills/             # Modular skill libraries (web, system, media, communication)
├── tests/              # Comprehensive test suites covering all 50 capabilities
└── voice/              # Piper TTS synthesis and ASR voice pipeline
```

---

## 🛠️ Getting Started

### Prerequisites
- **Python**: 3.11 or 3.12 (64-bit recommended)
- **Ollama**: Running locally with your preferred LLM (e.g. `llama3.2`, `mistral`, or `qwen2.5`)
- **System**: Windows 10/11 or Linux

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/aniket-chate/jarvis.git
   cd jarvis
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate   # Windows
   # source .venv/bin/activate # Linux/macOS
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment:**
   Copy `.env.example` to `.env` and fill in your optional API keys (Tavily, Google Cloud, Tailscale, etc.):
   ```bash
   cp .env.example .env
   ```

5. **Start JARVIS Server:**
   ```bash
   python -m uvicorn server.app:app --host 127.0.0.1 --port 8000 --reload
   ```

6. **Access the Unified Interface:**
   Open `http://localhost:8000` in your web browser.

---

## 🧪 Testing & Verification

JARVIS includes a rigorous test suite validating the entire 50-capability matrix:

```bash
# Run all live scenario tests
pytest tests/test_live_server_scenarios.py -v

# Run full capability regression audit
python scripts/run_first_50_audit_full_regression.py

# Verify hierarchical classifier benchmarks
pytest tests/test_hierarchical_classifier_benchmark.py -v
```

---

## 🔒 Security & Privacy

- All sensitive keys and tokens remain exclusively in `.env` and are strictly git-ignored.
- Local-first architecture: core LLM inferences run locally through Ollama.
- High-risk operations (file deletion, process termination) require explicit confirmation through the Safety Policy Kernel.

---

## 👤 Author

**Aniket Chate**  
- GitHub: [@aniket-chate](https://github.com/aniket-chate)
