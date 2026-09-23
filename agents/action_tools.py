"""Action & Tool Execution Layer for JARVIS.

Provides safe, generalized, structured execution for:
- OPEN_URL: Opens web URLs and named sites (Google, YouTube, etc.) in the default browser.
- OPEN_APPLICATION: Dynamically launches Windows desktop applications and URI protocols (Spotify, Camera, Chrome, etc.).
- CLOSE_APPLICATION: Safely terminates or closes processes.
- GET_CURRENT_TIME: Accurately queries live time in Asia/Kolkata (or configured timezone).

Enforces the ToolResult contract:
    success: bool
    tool: str
    action: str
    target: str
    message: str
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    duration_ms: float
"""

import os
import sys
import time
import shutil
import logging
import datetime
import subprocess
import webbrowser
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

logger = logging.getLogger("JARVIS.ActionTools")


@dataclass
class ToolResult:
    """Standardized tool execution contract."""
    success: bool
    tool: str
    action: str
    target: str
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Common Windows URI Protocol mappings for native apps
WINDOWS_PROTOCOL_MAP = {
    "spotify": "spotify:",
    "camera": "microsoft.windows.camera:",
    "calculator": "calculator:",
    "calc": "calculator:",
    "settings": "ms-settings:",
    "clock": "ms-clock:",
    "store": "ms-windows-store:",
    "photos": "ms-photos:",
    "maps": "bingmaps:",
}

# Common site name to URL mappings
COMMON_URLS = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "chatgpt": "https://chatgpt.com",
    "openai": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "groq": "https://groq.com",
    "perplexity": "https://www.perplexity.ai",
    "gemini": "https://gemini.google.com",
    "deepseek": "https://chat.deepseek.com",
    "copilot": "https://copilot.microsoft.com",
    "github": "https://github.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "reddit": "https://www.reddit.com",
    "wikipedia": "https://www.wikipedia.org",
    "gmail": "https://mail.google.com",
    "netflix": "https://www.netflix.com",
    "whatsapp": "https://web.whatsapp.com",
    "instagram": "https://www.instagram.com",
    "spotify": "https://open.spotify.com",
    "facebook": "https://www.facebook.com",
    "amazon": "https://www.amazon.com",
    "linkedin": "https://www.linkedin.com",
    "meet": "https://meet.google.com",
}


def find_windows_app_in_registry(app_name: str) -> Optional[str]:
    """Queries Windows Registry HKLM and HKCU App Paths dynamically to discover installed applications."""
    try:
        import winreg
    except ImportError:
        return None

    clean = app_name.lower().strip()
    candidates = [clean, f"{clean}.exe"]

    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    ]
    for hkey, subkey in roots:
        try:
            with winreg.OpenKey(hkey, subkey) as k:
                num_subkeys = winreg.QueryInfoKey(k)[0]
                for i in range(num_subkeys):
                    try:
                        key_name = winreg.EnumKey(k, i)
                        k_lower = key_name.lower()
                        if k_lower in candidates or k_lower == f"{clean}.exe" or k_lower.startswith(f"{clean}."):
                            with winreg.OpenKey(k, key_name) as app_k:
                                path_val = winreg.QueryValue(app_k, None)
                                if path_val:
                                    # Strip quotes if present
                                    path_val = path_val.strip('"')
                                    if os.path.exists(path_val):
                                        return path_val
                    except Exception:
                        continue
        except Exception:
            continue
    return None


def resolve_web_domain(target: str) -> Optional[str]:
    """Dynamically resolves a site name or query into a full URL using universal fuzzy matching."""
    from utils.fuzzy_matcher import normalize_query, match_app_or_site
    import re
    raw = (target or "").strip()
    # Conjunction splitting for compound requests like "chatgpt and say hi" -> "chatgpt"
    for conj in [" and ", ", then ", " then ", " with "]:
        if conj in raw.lower():
            raw = re.split(r"\s+(?:and|then|with)\s+", raw, flags=re.IGNORECASE)[0].strip()

    clean = normalize_query(raw)
    if not clean:
        clean = raw.lower().strip()

    # 1. Fuzzy match against known common URLs
    matched_site = match_app_or_site(clean, candidates=list(COMMON_URLS.keys()))
    if matched_site and matched_site in COMMON_URLS:
        return COMMON_URLS[matched_site]

    if clean in COMMON_URLS:
        return COMMON_URLS[clean]
    if clean.startswith("http://") or clean.startswith("https://"):
        return clean
    if "." in clean and " " not in clean:
        return f"https://{clean}"
    # Generalized domain resolution for named online services
    clean_alphanumeric = clean.replace(" ", "")
    if clean_alphanumeric.isalnum():
        return f"https://www.{clean_alphanumeric}.com"
    return None


