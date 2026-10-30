"""Regression tests ensuring JARVIS never copies personal Chrome profile secrets."""

from pathlib import Path


def test_managed_browser_profile_does_not_copy_personal_chrome_state(tmp_path, monkeypatch):
    from agents.browser_automation_agent import BrowserAutomationAgent

    personal_profile = tmp_path / "personal-chrome"
    default_profile = personal_profile / "Default"
    default_profile.mkdir(parents=True)
    (personal_profile / "Local State").write_text("private-dpapi-state", encoding="utf-8")
    (default_profile / "Login Data").write_text("private-password-database", encoding="utf-8")
    (default_profile / "Cookies").write_text("private-cookie-database", encoding="utf-8")

    managed_profile = tmp_path / "jarvis-managed-profile"
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    agent = BrowserAutomationAgent.__new__(BrowserAutomationAgent)
    agent._managed_profile_dir = str(managed_profile)

    resolved = agent._get_chrome_user_data_dir()

    assert resolved == managed_profile
    assert resolved.is_dir()
    assert not (resolved / "Local State").exists()
    assert not (resolved / "Default" / "Login Data").exists()
    assert not (resolved / "Default" / "Cookies").exists()
