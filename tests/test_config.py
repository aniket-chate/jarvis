"""Unit tests for JARVIS Config, Multi-Persona, and Secrets layer."""

import unittest
from config.settings import settings, PersonaConfig


class TestConfigLayer(unittest.TestCase):
    def test_personas_loaded(self):
        """Test that all 4 requested personas are registered."""
        expected_personas = ["jarvis", "friday", "ultron", "omi"]
        for p in expected_personas:
            self.assertIn(p, settings.personas, f"Persona {p} should be loaded from config.yaml")

    def test_persona_tones(self):
        """Test that persona tones match the multi-persona configuration specification."""
        jarvis = settings.get_persona("Jarvis")
        self.assertIn("formal", jarvis.tone)

        friday = settings.get_persona("Friday")
        self.assertIn("warm", friday.tone)

        ultron = settings.get_persona("Ultron")
        self.assertIn("sardonic", ultron.tone)

        omi = settings.get_persona("Omi")
        self.assertIn("minimal", omi.tone)

    def test_persona_switching(self):
        """Test dynamic switching of active persona."""
        self.assertTrue(settings.set_active_persona("Friday"))
        self.assertEqual(settings.active_persona_name, "Friday")

        self.assertTrue(settings.set_active_persona("Ultron"))
        self.assertEqual(settings.active_persona_name, "Ultron")

        # Revert back to Jarvis
        self.assertTrue(settings.set_active_persona("Jarvis"))
        self.assertEqual(settings.active_persona_name, "Jarvis")

    def test_invalid_persona_switch(self):
        """Test that attempting to switch to an unknown persona is rejected safely."""
        original = settings.active_persona_name
        result = settings.set_active_persona("NonExistentBot")
        self.assertFalse(result)
        self.assertEqual(settings.active_persona_name, original)

    def test_graceful_degradation_state(self):
        """Verify that search, google oauth, and other services expose status without throwing."""
        self.assertIsInstance(settings.search_available, bool)
        self.assertIsInstance(settings.google_oauth_configured, bool)
        self.assertIsInstance(settings.home_assistant_available, bool)
        self.assertIsInstance(settings.whatsapp_available, bool)


if __name__ == "__main__":
    unittest.main()
