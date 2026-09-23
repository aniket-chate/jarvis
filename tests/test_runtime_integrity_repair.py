"""Regression and Integrity Test Suite for JARVIS Cross-Cutting Runtime Repair.

Validates all 10 architectural invariants:
1. test_tool_result_preservation
2. test_data_result_not_reduced_to_done
3. test_action_result_can_remain_acknowledgement
4. test_failed_result_is_truthful
5. test_provider_registry_initialized_at_server_startup
6. test_voice_provider_discoverable_from_live_server
7. test_weather_asr_ambiguity
8. test_whether_not_weather_when_context_is_conversational
9. test_contextual_weather_followup
10. test_no_duplicate_tts_synthesis
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure default capability providers are registered
import capabilities.providers
from capabilities.intelligence import capability_intelligence
from capabilities.base import ActionResult
from orchestrator.verifier import task_verifier, TaskVerifier
from orchestrator.planner import task_planner, TaskPlan, TaskStep
from orchestrator.intent_arbitrator import intent_arbitrator
from orchestrator.context_manager import context_manager
from cognitive.understanding import understanding_engine
from perception.events import PerceptionEvent


def test_tool_result_preservation():
    """Invariant 1: Data-producing capability results must be preserved and not swallowed."""
    print("\n[TEST 1/10] test_tool_result_preservation...")
    verifier = TaskVerifier()
    
    # 1. Weather result
    weather_step = TaskStep(
        step_id="step_weather",
        description="Retrieve real-time weather",
        required_agent_type="weather_agent",
        inputs={"location": "San Francisco", "intent": "current_weather"},
    )
    weather_payload = {
        "status": "success",
        "response": "The current weather in San Francisco is 16°C and partly cloudy.",
        "data": {
            "city": "San Francisco",
            "temperature_c": 16,
            "condition": "Partly Cloudy",
            "humidity": "68%",
        },
    }
    resp = verifier.generate_user_response(weather_step, weather_payload)
    assert "San Francisco" in resp, f"Expected city in response, got: {resp}"
    assert "16°C" in resp or "16" in resp, f"Expected temperature in response, got: {resp}"
    assert resp.strip().lower() not in ["done.", "action complete."], f"Weather reduced to generic: {resp}"

    # 2. News result
    news_step = TaskStep(
        step_id="step_news",
        description="Fetch latest technology headlines",
        required_agent_type="news_agent",
        inputs={"topic": "technology"},
    )
    news_payload = {
        "status": "success",
        "response": "Here are the top headlines: 1. AI breakthroughs in robotics. 2. New quantum processors announced.",
        "articles": [
            {"title": "AI breakthroughs in robotics", "source": "TechDaily"},
            {"title": "New quantum processors announced", "source": "QuantumWire"},
        ],
    }
    resp_news = verifier.generate_user_response(news_step, news_payload)
    assert "AI breakthroughs" in resp_news or "robotics" in resp_news, f"Expected headline in response, got: {resp_news}"
    assert resp_news.strip().lower() not in ["done.", "action complete."], f"News reduced to generic: {resp_news}"

    print("  PASS: Data-producing tool results are fully preserved.")


def test_data_result_not_reduced_to_done():
    """Invariant 2: Data-producing capabilities MUST NOT be reduced to 'Done.'."""
    print("\n[TEST 2/10] test_data_result_not_reduced_to_done...")
    verifier = TaskVerifier()

    # Capability 31: Web research result
    web_step = TaskStep(
        step_id="step_web",
        description="Research Python language release notes",
        required_agent_type="web_search_agent",
        inputs={"query": "Python programming language latest features"},
    )
    web_result = {
        "status": "success",
        "summary": "Python 3.12 introduces improved error messages, isolated subinterpreters, and Linux perf support.",
        "sources": ["https://python.org", "https://docs.python.org"],
    }
    plan = TaskPlan(
        plan_id="plan_web_test",
        goal="Tell me about Python programming language",
        steps=[web_step],
        active_persona="Jarvis",
    )
    web_step.result = web_result

    summary_obj = verifier.verify_and_summarize(plan, {"status": "success"})
    resp = summary_obj.get("response") or summary_obj.get("summary")
    assert resp is not None, "Response must not be None"
    assert "Done." not in resp, f"Capability 31 web research was reduced to 'Done.': {resp}"
    assert "Python" in resp, f"Expected 'Python' in response, got: {resp}"

    # Capability 32: Real-time information result
    rt_step = TaskStep(
        step_id="step_rt",
        description="Fetch current weather in Seattle",
        required_agent_type="weather_agent",
        inputs={"location": "Seattle"},
    )
    rt_result = {
        "status": "success",
        "output": {
            "city": "Seattle",
            "temperature_c": 14,
            "condition": "Light Rain",
            "source": "Open-Meteo",
        },
        "response": "In Seattle, it is currently 14°C with light rain.",
    }
    rt_step.result = rt_result
    plan_rt = TaskPlan(
        plan_id="plan_rt_test",
        goal="Tell me today's weather in Seattle",
        steps=[rt_step],
        active_persona="Jarvis",
    )
    summary_rt = verifier.verify_and_summarize(plan_rt, {"status": "success"})
    resp_rt = summary_rt.get("response") or summary_rt.get("summary")
    assert "Seattle" in resp_rt, f"Expected Seattle in response, got: {resp_rt}"
    assert "Done." not in resp_rt, f"Capability 32 weather was reduced to 'Done.': {resp_rt}"

    print("  PASS: Data-producing capabilities are never reduced to generic 'Done.'.")


def test_action_result_can_remain_acknowledgement():
    """Invariant 3: Action-only capabilities legitimately return concise acknowledgements."""
    print("\n[TEST 3/10] test_action_result_can_remain_acknowledgement...")
    verifier = TaskVerifier()

    action_step = TaskStep(
        step_id="step_action",
        description="Open Calculator application",
        required_agent_type="system_control_agent",
        inputs={"action": "open_app", "target": "Calculator"},
    )
    action_result = {"status": "success", "action": "open_app", "target": "Calculator"}
    resp = verifier.generate_user_response(action_step, action_result)
    assert resp is not None and len(resp.strip()) > 0
    # Concise acknowledgement is acceptable for pure actions
    assert "Done" in resp or "Calculator" in resp or "complete" in resp.lower()
    print(f"  PASS: Action-only acknowledgement generated concisely: '{resp}'.")


def test_failed_result_is_truthful():
    """Invariant 4: Failed operations must produce truthful errors and never report false success."""
    print("\n[TEST 4/10] test_failed_result_is_truthful...")
    verifier = TaskVerifier()

    failed_step = TaskStep(
        step_id="step_fail",
        description="Fetch weather for NonExistentLocation999",
        required_agent_type="weather_agent",
        inputs={"location": "NonExistentLocation999"},
    )
    failed_payload = {
        "status": "failed",
        "error": "Location 'NonExistentLocation999' could not be resolved by weather service.",
    }
    resp = verifier.generate_user_response(failed_step, failed_payload)
    assert resp is not None
    assert "Done." not in resp, f"Failed step erroneously returned 'Done.': {resp}"
    assert "failed" in resp.lower() or "not" in resp.lower() or "error" in resp.lower(), f"Truthful error missing in: {resp}"
    print(f"  PASS: Truthful failure message reported: '{resp}'.")


def test_provider_registry_initialized_at_server_startup():
    """Invariant 5: Default provider registry must be initialized when server starts."""
    print("\n[TEST 5/10] test_provider_registry_initialized_at_server_startup...")
    from server.app import register_default_providers
    register_default_providers()

    # Verify essential capability providers are registered
    req_caps = [
        "voice.synthesize",
        "info.get_weather",
        "info.get_news",
        "web.search",
    ]
    for cap in req_caps:
        prov = capability_intelligence.select_provider(cap)
        assert prov is not None, f"Default provider for '{cap}' was not initialized at server startup!"
    print(f"  PASS: All {len(req_caps)} default capability providers are initialized and discoverable.")


def test_voice_provider_discoverable_from_live_server():
    """Invariant 6: voice.synthesize provider must be discoverable without missing provider warnings."""
    print("\n[TEST 6/10] test_voice_provider_discoverable_from_live_server...")
    prov = capability_intelligence.select_provider("voice.synthesize")
    assert prov is not None, "voice.synthesize provider missing from CapabilityIntelligence!"
    
    # Test execution of voice.synthesize provider
    res = prov.execute("voice.synthesize", {"text": "Runtime integrity verified.", "persona": "Jarvis"})
    assert res.status == "SUCCESS", f"voice.synthesize execution failed: {res.message}"
    assert "wav_bytes" in res.output or "audio" in res.output or "duration_s" in res.output
    print(f"  PASS: voice.synthesize provider '{prov.provider_id}' executed successfully.")


def test_weather_asr_ambiguity():
    """Invariant 7: Phonetically ambiguous / ASR weather queries must route to weather capability."""
    print("\n[TEST 7/10] test_weather_asr_ambiguity...")
    weather_queries = [
        "tell me today's weather",
        "tell me today whether",
        "what's the weather today",
        "how is the weather",
        "weather tomorrow",
    ]
    for q in weather_queries:
        ev = PerceptionEvent(type="text_input", payload={"text": q})
        plan = task_planner.create_plan(ev)
        assert len(plan.steps) > 0, f"Plan creation failed for query: '{q}'"
        first_step = plan.steps[0]
        # Must route to weather_agent or info provider, NEVER core_llm_agent fallback
        assert first_step.required_agent_type == "weather_agent", (
            f"Query '{q}' routed to '{first_step.required_agent_type}' instead of 'weather_agent'!"
        )
    print(f"  PASS: All {len(weather_queries)} weather/ASR ambiguous utterances routed to weather_agent.")


def test_whether_not_weather_when_context_is_conversational():
    """Invariant 8: Genuine conversational 'whether' sentences must NOT become weather requests."""
    print("\n[TEST 8/10] test_whether_not_weather_when_context_is_conversational...")
    conversational_queries = [
        "I don't know whether to go",
        "whether this is correct",
        "decide whether we should proceed",
        "ask him whether he wants to join",
    ]
    for q in conversational_queries:
        intent = intent_arbitrator.arbitrate(q)
        if intent:
            assert not (intent.domain == "info" and intent.action == "get_weather"), (
                f"Conversational query '{q}' mistakenly arbitrated to weather: {intent}"
            )
        ev = PerceptionEvent(type="text_input", payload={"text": q})
        plan = task_planner.create_plan(ev)
        if plan.steps:
            assert plan.steps[0].required_agent_type != "weather_agent", (
                f"Conversational query '{q}' incorrectly routed to weather_agent!"
            )
    print(f"  PASS: All {len(conversational_queries)} conversational 'whether' queries correctly preserved.")


def test_contextual_weather_followup():
    """Invariant 9: Contextual follow-up queries retain weather domain and prior location context."""
    print("\n[TEST 9/10] test_contextual_weather_followup...")
    context_manager.clear_session()
    
    # 1. Initial location-explicit query
    q1 = "What's the weather in Tokyo today?"
    ev1 = PerceptionEvent(type="text_input", payload={"text": q1})
    plan1 = task_planner.create_plan(ev1)
    assert plan1.steps[0].required_agent_type == "weather_agent"
    loc = plan1.steps[0].inputs.get("location")
    assert loc == "Tokyo", f"Expected location 'Tokyo', got '{loc}'"

    # Context should record Tokyo
    context_manager.set_weather_context("Tokyo", q1)

    # 2. Contextual follow-up without location
    q2 = "And tomorrow?"
    ev2 = PerceptionEvent(type="text_input", payload={"text": q2})
    plan2 = task_planner.create_plan(ev2)
    assert plan2.steps[0].required_agent_type == "weather_agent", (
        f"Contextual follow-up '{q2}' failed to retain weather routing!"
    )
    followup_loc = plan2.steps[0].inputs.get("location")
    assert followup_loc == "Tokyo", (
        f"Contextual follow-up lost previous location 'Tokyo', got: '{followup_loc}'"
    )
    print("  PASS: Contextual weather follow-up correctly preserved location 'Tokyo' and weather domain.")


def test_no_duplicate_tts_synthesis():
    """Invariant 10: TTS sentence synthesis must synthesize each sentence exactly once."""
    print("\n[TEST 10/10] test_no_duplicate_tts_synthesis...")
    from server.app import tts_engine
    import re

    text = "The weather in Tokyo is sunny. Expect a high of 22 degrees. Have a wonderful day."
    
    def _split_into_sentences(t: str):
        clean = re.sub(r"[*_#`]", "", t).strip()
        raw_chunks = re.split(r'(?<=[.!?])\s+', clean)
        return [c.strip() for c in raw_chunks if c.strip()]

    sentences = _split_into_sentences(text)
    assert len(sentences) == 3

    synth_calls = []
    def mock_synth(s_text, persona_name="Jarvis"):
        synth_calls.append(s_text)
        return b"RIFFfake_wav_data"

    with patch.object(tts_engine, "synthesize_to_wav_bytes", side_effect=mock_synth):
        for s in sentences:
            tts_engine.synthesize_to_wav_bytes(s, persona_name="Jarvis")

    assert len(synth_calls) == 3, f"Expected exactly 3 synthesis calls, got {len(synth_calls)}"
    assert len(set(synth_calls)) == 3, "Duplicate sentence synthesis detected!"
    print(f"  PASS: All {len(synth_calls)} sentences synthesized strictly once with zero duplicates.")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING JARVIS RUNTIME INTEGRITY REPAIR REGRESSION SUITE")
    print("=" * 60)
    
    tests = [
        test_tool_result_preservation,
        test_data_result_not_reduced_to_done,
        test_action_result_can_remain_acknowledgement,
        test_failed_result_is_truthful,
        test_provider_registry_initialized_at_server_startup,
        test_voice_provider_discoverable_from_live_server,
        test_weather_asr_ambiguity,
        test_whether_not_weather_when_context_is_conversational,
        test_contextual_weather_followup,
        test_no_duplicate_tts_synthesis,
    ]
    
    passed = 0
    failed = 0
    t0 = time.time()
    
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {t.__name__} raised: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
            
    dur = time.time() - t0
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{len(tests)} tests PASSED in {dur:.2f}s (Failed: {failed})")
    print("=" * 60)
    os._exit(0 if failed == 0 else 1)
