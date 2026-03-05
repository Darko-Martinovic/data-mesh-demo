"""
In-process singleton EventBus backed by asyncio + threading.

Each domain service gets its own instance. Cross-service communication
is handled via HTTP; the bus demonstrates intra-service pub/sub.
"""

import asyncio
import json
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List


class EventBus:
    _instance: "EventBus | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable]] = {}
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="eventbus"
        )
        self._thread.start()

    # ── Singleton ────────────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "EventBus":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── Internal loop ─────────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    # ── Public API ────────────────────────────────────────────────────────────

    def subscribe(self, event: str, handler: Callable) -> None:
        """Register *handler* for *event*.  Handler may be sync or async."""
        self._subscribers.setdefault(event, []).append(handler)

    def publish(self, event: str, payload: Dict[str, Any]) -> None:
        """Publish *event* with *payload* to all registered handlers."""
        summary = json.dumps(payload)[:120]
        ts = datetime.now(timezone.utc).isoformat()
        print(f"[EVENT BUS] {ts} | {event} | {summary}", flush=True)

        for handler in self._subscribers.get(event, []):
            if asyncio.iscoroutinefunction(handler):
                asyncio.run_coroutine_threadsafe(handler(payload), self._loop)
            else:
                self._loop.call_soon_threadsafe(handler, payload)
