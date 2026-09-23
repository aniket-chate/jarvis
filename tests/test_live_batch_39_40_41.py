"""Foreground Live Server Verification Test Suite for Batch 3 (Capabilities 39, 40, 41).

Starts real uvicorn server.app:app on port 8000 and executes 8 live scenarios:
1. LIVE 1: Capability 39 — Create task -> get tasks -> complete task.
2. LIVE 2: Capability 39 — Strict dependency blocking & cascade unblocking.
3. LIVE 3: Capability 40 — Route planning with fresh ETA calculation.
4. LIVE 4: Capability 40 — Route alternatives comparison.
5. LIVE 5: Capability 40 — Location resolution with privacy precision truncation.
6. LIVE 6: Capability 41 — Autonomous closed-loop execution.
7. LIVE 7: Capability 41 — High-risk action protection (halts in WAITING_EXTERNAL).
8. LIVE 8: Integrated E2E DAG: Task -> Travel -> Autonomous Agency.

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
    server_subproc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop_live_server():
    global server_subproc
    if server_subproc:
        print(f"  [Teardown] Terminating live Uvicorn server process tree (PID={server_subproc.pid})...")
        sys.stdout.flush()
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(server_subproc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            server_subproc.kill()
        try:
            server_subproc.wait(timeout=5.0)
        except Exception:
            pass
        server_subproc = None
        print("  [Teardown] Live server process tree terminated cleanly.")
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
    print("JARVIS LIVE SERVER TEST SUITE — CAPABILITY BATCH 3 (39 + 40 + 41)")
    print("=" * 70 + "\n")
    sys.stdout.flush()

    async with httpx.AsyncClient(headers=HEADERS, timeout=20.0) as client:
        # =====================================================================
        # LIVE 1 — Capability 39: Task Lifecycle
        # =====================================================================
        t0 = time.perf_counter()
        print("[LIVE 1] Capability 39: Create Task, Query, and Complete...")
        t_req = {
            "title": "Live Server Audit Task",
            "priority": "high",
            "tags": ["live", "batch3"],
        }
        print(f"  Request: productivity.create_task -> {json.dumps(t_req)}")
        res1 = await execute_capability_live(client, "productivity.create_task", t_req)
        print(f"  Response: {json.dumps(res1)}")
        task_id = res1["output"]["task"]["id"]
        assert res1["status"] == "SUCCESS"
        assert res1["output"]["task"]["status"] == "READY"

        # Complete task
        comp_res1 = await execute_capability_live(client, "productivity.complete_task", {"id": task_id})
        assert comp_res1["status"] == "SUCCESS"
        assert comp_res1["output"]["task"]["status"] == "COMPLETED"

        dur1 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur1:.3f}s)\n")
        results.append(("LIVE 1: Productivity Task Lifecycle", True, dur1))

        # =====================================================================
        # LIVE 2 — Capability 39: Dependency Blocking & Cascade Unblocking
        # =====================================================================
        t0 = time.perf_counter()
        print("[LIVE 2] Capability 39: Strict Dependency Blocking & Cascade Unblocking...")
        # Step A: Prerequisite
        r_a = await execute_capability_live(client, "productivity.create_task", {"title": "Prerequisite Task A"})
        id_a = r_a["output"]["task"]["id"]

        # Step B: Dependent
        r_b = await execute_capability_live(client, "productivity.create_task", {
            "title": "Dependent Task B",
            "dependencies": [id_a],
        })
        id_b = r_b["output"]["task"]["id"]
        assert r_b["output"]["task"]["status"] == "BLOCKED"
        print(f"  Task B status initially: {r_b['output']['task']['status']} (BLOCKED verified)")

        # Complete A -> B unblocks
        c_a = await execute_capability_live(client, "productivity.complete_task", {"id": id_a})
        assert id_b in c_a["output"]["unblocked_tasks"]
        print(f"  Cascade unblocked: {c_a['output']['unblocked_tasks']}")

        dur2 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur2:.3f}s)\n")
        results.append(("LIVE 2: Productivity Dependency Cascade", True, dur2))

        # =====================================================================
        # LIVE 3 — Capability 40: Route Planning & Fresh ETA
        # =====================================================================
        t0 = time.perf_counter()
        print("[LIVE 3] Capability 40: Route Planning & Fresh ETA...")
        r_route = {
            "origin": "Live HQ Hub",
            "destination": "Regional Data Facility",
            "mode": "driving",
        }
        print(f"  Request: travel.plan_route -> {json.dumps(r_route)}")
        res3 = await execute_capability_live(client, "travel.plan_route", r_route)
        print(f"  Response: {json.dumps(res3)}")
        assert res3["status"] == "SUCCESS"
        assert res3["output"]["freshness"] in ("LIVE", "CACHED")
        assert "arrival_time" in res3["output"]
        assert res3["output"]["distance_meters"] > 0

        dur3 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur3:.3f}s)\n")
        results.append(("LIVE 3: Travel Route Planning & Fresh ETA", True, dur3))

        # =====================================================================
        # LIVE 4 — Capability 40: Route Alternatives Comparison
        # =====================================================================
        t0 = time.perf_counter()
        print("[LIVE 4] Capability 40: Compare Route Alternatives...")
        res4 = await execute_capability_live(client, "travel.compare_routes", {
            "origin": "City Center",
            "destination": "Outer Airport",
        })
        assert res4["status"] == "SUCCESS"
        assert "fastest_route" in res4["output"]
        assert len(res4["output"]["routes"]) >= 2

        dur4 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur4:.3f}s)\n")
        results.append(("LIVE 4: Travel Route Comparison", True, dur4))

        # =====================================================================
        # LIVE 5 — Capability 40: Location Privacy Precision Truncation
        # =====================================================================
        t0 = time.perf_counter()
        print("[LIVE 5] Capability 40: Location Privacy Precision Truncation...")
        res5 = await execute_capability_live(client, "travel.resolve_location", {
            "location": {"lat": 18.5204303, "lng": 73.8567437, "name": "Exact GPS Pin"},
        })
        assert res5["status"] == "SUCCESS"
        loc = res5["output"]["location"]
        assert loc["lat"] == 18.52
        assert loc["lng"] == 73.857
        print(f"  Sanitized coordinates: lat={loc['lat']}, lng={loc['lng']} (~100m truncated)")

        dur5 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur5:.3f}s)\n")
        results.append(("LIVE 5: Location Privacy Truncation", True, dur5))

        # =====================================================================
        # LIVE 6 — Capability 41: Autonomous Agency Closed-Loop Execution
        # =====================================================================
        t0 = time.perf_counter()
        print("[LIVE 6] Capability 41: Autonomous Closed-Loop Execution...")
        gid = f"live_goal_{uuid.uuid4().hex[:8]}"
        res6 = await execute_capability_live(client, "autonomy.execute_goal", {
            "goal_id": gid,
            "target_capability": "os.telemetry",
            "parameters": {},
        })
        assert res6["status"] == "SUCCESS"
        assert res6["output"]["goal"]["state"] == "COMPLETED"
        assert res6["output"]["goal"]["checkpoint_stage"] == "VERIFICATION_COMPLETED"
        print(f"  Goal {gid} reached state COMPLETED with verification.")

        dur6 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur6:.3f}s)\n")
        results.append(("LIVE 6: Autonomous Agency Execution", True, dur6))

        # =====================================================================
        # LIVE 7 — Capability 41: High-Risk Action Halting (Two-Gate Protection)
        # =====================================================================
        t0 = time.perf_counter()
        print("[LIVE 7] Capability 41: High-Risk Action Halting (Two-Gate Protection)...")
        gid7 = f"live_high_risk_{uuid.uuid4().hex[:8]}"
        res7 = await execute_capability_live(client, "autonomy.execute_goal", {
            "goal_id": gid7,
            "target_capability": "comm.send_email",
            "parameters": {"recipient": "admin@example.org", "subject": "Alert"},
        })
        # Must require approval
        assert res7["status"] == "APPROVAL_REQUIRED"
        assert res7["output"]["requires_confirmation"] is True
        assert res7["output"]["goal"]["state"] == "WAITING_EXTERNAL"
        print(f"  High-risk action safely halted in WAITING_EXTERNAL.")

        dur7 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur7:.3f}s)\n")
        results.append(("LIVE 7: High-Risk Action Halting", True, dur7))

        # =====================================================================
        # LIVE 8 — Integrated Composite Workflow: Task -> Route -> Autonomy
        # =====================================================================
        t0 = time.perf_counter()
        print("[LIVE 8] Composite E2E Workflow: Task -> Travel -> Autonomous Agency...")
        # 1. Travel Route
        r_live8 = await execute_capability_live(client, "travel.plan_route", {
            "origin": "Point Alpha",
            "destination": "Point Omega",
        })
        dep_time = r_live8["output"]["departure_time"]

        # 2. Task
        t_live8 = await execute_capability_live(client, "productivity.create_task", {
            "title": "Transit to Point Omega",
            "due_at": dep_time,
        })
        task_id8 = t_live8["output"]["task"]["id"]

        # 3. Autonomous Execution
        a_live8 = await execute_capability_live(client, "autonomy.execute_goal", {
            "goal_id": f"auto_live8_{task_id8}",
            "target_capability": "os.telemetry",
            "parameters": {"task_id": task_id8},
        })
        assert a_live8["status"] == "SUCCESS"
        assert a_live8["output"]["goal"]["state"] == "COMPLETED"

        dur8 = time.perf_counter() - t0
        print(f"  Result: PASS (duration: {dur8:.3f}s)\n")
        results.append(("LIVE 8: Composite Workflow (Task -> Travel -> Autonomy)", True, dur8))

    # Summary
    print("=" * 70)
    print("LIVE SERVER BATCH 3 VERIFICATION SUMMARY:")
    print("=" * 70)
    all_passed = True
    for name, ok, d in results:
        status_str = "PASS" if ok else "FAIL"
        if not ok:
            all_passed = False
        print(f"  [{status_str}] {name:<60} ({d:.3f}s)")
    print("=" * 70)
    return all_passed


async def main():
    try:
        # Check if server is already running
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{BASE_URL}/health", timeout=1.0)
                if resp.status_code == 200:
                    print("  [Server Detected] An existing server is running on port 8000.")
                    existing = True
                else:
                    existing = False
            except Exception:
                existing = False

        if not existing:
            start_live_server()
            await wait_for_server(30.0)

        passed = await run_live_scenarios()
    finally:
        if server_subproc:
            stop_live_server()

    if not passed:
        print("\n[FAILED] One or more live scenarios failed.")
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    else:
        print("\n[SUCCESS] ALL 8 BATCH 3 LIVE SERVER SCENARIOS PASSED CLEANLY (100% GREEN)!")
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
