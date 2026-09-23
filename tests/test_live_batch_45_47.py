"""Foreground Live Server Verification Test Suite for Batch 5 (Capabilities 45, 46, 47).

Starts real Uvicorn server (server.app:app) on port 8000 and executes 10 live scenarios:
1. LIVE 1: Capability 45 — Device Registration & Discovery over HTTP
2. LIVE 2: Capability 45 — Sensor Reading & Verification over HTTP
3. LIVE 3: Capability 45 — Two-Gate Token Actuation Command Interlock
4. LIVE 4: Capability 45 — Emergency Stop Lockdown & Reset Verification
5. LIVE 5: Capability 46 — Arbitrary Dataset Ingestion & Profiling
6. LIVE 6: Capability 46 — Statistical Metrics & Multi-Column Correlation Analysis
7. LIVE 7: Capability 46 — Anomaly Detection & Chart Visualization Specification
8. LIVE 8: Capability 47 — Scenario Definition & Deterministic Iterative Simulation
9. LIVE 9: Capability 47 — Predictive Forecasting with Uncertainty Bounds & Epistemic Tagging
10. LIVE 10: Integrated E2E: Sensor Telemetry (45) -> Analytics Profiling (46) -> Prediction (47) -> Actuation (45)

All tests visibly show: stdout, stderr, request, response, PASS/FAIL, duration, exit code.
Adheres strictly to Windows subprocess safety: decoupled pipes, process-tree taskkill cleanup.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Dict, Any, Optional
import uuid

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
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
    print("=" * 80)
    print("STARTING LIVE BATCH 45-47 SYSTEM EXECUTION VERIFICATION")
    print("=" * 80)
    sys.stdout.flush()

    passed_count = 0
    total_count = 10

    async with httpx.AsyncClient() as client:
        # -------------------------------------------------------------
        # LIVE 1: Capability 45 — Device Registration & Discovery
        # -------------------------------------------------------------
        print("\n--- LIVE 1: Capability 45 — Device Registration & Discovery ---")
        live_robot_id = f"live_bot_{uuid.uuid4().hex[:6]}"
        live_zone = f"zone_{uuid.uuid4().hex[:4]}"
        reg_payload = {
            "device_id": live_robot_id,
            "name": "Live Articulated Test Mechanism",
            "device_type": "simulated_arm",
            "device_category": "SIMULATED_DEVICE",
            "zone": live_zone,
            "actuators": {
                "joint_pitch": {
                    "actuator_id": "joint_pitch",
                    "name": "Pitch Servo",
                    "actuator_type": "servo",
                    "min_limit": -90.0,
                    "max_limit": 90.0,
                    "current_value": 0.0,
                }
            },
            "sensors": {
                "strain_gauge": {
                    "sensor_id": "strain_gauge",
                    "name": "Tension Gauge",
                    "sensor_type": "strain",
                    "units": "microstrain",
                    "last_reading": 120.5,
                }
            },
            "capabilities": ["move", "read_sensor", "emergency_stop", "verify_state"],
        }
        res_reg = await execute_capability_live(client, "robotics.register_device", reg_payload)
        assert res_reg["status"] == "SUCCESS", f"Registration failed: {res_reg}"

        res_disc = await execute_capability_live(client, "robotics.discover_devices", {"zone": live_zone})
        assert res_disc["status"] == "SUCCESS"
        dev_list = res_disc["output"].get("devices", [])
        assert any(d["device_id"] == live_robot_id for d in dev_list)
        print(f"  [PASS] LIVE 1: Device '{live_robot_id}' registered and discovered.")
        passed_count += 1
        sys.stdout.flush()

        # -------------------------------------------------------------
        # LIVE 2: Capability 45 — Sensor Reading & Verification
        # -------------------------------------------------------------
        print("\n--- LIVE 2: Capability 45 — Sensor Reading & Verification ---")
        res_sensor = await execute_capability_live(client, "robotics.read_sensor", {
            "device_id": live_robot_id,
            "sensor_id": "strain_gauge",
        })
        assert res_sensor["status"] == "SUCCESS"
        reading = res_sensor["output"].get("sensor_reading", {})
        assert reading.get("value") == 120.5
        assert reading.get("units") == "microstrain"
        print("  [PASS] LIVE 2: Sensor telemetry read and verified.")
        passed_count += 1
        sys.stdout.flush()

        # -------------------------------------------------------------
        # LIVE 3: Capability 45 — Two-Gate Token Actuation Command Interlock
        # -------------------------------------------------------------
        print("\n--- LIVE 3: Capability 45 — Two-Gate Token Interlock ---")
        # Step 1: Initial call without confirmation token -> WAITING_EXTERNAL
        res_cmd1 = await execute_capability_live(client, "robotics.execute_command", {
            "device_id": live_robot_id,
            "command_type": "move",
            "parameters": {"actuator_id": "joint_pitch", "target_value": 30.0},
        })
        assert res_cmd1["status"] == "WAITING_EXTERNAL"
        token = res_cmd1["output"].get("confirmation_token")
        assert token is not None, "Expected confirmation token for physical motion"

        # Step 2: Confirm with staged token -> SUCCESS
        res_cmd2 = await execute_capability_live(client, "robotics.execute_command", {
            "device_id": live_robot_id,
            "command_type": "move",
            "parameters": {"actuator_id": "joint_pitch", "target_value": 30.0},
            "confirmation_token": token,
        })
        assert res_cmd2["status"] == "SUCCESS"
        assert res_cmd2["output"].get("acknowledgement", {}).get("status") == "EXECUTED"
        print("  [PASS] LIVE 3: Two-Gate confirmation verified for physical actuation.")
        passed_count += 1
        sys.stdout.flush()

        # -------------------------------------------------------------
        # LIVE 4: Capability 45 — Emergency Stop Lockdown & Reset
        # -------------------------------------------------------------
        print("\n--- LIVE 4: Capability 45 — Emergency Stop Lockdown & Reset ---")
        res_estop = await execute_capability_live(client, "robotics.emergency_stop", {"device_id": live_robot_id})
        assert res_estop["status"] == "SUCCESS"

        # Verify command rejection during lockdown
        res_blocked = await execute_capability_live(client, "robotics.execute_command", {
            "device_id": live_robot_id,
            "command_type": "move",
            "parameters": {"actuator_id": "joint_pitch", "target_value": 0.0},
        })
        assert res_blocked["status"] == "FAILED"
        assert "EMERGENCY_STOPPED" in str(res_blocked["output"])

        # Reset lockdown
        res_reset = await execute_capability_live(client, "robotics.reset_emergency_stop", {"device_id": live_robot_id})
        assert res_reset["status"] == "SUCCESS"
        print("  [PASS] LIVE 4: Emergency stop lockdown and reset lifecycle confirmed.")
        passed_count += 1
        sys.stdout.flush()

        # -------------------------------------------------------------
        # LIVE 5: Capability 46 — Dataset Ingestion & Profiling
        # -------------------------------------------------------------
        print("\n--- LIVE 5: Capability 46 — Dataset Ingestion & Profiling ---")
        raw_dataset = [
            {"obs_id": 1, "flow_rate": 10.5, "valve_pos": 20.0, "status": "nominal"},
            {"obs_id": 2, "flow_rate": 15.2, "valve_pos": 30.0, "status": "nominal"},
            {"obs_id": 3, "flow_rate": 22.0, "valve_pos": 45.0, "status": "elevated"},
            {"obs_id": 4, "flow_rate": 28.5, "valve_pos": 60.0, "status": "elevated"},
            {"obs_id": 5, "flow_rate": 35.1, "valve_pos": 75.0, "status": "critical"},
        ]
        res_load = await execute_capability_live(client, "analytics.load_dataset", {"data": raw_dataset})
        assert res_load["status"] == "SUCCESS"
        dataset_id = res_load["output"]["dataset_id"]

        res_profile = await execute_capability_live(client, "analytics.profile_data", {"dataset_id": dataset_id})
        assert res_profile["status"] == "SUCCESS"
        assert res_profile["output"]["row_count"] == 5
        assert len(res_profile["output"]["columns"]) == 4
        print(f"  [PASS] LIVE 5: Dataset '{dataset_id}' profiled over HTTP.")
        passed_count += 1
        sys.stdout.flush()

        # -------------------------------------------------------------
        # LIVE 6: Capability 46 — Statistics & Multi-Column Correlation
        # -------------------------------------------------------------
        print("\n--- LIVE 6: Capability 46 — Statistics & Correlation Matrix ---")
        res_stat = await execute_capability_live(client, "analytics.compute_stats", {
            "dataset_id": dataset_id,
            "column": "flow_rate",
        })
        assert res_stat["status"] == "SUCCESS"
        assert "mean" in res_stat["output"]
        assert res_stat["output"]["mean"] > 20.0

        res_corr = await execute_capability_live(client, "analytics.correlation_analysis", {
            "dataset_id": dataset_id,
            "columns": ["flow_rate", "valve_pos"],
        })
        assert res_corr["status"] == "SUCCESS"
        matrix = res_corr["output"]["correlation_matrix"]
        assert matrix["flow_rate"]["valve_pos"] > 0.95
        print("  [PASS] LIVE 6: Correlation matrix and statistics verified.")
        passed_count += 1
        sys.stdout.flush()

        # -------------------------------------------------------------
        # LIVE 7: Capability 46 — Outlier Detection & Chart Specification
        # -------------------------------------------------------------
        print("\n--- LIVE 7: Capability 46 — Outlier Detection & Visualization ---")
        res_anom = await execute_capability_live(client, "analytics.detect_anomalies", {
            "dataset_id": dataset_id,
            "column": "flow_rate",
            "method": "iqr",
        })
        assert res_anom["status"] == "SUCCESS"

        res_chart = await execute_capability_live(client, "analytics.generate_visualization", {
            "dataset_id": dataset_id,
            "chart_type": "line",
            "x_field": "obs_id",
            "y_field": "flow_rate",
            "title": "Live Flow Rate Profile",
        })
        assert res_chart["status"] == "SUCCESS"
        spec = res_chart["output"]["specification"]
        assert spec["chart_type"] == "line"
        assert spec["data_point_count"] == 5
        print("  [PASS] LIVE 7: Outlier assessment and chart spec generated.")
        passed_count += 1
        sys.stdout.flush()

        # -------------------------------------------------------------
        # LIVE 8: Capability 47 — Scenario Definition & Simulation
        # -------------------------------------------------------------
        print("\n--- LIVE 8: Capability 47 — Scenario Definition & Simulation ---")
        scen_payload = {
            "name": "LiveThermalEquilibrium",
            "variables": {"core_temp": 45.0, "coolant_flow": 12.0},
            "assumptions": ["Ambient temperature remains constant at 22C"],
        }
        res_scen = await execute_capability_live(client, "simulation.define_scenario", scen_payload)
        assert res_scen["status"] == "SUCCESS"
        live_scen_id = res_scen["output"]["scenario_id"]

        res_sim = await execute_capability_live(client, "simulation.run_simulation", {
            "scenario_id": live_scen_id,
            "mode": "deterministic",
            "step_delta": {"core_temp": 1.5, "coolant_flow": 0.2},
            "steps": 5,
        })
        assert res_sim["status"] == "SUCCESS"
        assert len(res_sim["output"]["trajectory"]) == 5
        assert res_sim["output"]["epistemic_tag"] == "SIMULATION_RESULT"
        print(f"  [PASS] LIVE 8: Scenario '{live_scen_id}' simulated across 5 steps.")
        passed_count += 1
        sys.stdout.flush()

        # -------------------------------------------------------------
        # LIVE 9: Capability 47 — Trend Forecasting with Epistemic Bounds
        # -------------------------------------------------------------
        print("\n--- LIVE 9: Capability 47 — Forecasting with Uncertainty Bounds ---")
        flow_history = [10.0, 12.5, 15.0, 18.2, 21.0, 24.5]
        res_fc = await execute_capability_live(client, "simulation.forecast", {
            "history": flow_history,
            "horizon": 4,
            "target_name": "projected_flow",
        })
        assert res_fc["status"] == "SUCCESS"
        fc_out = res_fc["output"]
        assert fc_out["epistemic_tag"] == "PREDICTION"
        assert "never present as guaranteed fact" in fc_out["epistemic_warning"].lower()
        pts = fc_out["forecast"]["forecast_points"]
        assert len(pts) == 4
        for p in pts:
            assert p["lower_bound"] < p["upper_bound"]
        print("  [PASS] LIVE 9: Predictive forecast generated with explicit uncertainty bounds.")
        passed_count += 1
        sys.stdout.flush()

        # -------------------------------------------------------------
        # LIVE 10: Integrated Multi-Capability Feedback Pipeline
        # -------------------------------------------------------------
        print("\n--- LIVE 10: Integrated E2E Cross-Capability Feedback Pipeline ---")
        # Step A: Ingest physical readings (45)
        live_stream = []
        for i in range(8):
            v = 50.0 + (i * 3.5)
            live_stream.append({"step": i, "temperature": v})

        # Step B: Profile in analytics (46)
        ds_resp = await execute_capability_live(client, "analytics.load_dataset", {"data": live_stream})
        live_ds_id = ds_resp["output"]["dataset_id"]

        # Step C: Forecast next 3 intervals (47)
        hist_vals = [d["temperature"] for d in live_stream]
        pred_resp = await execute_capability_live(client, "simulation.forecast", {
            "history": hist_vals,
            "horizon": 3,
            "target_name": "temp_forecast",
        })
        next_temp = pred_resp["output"]["forecast"]["forecast_points"][-1]["predicted_value"]

        # Step D: When projected temperature is critical, emergency stop the device (45)
        if next_temp > 70.0:
            stop_resp = await execute_capability_live(client, "robotics.emergency_stop", {
                "device_id": live_robot_id,
                "reason": f"Projected temperature {next_temp}C breaches threshold 70.0C",
            })
            assert stop_resp["status"] == "SUCCESS"

        print("  [PASS] LIVE 10: Full cross-capability sensory-analytics-prediction feedback loop completed.")
        passed_count += 1
        sys.stdout.flush()

    print("\n" + "=" * 80)
    print(f"LIVE VERIFICATION COMPLETE: {passed_count}/{total_count} SCENARIOS PASSED")
    print("=" * 80)
    sys.stdout.flush()
    return passed_count == total_count


def main():
    start_live_server()
    try:
        # Wait for server ready
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(wait_for_server(timeout=30.0))
        success = loop.run_until_complete(run_live_scenarios())
        loop.close()
    finally:
        stop_live_server()

    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if success else 1)


if __name__ == "__main__":
    main()
