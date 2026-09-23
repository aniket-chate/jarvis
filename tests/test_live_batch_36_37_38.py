"""Foreground Live Server Verification Test Suite for Batch 2 (Capabilities 36, 37, 38).

Starts real uvicorn server.app:app on port 8000 and executes the 8 mandatory live scenarios:
1. LIVE 1: Register TEST_DEVICE_ALPHA -> Discover it
2. LIVE 2: Register TEST_DEVICE_BETA -> Verify both are handled dynamically
3. LIVE 3: Create TEST_CONTACT_ALPHA -> Resolve it
4. LIVE 4: Create dynamic calendar event -> Retrieve it
5. LIVE 5: Modify the test event -> Verify modification
6. LIVE 6: Create calendar conflict -> Verify conflict detection
7. LIVE 7: Communication via safe test provider -> Verify delivery state
8. LIVE 8: Device -> Calendar -> Communication workflow -> Verify every step

All tests visibly show: stdout, stderr, request, response, PASS/FAIL, duration, exit code.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
AUTH_TOKEN = "jarvis-gateway-token-2026-auth"
HEADERS = {
    "X-JARVIS-Token": AUTH_TOKEN,
    "Content-Type": "application/json",
}

server_subproc: Optional[subprocess.Popen] = None


def start_live_server():
    global server_subproc
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "server.app:app",
        "--host",
        SERVER_HOST,
        "--port",
        str(SERVER_PORT),
    ]
    print(f"  [Server Command] {' '.join(cmd)}")
    sys.stdout.flush()
    server_subproc = subprocess.Popen(cmd)


def stop_live_server():
    global server_subproc
    if server_subproc:
        print("  [Teardown] Terminating live Uvicorn server subprocess...")
        server_subproc.terminate()
        try:
            server_subproc.wait(timeout=5.0)
        except Exception:
            server_subproc.kill()
        print("  [Teardown] Live server terminated cleanly.")
        sys.stdout.flush()


async def wait_for_server(timeout: float = 30.0):
    start_time = time.time()
    async with httpx.AsyncClient() as client:
        while time.time() - start_time < timeout:
            try:
                resp = await client.get(f"{BASE_URL}/health", timeout=2.0)
                if resp.status_code == 200:
                    print(f"  [Server Ready] Uvicorn responded 200 OK in {time.time() - start_time:.2f}s")
                    sys.stdout.flush()
                    return True
            except Exception:
                await asyncio.sleep(0.5)
    raise RuntimeError("Live server failed to bind within timeout.")


async def execute_capability_live(client: httpx.AsyncClient, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "action": action,
        "parameters": parameters,
    }
    resp = await client.post(
        f"{BASE_URL}/api/v1/capabilities/execute",
        headers=HEADERS,
        json=payload,
        timeout=15.0,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
    return resp.json()


async def run_live_scenarios():
    results = []
    print("\n" + "=" * 70)
    print("JARVIS LIVE SERVER TEST SUITE — CAPABILITY BATCH 2 (36 + 37 + 38)")
    print("=" * 70 + "\n")
    sys.stdout.flush()

    async with httpx.AsyncClient(headers=HEADERS, timeout=20.0) as client:
        # =====================================================================
        # LIVE 1 — Register TEST_DEVICE_ALPHA -> Discover it
        # =====================================================================
        t0 = time.perf_counter()
        print("[LIVE 1] Register TEST_DEVICE_ALPHA and Discover via Mesh...")
        req1 = {
            "device_id": "TEST_DEVICE_ALPHA",
            "name": "Alpha Node Workstation",
            "client_type": "windows",
            "capabilities": ["display", "notifications", "terminal"],
        }
        print(f"  Request: POST /api/devices/register -> {json.dumps(req1)}")
        res1 = await client.post(f"{BASE_URL}/api/devices/register", json=req1)
        resp1 = res1.json()
        print(f"  Response: {json.dumps(resp1)}")

        # Discovery check
        disc1 = await execute_capability_live(client, "mesh.discover_peers", {})
        discovered_ids = [d["device_id"] for d in disc1.get("output", {}).get("devices", [])]
        print(f"  Discovered Peers: {discovered_ids}")

        assert "TEST_DEVICE_ALPHA" in discovered_ids, "TEST_DEVICE_ALPHA not found in discovered peers!"
        dur1 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur1:.3f}s)\n")
        results.append(("LIVE 1: Register and Discover TEST_DEVICE_ALPHA", True, dur1))

        # =====================================================================
        # LIVE 2 — Register TEST_DEVICE_BETA -> Dynamic Discovery
        # =====================================================================
        t0 = time.perf_counter()
        print("[LIVE 2] Register TEST_DEVICE_BETA and verify dynamic handling...")
        req2 = {
            "device_id": "TEST_DEVICE_BETA",
            "name": "Beta Mobile Unit",
            "client_type": "phone",
            "capabilities": ["audio_output", "camera", "haptic"],
        }
        print(f"  Request: POST /api/devices/register -> {json.dumps(req2)}")
        res2 = await client.post(f"{BASE_URL}/api/devices/register", json=req2)
        resp2 = res2.json()
        print(f"  Response: {json.dumps(resp2)}")

        disc2 = await execute_capability_live(client, "mesh.discover_peers", {})
        discovered_ids2 = [d["device_id"] for d in disc2.get("output", {}).get("devices", [])]
        print(f"  Discovered Peers: {discovered_ids2}")

        assert "TEST_DEVICE_ALPHA" in discovered_ids2, "TEST_DEVICE_ALPHA disappeared!"
        assert "TEST_DEVICE_BETA" in discovered_ids2, "TEST_DEVICE_BETA not discovered!"
        dur2 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur2:.3f}s)\n")
        results.append(("LIVE 2: Register TEST_DEVICE_BETA & Multi-Device Discovery", True, dur2))

        # =====================================================================
        # LIVE 3 — Create TEST_CONTACT_ALPHA -> Resolve dynamically
        # =====================================================================
        t0 = time.perf_counter()
        print("[LIVE 3] Create dynamic contact and resolve via Communication Hub...")
        # Register contact dynamically via live provider endpoint
        reg3 = {
            "name": "TEST_CONTACT_ALPHA",
            "email": "test_alpha@internal.mesh",
            "phone": "+18005550199",
            "tags": ["vip", "test"],
        }
        print(f"  Request: comm.register_contact -> {json.dumps(reg3)}")
        reg_res = await execute_capability_live(client, "comm.register_contact", reg3)
        print(f"  Register Response: {json.dumps(reg_res)}")

        req3 = {"query": "TEST_CONTACT_ALPHA"}
        print(f"  Request: comm.lookup_contact -> {json.dumps(req3)}")
        res3 = await execute_capability_live(client, "comm.lookup_contact", req3)
        print(f"  Response: {json.dumps(res3)}")

        out3 = res3.get("output", {})
        assert out3.get("resolved") is True, f"Contact lookup failed: {out3}"
        assert out3.get("contact", {}).get("name") == "TEST_CONTACT_ALPHA"
        assert out3.get("contact", {}).get("email") == "test_alpha@internal.mesh"
        dur3 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur3:.3f}s)\n")
        results.append(("LIVE 3: Dynamic Contact Creation & Resolution", True, dur3))

        # =====================================================================
        # LIVE 4 — Create dynamic calendar event -> Retrieve it
        # =====================================================================
        t0 = time.perf_counter()
        dyn_title = f"Dynamic Event {uuid.uuid4().hex[:6]}"
        print(f"[LIVE 4] Create dynamic calendar event '{dyn_title}' and retrieve it...")
        req4 = {
            "title": dyn_title,
            "start_time": "2026-11-20T10:00:00+00:00",
            "duration_minutes": 60,
            "description": "Live server integration test event",
            "location": "Mesh Room 1",
            "attendees": ["test_alpha@internal.mesh"],
        }
        print(f"  Request: calendar.create_event -> {json.dumps(req4)}")
        res4 = await execute_capability_live(client, "calendar.create_event", req4)
        print(f"  Response: {json.dumps(res4)}")

        evt_id = res4.get("output", {}).get("event_id")
        assert evt_id is not None, f"Event creation failed: {res4}"

        # Retrieve
        req4_get = {"query": dyn_title}
        print(f"  Request: calendar.get_events -> {json.dumps(req4_get)}")
        res4_get = await execute_capability_live(client, "calendar.get_events", req4_get)
        print(f"  Response: {json.dumps(res4_get)}")

        matched_events = res4_get.get("output", {}).get("events", [])
        assert len(matched_events) >= 1, f"Event '{dyn_title}' not retrieved!"
        assert matched_events[0]["event_id"] == evt_id
        dur4 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur4:.3f}s)\n")
        results.append(("LIVE 4: Dynamic Calendar Event Creation & Retrieval", True, dur4))

        # =====================================================================
        # LIVE 5 — Modify the test event -> Verify modification
        # =====================================================================
        t0 = time.perf_counter()
        print(f"[LIVE 5] Modify test event '{evt_id}' and verify changes...")
        req5 = {
            "event_id": evt_id,
            "new_title": f"{dyn_title} (MODIFIED)",
            "location": "Mesh Room 2 (Upgraded)",
        }
        print(f"  Request: calendar.modify_event -> {json.dumps(req5)}")
        res5 = await execute_capability_live(client, "calendar.modify_event", req5)
        print(f"  Response: {json.dumps(res5)}")

        mod_evt = res5.get("output", {}).get("event", {})
        assert mod_evt.get("title") == f"{dyn_title} (MODIFIED)"
        assert mod_evt.get("location") == "Mesh Room 2 (Upgraded)"
        dur5 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur5:.3f}s)\n")
        results.append(("LIVE 5: Calendar Event Modification & Verification", True, dur5))

        # =====================================================================
        # LIVE 6 — Create a calendar conflict -> Verify conflict detection
        # =====================================================================
        t0 = time.perf_counter()
        print("[LIVE 6] Attempt overlapping event creation to verify conflict detection...")
        req6 = {
            "title": "Conflicting Session",
            "start_time": "2026-11-20T10:30:00+00:00",
            "duration_minutes": 30,
            "allow_conflicts": False,
        }
        print(f"  Request: calendar.create_event (conflicting) -> {json.dumps(req6)}")
        res6 = await execute_capability_live(client, "calendar.create_event", req6)
        print(f"  Response: {json.dumps(res6)}")

        out6 = res6.get("output", {})
        assert out6.get("success") is False, "Conflict was not blocked!"
        assert out6.get("status") == "CONFLICT_DETECTED", f"Unexpected status: {out6.get('status')}"
        assert len(out6.get("conflicts", [])) >= 1, "Conflict list empty!"
        dur6 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur6:.3f}s)\n")
        results.append(("LIVE 6: Calendar Conflict Detection Gate", True, dur6))

        # =====================================================================
        # LIVE 7 — Safe Communication -> Verify delivery state
        # =====================================================================
        t0 = time.perf_counter()
        print("[LIVE 7] Dispatch message via safe provider and verify delivery state...")
        req7 = {
            "recipient": "test_alpha@internal.mesh",
            "message": "Mesh synchronization complete. Operational status nominal.",
            "user_confirmed": True,
        }
        print(f"  Request: comm.send_message -> {json.dumps(req7)}")
        res7 = await execute_capability_live(client, "comm.send_message", req7)
        print(f"  Response: {json.dumps(res7)}")

        out7 = res7.get("output", {})
        assert out7.get("success") is True, f"Send failed: {out7}"
        assert out7.get("status") == "SENT"
        msg_id = out7.get("message_id")

        # Verify delivery against outbox ledger
        req7_ver = {"item_id": msg_id}
        print(f"  Request: comm.verify_delivery -> {json.dumps(req7_ver)}")
        res7_ver = await execute_capability_live(client, "comm.verify_delivery", req7_ver)
        print(f"  Response: {json.dumps(res7_ver)}")

        ver_out7 = res7_ver.get("output", {})
        assert ver_out7.get("found") is True
        assert ver_out7.get("delivery_status") == "SENT"
        dur7 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur7:.3f}s)\n")
        results.append(("LIVE 7: Safe Communication Delivery Verification", True, dur7))

        # =====================================================================
        # LIVE 8 — Device -> Calendar -> Communication Workflow
        # =====================================================================
        t0 = time.perf_counter()
        print("[LIVE 8] Execute integrated Device -> Calendar -> Communication workflow...")
        # Step 8.1: Calendar lookup
        req8_cal = {"limit": 3}
        print(f"  [Step 8.1] Query Calendar -> {json.dumps(req8_cal)}")
        res8_cal = await execute_capability_live(client, "calendar.get_events", req8_cal)
        cal_count = res8_cal.get("output", {}).get("count", 0)
        print(f"  [Step 8.1 Response] Found {cal_count} calendar event(s).")
        assert cal_count > 0

        # Step 8.2: Select reachable trusted device
        req8_dev = {"required_capability": "notifications", "require_trusted": True}
        print(f"  [Step 8.2] Select Device with 'notifications' -> {json.dumps(req8_dev)}")
        res8_dev = await execute_capability_live(client, "mesh.select_device", req8_dev)
        selected_dev = res8_dev.get("output", {}).get("device_id")
        print(f"  [Step 8.2 Response] Selected device: {selected_dev}")
        assert selected_dev is not None

        # Step 8.3: Dispatch notification to selected device
        req8_notif = {
            "title": "Schedule Briefing",
            "message": f"You have {cal_count} synchronized event(s) scheduled.",
            "target_device": selected_dev,
        }
        print(f"  [Step 8.3] Dispatch Notification -> {json.dumps(req8_notif)}")
        res8_notif = await execute_capability_live(client, "comm.notify_user", req8_notif)
        notif_out = res8_notif.get("output", {})
        print(f"  [Step 8.3 Response] Notification dispatched: {json.dumps(notif_out)}")
        assert notif_out.get("success") is True
        assert notif_out.get("status") == "DELIVERED"
        assert notif_out.get("target_device") == selected_dev

        dur8 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur8:.3f}s)\n")
        results.append(("LIVE 8: Integrated Device -> Calendar -> Communication Workflow", True, dur8))

    # Print summary table
    print("\n" + "=" * 70)
    print("LIVE SERVER TEST RESULTS SUMMARY")
    print("=" * 70)
    passed_count = sum(1 for _, ok, _ in results if ok)
    failed_count = len(results) - passed_count
    for name, ok, dur in results:
        status_str = "PASS" if ok else "FAIL"
        print(f"  [{status_str}] {name:<60} ({dur:.3f}s)")
    print("-" * 70)
    print(f"Total: {len(results)} | Passed: {passed_count} | Failed: {failed_count}")
    print("=" * 70 + "\n")
    sys.stdout.flush()

    if failed_count > 0:
        raise RuntimeError(f"{failed_count} live scenario(s) failed.")


def main():
    start_live_server()
    exit_code = 1
    try:
        asyncio.run(wait_for_server(timeout=30.0))
        asyncio.run(run_live_scenarios())
        exit_code = 0
    except Exception as exc:
        print(f"\n[FATAL LIVE SERVER ERROR] {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        exit_code = 1
    finally:
        stop_live_server()

    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)


if __name__ == "__main__":
    main()