def open_url(target: str) -> ToolResult:
    """Opens a website or URL in the default browser on the user's screen."""
    t0 = time.perf_counter()
    clean_target = (target or "").strip()
    if not clean_target:
        return ToolResult(
            success=False,
            tool="open_url",
            action="open_url",
            target=target,
            message="No URL or target website specified.",
            error="Target is empty",
            duration_ms=(time.perf_counter() - t0) * 1000
        )

    lower = clean_target.lower()
    
    # Strip common leading phrases like "open ", "launch ", "browse to ", "go to "
    for prefix in ["open ", "launch ", "browse to ", "go to ", "navigate to "]:
        if lower.startswith(prefix):
            lower = lower[len(prefix):].strip()
            clean_target = clean_target[len(prefix):].strip()

    # Strip trailing words like " for me", " please"
    for suffix in [" for me", " please", " on my pc", " on desktop"]:
        if lower.endswith(suffix):
            lower = lower[:-len(suffix)].strip()
            clean_target = clean_target[:-len(suffix)].strip()

    # Resolve URL dynamically
    url = resolve_web_domain(lower)
    if not url:
        url = f"https://www.google.com/search?q={clean_target}"
    display_name = clean_target.capitalize()

    try:
        logger.info("[ActionTools] Executing open_url: %s (target=%s)", url, clean_target)
        opened = webbrowser.open(url)
        # Windows OS foreground window activation
        try:
            from agents.browser_automation_agent import browser_automation_agent
            browser_automation_agent._bring_chrome_window_to_front()
        except Exception:
            pass
        duration_ms = (time.perf_counter() - t0) * 1000
        if opened:
            return ToolResult(
                success=True,
                tool="open_url",
                action="open_url",
                target=clean_target,
                message=f"Opening {display_name}.",
                data={"url": url},
                duration_ms=duration_ms
            )
        else:
            # Fallback to os.startfile on Windows
            os.startfile(url)
            try:
                from agents.browser_automation_agent import browser_automation_agent
                browser_automation_agent._bring_chrome_window_to_front()
            except Exception:
                pass
            return ToolResult(
                success=True,
                tool="open_url",
                action="open_url",
                target=clean_target,
                message=f"Opening {display_name}.",
                data={"url": url},
                duration_ms=duration_ms
            )
    except Exception as e:
        logger.error("[ActionTools] open_url failed for '%s': %s", clean_target, e)
        return ToolResult(
            success=False,
            tool="open_url",
            action="open_url",
            target=clean_target,
            message=f"Failed to open {clean_target}.",
            error=str(e),
            duration_ms=(time.perf_counter() - t0) * 1000
        )


