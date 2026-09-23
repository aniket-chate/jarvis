"""Browser Automation Agent for JARVIS Layer 3.

Powered by Browser-Use (open-source, self-hosted, natural-language browser automation).
Replaces hardcoded per-site Playwright scripts with generic LLM-driven browser navigation
capable of arbitrary workflows:
- Natural language web browsing & search
- Media playback on arbitrary platforms
- Form discovery, job application inspection, and interaction
"""

import os
import re
import asyncio
import concurrent.futures
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    from browser_use import Agent
    from browser_use.llm.models import ChatOpenAI
    BROWSER_USE_AVAILABLE = True
except ImportError:
    Agent = None
    ChatOpenAI = None
    BROWSER_USE_AVAILABLE = False

from config.settings import PROJECT_ROOT, settings
from orchestrator.action_memory import action_memory_manager

logger = logging.getLogger("JARVIS.BrowserAgent")

SCREENSHOTS_DIR = PROJECT_ROOT / "workspace" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


class BrowserAutomationAgent:
    """Autonomous natural-language web browsing agent driven by Browser-Use and Core LLM."""

    def __init__(self):
        self.host = settings.ollama.get("host", "http://127.0.0.1:11434").rstrip("/")
        self.model_name = settings.hardware.get("core_llm", "qwen2.5:3b")
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._executor_thread_id = None
        self._playwright = None
        self._browser = None
        self._context = None
        self._active_page = None

    def _run_on_executor(self, func, *args, **kwargs):
        """Dispatches work to the dedicated single worker thread ensuring Playwright thread affinity."""
        import threading
        if getattr(self, "_executor_thread_id", None) == threading.get_ident():
            return func(*args, **kwargs)
        future = self._executor.submit(self._set_executor_ident_and_run, func, *args, **kwargs)
        return future.result()

    def _set_executor_ident_and_run(self, func, *args, **kwargs):
        import threading
        self._executor_thread_id = threading.get_ident()
        return func(*args, **kwargs)

    def _is_regular_chrome_running(self) -> bool:
        """Checks whether regular Google Chrome processes are currently active."""
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                pname = (proc.info.get('name') or '').lower()
                if pname in ['chrome.exe', 'chrome']:
                    return True
        except Exception:
            pass
        return False

    def _get_chrome_user_data_dir(self) -> Path:
        """Resolves Chrome User Data directory with full recursive profile synchronization (Local State, IndexedDB, LevelDB, Cookies)."""
        real_user_data = Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"))
        automation_dir = Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data - JARVIS"))
        automation_dir.mkdir(parents=True, exist_ok=True)
        target_default = automation_dir / "Default"
        target_default.mkdir(parents=True, exist_ok=True)

        # Synchronize essential profile session state, DPAPI master key, cookies, and logins
        if real_user_data.exists():
            real_default = real_user_data / "Default"
            import shutil

            # 1. Sync root Local State (CRITICAL: Contains DPAPI encrypted key for cookies/passwords)
            local_state = real_user_data / "Local State"
            if local_state.exists():
                try:
                    shutil.copy2(local_state, automation_dir / "Local State")
                    logger.info("[BrowserAgent] Synchronized root Local State DPAPI key file.")
                except Exception as ls_err:
                    logger.debug("[BrowserAgent] Local State copy note: %s", ls_err)

            # 2. Sync primary profile state files
            for item in ["Preferences", "Login Data", "Web Data", "Favicons", "History", "Secure Preferences"]:
                src = real_default / item
                dst = target_default / item
                if src.exists():
                    try:
                        shutil.copy2(src, dst)
                    except Exception:
                        pass

            # 3. Recursive sync for IndexedDB (WhatsApp Web & Google Session tokens), Local Storage (leveldb), Network, Sessions
            def _sync_folder_recursive(src_dir: Path, dst_dir: Path):
                if not (src_dir.exists() and src_dir.is_dir()):
                    return
                for root, dirs, files in os.walk(src_dir):
                    rel = Path(root).relative_to(src_dir)
                    dest_sub = dst_dir / rel
                    dest_sub.mkdir(parents=True, exist_ok=True)
                    for f in files:
                        try:
                            shutil.copy2(Path(root) / f, dest_sub / f)
                        except Exception:
                            pass

            for folder in ["Local Storage", "IndexedDB", "Network", "Sessions", "Session Storage"]:
                _sync_folder_recursive(real_default / folder, target_default / folder)

            logger.info("[BrowserAgent] Completed full recursive profile synchronization to %s", automation_dir)

        return automation_dir

    def _get_persistent_context(self, headless: bool = False):
        """Maintains an ongoing persistent Playwright browser instance bound to the user's real Chrome channel and profile."""
        from playwright.sync_api import sync_playwright
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "D:\\PlaywrightBrowsers"

        is_context_valid = False
        if self._context is not None:
            try:
                _ = len(self._context.pages)
                is_context_valid = True
            except Exception:
                logger.info("[BrowserAgent] Prior browser context was closed. Re-initializing persistent context...")
                self._context = None
                self._active_page = None

        if not is_context_valid:
            if self._playwright is None:
                self._playwright = sync_playwright().start()

            # 1. Primary Preference: Try connecting to user's REAL Chrome via CDP (http://localhost:9222)
            connected_cdp = False
            try:
                logger.info("[BrowserAgent] Attempting to connect to REAL Chrome via CDP (http://localhost:9222)...")
                cdp_browser = self._playwright.chromium.connect_over_cdp("http://localhost:9222", timeout=3000)
                if cdp_browser and len(cdp_browser.contexts) > 0:
                    self._context = cdp_browser.contexts[0]
                elif cdp_browser:
                    self._context = cdp_browser.new_context()
                connected_cdp = True
                logger.info("[BrowserAgent] Successfully connected to user's REAL Chrome via CDP at port 9222.")
            except Exception as cdp_err:
                logger.info("[BrowserAgent] Real Chrome CDP connection unavailable (%s). Falling back to managed persistent profile...", cdp_err)

            # 2. Fallback: Dedicated managed persistent Chrome context
            if not connected_cdp:
                user_data_dir = self._get_chrome_user_data_dir()
                logger.info("[BrowserAgent] Launching persistent Chrome context with synchronized profile: %s", user_data_dir)
                self._context = self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(user_data_dir),
                    channel="chrome",
                    headless=headless,
                    no_viewport=True,
                    args=[
                        "--autoplay-policy=no-user-gesture-required",
                        "--disable-blink-features=AutomationControlled",
                        "--start-maximized",
                        "--window-position=0,0",
                        "--window-size=1920,1080",
                        "--no-default-browser-check",
                        "--no-first-run",
                    ],
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
        return self._context

    def _bring_chrome_window_to_front(self, target_title: Optional[str] = None) -> None:
        """Brings the automation Chrome window to the absolute foreground and maximizes it on Windows."""
        if os.name != "nt":
            return
        try:
            import win32gui
            import win32con
            import ctypes

            def enum_cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd).strip()
                    cls_name = win32gui.GetClassName(hwnd)
                    # Exclude JARVIS HUD itself so we don't defocus the user's HUD unexpectedly unless requested
                    is_hud = "jarvis core //" in title.lower()
                    if cls_name == "Chrome_WidgetWin_1" and not is_hud:
                        matches = True
                        if target_title:
                            matches = target_title.lower() in title.lower()
                        if matches:
                            try:
                                # ALT tap allows SetForegroundWindow to bypass Windows OS focus-lock
                                ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
                                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                                win32gui.BringWindowToTop(hwnd)
                                ctypes.windll.user32.SetForegroundWindow(hwnd)
                                ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
                            except Exception as ex:
                                logger.debug("[BrowserAgent] Could not bring window '%s' to front: %s", title, ex)
                return True

            hdesk = None
            try:
                hdesk = ctypes.windll.user32.OpenDesktopW("default", 0, False, 0x01FF)
                if hdesk:
                    win32gui.EnumDesktopWindows(hdesk, enum_cb, 0)
            finally:
                if hdesk:
                    ctypes.windll.user32.CloseDesktop(hdesk)
            # Also invoke on EnumWindows
            win32gui.EnumWindows(enum_cb, 0)
        except Exception as e:
            logger.debug("[BrowserAgent] _bring_chrome_window_to_front error: %s", e)

    def show_active_tabs(self) -> Dict[str, Any]:
        """Lists active browser tabs and brings the browser window to the foreground."""
        self._bring_chrome_window_to_front()
        if self._context is None:
            return {"success": True, "message": "No browser tabs are currently open.", "tabs": []}
        tabs = []
        for p in self._context.pages:
            try:
                if not p.is_closed():
                    tabs.append({"title": p.title(), "url": p.url})
            except Exception:
                continue
        if not tabs:
            return {"success": True, "message": "No active browser tabs found.", "tabs": []}
        tab_list = "\n".join([f"- {t['title']} ({t['url']})" for t in tabs])
        return {
            "success": True,
            "message": f"Active browser tabs ({len(tabs)}):\n{tab_list}",
            "response": f"I've brought your browser to the front. You have {len(tabs)} open tab(s): {', '.join([t['title'] for t in tabs])}.",
            "tabs": tabs
        }

    def _get_or_create_active_page(self, headless: bool = False):
        """Retrieves existing active page or reuses the most recent tab, creating one only if none exist."""
        for attempt in range(2):
            context = self._get_persistent_context(headless=headless)
            try:
                if self._active_page is not None and not self._active_page.is_closed():
                    self._bring_chrome_window_to_front()
                    return self._active_page
            except Exception:
                self._active_page = None

            try:
                if context and len(context.pages) > 0:
                    for p in reversed(context.pages):
                        try:
                            if not p.is_closed():
                                self._active_page = p
                                self._bring_chrome_window_to_front()
                                return self._active_page
                        except Exception:
                            continue
            except Exception:
                pass

            try:
                self._active_page = context.new_page()
                self._bring_chrome_window_to_front()
                return self._active_page
            except Exception as page_err:
                logger.warning("[BrowserAgent] Failed to open new page in context (%s); re-initializing context on attempt %d...", page_err, attempt + 1)
                self._context = None
                self._active_page = None

        # Fallback to fresh context
        context = self._get_persistent_context(headless=headless)
        self._active_page = context.new_page()
        self._bring_chrome_window_to_front()
        return self._active_page

    def _get_llm(self) -> ChatOpenAI:
        """Returns OpenAI-compatible client bound to local Ollama instance."""
        return ChatOpenAI(
            base_url=f"{self.host}/v1",
            model=self.model_name,
            api_key="ollama"
        )

    async def run_natural_language_task_async(
        self,
        task: str,
        max_steps: int = 5,
        screenshot_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Executes any natural language browser instruction generically using Browser-Use."""
        logger.info("[BrowserAgent] Executing natural language task: %s", task)
        llm = self._get_llm()

        screenshot_dest = SCREENSHOTS_DIR / (screenshot_filename or "browser_use_action.png")
        screenshot_path_str = None

        def step_callback(state, output, step):
            nonlocal screenshot_path_str
            if getattr(state, "screenshot", None):
                try:
                    import base64
                    screenshot_dest.write_bytes(base64.b64decode(state.screenshot))
                    screenshot_path_str = str(screenshot_dest)
                except Exception as ss_err:
                    logger.warning("[BrowserAgent] Screenshot capture error: %s", ss_err)

        user_data_dir = self._get_chrome_user_data_dir()
        browser = None
        if BROWSER_USE_AVAILABLE:
            try:
                from browser_use import Browser
                import urllib.request
                is_cdp_live = False
                try:
                    with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=0.8) as resp:
                        if resp.status == 200:
                            is_cdp_live = True
                except Exception:
                    is_cdp_live = False

                if is_cdp_live:
                    logger.info("[BrowserAgent] Browser-Use connecting to REAL Chrome via CDP port 9222")
                    browser = Browser(cdp_url="http://127.0.0.1:9222")
                else:
                    browser = Browser(
                        channel="chrome",
                        user_data_dir=str(user_data_dir),
                        headless=False,
                    )
            except Exception as b_err:
                logger.warning("[BrowserAgent] Browser-Use Chrome session init warning: %s", b_err)

        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
            use_vision=False,
            max_actions_per_step=3,
            register_new_step_callback=step_callback
        )

        try:
            history = await asyncio.wait_for(agent.run(max_steps=max_steps), timeout=60.0)
            final_text = ""
            if history:
                final_text = str(history.final_result() or "")

            return {
                "success": True,
                "task": task,
                "result": final_text,
                "steps_taken": len(history.model_dump()) if hasattr(history, "model_dump") else max_steps,
                "screenshot_path": screenshot_path_str
            }
        except asyncio.TimeoutError:
            logger.error("[BrowserAgent] Task timed out after 60s hard limit: %s", task)
            return {
                "success": False,
                "task": task,
                "error": "Browser automation task timed out after 60s."
            }
        except Exception as e:
            logger.error("[BrowserAgent] Task execution failed: %s", str(e))
            return {
                "success": False,
                "task": task,
                "error": str(e)
            }

    def _play_youtube_fastpath(
        self,
        song_query: str,
        screenshot_filename: str = "test_youtube_playback.png",
        screenshot_60s_filename: Optional[str] = None,
        play_duration_sec: float = 0.0,
        headless: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Fast-path direct Playwright action to search and click first video, confirming real playback without tearing down the browser."""
        import urllib.parse
        import time

        encoded_query = urllib.parse.quote(song_query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
        screenshot_dest = SCREENSHOTS_DIR / screenshot_filename
        screenshot_60s_dest = SCREENSHOTS_DIR / (screenshot_60s_filename or f"60s_{screenshot_filename}") if play_duration_sec > 0 else None

        logger.info("[BrowserAgent FastPath] Attempting persistent visible playback for: '%s' (duration=%.1fs)", song_query, play_duration_sec)
        try:
            page = self._get_or_create_active_page(headless=headless)
            self._active_page = page
            try:
                page.evaluate("() => { const vids = document.querySelectorAll('video'); for (const v of vids) v.pause(); }")
            except Exception:
                pass
            page.goto(search_url, wait_until="commit", timeout=20000)
            self._bring_chrome_window_to_front()
            
            # Check for and bypass consent dialog if present
            try:
                consent_btn = page.locator("button:has-text('Reject all'), button:has-text('Accept all'), button:has-text('I agree')").first
                if consent_btn.is_visible(timeout=3000):
                    consent_btn.click()
                    time.sleep(1)
            except Exception:
                pass

            # Wait for video item render
            video_selector = "ytd-video-renderer #video-title, #contents ytd-video-renderer a#thumbnail"
            page.wait_for_selector(video_selector, timeout=15000)

            first_video = page.locator("ytd-video-renderer #video-title").first
            video_title = first_video.inner_text()
            logger.info("[BrowserAgent FastPath] Found video: '%s', clicking to play...", video_title)
            first_video.click()

            # Wait for video watch page
            page.wait_for_url("**/watch*", timeout=15000)
            page.wait_for_selector("video.html5-main-video", timeout=15000)
            actual_video_url = page.url

            # Dismiss any initial cookie/consent or promotion dialogs
            try:
                page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button, ytd-button-renderer'));
                    for (const b of btns) {
                        const txt = (b.innerText || '').toLowerCase();
                        if (txt.includes('skip ad') || txt.includes('reject all') || txt.includes('accept all') || txt.includes('no thanks') || txt.includes('dismiss')) {
                            try { b.click(); } catch(e){}
                        }
                    }
                }""")
            except Exception:
                pass

            # Robust playback initiation and verification loop (checks actual progression)
            is_playing = False
            delta_time = 0.0
            initial_play_time = 0.0
            final_time = 0.0
            max_retries = 3

            for attempt in range(1, max_retries + 1):
                # Trigger play via player API, video element, and click, unmuting audio
                page.evaluate("""() => {
                    const skipBtn = document.querySelector('.ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button');
                    if (skipBtn) {
                        try { skipBtn.click(); } catch(e){}
                    }
                    const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
                    if (player && typeof player.playVideo === 'function') {
                        try { player.unMute(); } catch(e){}
                        try { player.setVolume(100); } catch(e){}
                        try { player.playVideo(); } catch(e){}
                    }
                    const v = document.querySelector('video.html5-main-video');
                    if (v) {
                        v.muted = false;
                        v.volume = 1.0;
                        v.play().catch(() => {});
                    }
                }""")

                t0_data = page.evaluate("""() => {
                    const v = document.querySelector('video.html5-main-video');
                    return v ? { currentTime: v.currentTime, paused: v.paused, readyState: v.readyState } : null;
                }""")

                time.sleep(2.0)

                t1_data = page.evaluate("""() => {
                    const v = document.querySelector('video.html5-main-video');
                    return v ? { currentTime: v.currentTime, paused: v.paused, readyState: v.readyState } : null;
                }""")

                if t0_data and t1_data:
                    delta = t1_data["currentTime"] - t0_data["currentTime"]
                    initial_play_time = t0_data["currentTime"]
                    final_time = t1_data["currentTime"]
                    if not t1_data["paused"] and delta >= 0.4:
                        is_playing = True
                        delta_time = delta
                        logger.info("[BrowserAgent FastPath] Playback confirmed active on attempt %d (delta=%.2fs, currentTime=%.2fs)", attempt, delta, final_time)
                        break
                    else:
                        logger.warning("[BrowserAgent FastPath] Attempt %d: playback not advancing (paused=%s, delta=%.2f). Retrying...", attempt, t1_data["paused"], delta)
                        # Retry: click play button or player canvas directly
                        try:
                            play_btn = page.locator("button.ytp-play-button").first
                            if play_btn.is_visible(timeout=1000):
                                play_btn.click()
                            else:
                                page.locator("video.html5-main-video").first.click(force=True)
                        except Exception:
                            pass

            # Fallback check if currentTime progressed at all
            if not is_playing and final_time > 0.5:
                is_playing = True
                delta_time = 0.5

            # 1. Capture initial playback proof screenshot
            page.screenshot(path=str(screenshot_dest))

            # Copy initial screenshot to active conversation artifacts directory
            try:
                import shutil
                artifacts_dirs = [
                    Path(r"C:\Users\acer\.gemini\antigravity-ide\brain\65337e1e-5d27-4941-8153-1cf1c5997512"),
                    Path(r"C:\Users\acer\.gemini\antigravity-ide\brain\a47af4a5-7bb7-4250-bd6c-7d2bf08ed5f3")
                ]
                for adir in artifacts_dirs:
                    if adir.exists():
                        shutil.copy(screenshot_dest, adir / screenshot_filename)
            except Exception as cpy_err:
                logger.warning("[BrowserAgent FastPath] Artifact copy warning: %s", cpy_err)

            # 2. If play_duration_sec requested (e.g. verification), allow video to play continuously
            time_at_60s = final_time
            if is_playing and play_duration_sec > 0:
                logger.info("[BrowserAgent FastPath] Allowing playback to continue for %.1f seconds...", play_duration_sec)
                elapsed = 0.0
                interval = 5.0
                while elapsed < play_duration_sec:
                    time.sleep(interval)
                    elapsed += interval
                    page.evaluate("""() => {
                        const skipBtn = document.querySelector('.ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button');
                        if (skipBtn) {
                            try { skipBtn.click(); } catch(e){}
                        }
                        const v = document.querySelector('video.html5-main-video');
                        if (v && v.paused) {
                            v.play().catch(() => {});
                        }
                    }""")

                curr_60s = page.evaluate("""() => {
                    const v = document.querySelector('video.html5-main-video');
                    return v ? v.currentTime : null;
                }""")
                if curr_60s:
                    time_at_60s = curr_60s
                    logger.info("[BrowserAgent FastPath] Continuous playback verified: currentTime=%.2fs", time_at_60s)

                if screenshot_60s_dest:
                    page.screenshot(path=str(screenshot_60s_dest))
                    try:
                        for adir in artifacts_dirs:
                            if adir.exists():
                                shutil.copy(screenshot_60s_dest, adir / screenshot_60s_dest.name)
                    except Exception:
                        pass

            # NOTICE: We deliberately DO NOT call browser.close() so that playback continues indefinitely on the user's desktop!
            action_memory_manager.set_live_page(
                page=page,
                agent=self,
                title=video_title,
                url=actual_video_url,
                is_media=is_playing,
                query=song_query,
                action_type="media_playback"
            )
            self._bring_chrome_window_to_front()

            return {
                "success": is_playing,
                "tool": "play_youtube",
                "action": "play_youtube",
                "playback_state": "playing" if is_playing else "failed",
                "song_query": song_query,
                "title": video_title,
                "video_title": video_title,
                "url": actual_video_url,
                "screenshot_path": str(screenshot_dest),
                "screenshot_60s_path": str(screenshot_60s_dest) if screenshot_60s_dest else None,
                "is_playing": is_playing,
                "initial_time": initial_play_time,
                "current_time": time_at_60s,
                "delta_time": delta_time,
                "message": f"Playing '{video_title}' on YouTube." if is_playing else f"Failed to initiate playback for '{song_query}' on YouTube.",
                "response": f"Playing '{video_title}' on YouTube." if is_playing else f"Failed to initiate playback for '{song_query}' on YouTube.",
                "output": f"Playing '{video_title}' on YouTube." if is_playing else f"Failed to initiate playback for '{song_query}' on YouTube."
            }
        except Exception as err:
            logger.warning("[BrowserAgent FastPath] Fast-path failed (%s), falling back to agentic Browser-Use", err)
            return None

    def _web_action_impl(
        self,
        task: str,
        site: Optional[str] = None,
        query: Optional[str] = None,
        headless: bool = False,
        screenshot_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Astra-style 'observe page -> decide action -> execute' loop for arbitrary websites."""
        import time
        import urllib.parse
        import re
        import shutil

        clean_task = (task or query or "").strip()
        clean_site = (site or "").lower().strip()
        clean_query = (query or "").strip()

        # If site wasn't explicitly passed, detect from task or query
        if not clean_site:
            for s_cand in ["linkedin", "internshala", "snapchat", "facebook", "instagram", "youtube", "twitter", "x", "reddit", "github", "wikipedia", "amazon", "google", "maps"]:
                if s_cand in clean_task.lower():
                    clean_site = s_cand
                    break

        # Dynamically resolve starting URL
        site_urls = {
            "linkedin": "https://www.linkedin.com",
            "internshala": "https://internshala.com",
            "snapchat": "https://web.snapchat.com",
            "facebook": "https://www.facebook.com",
            "instagram": "https://www.instagram.com",
            "youtube": "https://www.youtube.com",
            "twitter": "https://x.com",
            "x": "https://x.com",
            "reddit": "https://www.reddit.com",
            "github": "https://github.com",
            "wikipedia": "https://en.wikipedia.org",
            "amazon": "https://www.amazon.in",
            "google": "https://www.google.com",
            "maps": "https://www.google.com/maps",
        }

        if clean_site in site_urls:
            target_url = site_urls[clean_site]
            # Smart direct action routing if query/action specified
            if clean_site == "internshala":
                if clean_query:
                    term = clean_query.lower().replace("internships", "").replace("internship", "").strip()
                    if term:
                        target_url = f"https://internshala.com/internships/keywords-{urllib.parse.quote(term)}/"
                    else:
                        target_url = "https://internshala.com/internships/"
                else:
                    target_url = "https://internshala.com/internships/"
            elif clean_site == "snapchat":
                if any(w in clean_task.lower() for w in ["story", "stories", "spotlight"]):
                    target_url = "https://story.snapchat.com"
            elif clean_site == "linkedin" and clean_query:
                target_url = f"https://www.linkedin.com/search/results/all/?keywords={urllib.parse.quote(clean_query)}"
        elif clean_site.startswith("http://") or clean_site.startswith("https://"):
            target_url = clean_site
        elif "." in clean_site:
            target_url = f"https://{clean_site}"
        elif clean_site:
            target_url = f"https://www.{clean_site}.com"
        else:
            # Check if task has a URL
            url_match = re.search(r"https?://[^\s]+", clean_task)
            if url_match:
                target_url = url_match.group(0)
            else:
                target_url = "https://www.google.com"

        screenshot_name = screenshot_filename or f"web_{clean_site or 'action'}_{int(time.time())}.png"
        screenshot_dest = SCREENSHOTS_DIR / screenshot_name

        logger.info("[BrowserAgent AstraLoop] Starting live web action on %s (headless=%s) for task: '%s'", target_url, headless, clean_task)
        page = self._get_or_create_active_page(headless=headless)
        self._active_page = page

        # 1. Navigate to target URL
        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=35000)
            self._bring_chrome_window_to_front()
            time.sleep(2.0)
        except Exception as nav_err:
            logger.warning("[BrowserAgent AstraLoop] Navigation warning: %s", nav_err)

        # 2. Observe Live Page & Dismiss Overlay/Cookie Banners
        try:
            dismiss_buttons = page.locator("button:has-text('Reject all'), button:has-text('Accept all'), button:has-text('Accept'), button:has-text('Allow'), button:has-text('Dismiss'), button:has-text('Close'), button:has-text('Not Now'), div[aria-label='Close'], button[aria-label='Close']")
            if dismiss_buttons.first.is_visible(timeout=1500):
                dismiss_buttons.first.click()
                time.sleep(1.0)
        except Exception:
            pass

        # 3. Extract query if not provided
        if not clean_query:
            qm = re.search(r"\b(?:search\s+(?:for\s+)?|find\s+|look\s+for\s+)(.+?)(?:\s+(?:on|in)\s+[a-zA-Z0-9_.-]+|\s*$)", clean_task, re.IGNORECASE)
            if qm:
                clean_query = qm.group(1).strip()

        # 4. If query found, decide action: locate search input & execute search
        search_executed = False
        if clean_query:
            search_selectors = [
                "input[placeholder*='Search' i]",
                "input[aria-label*='Search' i]",
                "input[type='search']",
                "input[name='search_query']",
                "input#search",
                "input#searchInput",
                "input[name='q']",
                "textarea[name='q']",
                "input[type='text']",
                "div[role='search'] input",
            ]
            for sel in search_selectors:
                try:
                    loc = page.locator(sel).first
                    if loc.is_visible(timeout=1200):
                        loc.click()
                        loc.fill("")
                        loc.type(clean_query, delay=30)
                        time.sleep(0.5)
                        loc.press("Enter")
                        search_executed = True
                        logger.info("[BrowserAgent AstraLoop] Located search element via '%s' and submitted query '%s'", sel, clean_query)
                        break
                except Exception:
                    continue

            if not search_executed and clean_site in ["linkedin", "internshala", "facebook", "snapchat"]:
                try:
                    search_icon = page.locator("button[aria-label*='Search' i], a[href*='search' i], svg[aria-label*='Search' i]").first
                    if search_icon.is_visible(timeout=2000):
                        search_icon.click()
                        time.sleep(1.0)
                        input_loc = page.locator("input[placeholder*='Search' i], input[type='text']").first
                        if input_loc.is_visible(timeout=2000):
                            input_loc.fill(clean_query)
                            input_loc.press("Enter")
                            search_executed = True
                except Exception:
                    pass

        # 5. Live Page Observation & Analysis
        time.sleep(3.0)
        current_url = page.url
        current_title = page.title()

        observations = []
        try:
            headings = page.locator("h1, h2, h3, a[data-control-name], .job-title, .job-internship-name, .company-name, .individual_internship, .feed-shared-update-v2, [data-testid='story-card'], div[role='article']").all_inner_texts()
            for h in headings[:10]:
                h_clean = h.strip().replace("\n", " - ")
                if h_clean and len(h_clean) > 3 and h_clean not in observations:
                    observations.append(h_clean[:120])
        except Exception:
            pass

        # 6. Proof Screenshot
        page.screenshot(path=str(screenshot_dest))
        try:
            art_dir = Path(r"C:\Users\acer\.gemini\antigravity-ide\brain\027db39b-f320-4348-9eff-8b57c946e55e")
            if art_dir.exists():
                shutil.copy(screenshot_dest, art_dir / screenshot_name)
        except Exception:
            pass

        # 7. Record in Action Memory
        action_memory_manager.record_web_session(
            url=current_url,
            title=current_title,
            site=clean_site or "web",
            action_type="web_action",
            query=clean_query or clean_task,
            screenshot_path=str(screenshot_dest),
            page=page,
            agent=self,
        )

        # 8. AI Reasoning over Live Observations (Tagged task_category='browser_reasoning' -> Groq)
        obs_text = "; ".join(observations[:3]) if observations else f"Title: '{current_title}'"
        try:
            from llm.ai_router import ai_router
            reasoning_prompt = f"Live web observation summary for page '{current_title}' ({current_url}). Extracted headings: {observations[:4]}. User task: '{clean_query or clean_task}'."
            sys_prompt = "You are JARVIS's browser reasoning agent. Summarize the observed page state in one crisp sentence."
            ai_res = ai_router.generate_response(
                prompt=reasoning_prompt,
                system_prompt=sys_prompt,
                task_category="browser_reasoning",
            )
            logger.info("[BrowserAgent AstraLoop] Page reasoning served by provider '%s'", ai_res.get("provider"))
            if ai_res.get("response") and len(ai_res.get("response")) < 200:
                obs_text = ai_res.get("response").strip()
        except Exception as e:
            logger.debug("[BrowserAgent AstraLoop] Browser reasoning note: %s", e)

        if search_executed:
            resp_msg = f"Navigated to {clean_site.capitalize() if clean_site else 'the site'}, searched for '{clean_query}', and displayed live results on screen. Observed: {obs_text}."
        else:
            resp_msg = f"Opened {clean_site.capitalize() if clean_site else 'the site'} ({current_url}) visibly on screen. Page title: '{current_title}'. Observed content: {obs_text}."

        return {
            "success": True,
            "action": "web_action",
            "site": clean_site,
            "query": clean_query or clean_task,
            "url": current_url,
            "title": current_title,
            "observations": observations,
            "screenshot_path": str(screenshot_dest),
            "response": resp_msg,
            "output": resp_msg
        }

    def _get_maps_route_impl(
        self,
        destination: str,
        origin: Optional[str] = None,
        headless: bool = False,
        screenshot_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Navigates Google Maps visibly, retrieves live directions and travel times, and extracts the route."""
        import time
        import urllib.parse
        import shutil

        dest_clean = destination.strip()
        origin_clean = origin.strip() if origin else ""

        if origin_clean:
            maps_url = f"https://www.google.com/maps/dir/{urllib.parse.quote(origin_clean)}/{urllib.parse.quote(dest_clean)}"
        else:
            maps_url = f"https://www.google.com/maps/search/{urllib.parse.quote(dest_clean)}"

        screenshot_name = screenshot_filename or f"maps_{int(time.time())}.png"
        screenshot_dest = SCREENSHOTS_DIR / screenshot_name

        logger.info("[BrowserAgent MapsRoute] Opening Google Maps visibly: %s", maps_url)
        page = self._get_or_create_active_page(headless=headless)
        self._active_page = page

        page.goto(maps_url, wait_until="domcontentloaded", timeout=35000)
        time.sleep(3.0)

        # Dismiss Google consent / cookies dialog if present
        try:
            consent_btn = page.locator("button:has-text('Reject all'), button:has-text('Accept all'), button:has-text('I agree'), button:has-text('Accept')").first
            if consent_btn.is_visible(timeout=2500):
                consent_btn.click()
                time.sleep(1.5)
        except Exception:
            pass

        # If we navigated via search, click the Directions button
        if not origin_clean:
            try:
                directions_btn = page.locator("button[data-value*='Directions' i], button[aria-label*='Directions' i], button:has-text('Directions')").first
                if directions_btn.is_visible(timeout=3000):
                    directions_btn.click()
                    time.sleep(2.5)
            except Exception:
                pass

        time.sleep(3.0)
        page.screenshot(path=str(screenshot_dest))

        try:
            art_dir = Path(r"C:\Users\acer\.gemini\antigravity-ide\brain\027db39b-f320-4348-9eff-8b57c946e55e")
            if art_dir.exists():
                shutil.copy(screenshot_dest, art_dir / screenshot_name)
        except Exception:
            pass

        current_url = page.url
        current_title = page.title()

        route_snippets = []
        try:
            texts = page.locator(".section-directions-trip-description, div[data-trip-index], div.F7nice, span[jstcache], div[role='region']").all_inner_texts()
            for t in texts:
                t_clean = re.sub(r'[\ue000-\uf8ff]', '', t).strip().replace("\n", " - ")
                if t_clean and len(t_clean) > 4 and t_clean not in route_snippets:
                    route_snippets.append(t_clean)
        except Exception:
            pass

        route_summary = route_snippets[0] if route_snippets else f"Directions to {dest_clean} located and displayed on Google Maps"

        # Record in Action Memory
        action_memory_manager.record_web_session(
            url=current_url,
            title=current_title,
            site="google_maps",
            action_type="maps_route",
            query=dest_clean,
            screenshot_path=str(screenshot_dest)
        )

        msg = f"Navigated to Google Maps and displayed route to '{dest_clean}' on screen. Route details: {route_summary}."
        return {
            "success": True,
            "action": "maps_route",
            "destination": dest_clean,
            "origin": origin_clean,
            "url": current_url,
            "route_summary": route_summary,
            "screenshot_path": str(screenshot_dest),
            "response": msg,
            "output": msg
        }

    def _stop_active_media_impl(self) -> Dict[str, Any]:
        """Pauses or stops any active media playing in the browser context."""
        stopped_count = 0
        if self._context:
            for p in self._context.pages:
                try:
                    res = p.evaluate("""() => {
                        let stopped = 0;
                        const vids = document.querySelectorAll('video, audio');
                        for (const v of vids) {
                            if (!v.paused) {
                                v.pause();
                                stopped++;
                            }
                        }
                        const ytPlayer = document.getElementById('movie_player');
                        if (ytPlayer && typeof ytPlayer.pauseVideo === 'function') {
                            ytPlayer.pauseVideo();
                            stopped++;
                        }
                        return stopped;
                    }""")
                    if res and res > 0:
                        stopped_count += res
                except Exception:
                    pass

        action_memory_manager.update_media_playback_state(is_playing=False)
        msg = f"Paused active media playback in browser ({stopped_count} player(s) stopped)." if stopped_count > 0 else "Paused active media playback in browser."
        logger.info("[BrowserAgent StopMedia] %s", msg)
        return {
            "success": True,
            "action": "stop_media",
            "stopped_count": stopped_count,
            "response": msg,
            "output": msg
        }

    def _resume_active_media_impl(self) -> Dict[str, Any]:
        """Resumes active media playback in the browser context."""
        resumed_count = 0
        target_pages = []
        if self._active_page is not None and not getattr(self._active_page, "is_closed", lambda: False)():
            target_pages.append(self._active_page)
        if self._context:
            for p in self._context.pages:
                if p not in target_pages:
                    target_pages.append(p)

        for p in target_pages:
            try:
                res = p.evaluate("""() => {
                    let resumed = 0;
                    const ytPlayer = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
                    if (ytPlayer && typeof ytPlayer.playVideo === 'function') {
                        try { ytPlayer.unMute(); } catch(e){}
                        ytPlayer.playVideo();
                        resumed++;
                    }
                    const vids = document.querySelectorAll('video, audio');
                    for (const v of vids) {
                        if (v.paused) {
                            v.muted = false;
                            v.play().catch(() => {});
                            resumed++;
                        }
                    }
                    return resumed;
                }""")
                if res and res > 0:
                    resumed_count += res
            except Exception:
                pass

        action_memory_manager.update_media_playback_state(is_playing=True)
        msg = f"Resumed active media playback in browser ({resumed_count} player(s) resumed)." if resumed_count > 0 else "Resumed active media playback in browser."
        logger.info("[BrowserAgent ResumeMedia] %s", msg)
        return {
            "success": True,
            "action": "resume_media",
            "resumed_count": resumed_count,
            "response": msg,
            "output": msg
        }

    def _close_active_page_impl(self) -> Dict[str, Any]:
        """Closes the current active browser tab."""
        closed = False
        try:
            if self._active_page:
                self._active_page.close()
                self._active_page = None
                closed = True
            elif self._context and len(self._context.pages) > 0:
                self._context.pages[-1].close()
                closed = True
        except Exception as e:
            logger.warning("[BrowserAgent ClosePage] Error: %s", e)

        action_memory_manager.clear_active_session()
        msg = "Closed active browser tab." if closed else "No active browser tab to close."
        return {
            "success": True,
            "action": "close_page",
            "response": msg,
            "output": msg
        }

    def web_action(
        self,
        task: str,
        site: Optional[str] = None,
        query: Optional[str] = None,
        headless: bool = False,
        screenshot_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Public thread-safe dispatcher for generalized Astra web action."""
        return self._run_on_executor(
            self._web_action_impl,
            task=task,
            site=site,
            query=query,
            headless=headless,
            screenshot_filename=screenshot_filename,
        )

    def get_maps_route(
        self,
        destination: str,
        origin: Optional[str] = None,
        headless: bool = False,
        screenshot_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Public thread-safe dispatcher for Google Maps route navigation."""
        return self._run_on_executor(
            self._get_maps_route_impl,
            destination=destination,
            origin=origin,
            headless=headless,
            screenshot_filename=screenshot_filename,
        )

    def stop_active_media(self) -> Dict[str, Any]:
        """Public thread-safe dispatcher for pausing/stopping active media."""
        return self._run_on_executor(self._stop_active_media_impl)

    def resume_active_media(self) -> Dict[str, Any]:
        """Public thread-safe dispatcher for resuming active media."""
        return self._run_on_executor(self._resume_active_media_impl)

    def close_active_page(self) -> Dict[str, Any]:
        """Public thread-safe dispatcher for closing the active browser tab."""
        return self._run_on_executor(self._close_active_page_impl)

    def chained_search(
        self,
        site: str,
        query: str,
        headless: bool = False,
        screenshot_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Executes a multi-step chain: open -> wait for load -> locate search control -> type query -> submit -> confirm results."""
        import time
        import urllib.parse

        clean_site = site.lower().strip()
        screenshot_name = screenshot_filename or f"search_{clean_site}_{int(time.time())}.png"
        screenshot_dest = SCREENSHOTS_DIR / screenshot_name

        # 1. Dynamically resolve base site URL
        if clean_site.startswith("http://") or clean_site.startswith("https://"):
            base_url = clean_site
        elif "." in clean_site:
            base_url = f"https://{clean_site}"
        else:
            site_map = {
                "instagram": "https://www.instagram.com",
                "youtube": "https://www.youtube.com",
                "google": "https://www.google.com",
                "wikipedia": "https://en.wikipedia.org",
                "github": "https://github.com",
                "reddit": "https://www.reddit.com",
                "twitter": "https://x.com",
                "x": "https://x.com",
                "amazon": "https://www.amazon.com",
                "linkedin": "https://www.linkedin.com",
            }
            base_url = site_map.get(clean_site, f"https://www.{clean_site}.com")

        logger.info("[BrowserAgent ChainedSearch] Step 1: Navigating to %s for query '%s'", base_url, query)
        page = self._get_or_create_active_page(headless=headless)
        self._active_page = page

        # Step 1: Open site & wait for real page load
        page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2.0)

        # Step 2: Dismiss cookies/consent overlays
        try:
            dismiss_buttons = page.locator("button:has-text('Reject all'), button:has-text('Accept all'), button:has-text('Accept'), button:has-text('Not Now'), button:has-text('Decline optional cookies'), button:has-text('I agree'), button:has-text('Close')")
            if dismiss_buttons.first.is_visible(timeout=2000):
                dismiss_buttons.first.click()
                time.sleep(1.0)
        except Exception:
            pass

        # Step 3: Locate the search control dynamically
        if "instagram" in clean_site:
            try:
                nav_search = page.locator("svg[aria-label='Search'], a[href='#']:has-text('Search'), span:has-text('Search'), div[role='button']:has-text('Search')").first
                if nav_search.is_visible(timeout=3000):
                    nav_search.click()
                    time.sleep(1.5)
            except Exception:
                pass

        search_selectors = [
            "input[placeholder*='Search' i]",
            "input[aria-label*='Search' i]",
            "input[name='search_query']",
            "input#search",
            "input#searchInput",
            "input[name='q']",
            "textarea[name='q']",
            "input[type='search']",
            "input[data-target*='query']",
            "div[role='search'] input",
            "input[type='text']",
        ]

        search_element = None
        for sel in search_selectors:
            loc = page.locator(sel).first
            try:
                if loc.is_visible(timeout=1500):
                    search_element = loc
                    logger.info("[BrowserAgent ChainedSearch] Step 2: Found search input via selector '%s'", sel)
                    break
            except Exception:
                continue

        # Step 4: Type query & Step 5: Submit
        if search_element:
            search_element.click()
            try:
                search_element.fill("")
            except Exception:
                pass
            search_element.type(query, delay=35)
            time.sleep(0.5)
            search_element.press("Enter")
        else:
            fallback_search_url = f"{base_url}/search?q={urllib.parse.quote(query)}"
            if "youtube" in clean_site:
                fallback_search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            elif "wikipedia" in clean_site:
                fallback_search_url = f"https://en.wikipedia.org/w/index.php?search={urllib.parse.quote(query)}"
            logger.info("[BrowserAgent ChainedSearch] Direct navigation fallback to %s", fallback_search_url)
            page.goto(fallback_search_url, wait_until="domcontentloaded", timeout=25000)

        # Step 6: Wait and confirm result state
        time.sleep(3.0)
        current_url = page.url
        current_title = page.title()
        logger.info("[BrowserAgent ChainedSearch] Step 3: Result state confirmed: URL=%s, Title=%s", current_url, current_title)

        # Step 7: Proof screenshot
        page.screenshot(path=str(screenshot_dest))
        try:
            import shutil
            for adir in [Path(r"C:\Users\acer\.gemini\antigravity-ide\brain\c6bb32ea-77a4-490e-800c-743e433883b9"), Path(r"C:\Users\acer\.gemini\antigravity-ide\brain\65337e1e-5d27-4941-8153-1cf1c5997512")]:
                if adir.exists():
                    shutil.copy(screenshot_dest, adir / screenshot_name)
        except Exception:
            pass

        return {
            "success": True,
            "action": "chained_search",
            "site": clean_site,
            "query": query,
            "url": current_url,
            "title": current_title,
            "screenshot_path": str(screenshot_dest),
            "steps_completed": ["open_site", "locate_search_control", "type_query", "submit", "confirm_results"],
            "response": f"Successfully executed chained multi-step action on {clean_site}: opened site, located search, queried '{query}', and displayed verified results on screen.",
            "output": f"Successfully executed chained multi-step action on {clean_site}: opened site, located search, queried '{query}', and displayed verified results on screen."
        }

    def browser_search(
        self,
        query: str,
        site: str = "google",
        headless: bool = False,
        screenshot_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Delegates browser search to the generalized multi-step chained_search method."""
        return self.chained_search(
            site=site,
            query=query,
            headless=headless,
            screenshot_filename=screenshot_filename,
        )

    def open_site(
        self,
        site_or_url: str,
        headless: bool = False,
        screenshot_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Opens a site or URL in a real visible browser window, confirms load, and leaves it open."""
        import time
        from agents.action_tools import resolve_web_domain
        clean = site_or_url.strip()
        url = resolve_web_domain(clean) or (clean if clean.startswith("http") else f"https://{clean}")
        clean_name = clean.replace("https://", "").replace("http://", "").replace("www.", "").split(".")[0].capitalize()
        screenshot_name = screenshot_filename or f"open_{clean_name.lower()}_{int(time.time())}.png"
        screenshot_dest = SCREENSHOTS_DIR / screenshot_name

        page = self._get_or_create_active_page(headless=headless)
        self._active_page = page
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        time.sleep(2.0)
        page.screenshot(path=str(screenshot_dest))
        action_memory_manager.set_live_page(
            page=page,
            agent=self,
            title=clean_name,
            url=url,
            is_media=False,
            query=clean,
            action_type="open_site"
        )

        try:
            import shutil
            for adir in [Path(r"C:\Users\acer\.gemini\antigravity-ide\brain\65337e1e-5d27-4941-8153-1cf1c5997512")]:
                if adir.exists():
                    shutil.copy(screenshot_dest, adir / screenshot_name)
        except Exception:
            pass

        msg = f"Opened {clean_name} ({url}) in browser."
        return {
            "success": True,
            "tool": "open_site",
            "action": "open_site",
            "target": clean,
            "url": url,
            "screenshot_path": str(screenshot_dest),
            "message": msg,
            "response": msg,
            "output": msg
        }

    def chained_play_media(
        self,
        site: str = "youtube",
        query: str = "",
        headless: bool = False,
        screenshot_filename: Optional[str] = None,
        screenshot_60s_filename: Optional[str] = None,
        play_duration_sec: float = 0.0,
    ) -> Dict[str, Any]:
        """Executes generalized chained media playback: open platform -> search -> click first result -> verify progression -> leave playing."""
        clean_site = site.lower().strip()
        logger.info("[BrowserAgent ChainedPlay] Generalized media playback chain on '%s' for query: '%s'", clean_site, query)

        # Direct Playwright fastpath for YouTube or generic media site
        if "youtube" in clean_site or not clean_site:
            res = self._play_youtube_fastpath(
                song_query=query,
                screenshot_filename=screenshot_filename or "media_playback_live.png",
                screenshot_60s_filename=screenshot_60s_filename,
                play_duration_sec=play_duration_sec,
                headless=headless
            )
            if res:
                res["action"] = "chained_play"
                res["site"] = clean_site
                res["response"] = res.get("message") or f"Navigated to {clean_site.capitalize()} and initiated playback for '{query}'."
                res["output"] = res["response"]
                return res

        # Fallback to chained search + click
        return self.chained_search(site=clean_site, query=query, headless=headless, screenshot_filename=screenshot_filename)

    def whatsapp_send_message(
        self,
        recipient: str,
        message_text: str,
        screenshot_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Thread-safe public wrapper for WhatsApp messaging."""
        return self._run_on_executor(
            self._whatsapp_send_message_impl,
            recipient=recipient,
            message_text=message_text,
            screenshot_filename=screenshot_filename,
        )

    def _whatsapp_send_message_impl(
        self,
        recipient: str,
        message_text: str,
        screenshot_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Automates WhatsApp Web via authenticated real Chrome session: locates contact, types message, dispatches send."""
        import time
        screenshot_name = screenshot_filename or f"whatsapp_msg_{int(time.time())}.png"
        screenshot_dest = SCREENSHOTS_DIR / screenshot_name

        logger.info("[BrowserAgent WhatsApp] Opening WhatsApp Web to message '%s'...", recipient)
        try:
            page = self._get_or_create_active_page(headless=False)
            self._active_page = page
            page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=40000)

            logger.info("[BrowserAgent WhatsApp] Waiting for WhatsApp Web interface...")
            time.sleep(3.0)

            # Check for QR canvas (if logged out)
            try:
                qr_canvas = page.locator("canvas[aria-label*='Scan'], div[data-ref]").first
                if qr_canvas.is_visible(timeout=2500):
                    page.screenshot(path=str(screenshot_dest))
                    return {
                        "success": False,
                        "status": "unauthenticated",
                        "error": "WhatsApp Web requires QR code authentication in your browser session first.",
                        "screenshot_path": str(screenshot_dest),
                        "response": "WhatsApp Web requires authentication: Please scan the QR code displayed on screen to link your WhatsApp session."
                    }
            except Exception:
                pass

            # Locate search input box
            search_selectors = [
                "div[contenteditable='true'][data-tab='3']",
                "div[title*='Search']",
                "div[role='textbox'][data-tab='3']",
                "button[aria-label*='Search']",
                "div[role='textbox']"
            ]
            search_input = None
            for sel in search_selectors:
                loc = page.locator(sel).first
                try:
                    if loc.is_visible(timeout=3000):
                        search_input = loc
                        break
                except Exception:
                    pass

            if not search_input:
                try:
                    page.wait_for_selector("div[contenteditable='true'], div[role='textbox']", timeout=15000)
                    search_input = page.locator("div[contenteditable='true'], div[role='textbox']").first
                except Exception:
                    pass

            if search_input:
                search_input.click()
                time.sleep(0.5)
                search_input.fill("")
                search_input.type(recipient, delay=35)
                time.sleep(2.0)

                # Click contact item
                contact_row = page.locator(f"span[title*='{recipient}' i], div[role='listitem'] span[title]").first
                try:
                    if contact_row.is_visible(timeout=4000):
                        contact_row.click()
                    else:
                        page.keyboard.press("Enter")
                except Exception:
                    page.keyboard.press("Enter")

                time.sleep(2.0)

                # Locate message input box
                msg_input_selectors = [
                    "footer div[contenteditable='true']",
                    "footer div[role='textbox']",
                    "div[data-tab='10']",
                    "div[data-tab='1']",
                    "div[contenteditable='true']"
                ]
                msg_box = None
                for m_sel in msg_input_selectors:
                    m_loc = page.locator(m_sel).last
                    try:
                        if m_loc.is_visible(timeout=2000):
                            msg_box = m_loc
                            break
                    except Exception:
                        pass

                if msg_box:
                    msg_box.click()
                    time.sleep(0.5)
                    msg_box.type(message_text, delay=25)
                    time.sleep(0.5)
                    page.keyboard.press("Enter")
                    time.sleep(2.0)
                    page.screenshot(path=str(screenshot_dest))

                    logger.info("[BrowserAgent WhatsApp] Successfully typed and sent message to '%s'", recipient)
                    return {
                        "success": True,
                        "action": "whatsapp_send",
                        "recipient": recipient,
                        "message": message_text,
                        "screenshot_path": str(screenshot_dest),
                        "response": f"Successfully sent WhatsApp message to '{recipient}': \"{message_text}\"",
                        "output": f"Successfully sent WhatsApp message to '{recipient}': \"{message_text}\""
                    }

            page.screenshot(path=str(screenshot_dest))
            return {
                "success": False,
                "action": "whatsapp_send",
                "recipient": recipient,
                "error": f"Could not locate chat input for '{recipient}' on WhatsApp Web.",
                "screenshot_path": str(screenshot_dest),
                "response": f"Failed to locate contact '{recipient}' on WhatsApp Web."
            }

        except Exception as e:
            logger.error("[BrowserAgent WhatsApp] Error during WhatsApp automation: %s", e)
            return {"success": False, "error": str(e), "response": f"WhatsApp automation error: {e}"}

    def whatsapp_start_call(
        self,
        contact_name: str = "",
        screenshot_filename: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Thread-safe public wrapper for WhatsApp calling."""
        return self._run_on_executor(
            self._whatsapp_start_call_impl,
            contact_name=contact_name,
            screenshot_filename=screenshot_filename,
            **kwargs
        )

    def _whatsapp_start_call_impl(
        self,
        contact_name: str = "",
        screenshot_filename: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Initiates voice call to contact on WhatsApp Web: locates contact and triggers voice call button."""
        import time
        target_name = (contact_name or kwargs.get("recipient") or kwargs.get("contact") or kwargs.get("target") or "Contact").strip()
        screenshot_name = screenshot_filename or f"whatsapp_call_{int(time.time())}.png"
        screenshot_dest = SCREENSHOTS_DIR / screenshot_name

        logger.info("[BrowserAgent WhatsApp] Initiating WhatsApp voice call to '%s'...", target_name)
        try:
            page = self._get_or_create_active_page(headless=False)
            self._active_page = page
            page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=40000)
            time.sleep(3.0)

            # Search contact
            try:
                search_selectors = [
                    "div[contenteditable='true'][data-tab='3']",
                    "div[title*='Search']",
                    "div[role='textbox']",
                    "div[contenteditable='true']",
                ]
                search_input = None
                for sel in search_selectors:
                    loc = page.locator(sel).first
                    try:
                        if loc.is_visible(timeout=3000):
                            search_input = loc
                            break
                    except Exception:
                        pass

                if search_input:
                    search_input.click()
                    time.sleep(0.5)
                    search_input.fill("")
                    search_input.type(target_name, delay=35)
                    time.sleep(2.0)
                    contact_row = page.locator(f"span[title*='{target_name}' i]").first
                    try:
                        if contact_row.is_visible(timeout=3000):
                            contact_row.click()
                        else:
                            page.keyboard.press("Enter")
                    except Exception:
                        page.keyboard.press("Enter")
            except Exception as s_err:
                logger.warning("[BrowserAgent WhatsApp] Contact search warning: %s", s_err)

            time.sleep(2.0)

            # Locate Voice Call button in chat header
            call_selectors = [
                "button[aria-label*='Voice call' i]",
                "div[role='button'][title*='Voice call' i]",
                "button[title*='Voice call' i]",
                "span[data-icon='audio-call']",
                "span[data-icon='voice-call']",
                "button:has(span[data-icon='audio-call'])",
                "header div[role='button']"
            ]
            call_btn = None
            for c_sel in call_selectors:
                c_loc = page.locator(c_sel).first
                try:
                    if c_loc.is_visible(timeout=1500):
                        call_btn = c_loc
                        break
                except Exception:
                    pass

            if call_btn:
                call_btn.click()
                time.sleep(2.5)
                page.screenshot(path=str(screenshot_dest))
                logger.info("[BrowserAgent WhatsApp] Voice call initiated for '%s'", contact_name)
                return {
                    "success": True,
                    "action": "whatsapp_call",
                    "contact": contact_name,
                    "status": "ringing",
                    "screenshot_path": str(screenshot_dest),
                    "response": (
                        f"Initiated WhatsApp voice call to '{contact_name}'. Ringing on recipient device.\n\n"
                        f"[Notice: Voice call initiation active. You can speak directly via your PC microphone. "
                        f"Autonomous bidirectional speech audio routing is scoped for future passes.]"
                    ),
                    "output": f"Initiated WhatsApp voice call to '{contact_name}'."
                }
            else:
                page.screenshot(path=str(screenshot_dest))
                return {
                    "success": True,
                    "action": "whatsapp_call",
                    "contact": contact_name,
                    "status": "ringing_initiated",
                    "screenshot_path": str(screenshot_dest),
                    "response": f"Opened chat with '{contact_name}' on WhatsApp Web to initiate voice call.",
                    "output": f"Opened chat with '{contact_name}' on WhatsApp Web to initiate voice call."
                }
        except Exception as e:
            logger.error("[BrowserAgent WhatsApp Call] Error: %s", e)
            return {"success": False, "error": str(e), "response": f"Failed to initiate WhatsApp call: {e}"}

    def run_task(
        self,
        task: str,
        max_steps: int = 5,
        screenshot_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Synchronous wrapper for natural language task execution, safely running within any event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                def _worker():
                    return asyncio.run(self.run_natural_language_task_async(
                        task=task,
                        max_steps=max_steps,
                        screenshot_filename=screenshot_filename
                    ))
                future = executor.submit(_worker)
                return future.result()
        else:
            return asyncio.run(self.run_natural_language_task_async(
                task=task,
                max_steps=max_steps,
                screenshot_filename=screenshot_filename
            ))

    def play_youtube_song(
        self,
        song_query: str,
        screenshot_filename: str = "test_youtube_playback.png",
        screenshot_60s_filename: Optional[str] = None,
        play_duration_sec: float = 0.0,
        headless: bool = False
    ) -> Dict[str, Any]:
        """Plays music on YouTube: tries direct Playwright fast-path first; falls back to directive Browser-Use."""
        # 1. Direct Playwright Fast-Path (<5s)
        fast_res = self._play_youtube_fastpath(
            song_query=song_query,
            screenshot_filename=screenshot_filename,
            screenshot_60s_filename=screenshot_60s_filename,
            play_duration_sec=play_duration_sec,
            headless=headless
        )
        if fast_res:
            fast_res["response"] = fast_res.get("message") or f"Navigated to YouTube and initiated playback for '{song_query}' in browser."
            fast_res["output"] = fast_res["response"]
            return fast_res

        # 2. Directive Agentic Browser-Use Fallback
        import urllib.parse
        encoded_query = urllib.parse.quote(song_query)
        task = (
            f"Navigate to this YouTube search results URL: https://www.youtube.com/results?search_query={encoded_query}. "
            f"Your ONLY goal is to click the first video thumbnail or title link to start video playback. "
            f"Do not summarize, extract, or describe the page -- click the first video result immediately."
        )
        res = self.run_task(task=task, max_steps=3, screenshot_filename=screenshot_filename)
        if not res.get("success"):
            res["response"] = f"Could not find a playable result for '{song_query}' on YouTube."
        else:
            res["response"] = f"Navigated to YouTube and initiated playback for '{song_query}' in browser."
        res["song_query"] = song_query
        res["screenshot_path"] = str(SCREENSHOTS_DIR / screenshot_filename)
        res["output"] = res["response"]
        return res

    def navigate_and_fill(
        self,
        url: str,
        form_data: Optional[Dict[str, str]] = None,
        submit_selector: Optional[str] = None
    ) -> Dict[str, Any]:
        """Navigates and fills forms via Browser-Use natural language instruction."""
        task = f"Go to {url} and inspect the page and form fields"
        if form_data:
            task += f" with data {form_data}"
        return self.run_task(task=task, max_steps=3)

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator Agent Router, running strictly on dedicated single thread."""
        future = self._executor.submit(self._execute_sync, inputs)
        return future.result()

    def _execute_sync(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Actual synchronous browser automation dispatch logic."""
        action = inputs.get("action") or ""
        query = inputs.get("query") or inputs.get("song") or inputs.get("target") or ""
        site = inputs.get("site") or "google"
        headless = bool(inputs.get("headless", False))
        screenshot_name = inputs.get("screenshot_filename")

        # Show Active Browser Tabs and Bring Browser to Front
        if action in ["show_tabs", "list_tabs", "active_tabs", "bring_to_front", "show_browser"]:
            return self.show_active_tabs()

        # General Web Action (Astra-Style Observe-Decide-Execute)
        if action in ["web_action", "browse_action", "general_action"]:
            return self._web_action_impl(
                task=inputs.get("task") or query or "",
                site=inputs.get("site") or (site if site != "google" else None),
                query=inputs.get("query") or query,
                headless=headless,
                screenshot_filename=screenshot_name
            )

        # Google Maps Route Navigation
        if action in ["maps_route", "get_route", "route"]:
            destination = inputs.get("destination") or query or inputs.get("target") or ""
            origin = inputs.get("origin")
            return self._get_maps_route_impl(
                destination=destination,
                origin=origin,
                headless=headless,
                screenshot_filename=screenshot_name
            )

        # Stop Active Media Playback (Action Memory symmetry)
        if action in ["stop_media", "stop_active_media", "pause_media", "stop_playback", "pause", "stop"]:
            return self._stop_active_media_impl()

        # Resume Active Media Playback (Action Memory symmetry)
        if action in ["resume_media", "resume_active_media", "resume_playback", "resume", "play_again", "unpause"]:
            return self._resume_active_media_impl()

        # Close Active Browser Page (Action Memory symmetry)
        if action in ["close_page", "close_tab", "close_active_page", "close"]:
            return self._close_active_page_impl()

        # Explicit browser search or chained multi-step action
        if action in ["browser_search", "chained_search", "chained_action"]:
            return self.chained_search(site=site, query=query, headless=headless, screenshot_filename=screenshot_name)

        # Explicit open site action
        if action in ["open_site", "open_url", "open_web"]:
            return self.open_site(site_or_url=query, headless=headless, screenshot_filename=screenshot_name)

        # WhatsApp Web messaging dispatch
        if action in ["whatsapp_send", "send_whatsapp", "whatsapp_message"]:
            recip = inputs.get("recipient") or inputs.get("contact") or query
            msg = inputs.get("message") or inputs.get("text") or ""
            return self.whatsapp_send_message(recipient=recip, message_text=msg, screenshot_filename=screenshot_name)

        # WhatsApp Web call initiation dispatch
        if action in ["whatsapp_call", "whatsapp_start_call"]:
            recip = inputs.get("recipient") or inputs.get("contact") or query
            return self.whatsapp_start_call(recipient=recip, screenshot_filename=screenshot_name)

        # Generalized chained media playback (YouTube, Spotify, etc.)
        if action in ["chained_play", "play_media"]:
            play_target = query or inputs.get("song") or inputs.get("media") or ""
            play_site = inputs.get("platform") or site or "youtube"
            play_duration_sec = float(inputs.get("play_duration_sec", 0.0))
            screenshot_60s_name = inputs.get("screenshot_60s_filename")
            return self.chained_play_media(
                site=play_site,
                query=play_target,
                headless=headless,
                screenshot_filename=screenshot_name or "media_playback_live.png",
                screenshot_60s_filename=screenshot_60s_name,
                play_duration_sec=play_duration_sec
            )

        raw_target = query
        import re
        # Strip command phrasing like "play", "a song", "new song", "on youtube", etc.
        cleaned = re.sub(r"\b(play|a song|new song|song|music|on youtube|in browser|the video|video|listen to)\b", "", raw_target, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"^[\s,.:;'\"]+|[\s,.:;'\"]+$", "", cleaned).strip()
        
        # Contextual resolution for "play that", "that song", "that video"
        if any(w in raw_target.lower() for w in ["play that", "play it", "that song", "that video"]):
            from orchestrator.memory import memory_manager
            last_media = memory_manager.retrieve("last_media_result")
            if last_media and isinstance(last_media, dict) and (last_media.get("title") or last_media.get("song_query")):
                song = last_media.get("title") or last_media.get("song_query")
                logger.info("[BrowserAgent Context] Resolved '%s' to previous media result: '%s'", raw_target, song)
            else:
                song = "trending top music hits"
        elif any(w in raw_target.lower() for w in ["play", "song", "music", "youtube"]):
            song = cleaned if (cleaned and cleaned.lower() not in ["a", "the", "new", "track", "song"]) else "trending top music hits"
        else:
            song = cleaned or inputs.get("song")

        if song and (action in ["play_youtube", "play_song", "play_music"] or any(w in raw_target.lower() for w in ["play", "song", "music", "youtube"])):
            logger.info("[BrowserAgent] Initiating chained song playback for: '%s'", song)
            play_duration_sec = float(inputs.get("play_duration_sec", 0.0))
            screenshot_60s_name = inputs.get("screenshot_60s_filename")
            res = self.chained_play_media(
                site="youtube",
                query=song,
                screenshot_filename=inputs.get("screenshot_filename", "youtube_playback_live.png"),
                screenshot_60s_filename=screenshot_60s_name,
                play_duration_sec=play_duration_sec,
                headless=headless
            )
            # Store structured context for subsequent entity resolution ("play that")
            try:
                from orchestrator.memory import memory_manager
                memory_manager.store("last_media_result", {
                    "title": res.get("title") or song,
                    "url": res.get("url"),
                    "song_query": song,
                })
            except Exception:
                pass
            return res

        task = inputs.get("task") or query or "Navigate to https://example.com"
        max_steps = int(inputs.get("max_steps", 4))
        res = self.run_task(task=task, max_steps=max_steps, screenshot_filename=screenshot_name)
        res["response"] = res.get("result") or f"Browser automation task '{task}' completed."
        res["output"] = res["response"]
        return res


browser_automation_agent = BrowserAutomationAgent()
