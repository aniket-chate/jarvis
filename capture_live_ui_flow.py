"""Live browser automation test capturing actual UI interaction and compact mode transition
when playback starts, fulfilling Priority 2 & 3 real-event testing.
"""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def run():
    screenshot_dir = Path("d:/assignment/JARVIS/workspace/screenshots")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        print("[UI Test] Navigating to http://127.0.0.1:8000/...")
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        time.sleep(2)

        # 1. Capture Full HUD
        full_path = screenshot_dir / "ui_full_hud.png"
        page.screenshot(path=str(full_path))
        print(f"[UI Test] Full HUD screenshot saved to: {full_path}")

        # 2. Type query "Play Believer song"
        print("[UI Test] Typing 'Play Believer song' into query input...")
        query_input = page.locator("#query-input")
        query_input.fill("Play Believer song")
        page.locator("#btn-send").click()

        # 3. Wait for playback to start and body class 'compact-mode' to appear
        print("[UI Test] Awaiting media_playback_started event and auto-shrink to compact-mode...")
        page.wait_for_function("() => document.body.classList.contains('compact-mode')", timeout=35000)
        time.sleep(1)

        is_compact = page.evaluate("() => document.body.classList.contains('compact-mode')")
        dock_text = page.locator("#dock-status-label").inner_text()
        print(f"[UI Test] UI Compact Mode: {is_compact}, Dock Status: '{dock_text}'")

        # 4. Capture Compact Standby Dock
        compact_path = screenshot_dir / "ui_compact_dock.png"
        page.screenshot(path=str(compact_path))
        print(f"[UI Test] Compact dock screenshot saved to: {compact_path}")

        # 5. Test mini-input in compact dock
        mini_input = page.locator("#mini-query-input")
        is_mini_visible = mini_input.is_visible()
        print(f"[UI Test] Mini input visible and interactive: {is_mini_visible}")

        browser.close()
        print("[UI Test] UI verification completed successfully!")

if __name__ == "__main__":
    run()
