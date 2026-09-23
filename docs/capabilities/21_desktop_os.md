# Capability 21: Desktop / OS Control

**Capability ID:** `21_desktop_os`  
**Classification:** `EXISTING`  
**Safety Classification:** `MODIFYING`  
**Domain:** `os`  
**Primary Provider:** `provider.os.win32`  
**Fallback Provider:** `provider.os.pyautogui`  

---

## 1. Capability Purpose & Scope
Provides low-level Windows desktop automation and host operating system control: Win32 window snapping (left, right, maximize), process telemetry (CPU, RAM, disk, battery), master volume adjustment, and window focus management.

---

## 2. Supported Operations
- `os.window_management`: Snaps the foreground window left, right, or maximized using `SetWindowPos`.
- `os.telemetry`: Gathers real-time host hardware telemetry (CPU %, RAM GB/%, Disk C: GB/%, Battery %).
- `os.volume_control`: Sets, adjusts, mutes, or unmutes system master audio level via PyCAW / Win32.
- `os.process_control`: Lists active OS processes sorted by CPU and memory consumption.

---

## 3. Required Context & World Model State
- **Foreground HWND:** Current active window handle from `world_model.probe_window()`.
- **Display Geometry:** Monitor resolution and virtual desktop coordinates.

---

## 4. Provider Implementation & Selection
- **Implementation:** `capabilities/providers/os_provider.py` (`OSWin32Provider`), backed by `agents/system_control_agent.py`.
- **Fast-Path Latency:** Operates under System 1 fast path in **1.2 ms - 3.8 ms**.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED` for telemetry, volume, and snapping. Destructive process termination is governed by Two-Gate tokens.
- **Verification Strategy:** `WIN32_API_GETWINDOWRECT` verifies that window bounds actually shifted after snap commands.
