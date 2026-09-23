import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from playwright.async_api import async_playwright
import websockets

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

WS_URL = "ws://127.0.0.1:8000/ws?token=jarvis-gateway-token-2026-auth&device_id=client_aniket_runner"
ARTIFACTS_DIR = Path(r"C:\Users\acer\.gemini\antigravity-ide\brain\94f56a9a-4139-413e-b91f-4572270e65fc")


async def take_cdp_screenshot(filename: str) -> bool:
    """Takes a real screenshot of the active Chrome tab over CDP port 9222 using async Playwright."""
    try:
        dest = ARTIFACTS_DIR / filename
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=5000)
            if browser.contexts and browser.contexts[0].pages:
                page = browser.contexts[0].pages[-1]
                await page.screenshot(path=str(dest))
                print(f"  [SCREENSHOT CAPTURED] {dest} (Page: {page.url})", flush=True)
                return True
    except Exception as e:
        print(f"  [SCREENSHOT ERROR] {e}", flush=True)
    return False


async def run_30_turns():
    print("=" * 80, flush=True)
    print("JARVIS 30-TURN LIVE CONVERSATIONAL & REAL CHROME CDP CAPABILITY VALIDATION", flush=True)
    print("User: Aniket | Target: Real Google Chrome with CDP on port 9222 | Live HUD", flush=True)
    print("=" * 80, flush=True)

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
    print("Connected to JARVIS Gateway! Broadcasting turns live to Real Chrome HUD...\n", flush=True)

    records = []

    async def send_turn(turn_num: str, query: str, wait_response_s: float = 65.0) -> str:
        print(f"\n--- [TURN {turn_num}] ---", flush=True)
        print(f"ANIKET: {query}", flush=True)

        current_ws = await get_ws()

        # Drain any residual buffered messages before sending
        while True:
            try:
                _ = await asyncio.wait_for(current_ws.recv(), timeout=0.1)
            except Exception:
                break

        t_start = time.perf_counter()
        req_id = f"turn_{turn_num}_{int(time.time()*1000)}"
        req_payload = {
            "type": "chat",
            "query": query,
            "author": "Aniket",
            "request_id": req_id
        }

        await current_ws.send(json.dumps(req_payload))

        resp_text = ""
        while time.perf_counter() - t_start < wait_response_s:
            try:
                raw = await asyncio.wait_for(current_ws.recv(), timeout=wait_response_s)
                msg = json.loads(raw)
                m_type = msg.get("type")
                if m_type == "chat_response":
                    resp_text = msg.get("response") or msg.get("text") or ""
                    break
            except Exception as e:
                print(f"  [Recv note: {e}]", flush=True)
                break

        latency_ms = (time.perf_counter() - t_start) * 1000
        clean = resp_text.strip()
        print(f"JARVIS ({latency_ms:.0f}ms): {clean if clean else '[NO RESPONSE]'}", flush=True)
        records.append({
            "turn": turn_num,
            "query": query,
            "response": clean,
            "latency_ms": round(latency_ms, 1)
        })
        await asyncio.sleep(2.0)
        return clean

    # 1. Aniket: "hey"
    await send_turn("1", "hey")

    # 2. Aniket: "who is virat kohli"
    await send_turn("2", "who is virat kohli")

    # 3. Aniket: "who made you"
    await send_turn("3", "who made you")

    # 4. Aniket: "call yourself Friday"
    await send_turn("4", "call yourself Friday")

    # 5. Aniket: [3 unrelated factual questions - math, geography, science]
    await send_turn("5a", "What is the capital of Australia?")
    await send_turn("5b", "What is 17 multiplied by 19?")
    await send_turn("5c", "Why is the sky blue?")

    # 6. Aniket: "open youtube and play a song, any song is fine"
    await send_turn("6", "open youtube and play a song, any song is fine", wait_response_s=70.0)
    await asyncio.sleep(4.0)

    # 7. Aniket: "hold on, pause it"
    await send_turn("7", "hold on, pause it")
    await asyncio.sleep(2.0)
    await take_cdp_screenshot("turn_07_paused.png")

    # 8. Aniket: "ok go ahead, continue"
    await send_turn("8", "ok go ahead, continue")
    await asyncio.sleep(2.0)
    await take_cdp_screenshot("turn_08_resumed.png")

    # 9. Aniket: "actually play something else instead, maybe lofi music"
    await send_turn("9", "actually play something else instead, maybe lofi music", wait_response_s=70.0)
    await asyncio.sleep(4.0)
    await take_cdp_screenshot("turn_09_lofi.png")

    # 10. Aniket: "close that tab"
    await send_turn("10", "close that tab")
    await asyncio.sleep(2.0)
    await take_cdp_screenshot("turn_10_closed.png")

    # 11. Aniket: "open instagrm and search for a public account, like nasa"
    await send_turn("11", "open instagrm and search for a public account, like nasa", wait_response_s=70.0)

    # 12. Aniket: "whats app sachin and tell him I'm running late"
    await send_turn("12", "whats app sachin and tell him I'm running late")

    # 13. Aniket: "give me the route from jalna to pune"
    await send_turn("13", "give me the route from jalna to pune", wait_response_s=60.0)

    # 14. Aniket: "can you call +919876543210 for me"
    await send_turn("14", "can you call +919876543210 for me")

    # 15. Aniket: "whats my cpu and ram looking like"
    await send_turn("15", "whats my cpu and ram looking like")

    # 16. Aniket: "snap this to the left please"
    await send_turn("16", "snap this to the left please")
    await asyncio.sleep(1.5)
    await take_cdp_screenshot("turn_16_window_snapped.png")

    # 17. Aniket: "find a file on my system called requirements.txt"
    await send_turn("17", "find a file on my system called requirements.txt")

    # 18. Aniket: "make a note file on my desktop that says testing full run"
    resp_18 = await send_turn("18a", "make a note file on my desktop that says testing full run")
    if "confirm" in resp_18.lower() or "safety" in resp_18.lower() or "approval" in resp_18.lower():
        await send_turn("18b", "confirm")
    await asyncio.sleep(1.5)
    await take_cdp_screenshot("turn_18_desktop_note.png")

    # 19. Aniket: "move that file to downloads"
    resp_19 = await send_turn("19a", "move that file to downloads")
    if "confirm" in resp_19.lower() or "safety" in resp_19.lower():
        await send_turn("19b", "confirm")
    await asyncio.sleep(1.5)
    await take_cdp_screenshot("turn_19_moved_downloads.png")

    # 20. Aniket: "run whoami for me" / "can you execute ipconfig"
    await send_turn("20a", "run whoami for me")
    await send_turn("20b", "can you execute ipconfig")

    # 21. Aniket: "set a reminder in 90 seconds to check on this test"
    rem_start_time = time.time()
    print(f"\n[TURN 21 TIMING] Initiating 90-second reminder at {time.strftime('%X')}...", flush=True)
    await send_turn("21", "set a reminder in 90 seconds to check on this test")
    print("[TURN 21 TIMING] Waiting real elapsed 90 seconds (no shortcuts)...", flush=True)
    for elapsed in range(15, 95, 15):
        await asyncio.sleep(15)
        print(f"  [Reminder Wait] {elapsed}s / 90s elapsed...", flush=True)
    rem_end_time = time.time()
    print(f"[TURN 21 TIMING] 90-second wait complete at {time.strftime('%X')} (Total elapsed: {rem_end_time - rem_start_time:.1f}s)", flush=True)

    # 22. Aniket: "show me my recent notifications"
    await send_turn("22", "show me my recent notifications")

    # 23. Show JARVIS receipt: "read this and save the text"
    await send_turn("23", "read this and save the text", wait_response_s=45.0)

    # 24. Aniket: "who is my best friend" / "what book do I like"
    await send_turn("24a", "who is my best friend")
    await send_turn("24b", "what book do I like")

    # 25. Aniket: "what can you actually do right now"
    await send_turn("25", "what can you actually do right now")

    # 26. Aniket: "tell me about your learning/RL"
    await send_turn("26", "tell me about your learning/RL")

    # 27. Wait 10+ real minutes doing unrelated things, then "who is your owner again"
    mem_start_time = time.time()
    print(f"\n[TURN 27 TIMING] Starting 10-minute real-time memory gap at {time.strftime('%X')}...", flush=True)
    for m in range(1, 11):
        await asyncio.sleep(60)
        print(f"  [Memory Wait Progress] {m} / 10 minutes elapsed at {time.strftime('%X')}...", flush=True)
    mem_end_time = time.time()
    print(f"[TURN 27 TIMING] 10-minute wait complete at {time.strftime('%X')} (Total elapsed: {(mem_end_time - mem_start_time)/60:.2f} min)", flush=True)
    await send_turn("27", "who is your owner again")

    # 28. Aniket: "linkedin पर internship खोज के दो"
    await send_turn("28", "linkedin पर internship खोज के दो", wait_response_s=50.0)

    # 29. Aniket: "open snapchat"
    await send_turn("29", "open snapchat", wait_response_s=45.0)

    # 30. Aniket: "thanks, that's it for now"
    await send_turn("30", "thanks, that's it for now")

    try:
        if ws:
            await ws.close()
    except Exception:
        pass

    out_file = Path("d:/assignment/JARVIS/live_30_turns_results.json")
    out_file.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + "=" * 80, flush=True)
    print(f"30-TURN LIVE VALIDATION SESSION COMPLETE! Saved to {out_file}", flush=True)
    print("=" * 80, flush=True)


if __name__ == "__main__":
    asyncio.run(run_30_turns())
