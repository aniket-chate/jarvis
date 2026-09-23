# JARVIS Capabilities 1–50 Boundary Analysis & Disambiguation Specification

## Executive Summary
This document specifies the capability boundaries, semantic overlaps, shared tokens, distinguishing signals, and disambiguation criteria for all 50 JARVIS capabilities. It serves as the authoritative boundary specification for the **Hierarchical Classification Engine** and **Contextual Reranker**.

---

## 1. Core Capability Boundary Taxonomies

JARVIS Capabilities 1–50 are organized into 8 high-level semantic domains:
1. `PERCEPTION_MULTIMODAL` (Capabilities 1–4, 30)
2. `MEMORY_COGNITION` (Capabilities 5–10)
3. `DESKTOP_OS_CONTROL` (Capabilities 11–17, 33–35)
4. `PRODUCTIVITY_COMMUNICATION` (Capabilities 18–21)
5. `SMART_HOME_IOT_PHYSICAL` (Capabilities 22, 45)
6. `MOBILE_ANDROID` (Capabilities 23–29)
7. `RESEARCH_KNOWLEDGE_ANALYTICS` (Capabilities 31–32, 36–38, 46–47)
8. `AGENCY_GOVERNANCE_EVOLUTION` (Capabilities 39–44, 48–50)

---

## 2. Key Overlap Areas & Disambiguation Rules

### 2.1. Web Research vs Personal Search vs Real-Time Information
- **Capabilities Involved**:
  - `Cap 31`: Multi-Source Web Research (Deep web scraping, multi-source synthesis, citations)
  - `Cap 32`: Real-Time Information Retrieval (Weather, stocks, live sports, currency exchange)
  - `Cap 8`: Cross-Session Semantic Search (Searching personal episodic memory, past conversations)
  - `Cap 37`: Knowledge Base Synthesis (Internal documents, offline PDF/markdown indexed archives)

| Attribute | Cap 31 (Web Research) | Cap 32 (Real-Time Info) | Cap 8 (Personal Search) | Cap 37 (Knowledge Synthesis) |
|---|---|---|---|---|
| **Primary Intent** | Deep topic investigation, synthesis | Live, perishable factual updates | Past conversational/user history | Internal company/user documentation |
| **Distinguishing Signals** | "investigate", "compare technologies", "search web for articles on" | "current price of", "weather today", "live score", "convert USD to INR" | "what did I say about", "find our conversation on", "last week I mentioned" | "summarize local doc", "search notes", "synthesize PDF handbook" |
| **Shared Signals** | "search", "find information", "lookup", "what is" | "what is", "current", "latest" | "find", "search", "where is" | "document", "notes", "information" |
| **Disambiguation Rule** | If query references user's past actions or "I/we said", route to `Cap 8`. If query asks for volatile/live state (weather, stock), route to `Cap 32`. If query asks for local knowledge vault/files, route to `Cap 37`. Otherwise route to `Cap 31`. |

### 2.2. Desktop Control vs Application Intelligence
- **Capabilities Involved**:
  - `Cap 11`: Direct OS Application Control (Launch, terminate, focus windows, kill process)
  - `Cap 12`: Context-Aware Window Management (Tile, snap, maximize, monitor arrangements)
  - `Cap 16`: Specialized Application Intelligence (In-app automation, document editing, spreadsheet formulas)
  - `Cap 33`: Headless Browser Automation (DOM manipulation, web form filling, web scraping)

| Attribute | Cap 11 (OS App Control) | Cap 12 (Window Mgmt) | Cap 16 (App Intelligence) | Cap 33 (Headless Browser) |
|---|---|---|---|---|
| **Primary Intent** | Process lifecycle & focus | Window geometry & layout | High-level internal app workflow | Web DOM interactions & web RPA |
| **Distinguishing Signals** | "open chrome", "launch vs code", "kill process pid" | "tile side by side", "minimize all", "move to second monitor" | "add row to excel spreadsheet", "format docx heading", "render markdown in app" | "navigate to portal and submit login form", "click css selector" |
| **Disambiguation Rule** | If action specifies window layout or screen position $\rightarrow$ `Cap 12`. If action requires in-browser DOM interaction $\rightarrow$ `Cap 33`. If action manipulates in-app data models (spreadsheets, docs) $\rightarrow$ `Cap 16`. If simply launching or closing an executable $\rightarrow$ `Cap 11`. |

### 2.3. Memory vs Knowledge Management
- **Capabilities Involved**:
  - `Cap 5`: Working Memory (Immediate active context, scratchpad)
  - `Cap 6`: Short-Term Context Tracking (Recent turns in ongoing dialogue)
  - `Cap 7`: Long-Term Episodic & Fact Storage (Permanent user preferences, biographical facts)
  - `Cap 37`: Knowledge Base Synthesis (Curated knowledge corpora, manuals, technical documents)

| Attribute | Cap 5/6 (Working Context) | Cap 7 (Long-Term Episodic) | Cap 37 (Knowledge Vault) |
|---|---|---|---|
| **Scope** | Current turn / session execution | User facts, identity, lifelong memory | External texts, books, policies, code repos |
| **Signals** | "as I just said", "the variable above", "step 2 from before" | "remember that my car is a Honda", "store my preferred editor" | "index this folder of PDFs", "search corporate policy" |
| **Disambiguation Rule** | Personal user preferences and autobiographical facts $\rightarrow$ `Cap 7`. Transformed multi-file documentation repositories $\rightarrow$ `Cap 37`. In-flight multi-step reasoning context $\rightarrow$ `Cap 5`. |

