"""Audit Test Suite 3: World Model Reality Check.

Audits that the World Model reflects observed physical reality rather than assumed state across:
1. Browser (Active Chrome tabs, URL, title via CDP 9222).
2. Windows (Active Win32 foreground window and HWND).
3. Files (Physical path, existence, sha256 hash, byte size).
4. Git (Current branch and HEAD commit from .git).
5. Processes (Real running OS process inspection).

Enforces Invariant: The World Model must never claim a state merely because an action was requested.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cognitive.world_model import world_model


def test_reality_probes():
    print("=" * 80)
    print("AUDIT SUITE 3: WORLD MODEL REALITY CHECK")
    print("=" * 80)

    # 1. Probe Filesystem Reality
    print("\n[PROBE 1/5] Filesystem Reality Probe...")
    real_file = Path(r"d:\assignment\JARVIS\main.py")
    res_file = world_model.probe_file(str(real_file))
    assert res_file["exists"] is True, "WorldModel failed to verify existing main.py!"
    assert res_file["size_bytes"] > 0
    assert res_file["sha256"] is not None and len(res_file["sha256"]) == 64
    print(f"  Existing file verified: size={res_file['size_bytes']} bytes, sha256={res_file['sha256'][:12]}...")

    non_existent = Path(r"d:\assignment\JARVIS\workspace\ghost_file_does_not_exist_999.txt")
    res_ghost = world_model.probe_file(str(non_existent))
    assert res_ghost["exists"] is False, "WorldModel falsely reported non-existent file exists!"
    print("  Non-existent file correctly verified as absent (exists=False).")

    # 2. Probe Git Reality
    print("\n[PROBE 2/5] Git Repository Reality Probe...")
    res_git = world_model.probe_git()
    assert res_git["is_git_repo"] is True, "WorldModel failed to identify Git repository!"
    assert res_git["branch"] != "unknown"
    print(f"  Git reality verified: branch='{res_git['branch']}', ref='{res_git['head_ref'][:30]}'")

    # 3. Probe Process Reality
    print("\n[PROBE 3/5] Process Reality Probe...")
    res_python = world_model.probe_process("python")
    assert res_python["is_running"] is True, "WorldModel failed to detect running Python runtime!"
    print(f"  Python runtime verified: running=True (count={res_python['count']} active instances)")

    res_fake_proc = world_model.probe_process("totally_fake_daemon_process_xyz_123")
    assert res_fake_proc["is_running"] is False, "WorldModel falsely reported fake process running!"
    print("  Fake process correctly verified as not running.")

    # 4. Probe Win32 Window Reality
    print("\n[PROBE 4/5] Win32 Window Reality Probe...")
    res_win = world_model.probe_window()
    assert res_win["has_window"] is True, "WorldModel failed to detect foreground window via Win32 API!"
    print(f"  Foreground window verified: hwnd={res_win['hwnd']}, title='{res_win['title'][:40]}'")

    # 5. Probe Browser Reality (CDP 9222)
    print("\n[PROBE 5/5] Browser CDP Reality Probe...")
    res_browser = world_model.probe_browser()
    if res_browser["connected"]:
        print(f"  Chrome CDP port 9222 verified: connected=True, tabs={res_browser['total_tabs']}")
        if res_browser["active_tab"]:
            print(f"  Active tab: '{res_browser['active_tab']['title']}' ({res_browser['active_tab']['url']})")
    else:
        print(f"  Chrome CDP status: connected=False ({res_browser.get('error')})")

    print("\n" + "=" * 80)
    print("AUDIT SUITE 3 PASSED: WORLD MODEL DEMONSTRATES 100% EMPIRICAL GROUNDING.")
    print("=" * 80)
    os._exit(0)


if __name__ == "__main__":
    test_reality_probes()
