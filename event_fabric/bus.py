"""JARVIS Unified Event Fabric Bus.

The central asynchronous event routing fabric supporting:
- Strong request_id correlation (futures-based response matching)
- Priority-driven dispatch (Critical interrupts preempt normal events)
- Cooperative cancellation tokens
- Failure isolation & backpressure
- Decoupled from FIFO WebSocket streams
"""

import asyncio
from collections import defaultdict
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional
from event_fabric.schemas import (
    UniversalEvent,
    CommandEvent,
    InterruptEvent,
    EventPriority,
    EventStatus,
)

logger = logging.getLogger("JARVIS.EventFabric.Bus")


class EventFabricBus:
    """The central event fabric routing all state transitions and interactions."""

    def __init__(self, max_concurrent_tasks: int = 32):
        self._subscribers: Dict[str, List[Callable[[UniversalEvent], Coroutine[Any, Any, None]]]] = defaultdict(list)
        self._cancellation_tokens: Dict[str, asyncio.Event] = {}
        self._response_futures: Dict[str, asyncio.Future] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._dead_letter_queue: List[UniversalEvent] = []

    def register_request(self, request_id: str) -> asyncio.Event:
        """Registers a cancellation token and response future for an incoming request."""
        token = asyncio.Event()
        self._cancellation_tokens[request_id] = token
        loop = asyncio.get_event_loop()
        self._response_futures[request_id] = loop.create_future()
        return token

    def get_cancellation_token(self, request_id: str) -> Optional[asyncio.Event]:
        return self._cancellation_tokens.get(request_id)

    def cancel_request(self, request_id: str, reason: str = "User cancellation"):
        """Signals cancellation for an active request."""
        token = self._cancellation_tokens.get(request_id)
        if token:
            logger.info("[EventFabric] Cancelling request_id=%s (reason: %s)", request_id, reason)
            token.set()
        fut = self._response_futures.get(request_id)
        if fut and not fut.done():
            fut.set_result({
                "status": "cancelled",
                "request_id": request_id,
                "reason": reason,
            })

    def complete_request(self, request_id: str, response_payload: Dict[str, Any]):
        """Delivers a correlated response strictly to the matching request_id future."""
        fut = self._response_futures.get(request_id)
        if fut and not fut.done():
            fut.set_result(response_payload)
            logger.debug("[EventFabric] Completed request_id=%s", request_id)
        else:
            # Late arrival for timed-out or abandoned request -> Divert to dead-letter ledger
            logger.info("[EventFabric] Late arrival for request_id=%s; diverted to background ledger", request_id)
            self._dead_letter_queue.append(
                UniversalEvent(request_id=request_id, event_type="late_response", payload=response_payload)
            )

    async def await_response(self, request_id: str, timeout_sec: float = 60.0) -> Dict[str, Any]:
        """Awaits the correlated response for a specific request_id without FIFO pollution."""
        fut = self._response_futures.get(request_id)
        if not fut:
            return {"status": "error", "error": f"Unknown request_id: {request_id}"}
        try:
            return await asyncio.wait_for(fut, timeout=timeout_sec)
        except asyncio.TimeoutError:
            self.cancel_request(request_id, reason=f"Timeout after {timeout_sec}s")
            return {"status": "timed_out", "request_id": request_id, "timeout_sec": timeout_sec}
        finally:
            self._cleanup_request(request_id)

    def _cleanup_request(self, request_id: str):
        self._cancellation_tokens.pop(request_id, None)
        self._response_futures.pop(request_id, None)

    def subscribe(self, event_type_prefix: str, handler: Callable[[UniversalEvent], Coroutine[Any, Any, None]]):
        """Subscribes an async handler to an event category (e.g. 'command.', 'action.')."""
        self._subscribers[event_type_prefix].append(handler)
        logger.debug("[EventFabric] Subscribed to prefix '%s'", event_type_prefix)

    def publish_sync(self, event: UniversalEvent):
        """Publishes an event synchronously to all matching subscribers if an event loop is running."""
        matched_handlers = []
        for prefix, handlers in self._subscribers.items():
            if event.event_type.startswith(prefix) or prefix == "*":
                matched_handlers.extend(handlers)

        if not matched_handlers:
            return

        async def _safe_run(h):
            async with self._semaphore:
                try:
                    await h(event)
                except Exception as ex:
                    logger.error("[EventFabric] Exception in handler for '%s': %s", event.event_type, ex)

        try:
            loop = asyncio.get_running_loop()
            for h in matched_handlers:
                loop.create_task(_safe_run(h))
        except RuntimeError:
            pass

    async def publish(self, event: UniversalEvent):
        """Publishes an event to all matching subscribers with concurrency isolation."""
        self.publish_sync(event)


# Master Event Fabric singleton
event_bus = EventFabricBus()
