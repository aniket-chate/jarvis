"""Test script verifying Priority 5 (Shutdown/Restart) and Priority 6 (File Parameter Handoff)
over the REAL live running JARVIS server WebSocket.
"""

import asyncio
import json
import logging
import subprocess
import time
from pathlib import Path
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LiveHandoffTest")

WS_URL = "ws://127.0.0.1:8000/ws?token=jarvis-gateway-token-2026-auth"

async def run_chat_turn(ws, query: str, persona: str = "Jarvis") -> dict:
    req_id = f"test_{int(time.time()*1000)}"
    logger.info(">>> USER [%s]: %s", persona, query)
    
    msg = {
        "type": "chat",
        "query": query,
        "persona": persona,
        "request_id": req_id,
    }
    await ws.send(json.dumps(msg))
    
    received_chunks = []
    final_response = None
    
    t0 = time.time()
    while time.time() - t0 < 30.0:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
        except asyncio.TimeoutError:
            break
        data = json.loads(raw)
        msg_type = data.get("type")
        msg_req = data.get("request_id")

        if msg_req and msg_req != req_id:
            continue
        
        if msg_type == "chat_stream_chunk":
            received_chunks.append(data.get("token", ""))
        elif msg_type == "chat_response":
            final_response = data
            logger.info("<<< JARVIS [%s]: %s", data.get("active_persona"), data.get("response", "")[:120])
            break
                
    return {
        "query": query,
        "response": final_response.get("response", "") if final_response else "".join(received_chunks),
        "persona": final_response.get("active_persona", persona) if final_response else persona,
        "raw": final_response,
    }

async def main():
    logger.info("Connecting to live JARVIS server WebSocket...")
    async with websockets.connect(WS_URL, max_size=10_000_000) as ws:
        welcome = json.loads(await ws.recv())
        logger.info("WebSocket connection established: %s", welcome)

        # -------------------------------------------------------------
        # PRIORITY 5: Restart Confirmation Gate -> Real Execution
        # -------------------------------------------------------------
        logger.info("\n--- PRIORITY 5: Testing System Restart Gate & Execution ---")
        t1 = await run_chat_turn(ws, "Restart the computer")
        logger.info("Turn 1 response: %s", t1["response"])
        assert "confirm" in t1["response"].lower() or "gate" in t1["response"].lower() or "safety" in t1["response"].lower(), f"Expected gate, got: {t1['response']}"

        t2 = await run_chat_turn(ws, "Yes, confirm")
        logger.info("Turn 2 response: %s", t2["response"])
        
        # Abort the shutdown immediately for safety
        abort_res = subprocess.run(["shutdown", "/a"], capture_output=True, text=True)
        logger.info("Shutdown abort result: code=%d, stdout='%s', stderr='%s'", abort_res.returncode, abort_res.stdout.strip(), abort_res.stderr.strip())
        
        restart_verified = "restart" in t2["response"].lower() or "initiated" in t2["response"].lower() or abort_res.returncode == 0
        logger.info("Priority 5 Restart Execution Verified: %s", restart_verified)

        # -------------------------------------------------------------
        # PRIORITY 6: File Actions Gate Parameter Handoff
        # -------------------------------------------------------------
        logger.info("\n--- PRIORITY 6: Testing File Delete Parameter Handoff ---")
        test_file = Path("d:/assignment/JARVIS/workspace/test_handoff_delete.txt")
        test_file.write_text("This file must be deleted upon confirmation handoff.")
        assert test_file.exists(), "Setup failed: test file does not exist"

        t_del1 = await run_chat_turn(ws, f"Delete file {test_file.name} in workspace")
        logger.info("Delete Turn 1 response: %s", t_del1["response"])
        assert test_file.exists(), "File was deleted prematurely before confirmation!"

        t_del2 = await run_chat_turn(ws, "Yes, confirm")
        logger.info("Delete Turn 2 response: %s", t_del2["response"])
        time.sleep(0.5)

        del_verified = not test_file.exists()
        logger.info("Priority 6 File Deletion Executed: %s (File exists: %s)", del_verified, test_file.exists())

        result_summary = {
            "priority_5_restart": {
                "turn_1": t1["response"],
                "turn_2": t2["response"],
                "abort_code": abort_res.returncode,
                "verified": restart_verified
            },
            "priority_6_file_handoff": {
                "turn_1": t_del1["response"],
                "turn_2": t_del2["response"],
                "file_deleted": del_verified,
                "verified": del_verified
            }
        }
        
        Path("d:/assignment/JARVIS/workspace/handoff_verification.json").write_text(json.dumps(result_summary, indent=2))
        logger.info("\n=== VERIFICATION SUMMARY ===")
        logger.info(json.dumps(result_summary, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
