import asyncio
import json
import sys
import time
import websockets

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

WS_URL = "ws://127.0.0.1:8000/ws?token=jarvis-gateway-token-2026-auth&device_id=client_aniket_runner"

TEST_TURNS = [
    # TEST 001 - BASIC IDENTITY
    ("TEST 001 - BASIC IDENTITY", "JARVIS, who am I?"),
    ("TEST 001 - FOLLOW-UP", "And what should I call you?"),

    # TEST 002 - NATURAL CONVERSATION
    ("TEST 002 - NATURAL CONVERSATION", "You know, I've been thinking about rebuilding the whole thing again."),
    ("TEST 002 - FOLLOW-UP", "The AI part."),

    # TEST 007 - WINDOWS CONTROL
    ("TEST 007 - WINDOWS CONTROL", "Open File Explorer."),

    # TEST 026 - SYSTEM INFORMATION (RAM)
    ("TEST 026 - SYSTEM INFORMATION", "How much RAM am I using right now?"),
    ("TEST 026 - FOLLOW-UP", "What's eating the most memory?"),

    # TEST 027 - CPU
    ("TEST 027 - CPU TELEMETRY", "And CPU?"),

    # TEST 028 - NETWORK
    ("TEST 028 - NETWORK TELEMETRY", "Is my internet working?"),

    # TEST 029 - DEVICE CONNECTION
    ("TEST 029 - DEVICE CONNECTION", "Is my phone connected to JARVIS?"),

    # TEST 038 - CODE GENERATION
    ("TEST 038 - CODE GENERATION", "Write a Python function that checks whether the backend is alive."),

    # TEST 087 - RAPID QUESTIONS
    ("TEST 087 - RAPID: CPU", "CPU?"),
    ("TEST 087 - RAPID: RAM", "RAM?"),
    ("TEST 087 - RAPID: NETWORK", "Network?"),
    ("TEST 087 - RAPID: PHONE", "Phone?"),

    # TEST 098 - HEALTH CHECK
    ("TEST 098 - HEALTH CHECK", "Give me the full JARVIS health report."),

    # FINAL STRESS SEQUENCE
    ("FINAL STRESS - BACKEND", "JARVIS, check the backend."),
    ("FINAL STRESS - PHONE", "And my phone?"),
    ("FINAL STRESS - COMPLETE REPORT", "Good. Now give me the complete JARVIS health report.")
]

async def run_test():
    print("=" * 70, flush=True)
    print("STARTING LIVE ANIKET TEST SUITE ON SCREEN (CHROME HUD)", flush=True)
    print("=" * 70, flush=True)
    print(f"Connecting to {WS_URL} ...", flush=True)
    
    ws = None
    async def get_ws():
        nonlocal ws
        is_open = False
        try:
            if ws is not None and getattr(ws, "protocol", None) and ws.protocol.state.name == "OPEN":
                is_open = True
        except Exception:
            is_open = False

        if not is_open:
            ws = await websockets.connect(WS_URL, max_size=16 * 1024 * 1024, ping_interval=None, ping_timeout=None)
            init_msg = await ws.recv()
            await ws.send(json.dumps({
                "type": "register",
                "device_id": "client_aniket_runner",
                "name": "Aniket (Test Runner)",
                "client_type": "pc"
            }))
            await ws.recv()
        return ws

    ws = await get_ws()
    print("\nConnected! All queries and JARVIS responses will broadcast LIVE to user's Chrome HUD on screen!\n", flush=True)

    passed = 0
    total = len(TEST_TURNS)

    for idx, (label, query) in enumerate(TEST_TURNS, 1):
        print(f"\n--- [{idx}/{total}] {label} ---", flush=True)
        print(f"ANIKET: {query}", flush=True)

        req_payload = {
            "type": "chat",
            "query": query,
            "author": "Aniket",
            "request_id": f"aniket_req_{idx}_{int(time.time()*1000)}"
        }

        try:
            current_ws = await get_ws()
            await current_ws.send(json.dumps(req_payload))
        except Exception as conn_err:
            print(f"  [Reconnecting on error: {conn_err}]", flush=True)
            ws = None
            current_ws = await get_ws()
            await current_ws.send(json.dumps(req_payload))

        # Await response from server
        got_response = False
        response_text = ""
        start_t = time.time()

        while time.time() - start_t < 45:
            try:
                raw = await asyncio.wait_for(current_ws.recv(), timeout=40.0)
                msg = json.loads(raw)
                m_type = msg.get("type")

                if m_type == "chat_response":
                    response_text = msg.get("response") or msg.get("text") or ""
                    got_response = True
                    break
                elif m_type == "task_progress":
                    pass
            except asyncio.TimeoutError:
                print("  [Timeout waiting for turn response]", flush=True)
                break
            except Exception as e:
                print(f"  [Recv notice: {e}]", flush=True)
                break

        if got_response and response_text:
            print(f"JARVIS: {response_text.strip()}", flush=True)
            passed += 1
        else:
            print("JARVIS: [NO RESPONSE RECEIVED]", flush=True)

        # Pause naturally so HUD updates visually and audio can play
        await asyncio.sleep(2.0)

    try:
        if ws:
            await ws.close()
    except Exception:
        pass

    print("\n" + "=" * 70, flush=True)
    print(f"TEST SUITE COMPLETE: {passed}/{total} TURNS PASSED", flush=True)
    print("=" * 70, flush=True)

if __name__ == "__main__":
    asyncio.run(run_test())
