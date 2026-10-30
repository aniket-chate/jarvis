"""Regression tests ensuring JARVIS never copies personal Chrome profile secrets."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_managed_browser_profile_does_not_copy_personal_chrome_state(tmp_path, monkeypatch):
    from agents.browser_automation_agent import BrowserAutomationAgent

    # Mirror the legacy implementation's exact LOCALAPPDATA Chrome User Data
    # location, including its Windows-style expansion behavior on non-Windows CI.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    personal_profile = tmp_path / "Google" / "Chrome" / "User Data"
    default_profile = personal_profile / "Default"
    default_profile.mkdir(parents=True)
    (personal_profile / "Local State").write_text("private-dpapi-state", encoding="utf-8")
    (default_profile / "Login Data").write_text("private-password-database", encoding="utf-8")
    (default_profile / "Cookies").write_text("private-cookie-database", encoding="utf-8")

    managed_profile = tmp_path / "jarvis-managed-profile"

    agent = BrowserAutomationAgent.__new__(BrowserAutomationAgent)
    agent._managed_profile_dir = str(managed_profile)

    resolved = agent._get_chrome_user_data_dir()

    assert resolved == managed_profile
    assert resolved.is_dir()
    assert not (resolved / "Local State").exists()
    assert not (resolved / "Default" / "Login Data").exists()
    assert not (resolved / "Default" / "Cookies").exists()



def test_active_browser_page_is_reused_instead_of_opening_another_tab(monkeypatch):
    from agents.browser_automation_agent import BrowserAutomationAgent, action_memory_manager

    class FakePage:
        def __init__(self):
            self.closed = False

        def is_closed(self):
            return self.closed

    class FakeContext:
        def __init__(self, pages):
            self.pages = pages
            self.created_pages = 0

        def new_page(self):
            self.created_pages += 1
            page = FakePage()
            self.pages.append(page)
            return page

    existing_page = FakePage()
    context = FakeContext([existing_page])
    agent = BrowserAutomationAgent.__new__(BrowserAutomationAgent)
    agent._active_page = existing_page
    agent._context = context
    agent._get_persistent_context = lambda headless=False: context
    agent._bring_chrome_window_to_front = lambda: None
    monkeypatch.setattr(action_memory_manager, "get_live_page", lambda: None)

    selected = agent._get_or_create_active_page()

    assert selected is existing_page
    assert context.created_pages == 0

