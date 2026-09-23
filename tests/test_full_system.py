"""Full-System Re-Verification Pytest Suite (Prompt 3).

Validates end-to-end integration across Prompts 1, 2, and 3:
1. Native Android Client & Mobile PWA Dual Simultaneous Connectivity & Handshake.
2. Live Web Search with External Knowledge (DDG / Wikipedia / Weather).
3. Semantic RAG Vector Retrieval & Fact-Grounded LLM Generation.
4. Non-Bypassable Two-Independent-Gates Permission Verification.
5. Cross-Device Media Casting Dispatch.
"""

import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from config.settings import settings
from server.app import app
from skills.web_skills import wikipedia_skill, weather_skill
from agents.wikipedia_agent import wikipedia_agent
from agents.weather_agent import weather_agent
from agents.personal_knowledge_base import PersonalKnowledgeBase
from agents.semantic_rag import LocalVectorStore
from agents.core_llm_agent import core_llm_agent
from agents.permission_checks import permission_gate, PermissionState
from agents.cast_agent import cast_agent


@pytest.fixture
def test_client():
    return TestClient(app)


def test_dual_client_simultaneous_connectivity(test_client):
    auth_token = settings.gateway_auth_token

    # 1. Android REST health check
    res_health = test_client.get("/api/v1/health")
    assert res_health.status_code == 200 and res_health.json()["status"] == "healthy"

    # 2. Android device registration
    res_reg = test_client.post(
        "/api/v1/devices/register",
        headers={"X-JARVIS-Token": auth_token},
        json={
            "device_id": "vivo_v29_native",
            "name": "Aniket's Vivo V29",
            "client_type": "phone",
            "capabilities": ["microphone", "speaker", "accessibility"]
        }
    )
    assert res_reg.status_code == 200

    # 3. Android device heartbeat
    res_hb = test_client.post(
        "/api/v1/devices/vivo_v29_native/heartbeat",
        headers={"X-JARVIS-Token": auth_token}
    )
    assert res_hb.status_code == 200 and res_hb.json()["status"] == "alive"

    # 4. Simultaneous WebSocket duplex test
    with test_client.websocket_connect(f"/api/v1/ws?token={auth_token}&device_id=vivo_v29_native") as ws_android, \
         test_client.websocket_connect(f"/ws?token={auth_token}&device_id=pwa_mobile_chrome") as ws_pwa:

        # Handshakes
        w_android = ws_android.receive_json()
        assert w_android["type"] == "welcome"
        w_pwa = ws_pwa.receive_json()
        assert w_pwa["type"] == "welcome"

        # Android Auth
        ws_android.send_json({
            "type": "auth",
            "token": auth_token,
            "user_id": "default_user",
            "device_id": "vivo_v29_native",
            "device_name": "Aniket's Vivo V29",
            "client_type": "phone"
        })
        ack = ws_android.receive_json()
        assert ack["type"] == "auth_success"

        # PWA Register
        ws_pwa.send_json({
            "type": "register",
            "device_id": "pwa_mobile_chrome",
            "name": "Mobile Web PWA",
            "client_type": "phone"
        })
        reg_ack = ws_pwa.receive_json()
        assert reg_ack["type"] == "registered"

        # Android command execution & payload.text schema verification
        ws_android.send_json({
            "type": "chat",
            "message": "System diagnostics status check",
            "persona": "Jarvis"
        })
        p1 = ws_android.receive_json()
        assert p1["type"] == "task_progress"
        resp_android = ws_android.receive_json()
        assert resp_android["type"] == "chat_response"
        assert "payload" in resp_android and len(resp_android["payload"]["text"]) > 0

        # PWA command execution & top-level response schema verification
        ws_pwa.send_json({
            "type": "chat",
            "command": "Confirm mobile mesh connectivity",
            "persona": "Jarvis"
        })
        p2 = ws_pwa.receive_json()
        assert p2["type"] == "task_progress"
        resp_pwa = ws_pwa.receive_json()
        assert resp_pwa["type"] == "chat_response"
        assert "response" in resp_pwa and len(resp_pwa["response"]) > 0


def test_scenario_1_live_web_search():
    query = "Alan Turing"
    wiki_res = wikipedia_agent.lookup(query)
    assert wiki_res["success"] is True
    assert "turing" in wiki_res["title"].lower()
    assert len(wiki_res["summary"]) > 50

    weather_res = weather_agent.get_weather("London")
    assert weather_res["success"] is True
    assert isinstance(weather_res["temperature"], (int, float))


def test_scenario_2_semantic_rag_recall():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        storage = Path(tmp_dir) / "notes"
        storage.mkdir()
        vdb = Path(tmp_dir) / "rag_vectors.db"
        vstore = LocalVectorStore(db_path=vdb)
        pkb = PersonalKnowledgeBase(storage_dir=storage, vector_store=vstore)

        n1 = pkb.add_note(
            "Project Titan Energy Specs",
            "The next-generation carbon battery uses solid-state electrolyte with 850 Wh/L volumetric density.",
            tags=["engineering", "battery"]
        )
        pkb.add_note(
            "Kyoto Travel Itinerary",
            "Flight arrives at Kansai International on November 12; hotel reservation is at Ryokan Gion.",
            tags=["travel"]
        )
        pkb.add_note(
            "Executive Sync Agenda",
            "Thursday morning keynote by Dr. Aris Thorne in the Grand Ballroom on quantum algorithms.",
            tags=["schedule"]
        )

        semantic_query = "What is the energy storage capacity of the portable power cell?"
        matches = pkb.semantic_search(semantic_query, top_k=2)
        assert len(matches) > 0
        top = matches[0]
        assert top["doc_id"] == n1["note_id"]
        assert top["score"] > 0.40

        gen_res = core_llm_agent.generate_with_metadata(
            prompt=semantic_query,
            persona_name="Jarvis",
            enable_rag=True,
            knowledge_base=pkb
        )
        assert gen_res.get("rag_applied") is True
        resp_lower = gen_res["response"].lower()
        assert any(term in resp_lower for term in ["850", "battery", "titan", "solid-state"])


def test_scenario_3_sensitive_action_permission():
    dec_unconfirmed = permission_gate.check_permission(
        domain="filesystem",
        action="delete_file",
        details={"path": "D:/assignment/JARVIS/workspace/prod_release.key"},
        confirmed=False
    )
    assert dec_unconfirmed.allowed is False

    dec_confirmed = permission_gate.check_permission(
        domain="filesystem",
        action="delete_file",
        details={"path": "D:/assignment/JARVIS/workspace/prod_release.key"},
        confirmed=True
    )
    assert dec_confirmed.allowed is True


def test_scenario_4_media_cast_command():
    from gateway.registry import gateway_registry
    target_device = "Living Room TV"
    gateway_registry.register_device(
        device_id="living_room_tv_client",
        name=target_device,
        client_type="tv",
        ip_address="192.168.1.150"
    )
    stream_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
    title = "Beethoven Symphony No. 5"

    res = cast_agent.cast_to_device(
        device_name=target_device,
        media_url=stream_url,
        title=title
    )
    assert res["success"] is True
    assert res["device"] == target_device