### 2.4. Calendar vs Productivity vs Autonomous Agency
- **Capabilities Involved**:
  - `Cap 18`: Calendar & Scheduling (Events, meetings, reminders, conflict resolution)
  - `Cap 19`: Communication Drafting (Email drafts, message composition)
  - `Cap 39`: Autonomous Goal Decomposition (Hierarchical breakdown of complex goals into subtasks)
  - `Cap 41`: Multi-Step Task Execution (Automated execution of multi-step task DAG)

| Attribute | Cap 18 (Calendar) | Cap 19 (Comms Drafting) | Cap 39 (Goal Decomposition) | Cap 41 (Autonomous DAG Execution) |
|---|---|---|---|---|
| **Distinguishing Signals** | "schedule meeting at 3pm", "reschedule dentist", "check calendar" | "draft email to team", "compose message to Aniket", "reply to thread" | "plan our product launch", "break down project into steps" | "execute tasks in sequence", "run workflow step by step" |
| **Ambiguity Handling** | "Plan a meeting with team" $\rightarrow$ Multi-intent: `Cap 18` (Calendar) + `Cap 19` (Notification email). Multi-intent planner decomposes into sequence. |

### 2.5. Data Science vs Simulation & Prediction
- **Capabilities Involved**:
  - `Cap 46`: Data Science & Analytics (Statistical aggregation, data cleaning, regression, correlation)
  - `Cap 47`: Simulation & Prediction (Monte Carlo, dynamical systems, ODEs, forecast projection)

| Attribute | Cap 46 (Data Science & Analytics) | Cap 47 (Simulation & Prediction) |
|---|---|---|
| **Core Technique** | Descriptive & inferential statistics, clustering, correlation matrix | Numerical simulation, trajectory modeling, Monte Carlo uncertainty bounds |
| **Distinguishing Signals** | "calculate mean and variance", "run correlation matrix on sales.csv", "find outliers" | "simulate 10,000 Monte Carlo runs", "predict trajectory under 10% drift", "solve differential equation" |
| **Disambiguation Rule** | Retrospective data analysis on observed datasets $\rightarrow$ `Cap 46`. Stochastic forward forecasting or parametric physics/agent simulation $\rightarrow$ `Cap 47`. |

### 2.6. Verification vs Diagnostics vs Security
- **Capabilities Involved**:
  - `Cap 48`: Security & Identity (Authentication, tokens, policy access control, sandbox boundary)
  - `Cap 49`: Verification & Self-Diagnostics (Subsystem probes, resource health, component self-test)
  - `Cap 50`: Capability Evolution (Self-improvement proposals, contract generation, sandboxed test validation)

| Attribute | Cap 48 (Security & Identity) | Cap 49 (Verification & Self-Diagnostics) | Cap 50 (Capability Evolution) |
|---|---|---|---|
| **Signals** | "verify token", "check permission for admin", "enforce policy boundary" | "run system self test", "check subsystem health", "diagnose memory leak" | "propose optimization for cap 12", "generate new capability contract" |
| **Disambiguation Rule** | Identity checks, authorization, cryptographic verification $\rightarrow$ `Cap 48`. Internal system health, heartbeats, CPU/memory telemetry $\rightarrow$ `Cap 49`. Architectural contract expansion and evolutionary proposals $\rightarrow$ `Cap 50`. |

---

## 3. Multi-Intent Routing Strategies

When user requests combine multiple actions:
1. **Classifier Candidate Generation**: Return top-K candidates across domains.
2. **Multi-Intent Decomposition**:
   - If user input contains sequential connectives ("and then", "after that", "also"):
     - Example: *"Summarize paper.pdf and then email the notes to Alex"*
     - Decomposed into:
       1. Sub-task 1: `Cap 37` (Knowledge Base Synthesis)
       2. Sub-task 2: `Cap 19` (Communication Drafting)
3. **DAG Orchestration**:
   - Routed to `Cap 39` (Autonomous Goal Decomposition) and `Cap 41` (Multi-Step Task Execution Engine).

---

## 4. Contextual Disambiguation Requirements

The Reranker utilizes:
1. **Active Foreground Application** (from `WorldModel.active_app`):
   - If active app is "Chrome" and request is "search python docs" $\rightarrow$ prioritize `Cap 33` or `Cap 31`.
   - If active app is "Excel" and request is "calculate variance" $\rightarrow$ prioritize `Cap 16` or `Cap 46`.
2. **Conversation History** (from `UnifiedMemory` Tier 1 & 2):
   - If the previous turn asked "What is quantum computing?", and current turn is "Tell me more about it" $\rightarrow$ `Cap 31` (Multi-Source Research) rather than unknown intent.
3. **Temporal Markers**:
   - "Right now", "live", "current price" $\rightarrow$ prioritize `Cap 32`.
   - "Historically", "yesterday's data", "dataset analysis" $\rightarrow$ prioritize `Cap 46`.
