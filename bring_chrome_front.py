import time
import win32gui
import win32con
import ctypes

def bring_chrome_front():
    found_hwnds = []
    def enum_cb(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "JARVIS" in title or "Chrome" in title:
                found_hwnds.append((hwnd, title))
        return True

    win32gui.EnumWindows(enum_cb, None)
    print("Found candidate windows:", found_hwnds)
    for hwnd, title in found_hwnds:
        if "JARVIS Core" in title or "Google Chrome" in title:
            print(f"Bringing window to front: '{title}' (hwnd={hwnd})")
            try:
                # Windows focus bypass trick
                ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
                print("Window brought to front successfully.")
                return True
            except Exception as e:
                print(f"Failed to focus hwnd {hwnd}: {e}")
    return False

if __name__ == "__main__":
    bring_chrome_front()
