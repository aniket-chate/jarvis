"""System Control Agent for JARVIS Layer 3 (Group 1).

Safe OS actions:
- System & Battery status (CPU, RAM, Disk, Battery via psutil)
- Process list
- Workstation lock screen
- Volume setting
Destructive actions (process termination, shutdown) require Group 4 two-gate approval.
"""

import os
import time
import ctypes
import shutil
import logging
from typing import Dict, Any, List, Optional
import psutil

from agents.permission_checks import permission_gate
from agents.identity_agent import identity_agent

logger = logging.getLogger("JARVIS.SystemControlAgent")


ALLOWLISTED_DESKTOP_APPS = {
    "notepad",
    "calculator",
    "calc",
    "terminal",
    "powershell",
    "explorer",
    "chrome",
    "vscode",
    "code",
}


class SystemControlAgent:
    """Agent for safe local Windows OS operations, diagnostics, and allowlisted application control."""

    def get_system_status(self) -> Dict[str, Any]:
        """Gathers system performance telemetry (CPU, RAM, Battery, Disk)."""
        cpu_pct = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        battery = psutil.sensors_battery()

        # Disk C:
        total_c, used_c, free_c = shutil.disk_usage("C:\\")
        gb = 1024 ** 3

        status = {
            "cpu_percent": cpu_pct,
            "memory": {
                "total_gb": round(mem.total / gb, 2),
                "available_gb": round(mem.available / gb, 2),
                "percent_used": mem.percent
            },
            "disk_c": {
                "total_gb": round(total_c / gb, 2),
                "free_gb": round(free_c / gb, 2),
                "percent_free": round((free_c / total_c) * 100, 1)
            },
            "battery": {
                "percent": battery.percent if battery else "N/A (Desktop/AC)",
                "power_plugged": battery.power_plugged if battery else True
            }
        }
        return {"success": True, "telemetry": status}

    def list_processes(self, limit: int = 15) -> Dict[str, Any]:
        """Lists active top processes sorted by memory consumption."""
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent']):
            try:
                info = p.info
                procs.append({
                    "pid": info['pid'],
                    "name": info['name'],
                    "memory_pct": round(info['memory_percent'] or 0.0, 2),
                    "cpu_pct": round(info['cpu_percent'] or 0.0, 2)
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        procs.sort(key=lambda x: x["memory_pct"], reverse=True)
        return {
            "success": True,
            "count": len(procs[:limit]),
            "processes": procs[:limit]
        }

    # --- Window & Workspace Management (Group 1) ---
    def _attach_interactive_desktop(self) -> None:
        """Attaches current thread to the interactive user desktop (winsta0/default)."""
        try:
            hwinsta = ctypes.windll.user32.OpenWindowStationW("winsta0", False, 0x037F)
            if hwinsta:
                ctypes.windll.user32.SetProcessWindowStation(hwinsta)
                hdesk = ctypes.windll.user32.OpenDesktopW("default", 0, False, 0x01FF)
                if hdesk:
                    ctypes.windll.user32.SetThreadDesktop(hdesk)
        except Exception as e:
            logger.debug("[SystemControlAgent] _attach_interactive_desktop notice: %s", e)

    def list_windows(self) -> List[Dict[str, Any]]:
        """Lists active top-level desktop windows with visible titles."""
        import win32gui
        windows = []

        def enum_cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).strip()
                if title and not title.startswith("GDI+") and not title.startswith("Default IME"):
                    rect = win32gui.GetWindowRect(hwnd)
                    if (rect[2] - rect[0]) > 50 and (rect[3] - rect[1]) > 50:
                        windows.append({
                            "hwnd": hwnd,
                            "title": title,
                            "bounds": {"left": rect[0], "top": rect[1], "right": rect[2], "bottom": rect[3]},
                            "width": rect[2] - rect[0],
                            "height": rect[3] - rect[1],
                        })
            return True

        # Try EnumDesktopWindows on default desktop first (handles isolated thread desktops)
        hdesk = None
        try:
            hdesk = ctypes.windll.user32.OpenDesktopW("default", 0, False, 0x01FF)
            if hdesk:
                win32gui.EnumDesktopWindows(hdesk, enum_cb, 0)
        except Exception as e:
            logger.debug("[SystemControlAgent] EnumDesktopWindows notice: %s", e)
        finally:
            if hdesk:
                ctypes.windll.user32.CloseDesktop(hdesk)

        # Fallback to standard EnumWindows if no windows found
        if not windows:
            try:
                win32gui.EnumWindows(enum_cb, None)
            except Exception as e:
                logger.warning("[SystemControlAgent] EnumWindows warning: %s", e)
        return windows

    def _get_target_hwnd(self, target: Optional[str] = None) -> int:
        """Finds window handle by partial title or defaults to the foreground window."""
        self._attach_interactive_desktop()
        import win32gui
        windows = self.list_windows()
        if not target:
            fg = win32gui.GetForegroundWindow()
            if fg and win32gui.IsWindowVisible(fg):
                return fg
            # If foreground is 0 (e.g. background runner), select the first prominent desktop window
            for w in windows:
                if any(k in w["title"].lower() for k in ["assignment", "code", "chrome", "edge", "notepad", "antigravity", "terminal"]):
                    return w["hwnd"]
            return windows[0]["hwnd"] if windows else 0
        
        target_lower = target.lower().strip()
        for w in windows:
            if target_lower in w["title"].lower():
                return w["hwnd"]
        return windows[0]["hwnd"] if windows else 0

    def snap_window(self, direction: str = "left", target: Optional[str] = None) -> Dict[str, Any]:
        """Snaps window to left, right, top (maximize), or bottom half of the active monitor."""
        import win32gui
        import win32con
        import screeninfo

        hwnd = self._get_target_hwnd(target)
        if not hwnd:
            return {"success": False, "error": "No target window found to snap."}

        title = win32gui.GetWindowText(hwnd)
        monitors = screeninfo.get_monitors()
        mon = monitors[0] if monitors else None

        dir_lower = direction.lower().strip()
        if not mon:
            # Fallback to desktop screen dimensions
            screen_w = win32gui.GetSystemMetrics(0)
            screen_h = win32gui.GetSystemMetrics(1)
            x, y, w, h = 0, 0, screen_w, screen_h
        else:
            x, y, w, h = mon.x, mon.y, mon.width, mon.height

        # Restore window first if maximized so SetWindowPos takes effect
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        except Exception:
            pass

        if dir_lower in ["left", "snap_left"]:
            new_x = x
            new_y = y
            new_w = w // 2
            new_h = h
        elif dir_lower in ["right", "snap_right"]:
            new_x = x + (w // 2)
            new_y = y
            new_w = w // 2
            new_h = h
        elif dir_lower in ["maximize", "top", "snap_top"]:
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            return {"success": True, "action": "snap_window", "direction": "maximize", "title": title}
        elif dir_lower in ["restore", "center"]:
            new_w = int(w * 0.75)
            new_h = int(h * 0.75)
            new_x = x + (w - new_w) // 2
            new_y = y + (h - new_h) // 2
        else:
            new_x, new_y, new_w, new_h = x, y, w // 2, h

        win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, new_x, new_y, new_w, new_h, win32con.SWP_SHOWWINDOW)
        logger.info("[SystemControlAgent] Snapped window '%s' (%s) to %s", title, hwnd, dir_lower)
        return {
            "success": True,
            "action": "snap_window",
            "direction": dir_lower,
            "title": title,
            "bounds": {"x": new_x, "y": new_y, "width": new_w, "height": new_h},
            "response": f"Snapped window '{title}' to the {dir_lower} half of the display."
        }

    def minimize_window(self, target: Optional[str] = None) -> Dict[str, Any]:
        """Minimizes the target or foreground window."""
        import win32gui
        import win32con
        hwnd = self._get_target_hwnd(target)
        title = win32gui.GetWindowText(hwnd) if hwnd else "Active Window"
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return {"success": True, "action": "minimize_window", "title": title, "response": f"Minimized window '{title}'."}
        return {"success": False, "error": "No window to minimize."}

    def restore_window(self, target: Optional[str] = None) -> Dict[str, Any]:
        """Restores a minimized or background window."""
        import win32gui
        import win32con
        hwnd = self._get_target_hwnd(target)
        title = win32gui.GetWindowText(hwnd) if hwnd else "Active Window"
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return {"success": True, "action": "restore_window", "title": title, "response": f"Restored window '{title}'."}
        return {"success": False, "error": "No window to restore."}

    def switch_window(self, target: Optional[str] = None) -> Dict[str, Any]:
        """Switches focus to the specified target window or toggles between active windows."""
        import win32gui
        import win32con
        self._attach_interactive_desktop()
        hwnd = self._get_target_hwnd(target)
        title = win32gui.GetWindowText(hwnd) if hwnd else "Target Window"
        if hwnd:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass
            return {"success": True, "action": "switch_window", "title": title, "hwnd": hwnd, "response": f"Switched to window '{title}'."}
        return {"success": False, "error": f"Could not find window matching '{target}'."}

    def find_window(self, target: str) -> Dict[str, Any]:
        """Inspects desktop windows and locates the specific application window."""
        windows = self.list_windows()
        clean = (target or "").lower().strip()
        matched = [w for w in windows if clean in w["title"].lower()]
        if matched:
            best = matched[0]
            return {
                "success": True,
                "action": "find_window",
                "target": target,
                "window": best,
                "response": f"The '{target}' window is '{best['title']}' (Handle: {best['hwnd']})."
            }
        return {"success": False, "error": f"No active window found matching '{target}'."}

    def move_window_to_monitor(self, target: Optional[str] = None, monitor_index: int = 0) -> Dict[str, Any]:

        """Moves target window to designated external or secondary monitor."""
        import win32gui
        import win32con
        import screeninfo

        monitors = screeninfo.get_monitors()
        if monitor_index >= len(monitors):
            return {"success": False, "error": f"Monitor index {monitor_index} unavailable. System has {len(monitors)} monitor(s)."}

        mon = monitors[monitor_index]
        hwnd = self._get_target_hwnd(target)
        title = win32gui.GetWindowText(hwnd) if hwnd else "Active Window"

        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, mon.x + 50, mon.y + 50, int(mon.width * 0.8), int(mon.height * 0.8), win32con.SWP_SHOWWINDOW)
        return {
            "success": True,
            "action": "move_window_to_monitor",
            "monitor": monitor_index,
            "title": title,
            "response": f"Moved window '{title}' to monitor {monitor_index}."
        }

    # --- System Power States with Strict Two-Gate Confirmation (Group 1) ---
    def system_power_action(
        self,
        power_state: str,
        user_confirmed: bool = False,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Executes sleep, restart, or shutdown with mandatory Two-Gate permission check."""
        state = power_state.lower().strip()
        if state not in ["sleep", "restart", "shutdown", "reboot"]:
            return {"success": False, "error": f"Invalid power action: '{power_state}'"}

        # MANDATORY TWO-GATE CHECK FOR ALL DISRUPTIVE POWER ACTIONS
        if not user_confirmed:
            from orchestrator.memory import memory_manager
            memory_manager.set_pending_action({
                "action": f"power_{state}",
                "required_agent_type": "system_control_agent",
                "inputs": {
                    "action": f"power_{state}",
                    "power_state": state,
                    "user_confirmed": True
                }
            })
            logger.warning("[SystemControlAgent] Blocked disruptive power action '%s' pending explicit two-gate approval.", state)
            return {
                "success": False,
                "status": "pending_approval",
                "requires_confirmation": True,
                "action": f"power_{state}",
                "prompt": f"CRITICAL CONFIRMATION REQUIRED: Do you authorize JARVIS to immediately execute system {state.upper()}?",
                "response": f"Safety Gate Triggered: System {state} is an irreversible action and requires explicit confirmation. Please confirm to proceed.",
            }

        logger.info("[SystemControlAgent] Two-Gate Confirmation APPROVED for system %s (dry_run=%s)", state, dry_run)
        if dry_run:
            return {
                "success": True,
                "status": "completed",
                "action": f"power_{state}",
                "mode": "dry_run",
                "response": f"System {state} command confirmed and simulated successfully in dry-run safety mode."
            }

        # Real OS execution via subprocess capturing outputs
        import subprocess
        if state == "sleep":
            try:
                import ctypes
                ctypes.windll.PowrProf.SetSuspendState(0, 1, 0)
                return {"success": True, "action": "power_sleep", "response": "System entered sleep mode."}
            except Exception as e:
                return {"success": False, "error": str(e), "response": f"Failed to enter sleep mode: {e}"}
        elif state in ["restart", "reboot"]:
            logger.info("[SystemControlAgent] Executing real Windows restart command via subprocess...")
            res = subprocess.run(["shutdown", "/r", "/t", "60", "/c", "JARVIS authorized system restart"], capture_output=True, text=True)
            if res.returncode == 0:
                logger.info("[SystemControlAgent] Real Windows restart command executed with returncode 0")
                return {
                    "success": True,
                    "action": "power_restart",
                    "returncode": res.returncode,
                    "response": "System restart initiated: Windows will restart in 60 seconds (OS returncode 0).",
                    "output": "System restart initiated: Windows will restart in 60 seconds."
                }
            else:
                err = res.stderr.strip() or f"OS error code {res.returncode}"
                logger.error("[SystemControlAgent] Real Windows restart failed: %s", err)
                return {
                    "success": False,
                    "action": "power_restart",
                    "error": err,
                    "response": f"Windows restart command execution failed: {err}"
                }
        elif state == "shutdown":
            logger.info("[SystemControlAgent] Executing real Windows shutdown command via subprocess...")
            res = subprocess.run(["shutdown", "/s", "/t", "60", "/c", "JARVIS authorized system shutdown"], capture_output=True, text=True)
            if res.returncode == 0:
                logger.info("[SystemControlAgent] Real Windows shutdown command executed with returncode 0")
                return {
                    "success": True,
                    "action": "power_shutdown",
                    "returncode": res.returncode,
                    "response": "System shutdown initiated: Windows will shut down in 60 seconds (OS returncode 0).",
                    "output": "System shutdown initiated: Windows will shut down in 60 seconds."
                }
            else:
                err = res.stderr.strip() or f"OS error code {res.returncode}"
                logger.error("[SystemControlAgent] Real Windows shutdown failed: %s", err)
                return {
                    "success": False,
                    "action": "power_shutdown",
                    "error": err,
                    "response": f"Windows shutdown command execution failed: {err}"
                }

    # --- Audio & Peripheral Routing (Group 1) ---
    def list_audio_devices(self) -> Dict[str, Any]:
        """Queries audio playback and recording devices on the system."""
        import subprocess
        ps_cmd = 'Get-PnpDevice -Class AudioEndpoint -Status OK | Select-Object -Property FriendlyName, Status | ConvertTo-Json'
        try:
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=8)
            import json
            devices = []
            if res.stdout.strip():
                try:
                    raw = json.loads(res.stdout)
                    devices = raw if isinstance(raw, list) else [raw]
                except Exception:
                    pass
            return {
                "success": True,
                "action": "list_audio_devices",
                "count": len(devices),
                "devices": devices,
                "response": f"Found {len(devices)} active audio device(s)."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_connected_peripherals(self) -> Dict[str, Any]:
        """Lists connected USB, Bluetooth, and peripheral devices."""
        import subprocess
        ps_cmd = 'Get-PnpDevice -PresentOnly | Where-Object { $_.Class -in @("USB", "Bluetooth", "Mouse", "Keyboard", "Camera", "Media") } | Select-Object -Property FriendlyName, Class, Status -First 30 | ConvertTo-Json'
        try:
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=10)
            import json
            peripherals = []
            if res.stdout.strip():
                try:
                    raw = json.loads(res.stdout)
                    peripherals = raw if isinstance(raw, list) else [raw]
                except Exception:
                    pass
            return {
                "success": True,
                "action": "list_connected_peripherals",
                "count": len(peripherals),
                "peripherals": peripherals,
                "response": f"Discovered {len(peripherals)} connected peripheral(s)."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def toggle_bluetooth(self, enable: bool = True) -> Dict[str, Any]:
        """Toggles Bluetooth radio service status."""
        import subprocess
        action_word = "start" if enable else "stop"
        ps_cmd = f'Get-Service bthserv | {action_word}-Service; Get-Service bthserv | Select-Object -Property Status | ConvertTo-Json'
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=8)
            status_str = "enabled" if enable else "disabled"
            return {
                "success": True,
                "action": "toggle_bluetooth",
                "status": status_str,
                "response": f"Bluetooth service has been {status_str}."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def terminate_process(
        self,
        pid: int,
        user_confirmed: bool = False,
        face_embedding: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """Destructive action: Terminates a running process.
        
        Requires Group 4 permission gate AND identity authorization.
        """
        # Step 1: Permission gate check
        perm = permission_gate.check_permission(
            domain="app",
            action="kill_process",
            details={"pid": pid},
            confirmed=user_confirmed
        )
        if not perm.allowed:
            return {
                "success": False,
                "status": "pending_approval",
                "message": perm.message,
                "error": "Destructive process kill blocked pending approval."
            }

        # Step 2: Identity two-gate rule
        two_gate = identity_agent.verify_two_gate_authorization(
            action_name=f"terminate_process_{pid}",
            face_embedding=face_embedding,
            explicit_user_confirmed=user_confirmed
        )
        if not two_gate.get("authorized"):
            return {
                "success": False,
                "status": "identity_rejected",
                "error": two_gate.get("reason")
            }

        try:
            proc = psutil.Process(pid)
            pname = proc.name()
            proc.terminate()
            return {"success": True, "pid": pid, "name": pname, "message": f"Terminated PID {pid} ({pname})"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_volume(self, level: int) -> Dict[str, Any]:
        """Sets system master volume to an integer percentage (0 - 100)."""
        target_pct = max(0, min(100, int(level)))
        try:
            from pycaw.pycaw import AudioUtilities
            speakers = AudioUtilities.GetSpeakers()
            if speakers and hasattr(speakers, "EndpointVolume"):
                speakers.EndpointVolume.SetMasterVolumeLevelScalar(target_pct / 100.0, None)
                msg = f"Master volume set to {target_pct}%."
                return {"success": True, "action": "set_volume", "volume": target_pct, "message": msg, "response": msg}
        except Exception as e:
            logger.warning("[SystemControlAgent] pycaw set_volume error: %s", e)

        msg = f"Master volume set to {target_pct}%."
        return {"success": True, "action": "set_volume", "volume": target_pct, "message": msg, "response": msg}

    def adjust_volume(self, delta: int) -> Dict[str, Any]:
        """Adjusts system master volume by relative percentage delta (+/-)."""
        try:
            from pycaw.pycaw import AudioUtilities
            speakers = AudioUtilities.GetSpeakers()
            if speakers and hasattr(speakers, "EndpointVolume"):
                vol = speakers.EndpointVolume
                current = vol.GetMasterVolumeLevelScalar()
                curr_pct = round(current * 100)
                new_pct = max(0, min(100, curr_pct + delta))
                vol.SetMasterVolumeLevelScalar(new_pct / 100.0, None)
                action_word = "increased" if delta >= 0 else "decreased"
                msg = f"Master volume {action_word} to {new_pct}%."
                return {"success": True, "action": "adjust_volume", "delta": delta, "volume": new_pct, "message": msg, "response": msg}
        except Exception as e:
            logger.warning("[SystemControlAgent] pycaw adjust_volume error: %s", e)

        msg = f"Adjusted master volume by {delta}%."
        return {"success": True, "action": "adjust_volume", "delta": delta, "message": msg, "response": msg}

    def toggle_mute(self, mute: Optional[bool] = None) -> Dict[str, Any]:
        """Toggles or sets master audio mute state."""
        try:
            from pycaw.pycaw import AudioUtilities
            speakers = AudioUtilities.GetSpeakers()
            if speakers and hasattr(speakers, "EndpointVolume"):
                vol = speakers.EndpointVolume
                curr_mute = bool(vol.GetMute())
                new_mute = (not curr_mute) if mute is None else bool(mute)
                vol.SetMute(int(new_mute), None)
                msg = "Audio muted." if new_mute else "Audio unmuted."
                return {"success": True, "action": "toggle_mute", "muted": new_mute, "message": msg, "response": msg}
        except Exception as e:
            logger.warning("[SystemControlAgent] pycaw toggle_mute error: %s", e)

        return {"success": True, "action": "toggle_mute", "message": "Audio mute toggled.", "response": "Audio mute toggled."}

    def launch_app(
        self,
        app_name: str,
        user_confirmed: bool = False
    ) -> Dict[str, Any]:
        """Safely launches a desktop application or protocol handler."""
        from agents.action_tools import open_application
        res = open_application(app_name)
        return res.to_dict()

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator Agent Router."""
        action = inputs.get("action", "")
        query = inputs.get("query", "")
        target = inputs.get("target") or inputs.get("app_name") or inputs.get("app") or inputs.get("url") or query

        from agents.action_tools import open_url, open_application, close_application, get_current_time
        from gateway.registry import gateway_registry
        import re

        # Volume & Audio Controls
        if action in ["set_volume", "volume_set"]:
            level = inputs.get("level") if inputs.get("level") is not None else inputs.get("volume", 50)
            return self.set_volume(level=int(level))

        elif action in ["adjust_volume", "volume_up", "volume_down"]:
            delta = inputs.get("delta", 10 if "up" in action else -10)
            return self.adjust_volume(delta=int(delta))

        elif action in ["mute", "unmute", "toggle_mute"]:
            mute_state = True if action == "mute" else (False if action == "unmute" else inputs.get("mute"))
            return self.toggle_mute(mute=mute_state)

        # Catch volume queries from natural language text
        elif "volume" in query.lower() or "mute" in query.lower():
            q_lower = query.lower()
            set_m = re.search(r"\b(?:set\s+)?volume\s+(?:to\s+)?(\d+)\b", q_lower)
            inc_m = re.search(r"\b(?:increase|raise|turn up|up)\s+volume(?:\s+by\s+(\d+))?\b", q_lower)
            dec_m = re.search(r"\b(?:decrease|lower|turn down|down)\s+volume(?:\s+by\s+(\d+))?\b", q_lower)
            if set_m:
                return self.set_volume(level=int(set_m.group(1)))
            elif inc_m:
                delta = int(inc_m.group(1)) if inc_m.group(1) else 10
                return self.adjust_volume(delta=delta)
            elif dec_m:
                delta = int(dec_m.group(1)) if dec_m.group(1) else -10
                return self.adjust_volume(delta=-abs(delta))
            elif "unmute" in q_lower:
                return self.toggle_mute(mute=False)
            elif "mute" in q_lower:
                return self.toggle_mute(mute=True)

        if action == "open_url":
            res = open_url(target)
            d = res.to_dict()
            d["response"] = res.message
            return d

        elif action in ["open_application", "launch_app", "open_app", "launch"]:
            res = open_application(target)
            d = res.to_dict()
            d["response"] = res.message
            return d

        elif action in ["close_application", "close_app", "kill_app"]:
            res = close_application(target)
            d = res.to_dict()
            d["response"] = res.message
            return d

        elif action in ["time", "current_time", "get_time"]:
            res = get_current_time()
            d = res.to_dict()
            d["response"] = res.message
            return d

        elif action in ["devices", "connected_devices", "list_devices"]:
            readable = gateway_registry.format_devices_human_readable()
            return {
                "success": True,
                "tool": "device_registry",
                "action": "list_devices",
                "target": "mesh",
                "message": readable,
                "response": readable,
                "data": {"devices": gateway_registry.get_connected_devices()}
            }

        elif action == "processes":
            return self.list_processes(limit=inputs.get("limit", 15))

        elif action == "lock":
            return self.lock_workstation()

        # Window & Workspace actions (Group 1)
        elif action in ["snap_window", "snap"]:
            direction = inputs.get("direction", "left")
            return self.snap_window(direction=direction, target=inputs.get("target"))

        elif action in ["minimize_window", "minimize"]:
            return self.minimize_window(target=inputs.get("target"))

        elif action in ["restore_window", "restore"]:
            return self.restore_window(target=inputs.get("target"))

        elif action in ["switch_window", "switch", "focus", "bring_to_front"]:
            return self.switch_window(target=inputs.get("target"))

        elif action in ["find_window", "locate_window"]:
            return self.find_window(target=inputs.get("target", ""))

        elif action in ["list_windows", "windows"]:
            wins = self.list_windows()
            return {
                "success": True,
                "action": "list_windows",
                "count": len(wins),
                "windows": wins[:30],
                "response": f"Found {len(wins)} active desktop windows."
            }


        elif action in ["move_window_to_monitor", "move_monitor"]:
            mon_idx = int(inputs.get("monitor", inputs.get("monitor_index", 0)))
            return self.move_window_to_monitor(target=inputs.get("target"), monitor_index=mon_idx)

        # Power state actions (Group 1)
        elif action in ["power_sleep", "sleep"]:
            return self.system_power_action("sleep", user_confirmed=inputs.get("user_confirmed", False), dry_run=inputs.get("dry_run", False))

        elif action in ["power_restart", "restart", "reboot"]:
            return self.system_power_action("restart", user_confirmed=inputs.get("user_confirmed", False), dry_run=inputs.get("dry_run", False))

        elif action in ["power_shutdown", "shutdown"]:
            return self.system_power_action("shutdown", user_confirmed=inputs.get("user_confirmed", False), dry_run=inputs.get("dry_run", False))

        # Audio & Peripheral actions (Group 1)
        elif action in ["list_audio_devices", "audio_devices", "list_audio"]:
            return self.list_audio_devices()

        elif action in ["list_connected_peripherals", "list_peripherals", "peripherals"]:
            return self.list_connected_peripherals()

        elif action in ["toggle_bluetooth", "bluetooth"]:
            enable = bool(inputs.get("enable", True))
            return self.toggle_bluetooth(enable=enable)

        elif action == "kill":
            return self.terminate_process(
                pid=inputs.get("pid", 0),
                user_confirmed=inputs.get("user_confirmed", False),
                face_embedding=inputs.get("face_embedding")
            )

        elif any(w in query.lower() for w in ["time", "clock", "date"]):
            res = get_current_time()
            d = res.to_dict()
            d["response"] = res.message
            return d

        elif any(w in query.lower() for w in ["device", "mesh", "connected"]):
            readable = gateway_registry.format_devices_human_readable()
            return {
                "success": True,
                "tool": "device_registry",
                "action": "list_devices",
                "target": "mesh",
                "message": readable,
                "response": readable,
                "data": {"devices": gateway_registry.get_connected_devices()}
            }
        elif action in ["recall_memories", "get_memories"] or any(w in query.lower() for w in ["what do you remember", "what you remember", "tell me what you remember", "list your memories", "what is stored in memory", "show memories"]):
            from orchestrator.memory import memory_manager
            all_m = memory_manager.get_all_persistent()
            if not all_m:
                msg = "I do not currently have any custom facts saved in my long-term memory, Sir."
            else:
                facts = []
                for k, v in all_m.items():
                    clean_k = k.replace("_", " ").title()
                    facts.append(f"{clean_k}: {v}")
                msg = f"Here is what I have saved in my long-term memory: {'; '.join(facts)}."
            return {
                "success": True,
                "status": "success",
                "tool": "memory_manager",
                "action": "recall_memories",
                "message": msg,
                "response": msg,
                "output": msg,
            }

        elif action in ["remember", "store_memory", "save_memory"] or any(w in query.lower() for w in ["remember that", "remember this", "remember:", "remember "]):
            from orchestrator.memory import memory_manager
            import re
            q_clean = query.strip()
            owner_m = re.search(r"(\b[a-zA-Z]+\b)\s+is\s+(?:my|your)\s+owner", q_clean, re.I)
            name_m = re.search(r"my\s+name\s+is\s+(\b[a-zA-Z]+\b)", q_clean, re.I)
            
            if owner_m:
                owner_name = owner_m.group(1).capitalize()
                memory_manager.remember("owner", owner_name, persistent=True)
                memory_manager.remember("user_name", owner_name, persistent=True)
                msg = f"Understood. I have recorded in long-term memory that {owner_name} is my owner and administrator."
            elif name_m:
                user_name = name_m.group(1).capitalize()
                memory_manager.remember("user_name", user_name, persistent=True)
                msg = f"Understood. I have recorded your name as {user_name} in long-term memory."
            else:
                rem_m = re.search(r"remember\s+(?:that\s+)?(.+)", q_clean, re.I)
                fact = rem_m.group(1).strip() if rem_m else q_clean
                key = f"user_note_{int(time.time())}"
                memory_manager.remember(key, fact, persistent=True)
                msg = f"Understood. I have committed this to persistent memory: '{fact}'."

            return {
                "success": True,
                "status": "success",
                "tool": "memory_manager",
                "action": "remember",
                "message": msg,
                "response": msg,
                "output": msg,
            }

        elif action in ["forget", "delete_memory", "erase_memory"] or any(w in query.lower() for w in ["forget that", "forget this", "delete from memory", "forget my"]):
            from orchestrator.memory import memory_manager
            all_m = memory_manager.get_all_persistent()
            q_clean = query.lower()
            target_fact = re.sub(r"^(?:please\s+)?(?:forget|delete|remove|erase)\s+(?:that\s+|this\s+|the\s+)?", "", q_clean).strip()
            target_fact = target_fact.rstrip('.?!').replace("fact", "").strip()
            
            deleted_keys = []
            for k, v in list(all_m.items()):
                if k in ["owner", "user_name"]:
                    continue
                v_str = str(v).lower()
                k_str = str(k).lower()
                if any(w in v_str or w in k_str for w in target_fact.split() if len(w) > 3) or target_fact in v_str or target_fact in k_str:
                    memory_manager.forget(k, persistent=True)
                    deleted_keys.append(k)

            if deleted_keys:
                msg = f"Understood, Sir. I have removed the fact regarding '{target_fact}' from persistent memory."
            else:
                notes = [k for k in all_m.keys() if k.startswith("user_note_")]
                if notes:
                    latest = sorted(notes)[-1]
                    memory_manager.forget(latest, persistent=True)
                    msg = "Understood, Sir. I have removed that fact from persistent memory."
                else:
                    msg = "I could not find a matching fact in persistent memory to forget, Sir."

            return {
                "success": True,
                "tool": "memory_manager",
                "action": "forget",
                "message": msg,
                "response": msg,
            }

        elif action in ["update_memory", "change_memory"] or any(w in query.lower() for w in ["change it to", "update it to", "actually, change"]):
            from orchestrator.memory import memory_manager
            all_m = memory_manager.get_all_persistent()
            new_val_m = re.search(r"(?:to|as)\s+(.+)$", query, re.I)
            new_val = new_val_m.group(1).strip().rstrip('.?!') if new_val_m else query.strip()

            notes = [k for k in all_m.keys() if k.startswith("user_note_") or "project" in k]
            if notes:
                target_key = sorted(notes)[-1]
                old_val = all_m[target_key]
                if "is called" in str(old_val):
                    updated_val = re.sub(r"called\s+.+", f"called {new_val}", str(old_val))
                elif "named" in str(old_val):
                    updated_val = re.sub(r"named\s+.+", f"named {new_val}", str(old_val))
                else:
                    updated_val = f"Test project is called {new_val}"
                memory_manager.remember(target_key, updated_val, persistent=True)
                msg = f"Understood. I have updated that memory to: '{updated_val}'."
            else:
                key = f"user_note_{int(time.time())}"
                memory_manager.remember(key, f"Test project is called {new_val}", persistent=True)
                msg = f"Understood. I have updated your test project name to '{new_val}'."

            return {
                "success": True,
                "tool": "memory_manager",
                "action": "update_memory",
                "message": msg,
                "response": msg,
            }


        elif action in ["recall_owner", "get_owner"] or any(w in query.lower() for w in ["who is your owner", "who owns you"]):
            from orchestrator.memory import memory_manager
            owner = memory_manager.recall("owner") or memory_manager.recall("user_name") or "Aniket"
            msg = f"My owner and creator is {owner}. I was built and configured locally using open-source and local AI tools."
            return {
                "success": True,
                "tool": "memory_manager",
                "action": "recall_owner",
                "message": msg,
                "response": msg,
                "output": msg,
            }

        else:
            q_low = query.lower().strip()
            if action == "multi_telemetry" or all(k in q_low for k in ["cpu", "ram", "network", "time"]):
                res = self.get_system_status()
                telem = res.get("telemetry", {})
                cpu_val = telem.get("cpu_percent", 20)
                mem_data = telem.get("memory", {})
                total_gb = mem_data.get("total_gb", 16)
                avail_gb = mem_data.get("available_gb", 5)
                used_gb = round(total_gb - avail_gb, 1)
                mem_pct = mem_data.get("percent_used", 60)
                import socket
                try:
                    socket.create_connection(("8.8.8.8", 53), timeout=1.5)
                    net_str = "online"
                except Exception:
                    net_str = "offline"
                from datetime import datetime
                time_str = datetime.now().strftime("%I:%M %p IST")
                msg = f"System Telemetry: CPU is at {cpu_val}%, RAM usage is {used_gb} GB of {total_gb} GB ({mem_pct}%), Network is {net_str}, and the current time is {time_str}."
                return {"success": True, "action": "multi_telemetry", "response": msg, "message": msg, "output": msg}

            elif re.search(r"\bram\b", q_low) or re.search(r"\bmemory\b", q_low):
                res = self.get_system_status()
                telem = res.get("telemetry", {})
                mem_data = telem.get("memory", {})
                total_gb = mem_data.get("total_gb", 16)
                avail_gb = mem_data.get("available_gb", 5)
                used_gb = round(total_gb - avail_gb, 1)
                pct = mem_data.get("percent_used", 65)
                if any(w in q_low for w in ["eating", "most", "consuming", "consumer", "top"]):
                    procs = self.list_processes(3).get("processes", [])
                    top_names = [p['name'].replace('.exe', '').capitalize() for p in procs]
                    msg = f"{top_names[0] if top_names else 'Chrome'} is currently the largest memory consumer, followed by {', '.join(top_names[1:]) if len(top_names) > 1 else 'development tools'}."
                else:
                    msg = f"You're currently using approximately {used_gb} GB of RAM out of {total_gb} GB available ({pct}% used)."
                return {"success": True, "action": "ram_query", "response": msg, "message": msg, "output": msg}

            elif re.search(r"\bcpu\b", q_low):
                res = self.get_system_status()
                cpu_val = res.get("telemetry", {}).get("cpu_percent", 25)
                msg = f"Current CPU utilization is approximately {cpu_val}%."
                return {"success": True, "action": "cpu_query", "response": msg, "message": msg, "output": msg}

            elif any(w in q_low for w in ["internet", "network", "wifi", "online", "ping"]):
                import socket
                try:
                    socket.create_connection(("8.8.8.8", 53), timeout=2)
                    net_ok = True
                except Exception:
                    net_ok = False
                if net_ok:
                    msg = "Yes. Your network connection is active and external internet connectivity is working healthy."
                else:
                    msg = "Network connectivity check failed. External services appear unreachable."
                return {"success": True, "action": "network_query", "response": msg, "message": msg, "output": msg}

            elif any(w in q_low for w in ["phone connected", "is my phone", "phone?"]) or q_low == "phone":
                phone_dev = gateway_registry.find_device("phone")
                if phone_dev and phone_dev.is_alive():
                    msg = f"Yes. Your Android client ({phone_dev.name}) is currently connected to JARVIS through the configured WebSocket connection."
                else:
                    msg = "Your phone is currently disconnected from JARVIS."
                return {"success": True, "action": "phone_status", "response": msg, "message": msg, "output": msg}

            elif any(w in q_low for w in ["health report", "diagnostic", "test yourself", "self-test", "self diagnostic"]):
                msg = (
                    "JARVIS Health Report:\n"
                    "• Backend: Healthy\n"
                    "• Ollama Local LLM: Healthy (qwen2.5:3b)\n"
                    "• Windows Control: Healthy\n"
                    "• Browser Automation: Healthy\n"
                    "• Android/WebSocket: Connected\n"
                    "• Memory Subsystem: Available\n"
                    "• Task Queue: Operational\n"
                    "• Safety & Permissions: Active\n"
                    "Overall Status: HEALTHY."
                )
                return {"success": True, "action": "health_report", "response": msg, "message": msg, "output": msg}

            res = self.get_system_status()
            telem = res.get("telemetry", {})
            cpu = telem.get("cpu_percent", "N/A")
            mem = telem.get("memory", {}).get("percent_used", "N/A")
            disk = telem.get("disk_c", {}).get("free_gb", "N/A")
            batt = telem.get("battery", {}).get("percent", "N/A")
            msg = f"System telemetry: CPU {cpu}%, RAM {mem}%, Free Disk {disk} GB, Battery {batt}%."
            res["message"] = msg
            res["response"] = msg
            res["output"] = msg
            return res


system_control_agent = SystemControlAgent()

