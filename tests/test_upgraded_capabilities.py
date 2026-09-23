"""Comprehensive Unit Test Suite for Upgraded JARVIS Core Capabilities (Prompt 2).

Verifies:
1. Web Skills (DuckDuckGo, Wikipedia, Open-Meteo) for 3 distinct real queries.
2. Gateway Merge: zero conflicting routes, mobile client endpoints 100% operational.
3. Windows Laptop Agent: sandboxed file read/write, blocked path traversal, allowlisted app launch.
4. Semantic RAG: 4 varied notes, zero-keyword-overlap semantic query, grounded LLM response.
"""

import os
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from config.settings import settings, PROJECT_ROOT
from skills.web_skills import duckduckgo_skill, wikipedia_skill, weather_skill
from agents.weather_agent import weather_agent
from agents.wikipedia_agent import wikipedia_agent
from server.app import app
from agents.file_document_agent import FileDocumentAgent, WORKSPACE_DIR
from agents.system_control_agent import system_control_agent, ALLOWLISTED_DESKTOP_APPS
from agents.personal_knowledge_base import PersonalKnowledgeBase
from agents.semantic_rag import LocalVectorStore
from agents.core_llm_agent import core_llm_agent


# =========================================================================
# 1. Web Skills: DuckDuckGo, Wikipedia, Weather
# =========================================================================
def test_1_web_skills_three_varied_queries():
    """Verifies real results for three different, varied queries across web skills."""
    # Query 1: DuckDuckGo Search
    q1 = "Python programming language overview"
    ddg_res = duckduckgo_skill.search(query=q1, max_results=3)
    assert ddg_res["success"] is True, f"DuckDuckGo search failed: {ddg_res.get('error')}"
    assert len(ddg_res["results"]) > 0, "DuckDuckGo returned empty results"
    assert any("python" in r["title"].lower() or "python" in r["content"].lower() for r in ddg_res["results"]), \
        "DuckDuckGo results did not mention Python"

    # Query 2: Wikipedia Summary
    q2 = "Ada Lovelace"
    wiki_res = wikipedia_agent.lookup(query=q2)
    assert wiki_res["success"] is True, f"Wikipedia lookup failed: {wiki_res.get('error')}"
    assert "ada lovelace" in wiki_res["title"].lower(), f"Unexpected Wikipedia title: {wiki_res.get('title')}"
    assert len(wiki_res.get("summary", "")) > 40, "Wikipedia extract too short or empty"

    # Query 3: Open-Meteo Weather
    q3 = "Tokyo"
    weather_res = weather_agent.get_weather(location=q3)
    assert weather_res["success"] is True, f"Weather query failed: {weather_res.get('error')}"
    assert "Tokyo" in weather_res["location"] or "Tokyo" in weather_res.get("city", "")
    assert isinstance(weather_res["temperature"], (int, float))
    assert "condition" in weather_res and len(weather_res["condition"]) > 0


# =========================================================================
# 2. Gateway Merge: Route Integrity & Mobile Client Compatibility
# =========================================================================
def test_2_gateway_merge_and_mobile_compatibility():
    """Verifies no route conflicts and confirms mobile thin client endpoints work unchanged."""
    client = TestClient(app)
    auth_headers = {"X-JARVIS-Token": settings.gateway_auth_token}

    # 1. Verify zero conflicting/duplicate route paths (same path + same HTTP method)
    route_endpoints = []
    for route in app.routes:
        if hasattr(route, "path"):
            methods = getattr(route, "methods", None)
            if methods:
                for m in methods:
                    route_endpoints.append((route.path, m))
            else:
                route_endpoints.append((route.path, "MOUNT"))

    assert len(route_endpoints) == len(set(route_endpoints)), \
        f"Conflicting duplicate endpoint detected: {[ep for ep in route_endpoints if route_endpoints.count(ep) > 1]}"

    # 2. Verify new merged endpoints exist
    route_paths = [r.path for r in app.routes if hasattr(r, "path")]
    assert "/api/skills" in route_paths
    assert "/api/memory" in route_paths

    # 3. Verify original mobile client endpoints work unchanged
    # Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    # Device list (mobile client startup call)
    res_devices = client.get("/api/devices", headers=auth_headers)
    assert res_devices.status_code == 200
    assert "devices" in res_devices.json()

    # Chat endpoint (mobile client text interaction)
    res_chat = client.post(
        "/api/chat",
        headers=auth_headers,
        json={"query": "System status check", "persona": "Jarvis", "device_id": "mobile_phone_test"}
    )
    assert res_chat.status_code == 200
    assert res_chat.json()["status"] == "ok"
    assert len(res_chat.json()["response"]) > 0

    # Skills introspection (new merged endpoint)
    res_skills = client.get("/api/skills", headers=auth_headers)
    assert res_skills.status_code == 200
    skills_data = res_skills.json()
    assert skills_data["total_count"] >= 14
    skill_ids = [s["id"] for s in skills_data["skills"]]
    assert "weather_agent" in skill_ids
    assert "wikipedia_agent" in skill_ids

    # Memory inspection (new merged endpoint)
    res_mem = client.get("/api/memory", headers=auth_headers)
    assert res_mem.status_code == 200
    assert "memories" in res_mem.json()


