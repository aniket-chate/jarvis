"""Architectural Verification Test: Event Fabric Concurrency & Request Correlation."""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import time
from event_fabric.bus import EventFabricBus
from event_fabric.schemas import CommandEvent, InterruptEvent, EventPriority


async def test_concurrency_and_correlation():
    """Verifies that slow tasks never bleed responses into fast tasks and responses match request_id."""
    bus = EventFabricBus()

    req_slow_id = "req_slow_001"
    req_fast_id = "req_fast_002"

    bus.register_request(req_slow_id)
    bus.register_request(req_fast_id)

    async def _handle_commands(event):
        if event.request_id == req_slow_id:
            await asyncio.sleep(0.3)
            bus.complete_request(req_slow_id, {"response": "SLOW_DONE", "req": req_slow_id})
        elif event.request_id == req_fast_id:
            await asyncio.sleep(0.02)
            bus.complete_request(req_fast_id, {"response": "FAST_DONE", "req": req_fast_id})

    bus.subscribe("command.", _handle_commands)

    # Launch both events concurrently
    evt_slow = CommandEvent(request_id=req_slow_id, query="slow operation")
    evt_fast = CommandEvent(request_id=req_fast_id, query="fast operation")

    t_start = time.perf_counter()

    task_slow = asyncio.create_task(bus.await_response(req_slow_id, timeout_sec=2.0))
    task_fast = asyncio.create_task(bus.await_response(req_fast_id, timeout_sec=2.0))

    await bus.publish(evt_slow)
    await bus.publish(evt_fast)

    # Fast task must complete first
    res_fast = await task_fast
    t_fast_elapsed = time.perf_counter() - t_start

    assert res_fast["response"] == "FAST_DONE"
    assert res_fast["req"] == req_fast_id
    assert t_fast_elapsed < 0.2, f"Fast task was delayed by slow task! Elapsed: {t_fast_elapsed}s"

    # Slow task completes second
    res_slow = await task_slow
    assert res_slow["response"] == "SLOW_DONE"
    assert res_slow["req"] == req_slow_id


async def test_cancellation_isolation():
    """Verifies that cancelling one request does not abort unrelated requests."""
    bus = EventFabricBus()
    req_cancel = "req_cancel_1"
    req_survive = "req_survive_2"

    bus.register_request(req_cancel)
    bus.register_request(req_survive)

    async def _handle(event):
        if event.request_id == req_cancel:
            # Check cancellation token
            token = bus.get_cancellation_token(req_cancel)
            for _ in range(10):
                if token and token.is_set():
                    return
                await asyncio.sleep(0.05)
        elif event.request_id == req_survive:
            await asyncio.sleep(0.1)
            bus.complete_request(req_survive, {"response": "SURVIVED"})

    bus.subscribe("command.", _handle)

    task_cancel = asyncio.create_task(bus.await_response(req_cancel, timeout_sec=1.0))
    task_survive = asyncio.create_task(bus.await_response(req_survive, timeout_sec=1.0))

    await bus.publish(CommandEvent(request_id=req_cancel, query="to be cancelled"))
    await bus.publish(CommandEvent(request_id=req_survive, query="to survive"))

    # Cancel req_cancel
    await asyncio.sleep(0.02)
    bus.cancel_request(req_cancel, reason="User clicked stop")

    res_c = await task_cancel
    res_s = await task_survive

    assert res_c["status"] == "cancelled"
    assert res_s["response"] == "SURVIVED"


if __name__ == "__main__":
    asyncio.run(test_concurrency_and_correlation())
    asyncio.run(test_cancellation_isolation())
    print("ALL CONCURRENCY AND CANCELLATION TESTS PASSED CLEANLY!")
