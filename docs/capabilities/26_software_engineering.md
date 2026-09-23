# Capability 26: Software Engineering

**Capability ID:** `26_software_engineering`  
**Classification:** `EXISTING`  
**Safety Classification:** `MODIFYING`  
**Domain:** `code`  
**Primary Provider:** `provider.dev.git_code`  
**Fallback Provider:** `provider.llm.cloud_gemini`  

---

## 1. Capability Purpose & Scope
Provides code generation, AST understanding, static syntax analysis, unit test generation, automated bug repair, and isolated Python sandbox execution. Separates code reasoning from actual physical execution.

---

## 2. Supported Operations
- `code.generation`: Synthesizes algorithms, functions, and documentation from natural language.
- `code.sandbox_execution`: Executes Python code inside an isolated namespace with strict timeouts.
- `code.review`: Inspects source code for potential vulnerabilities, zero-division, and bugs.
- `code.dependency_analysis`: Analyzes module import graphs and missing libraries.

---

## 3. Required Context & World Model State
- **Active Code Snippet:** Captured in `WorldModel.state.last_code_snippet`.

---

## 4. Provider Implementation & Selection
- **Implementation:** `capabilities/providers/developer_provider.py` (`DeveloperTaskProvider`), backed by `agents/dev_tool_agent.py` and `agents/core_llm_agent.py`.
- **Sandbox Security:** Python execution operates in restricted dictionaries preventing arbitrary OS breakout.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 1: LOW_RISK` for sandboxed evaluation.
- **Verification Strategy:** Returncode validation, output dictionary inspection, and unit test execution.
