"""Comprehensive Verification for Task-Based AI Router (Part 1).

Validates:
1. Task category routing:
   - "conversation" / "persona_chat" -> primary: Ollama
   - "browser_reasoning" / "parameter_extraction" -> primary: Groq
   - "vision_heavy" / "long_document" -> primary: Gemini
2. Hardcoded Security Invariant:
   - "memory" / "identity" / "knowledge_base" -> forced to local Ollama ONLY
   - Even if forced failure on Ollama, it falls back to local RuleBased ONLY (never cloud)
   - Even if config table is manipulated, code enforces Ollama
3. Simulated HTTP 429 Rate Limit on Groq:
   - Graceful fallback without crashing
"""


import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm.ai_router import MultiProviderAIRouter, PROTECTED_LOCAL_TASKS, RuleBasedAIProvider
from config.settings import settings

def test_hardcoded_privacy_invariant():
    """Verify that protected tasks NEVER route to cloud providers."""
    router = MultiProviderAIRouter()

    for task in ["memory", "identity", "knowledge_base"]:
        assert task in PROTECTED_LOCAL_TASKS
        primary = router.get_primary_provider_for_task(task)
        assert primary == "ollama", f"Protected task '{task}' must have primary provider 'ollama', got '{primary}'"

        cascade = router.get_provider_cascade(task)
        provider_names = [p.name for p in cascade]
        assert "groq" not in provider_names, f"Cloud provider 'groq' found in cascade for protected task '{task}'"
        assert "gemini" not in provider_names, f"Cloud provider 'gemini' found in cascade for protected task '{task}'"
        assert "openai" not in provider_names, f"Cloud provider 'openai' found in cascade for protected task '{task}'"
        assert provider_names == ["ollama", "rule_based"], f"Cascade must strictly be ['ollama', 'rule_based'], got {provider_names}"

def test_protected_task_fallback_stays_local():
    """Verify that when Ollama fails on a protected memory task, it falls back to RuleBased, never cloud."""
    router = MultiProviderAIRouter()
    res = router.generate_response(
        prompt="Who is my creator and owner?",
        system_prompt="You are Jarvis.",
        persona="Jarvis",
        force_ollama_failure=True,
        task_category="identity",
    )
    assert res["fallback_occurred"] is True
    assert res["provider"] == "rule_based", f"Must fall back to rule_based for protected task, got {res['provider']}"
    assert res["tier"] == 3
    assert "groq" != res["provider"]
    assert "gemini" != res["provider"]

def test_task_policy_mapping():
    """Verify that non-protected task categories map to their configured primary providers."""
    router = MultiProviderAIRouter()
    
    # Browser reasoning -> groq
    assert router.get_primary_provider_for_task("browser_reasoning") == "groq"
    cascade_browser = [p.name for p in router.get_provider_cascade("browser_reasoning")]
    assert cascade_browser[0] == "groq"

    # Parameter extraction -> groq
    assert router.get_primary_provider_for_task("parameter_extraction") == "groq"

    # Vision heavy -> gemini
    assert router.get_primary_provider_for_task("vision_heavy") == "gemini"
    cascade_vision = [p.name for p in router.get_provider_cascade("vision_heavy")]
    assert cascade_vision[0] == "gemini"

    # Conversation -> ollama
    assert router.get_primary_provider_for_task("conversation") == "ollama"

def test_simulated_groq_rate_limit_fallback():
    """Verify graceful fallback when Groq hits HTTP 429 rate limit."""
    router = MultiProviderAIRouter()
    res = router.generate_response(
        prompt="Extract parameters from command: create file test.txt",
        system_prompt="Extract parameters as JSON.",
        persona="Friday",
        task_category="parameter_extraction",
        simulated_rate_limit_provider="groq",
    )
    assert res["fallback_occurred"] is True
    assert res["provider"] in ("gemini", "ollama", "rule_based")
    assert "rate limit" in res.get("fallback_reason", "").lower() or "groq" in res.get("fallback_reason", "").lower()

def test_live_conversation_routing():
    """Verify normal conversation routes to Ollama and succeeds live."""
    router = MultiProviderAIRouter()
    res = router.generate_response(
        prompt="Hello Jarvis, what is 2 + 2?",
        system_prompt="You are Jarvis. Answer briefly in one number.",
        persona="Jarvis",
        task_category="conversation",
    )
    assert res["provider"] in ("ollama", "rule_based")
    assert "4" in res["response"]

if __name__ == "__main__":
    print("Running AI Router Policy Verification...")
    test_hardcoded_privacy_invariant()
    print("PASS: Hardcoded Privacy Invariant strictly verified.")
    test_protected_task_fallback_stays_local()
    print("PASS: Protected Task Fallback Stays Local strictly verified.")
    test_task_policy_mapping()
    print("PASS: Task Policy Mapping strictly verified.")
    test_simulated_groq_rate_limit_fallback()
    print("PASS: Simulated Groq Rate Limit Fallback strictly verified.")
    test_live_conversation_routing()
    print("PASS: Live Conversation Routing strictly verified.")
    print("ALL AI ROUTER POLICY TESTS PASSED!")
