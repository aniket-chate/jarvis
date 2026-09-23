"""Comprehensive test suite for JARVIS Model & Tool Stack."""

import unittest
import asyncio
from config.settings import settings
from wakeword.engine import MultiPersonaWakeWordEngine
from llm.personas import get_system_prompt
from llm.ollama_client import OllamaClient
from llm.router import router
from skills.tavily_search import search_skill
from skills.system_control import system_skill
from skills.google_calendar import calendar_skill
from skills.google_gmail import gmail_skill
from skills.cast_skill import cast_skill
from gateway.registry import gateway_registry


class TestJarvisCore(unittest.TestCase):
    def test_01_config_and_personas(self):
        """Test central config.yaml loading and persona specifications."""
        personas = settings.list_personas()
        self.assertEqual(len(personas), 4)
        names = [p["name"] for p in personas]
        self.assertIn("Jarvis", names)
        self.assertIn("Friday", names)
        self.assertIn("Ultron", names)
        self.assertIn("Omi", names)

    def test_02_dynamic_persona_switching(self):
        """Test switching active personas and tone prompts."""
        settings.set_active_persona("Friday")
        self.assertEqual(settings.active_persona_name, "Friday")
        prompt = get_system_prompt("Friday")
        self.assertIn("warm", prompt.lower())

        settings.set_active_persona("Ultron")
        self.assertEqual(settings.active_persona_name, "Ultron")
        prompt = get_system_prompt("Ultron")
        self.assertIn("sardonic", prompt.lower())

        # Reset to default Jarvis
        settings.set_active_persona("Jarvis")
        self.assertEqual(settings.active_persona_name, "Jarvis")

    def test_03_secrets_layer_graceful_degradation(self):
        """Test that missing/unconfigured secrets disable modules gracefully."""
        self.assertTrue(settings.search_available)
        self.assertIsNotNone(settings.tavily_api_key)

        # Home assistant is not configured with token -> gracefully disabled
        self.assertFalse(settings.home_assistant_available)

        # WhatsApp is not configured -> gracefully disabled
        self.assertFalse(settings.whatsapp_available)

    def test_04_wakeword_engine(self):
        """Test multi-persona wake-word detector initialization."""
        engine = MultiPersonaWakeWordEngine()
        self.assertIsNotNone(engine.model)
        # Verify fallback is active when custom ONNX models are not yet on disk
        self.assertTrue(engine.is_fallback)
        self.assertIn("hey_jarvis", engine.active_models)

    def test_05_system_control_skill(self):
        """Test local Windows system control and telemetry."""
        time_info = system_skill.get_time()
        self.assertIn("time", time_info)
        self.assertIn("date", time_info)

        storage = system_skill.get_storage_status("C:")
        self.assertIn("free_gb", storage)
        self.assertGreater(storage["free_gb"], 0)

    def test_06_device_gateway_registry(self):
        """Test Device Gateway multi-client registry."""
        dev = gateway_registry.register_device(
            device_id="phone_android_01",
            name="Pixel Phone",
            client_type="phone",
            ip_address="100.64.0.1",
            capabilities=["audio_output", "camera"],
        )
        self.assertEqual(dev.name, "Pixel Phone")
        self.assertTrue(dev.is_alive())

        devices = gateway_registry.list_active_devices()
        self.assertTrue(any(d["device_id"] == "phone_android_01" for d in devices))

    def test_07_router_persona_and_system(self):
        """Test intent router for system time queries."""
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(router.handle_input("What time is it right now?"))
        self.assertEqual(res["type"], "system")
        self.assertIn("currently", res["response"])

    def test_08_ollama_resilience(self):
        """Test Ollama resilience policy: handles unreachable server gracefully."""
        client = OllamaClient()
        client.host = "http://127.0.0.1:54321"  # Dummy offline host
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(client.generate_response("Test prompt"))
        self.assertIn("unable to connect to my core intelligence engine", res)


if __name__ == "__main__":
    unittest.main()