def find_windows_shortcut_or_game(app_name: str) -> Optional[str]:
    """Scans Windows Start Menu, Desktop, and common game directories for shortcuts or executables."""
    import os
    from pathlib import Path
    clean_target = app_name.lower().strip()
    if not clean_target:
        return None

    # Priority directories for installed apps & desktop games
    search_dirs = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("ProgramData", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("USERPROFILE", "")) / "Desktop",
        Path(os.environ.get("PUBLIC", "")) / "Desktop",
    ]

    # Check shortcuts (.lnk and .url)
    for sdir in search_dirs:
        if not sdir.exists():
            continue
        try:
            for p in sdir.rglob("*.lnk"):
                stem_lower = p.stem.lower()
                if clean_target == stem_lower or clean_target in stem_lower or stem_lower in clean_target:
                    return str(p)
            for p in sdir.rglob("*.url"):
                stem_lower = p.stem.lower()
                if clean_target == stem_lower or clean_target in stem_lower or stem_lower in clean_target:
                    return str(p)
        except Exception:
            pass

    # Common game install paths (Steam, Epic, Riot, GOG, etc.)
    game_base_dirs = [
        Path(r"C:\Program Files (x86)\Steam\steamapps\common"),
        Path(r"C:\Program Files\Steam\steamapps\common"),
        Path(r"D:\SteamLibrary\steamapps\common"),
        Path(r"D:\Steam\steamapps\common"),
        Path(r"D:\Games"),
        Path(r"C:\Games"),
        Path(r"C:\Riot Games"),
        Path(r"C:\Program Files\Epic Games"),
        Path(r"C:\Program Files\GOG Galaxy\Games"),
        Path(r"D:\GOG Games"),
        Path(r"E:\Games"),
        Path(r"E:\SteamLibrary\steamapps\common"),
    ]
    for gdir in game_base_dirs:
        if not gdir.exists():
            continue
        try:
            for item in gdir.iterdir():
                if item.is_dir() and (clean_target in item.name.lower() or item.name.lower() in clean_target):
                    # Find principal executable in the game folder
                    exes = list(item.glob("*.exe"))
                    for exe in exes:
                        if not any(bad in exe.name.lower() for bad in ["crash", "unins", "setup", "update", "helper", "dxsetup"]):
                            return str(exe)
                    if exes:
                        return str(exes[0])
        except Exception:
            pass

    return None


