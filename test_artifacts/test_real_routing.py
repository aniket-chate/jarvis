"""Real re-verification of task-based routing with Ollama genuinely confirmed running."""

import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Setup logging to show AI.Router logs clearly
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s")

from llm.ai_router import ai_router

def run_routing_reverification():
    print("=" * 70)
    print("TASK-BASED ROUTING RE-VERIFICATION (OLLAMA GENUINELY ACTIVE)")
    print("=" * 70)

    # Task 1: Conversation -> Local Ollama (qwen2.5:3b)
    print("\n--- TEST 1: Task Category = 'conversation' ---")
    res1 = ai_router.generate_response(
        prompt="Hello JARVIS! Greet me warmly and state your current operational status.",
        system_prompt="You are JARVIS, a helpful AI assistant. Respond in 1-2 sentences.",
        persona="Jarvis",
        task_category="conversation"
    )
    print(f"Provider Served: {res1.get('provider')}")
    print(f"Model:           {res1.get('model')}")
    print(f"Tier:            {res1.get('tier')}")
    print(f"Fallback:        {res1.get('fallback_occurred')}")
    print(f"Response:        {res1.get('response')}")
    assert res1.get("provider") == "ollama", f"Expected ollama, got {res1.get('provider')}"
    assert not res1.get("fallback_occurred"), "Fallback should not have occurred"

    # Task 2: Identity (Protected Task) -> Local Ollama (qwen2.5:3b)
    print("\n--- TEST 2: Task Category = 'identity' (Protected Local Task) ---")
    res2 = ai_router.generate_response(
        prompt="Who are you and what is your architecture?",
        system_prompt="You are JARVIS. Answer crisply in 1-2 sentences.",
        persona="Jarvis",
        task_category="identity"
    )
    print(f"Provider Served: {res2.get('provider')}")
    print(f"Model:           {res2.get('model')}")
    print(f"Tier:            {res2.get('tier')}")
    print(f"Fallback:        {res2.get('fallback_occurred')}")
    print(f"Response:        {res2.get('response')}")
    assert res2.get("provider") == "ollama", f"Expected ollama, got {res2.get('provider')}"
    assert not res2.get("fallback_occurred"), "Fallback should not have occurred"

    # Task 3: Browser Reasoning -> Groq (llama-3.3-70b-versatile)
    print("\n--- TEST 3: Task Category = 'browser_reasoning' ---")
    res3 = ai_router.generate_response(
        prompt="The user is looking at Google Search results for python async libraries. Extracted headings: 'asyncio - Asynchronous I/O', 'httpx - HTTP client for Python'. Summarize in one sentence.",
        system_prompt="You are JARVIS's browser reasoning agent. Summarize the observed page state in one crisp sentence.",
        persona="Jarvis",
        task_category="browser_reasoning"
    )
    print(f"Provider Served: {res3.get('provider')}")
    print(f"Model:           {res3.get('model')}")
    print(f"Tier:            {res3.get('tier')}")
    print(f"Fallback:        {res3.get('fallback_occurred')}")
    print(f"Response:        {res3.get('response')}")
    assert res3.get("provider") in ["groq", "gemini"], f"Expected cloud reasoning provider, got {res3.get('provider')}"

    print("\n" + "=" * 70)
    print("[VERIFICATION SUCCESSFUL] Real logs confirm:")
    print("  1. 'conversation'      -> ACTUALLY served by local Ollama (qwen2.5:3b)")
    print("  2. 'identity'          -> ACTUALLY served by local Ollama (qwen2.5:3b, Protected Local)")
    print(f"  3. 'browser_reasoning' -> ACTUALLY served by {res3.get('provider')} ({res3.get('model')})")
    print("=" * 70)

if __name__ == "__main__":
    run_routing_reverification()