# =========================================================================
# 3. Windows Laptop Agent: Sandbox, Traversal Block, App Allowlist
# =========================================================================
def test_3_windows_laptop_agent_sandbox_and_app_allowlist(tmp_path):
    """Verifies sandboxed file operations, strict traversal block, and allowlisted app launching."""
    test_sandbox = tmp_path / "sandbox"
    test_sandbox.mkdir()
    agent = FileDocumentAgent(sandbox_root=test_sandbox)

    # 1. Real write inside sandbox
    write_res = agent.write_file("project_notes.txt", "Alpha test data content 12345", user_confirmed=True)
    assert write_res["success"] is True
    assert (test_sandbox / "project_notes.txt").exists()

    # 2. Real read inside sandbox
    read_res = agent.read_file("project_notes.txt")
    assert read_res["success"] is True
    assert "Alpha test data content 12345" in read_res["content"]

    # 3. Path traversal outside sandbox MUST be strictly blocked
    traversal_paths = [
        "../../outside.txt",
        "..\\..\\windows\\system32\\cmd.exe",
        "C:\\Windows\\win.ini",
        "nested/../../../../etc/passwd"
    ]
    for bad_path in traversal_paths:
        with pytest.raises(PermissionError):
            agent._resolve_safe_path(bad_path)

    # 4. Forbidden credential files MUST be strictly blocked
    forbidden_files = ["secrets.env", "private.pem", "id_rsa", "ssl.key"]
    for secret_file in forbidden_files:
        with pytest.raises(PermissionError):
            agent._resolve_safe_path(secret_file)

    # 5. Allowlisted Desktop App Launch
    allowed_app = "notepad"
    launch_res = system_control_agent.launch_app(app_name=allowed_app, user_confirmed=True)
    assert launch_res["success"] is True
    assert launch_res["status"] == "launched"

    # 6. Unlisted App Launch MUST be rejected
    unlisted_app = "malicious_ransomware.exe"
    reject_res = system_control_agent.launch_app(app_name=unlisted_app, user_confirmed=True)
    assert reject_res["success"] is False
    assert "not in the allowlist" in reject_res["error"]


# =========================================================================
# 4. REBUILT RAG: Local Semantic Embeddings & Cosine Retrieval
# =========================================================================
def test_4_semantic_rag_retrieval_and_llm_grounding(tmp_path):
    """Stores 4 varied notes, executes zero-keyword-overlap query, and verifies grounded LLM output."""
    kb_dir = tmp_path / "kb_storage"
    kb_dir.mkdir()
    vec_db = tmp_path / "test_vec.db"
    vstore = LocalVectorStore(db_path=vec_db)
    pkb = PersonalKnowledgeBase(storage_dir=kb_dir, vector_store=vstore)

    # Store 4 varied, realistic knowledge notes
    n1 = pkb.add_note(
        title="Domestic Animals Note",
        content="The canine was barking loudly throughout the morning in the backyard garden.",
        tags=["pets", "animals"]
    )
    n2 = pkb.add_note(
        title="Modern Physics Research",
        content="Quantum entanglement enables instantaneous correlation between paired photons.",
        tags=["physics", "science"]
    )
    n3 = pkb.add_note(
        title="Internal Team Operations",
        content="Our weekly sync meeting has been moved to Friday afternoon in room 302.",
        tags=["team", "schedule"]
    )
    n4 = pkb.add_note(
        title="Mediterranean Cooking",
        content="The culinary recipe calls for roasting fresh garlic and rosemary in extra virgin olive oil.",
        tags=["food", "cooking"]
    )

    # Semantic Query with ZERO exact keyword overlap with Note 1
    # Query words: "pet", "making", "noise", "outside"
    # Note words: "canine", "barking", "loudly", "garden"
    semantic_query = "What pet was making loud noise outside?"

    # Execute semantic search
    matches = pkb.semantic_search(query=semantic_query, top_k=2)
    assert len(matches) > 0, "Semantic search returned no results"

    top_match = matches[0]
    assert top_match["doc_id"] == n1["note_id"], \
        f"Semantic search failed to rank Note 1 highest. Top match: {top_match['title']} (score: {top_match['score']})"
    assert top_match["score"] > 0.30, f"Expected strong semantic similarity, got {top_match['score']}"

    # Verify LLM generation uses the retrieved note
    gen_result = core_llm_agent.generate_with_metadata(
        prompt=semantic_query,
        persona_name="Jarvis",
        enable_rag=True,
        knowledge_base=pkb
    )
    assert gen_result.get("rag_applied") is True, "RAG was not applied in generation"
    assert len(gen_result.get("retrieved_notes", [])) > 0, "No notes retrieved for generation context"

    response_text = gen_result["response"].lower()
    # Response must incorporate the retrieved fact (canine / barking / garden)
    assert any(term in response_text for term in ["canine", "barking", "garden", "dog"]), \
        f"LLM response did not incorporate retrieved knowledge: {gen_result['response']}"