def open_application(app_name: str) -> ToolResult:
    """Dynamically launches any application or game on Windows (generalized via Registry, Start Menu, PATH, Game Libraries, and URI protocols)."""
    t0 = time.perf_counter()
    clean_app = (app_name or "").strip()
    if not clean_app:
        return ToolResult(
            success=False,
            tool="open_application",
            action="open_application",
            target=app_name,
            message="No application name specified.",
            error="Application name is empty",
            duration_ms=(time.perf_counter() - t0) * 1000
        )

    # Conjunction splitting: extract primary app from compound phrasing ("open chatgpt and say hi" -> "chatgpt")
    import re
    for conj in [" and ", ", then ", " then ", " with "]:
        if conj in clean_app.lower():
            clean_app = re.split(r"\s+(?:and|then|with)\s+", clean_app, flags=re.IGNORECASE)[0].strip()

    from utils.fuzzy_matcher import normalize_query, match_app_or_site
    normalized = normalize_query(clean_app)
    fuzzy_name = match_app_or_site(normalized) or normalized
    lower = fuzzy_name.lower()

    # 1. Check if it is a website URL or named online service (e.g. Google, YouTube, ChatGPT, Claude)
    if lower in COMMON_URLS or lower.endswith(".com") or lower.endswith(".org") or lower.startswith("http"):
        return open_url(lower)

    # 2. Check Windows Protocol Handlers (e.g. spotify:, calculator:, steam:, minecraft:, xbox:)
    if lower in WINDOWS_PROTOCOL_MAP:
        protocol_uri = WINDOWS_PROTOCOL_MAP[lower]
        try:
            logger.info("[ActionTools] Launching Windows protocol URI: %s for app '%s'", protocol_uri, lower)
            os.startfile(protocol_uri)
            return ToolResult(
                success=True,
                tool="open_application",
                action="open_application",
                target=clean_app,
                message=f"Opening {clean_app.capitalize()}.",
                data={"uri": protocol_uri},
                duration_ms=(time.perf_counter() - t0) * 1000
            )
        except Exception as e:
            logger.warning("[ActionTools] Protocol launch failed for '%s': %s", protocol_uri, e)

    # 3. Dynamic Windows Registry App Paths discovery
    reg_app_path = find_windows_app_in_registry(lower)
    if reg_app_path:
        try:
            logger.info("[ActionTools] Launching discovered registry application: %s", reg_app_path)
            subprocess.Popen([reg_app_path], shell=True)
            return ToolResult(
                success=True,
                tool="open_application",
                action="open_application",
                target=clean_app,
                message=f"Opening {clean_app.capitalize()}.",
                data={"path": reg_app_path, "method": "registry"},
                duration_ms=(time.perf_counter() - t0) * 1000
            )
        except Exception as e:
            logger.warning("[ActionTools] Failed launching registry path '%s': %s", reg_app_path, e)

    # 4. Check system executables and PATH (Notepad, Calculator, Paint, CMD, Explorer, etc.)
    candidate_binaries = [
        lower,
        f"{lower}.exe",
    ]
    if lower == "chrome":
        candidate_binaries = ["chrome.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]
    elif lower in ["notepad", "notes"]:
        candidate_binaries = ["notepad.exe", r"C:\Windows\System32\notepad.exe"]
    elif lower in ["calc", "calculator"]:
        candidate_binaries = ["calc.exe", r"C:\Windows\System32\calc.exe"]
    elif lower in ["explorer", "file explorer"]:
        candidate_binaries = ["explorer.exe", r"C:\Windows\explorer.exe"]
    elif lower in ["terminal", "powershell"]:
        candidate_binaries = ["powershell.exe", r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"]
    elif lower in ["paint", "mspaint"]:
        candidate_binaries = ["mspaint.exe", r"C:\Windows\System32\mspaint.exe"]
    elif lower == "spotify":
        roaming = os.getenv("APPDATA", "")
        if roaming:
            candidate_binaries.append(os.path.join(roaming, "Spotify", "Spotify.exe"))

    for binary in candidate_binaries:
        resolved = shutil.which(binary) or (binary if os.path.exists(binary) else None)
        if resolved:
            try:
                logger.info("[ActionTools] Launching binary: %s", resolved)
                subprocess.Popen([resolved], shell=True)
                return ToolResult(
                    success=True,
                    tool="open_application",
                    action="open_application",
                    target=clean_app,
                    message=f"Opening {clean_app.capitalize()}.",
                    data={"binary": resolved},
                    duration_ms=(time.perf_counter() - t0) * 1000
                )
            except Exception as e:
                logger.warning("[ActionTools] Failed to launch binary '%s': %s", resolved, e)

    # 5. Check Windows Start Menu, Desktop shortcuts, and Game Libraries (Universal Games & Installed Apps)
    shortcut_match = find_windows_shortcut_or_game(clean_app)
    if shortcut_match:
        try:
            logger.info("[ActionTools] Launching discovered shortcut or game executable: %s", shortcut_match)
            os.startfile(shortcut_match)
            return ToolResult(
                success=True,
                tool="open_application",
                action="open_application",
                target=clean_app,
                message=f"Opening {clean_app.capitalize()}.",
                data={"path": shortcut_match, "method": "shortcut_or_game"},
                duration_ms=(time.perf_counter() - t0) * 1000
            )
        except Exception as e:
            logger.warning("[ActionTools] Failed launching shortcut '%s': %s", shortcut_match, e)

    # 6. Check if it resolves to a popular web application (e.g. facebook, instagram)
    web_domain = resolve_web_domain(lower)
    if web_domain and "." in web_domain:
        logger.info("[ActionTools] Application '%s' resolved to web application: %s", clean_app, web_domain)
        return open_url(lower)

    # 7. Fallback to Windows Shell `start` command via os.startfile
    try:
        logger.info("[ActionTools] Attempting Windows startfile fallback for: %s", lower)
        os.startfile(lower)
        return ToolResult(
            success=True,
            tool="open_application",
            action="open_application",
            target=clean_app,
            message=f"Opening {clean_app.capitalize()}.",
            data={"method": "startfile"},
            duration_ms=(time.perf_counter() - t0) * 1000
        )
    except Exception as e:
        logger.error("[ActionTools] Failed to launch '%s': %s", clean_app, e)
        return ToolResult(
            success=False,
            tool="open_application",
            action="open_application",
            target=clean_app,
            message=f"Could not open application '{clean_app}'.",
            error=str(e),
            duration_ms=(time.perf_counter() - t0) * 1000
        )
        return ToolResult(
            success=False,
            tool="open_application",
            action="open_application",
            target=clean_app,
            message=f"Could not open application '{clean_app}'.",
            error=str(e),
            duration_ms=(time.perf_counter() - t0) * 1000
        )


def close_application(app_name: str) -> ToolResult:
    """Closes an active process on Windows using universal fuzzy matching and article stripping."""
    t0 = time.perf_counter()
    from utils.fuzzy_matcher import normalize_query, match_app_or_site, calculate_similarity
    clean_app = normalize_query(app_name or "")
    if clean_app.endswith(".exe"):
        clean_app = clean_app[:-4]

    import psutil
    if clean_app in ["active", "the application", "application", "the app", "app", "this", "it", "this window", "active window"]:
        try:
            import win32gui
            import win32process
            fg = win32gui.GetForegroundWindow()
            if fg:
                _, pid = win32process.GetWindowThreadProcessId(fg)
                if pid:
                    proc = psutil.Process(pid)
                    p_name = proc.name()
                    proc.terminate()
                    return ToolResult(
                        success=True,
                        tool="close_application",
                        action="close_application",
                        target=p_name,
                        message=f"Closed active application '{p_name}'.",
                        data={"closed_count": 1, "pid": pid},
                        duration_ms=(time.perf_counter() - t0) * 1000
                    )
        except Exception:
            pass

    fuzzy_name = match_app_or_site(clean_app)
    target_names = [clean_app]
    if fuzzy_name and fuzzy_name not in target_names:
        target_names.append(fuzzy_name)
    if "chrome" in target_names or clean_app == "chrome":
        target_names.extend(["chrome", "chrome.exe"])

    closed_count = 0

    try:
        for p in psutil.process_iter(['pid', 'name']):
            p_name = (p.info.get('name') or "").lower()
            p_base = p_name[:-4] if p_name.endswith(".exe") else p_name
            matched = any(t == p_name or t == p_base or t in p_name for t in target_names)
            if not matched:
                matched = any(calculate_similarity(t, p_base) >= 0.85 for t in target_names)
            if matched:
                p.terminate()
                closed_count += 1
        
        if closed_count > 0:
            return ToolResult(
                success=True,
                tool="close_application",
                action="close_application",
                target=app_name,
                message=f"Closed {app_name} ({closed_count} process(es) terminated).",
                data={"closed_count": closed_count},
                duration_ms=(time.perf_counter() - t0) * 1000
            )
        else:
            return ToolResult(
                success=False,
                tool="close_application",
                action="close_application",
                target=app_name,
                message=f"No running process found for '{app_name}'.",
                error="Process not found",
                duration_ms=(time.perf_counter() - t0) * 1000
            )
    except Exception as e:
        return ToolResult(
            success=False,
            tool="close_application",
            action="close_application",
            target=app_name,
            message=f"Failed to close '{app_name}'.",
            error=str(e),
            duration_ms=(time.perf_counter() - t0) * 1000
        )


def get_current_time(timezone_str: str = "Asia/Kolkata") -> ToolResult:
    """Returns real authoritative current time in the configured timezone (Asia/Kolkata)."""
    t0 = time.perf_counter()
    try:
        tz = None
        if ZoneInfo is not None:
            try:
                tz = ZoneInfo(timezone_str)
            except Exception:
                tz = None

        if tz is None:
            import pytz
            tz = pytz.timezone(timezone_str)

        now = datetime.datetime.now(tz)
        formatted_time = now.strftime("%I:%M %p").lstrip("0")
        formatted_date = now.strftime("%A, %d %B %Y")
        readable = f"The current time is {formatted_time} IST on {formatted_date}."

        return ToolResult(
            success=True,
            tool="get_current_time",
            action="get_current_time",
            target=timezone_str,
            message=readable,
            data={
                "time_12h": formatted_time,
                "date": formatted_date,
                "timezone": timezone_str,
                "iso": now.isoformat()
            },
            duration_ms=(time.perf_counter() - t0) * 1000
        )
    except Exception as e:
        # Fallback to local system time
        now = datetime.datetime.now()
        formatted_time = now.strftime("%I:%M %p").lstrip("0")
        formatted_date = now.strftime("%A, %d %B %Y")
        readable = f"The current time is {formatted_time} on {formatted_date}."
        return ToolResult(
            success=True,
            tool="get_current_time",
            action="get_current_time",
            target="local",
            message=readable,
            data={"time_12h": formatted_time, "date": formatted_date},
            duration_ms=(time.perf_counter() - t0) * 1000
        )
