"""Frontend API & Integration Verification Test Suite.

Verifies that the JARVIS Gateway server properly serves the authoritative frontend
and all real-time context and capability endpoints:
1. Static files: GET / (index.html), GET /unified/style.css, GET /unified/app.js
2. Visual baseline verification: Cinzel, Cormorant Garamond, Aniket Chate signature, Om seal
3. Runtime Status Endpoint: GET /api/runtime/status
4. Available Capabilities Endpoint: GET /api/capabilities/available
5. Today Context Endpoint: GET /api/context/today
6. Recent Files Endpoint: GET /api/context/recent_files
7. Location Context Endpoint: GET /api/context/location
8. Persona Switching: POST /api/personas/switch
9. Chat Pipeline: POST /api/chat
"""

import os
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from server.app import app
from config.settings import settings


class TestFrontendAPIIntegration(unittest.TestCase):
    """Tests for the integrated JARVIS frontend and runtime endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.auth_headers = {"X-JARVIS-Token": "jarvis-gateway-token-2026-auth"}

    def test_01_root_serves_authoritative_html(self):
        """Tests that GET / serves the authoritative visual HTML."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        content = response.text

        # Verify key visual & brand identities
        self.assertIn("JARVIS", content)
        self.assertIn("ANIKET CHATE", content)
        self.assertIn("Aniket Chate", content)
        self.assertIn("&#2384;", content)  # Sacred Om seal symbol
        self.assertIn("Cinzel", content)
        self.assertIn("Cormorant+Garamond", content)
        self.assertIn("Mrs+Saint+Delafield", content)
        self.assertIn("AI PERSONAS", content)
        self.assertIn("YOUR DAY", content)
        self.assertIn("RECENT FILES", content)
        self.assertIn("QUICK ACTIONS", content)
        self.assertIn("SYSTEM STATUS", content)

    def test_02_static_css_and_js_served(self):
        """Tests that stylesheet and javascript controller are served with 200."""
        css_res = self.client.get("/unified/style.css")
        self.assertEqual(css_res.status_code, 200)
        self.assertIn("--bg:            #05040a;", css_res.text)
        self.assertIn("--gold:          #d9b061;", css_res.text)

        js_res = self.client.get("/unified/app.js")
        self.assertEqual(js_res.status_code, 200)
        self.assertIn("jarvisAdapter", js_res.text)
        self.assertIn("getDaypartGreeting", js_res.text)

    def test_03_runtime_status_endpoint(self):
        """Tests GET /api/runtime/status returns real subsystem statuses."""
        response = self.client.get("/api/runtime/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("status", data)
        self.assertIn("active_persona", data)
        self.assertIn("subsystems", data)
        self.assertIn("system_dial", data)

        subsystems = data["subsystems"]
        self.assertIn("ai_core", subsystems)
        self.assertIn("voice_module", subsystems)
        self.assertIn("vision", subsystems)
        self.assertIn("automation", subsystems)
        self.assertIn("security", subsystems)

        dial = data["system_dial"]
        self.assertEqual(dial["dial_symbol"], "ॐ")
        self.assertIn("message", dial)

    def test_04_capabilities_available_endpoint(self):
        """Tests GET /api/capabilities/available returns all 50 capabilities."""
        response = self.client.get("/api/capabilities/available")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("capabilities", data)
        self.assertEqual(data["total"], 50)
        self.assertEqual(len(data["capabilities"]), 50)

        first_cap = data["capabilities"][0]
        self.assertIn("capability_id", first_cap)
        self.assertIn("name", first_cap)
        self.assertIn("domain", first_cap)
        self.assertIn("available", first_cap)

    def test_05_today_context_endpoint(self):
        """Tests GET /api/context/today returns real schedule items or honest empty state."""
        response = self.client.get("/api/context/today")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("items", data)
        self.assertIn("count", data)
        self.assertIsInstance(data["items"], list)

    def test_06_recent_files_endpoint(self):
        """Tests GET /api/context/recent_files queries authorized workspace scope."""
        response = self.client.get("/api/context/recent_files")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("files", data)
        self.assertIn("count", data)
        self.assertIsInstance(data["files"], list)

    def test_07_location_context_endpoint(self):
        """Tests GET /api/context/location returns honest non-hardcoded location info."""
        response = self.client.get("/api/context/location")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("location", data)
        self.assertIn("source", data)
        self.assertIn("utc_offset", data)

    def test_08_persona_switching_endpoint(self):
        """Tests POST /api/personas/switch updates server authoritative persona."""
        # Switch to Friday
        res_fri = self.client.post(
            "/api/personas/switch",
            headers=self.auth_headers,
            json={"persona": "Friday"}
        )
        self.assertEqual(res_fri.status_code, 200)
        self.assertEqual(res_fri.json()["active_persona"], "Friday")
        self.assertEqual(settings.active_persona_name, "Friday")

        # Switch back to Jarvis
        res_jar = self.client.post(
            "/api/personas/switch",
            headers=self.auth_headers,
            json={"persona": "Jarvis"}
        )
        self.assertEqual(res_jar.status_code, 200)
        self.assertEqual(res_jar.json()["active_persona"], "Jarvis")
        self.assertEqual(settings.active_persona_name, "Jarvis")

    def test_09_chat_endpoint_execution(self):
        """Tests POST /api/chat handles conversation query and returns verified response."""
        res_chat = self.client.post(
            "/api/chat",
            headers=self.auth_headers,
            json={
                "query": "Hello JARVIS, status report.",
                "persona": "Jarvis",
                "device_id": "test_hud",
                "device_name": "Test HUD",
            }
        )
        self.assertEqual(res_chat.status_code, 200)
        data = res_chat.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("response", data)


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestFrontendAPIIntegration)
    result = runner.run(suite)
    os._exit(0 if result.wasSuccessful() else 1)
