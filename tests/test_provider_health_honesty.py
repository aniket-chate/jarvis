"""Test Provider Health Honesty and Cascading Fallback.

Verifies BUG 3 Requirements:
1. Diagnose why Ollama is unhealthy.
2. Verify whether provider is expected to be running.
3. Ensure fallback works.
4. Ensure frontend runtime status reflects provider-level health honestly.
5. Do NOT claim 'ALL SYSTEMS OPERATIONAL' if a configured critical provider is unavailable.
6. Represent provider health separately: Backend, Ollama, Gemini, Groq, OpenRouter, Piper TTS, Rule-Based.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from server.app import app, ollama
from llm.ai_router import MultiProviderAIRouter


class TestProviderHealthHonesty(unittest.TestCase):
    """Verifies honest provider health surfacing and fallback execution."""

    def setUp(self):
        self.client = TestClient(app)

    def test_01_ollama_offline_surfaces_degraded_honestly(self):
        """When Ollama is unreachable, status must be DEGRADED and never claim 'ALL SYSTEMS OPERATIONAL'."""
        with patch.object(ollama, "check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = {
                "online": False,
                "status": "unhealthy",
                "models": [],
                "core_ready": False,
                "vision_ready": False,
            }

            resp = self.client.get("/api/runtime/status")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()

            # 1. Must NOT claim ALL SYSTEMS OPERATIONAL
            self.assertNotEqual(data.get("status"), "Healthy")
            self.assertEqual(data.get("status"), "Degraded")
            dial_msg = data.get("system_dial", {}).get("message", "")
            self.assertNotEqual(dial_msg, "ALL SYSTEMS OPERATIONAL")
            self.assertIn("DEGRADED", dial_msg)

            # 2. Providers must be represented separately
            providers = data.get("providers", {})
            self.assertEqual(providers.get("backend"), "Online")
            self.assertEqual(providers.get("ollama"), "Offline")
            self.assertIn("gemini", providers)
            self.assertIn("groq", providers)
            self.assertIn("openrouter", providers)
            self.assertIn("piper_tts", providers)
            self.assertIn("rule_based", providers)

    def test_02_ollama_online_surfaces_healthy(self):
        """When Ollama is healthy and reachable, status reports Healthy and Online."""
        with patch.object(ollama, "check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = {
                "online": True,
                "status": "healthy",
                "models": ["qwen2.5:3b", "moondream:latest"],
                "core_ready": True,
                "vision_ready": True,
            }

            resp = self.client.get("/api/runtime/status")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()

            providers = data.get("providers", {})
            self.assertEqual(providers.get("ollama"), "Online")
            self.assertEqual(data.get("status"), "Healthy")
            self.assertEqual(data.get("system_dial", {}).get("message"), "ALL SYSTEMS OPERATIONAL")

    def test_03_cascading_fallback_when_ollama_fails(self):
        """When Ollama is unreachable or throws error, router gracefully falls back without crashing."""
        router = MultiProviderAIRouter()
        # Force Ollama failure to test deterministic rule-based / cloud cascade
        res = router.generate_response(
            prompt="Hello there, JARVIS.",
            system_prompt="You are Jarvis.",
            persona="Jarvis",
            force_ollama_failure=True,
            task_category="conversation",
        )
        self.assertTrue(bool(res.get("response")), "Router should return text response")
        self.assertTrue(res.get("fallback_occurred"), "fallback_occurred must be True")
        self.assertIn(res.get("provider"), ["rule_based", "groq", "gemini", "openai"])
        self.assertTrue(len(res.get("response", "")) > 0)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestProviderHealthHonesty)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    os._exit(0 if result.wasSuccessful() else 1)
