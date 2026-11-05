"""In-process pub/sub for WebSocket clients.

Each subscriber gets a bounded queue. Publishing never blocks: when a slow
client's queue is full the oldest message is dropped, so one stuck browser tab
cannot stall the simulator.
"""
from __future__ import annotations

import asyncio
import itertools
from datetime import datetime, timezone
from typing import Any

from app.logging_config import get_logger

log = get_logger("ws")

# Phase 1 infrastructure events; later phases register their own types here.
EVENT_TYPES = ("system_error", "settings_updated", "shutdown")


class EventBus:
    def __init__(self, queue_size: int = 256):
        self._subs: dict[int, asyncio.Queue[dict[str, Any]]] = {}
        self._ids = itertools.count(1)
        self._queue_size = queue_size
        self.published = 0
        self.dropped = 0

    def subscribe(self) -> tuple[int, asyncio.Queue[dict[str, Any]]]:
        sid = next(self._ids)
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._queue_size)
        self._subs[sid] = q
        log.debug("websocket client subscribed (%d active)", len(self._subs))
        return sid, q

    def unsubscribe(self, sid: int) -> None:
        if self._subs.pop(sid, None) is not None:
            log.debug("websocket client unsubscribed (%d active)", len(self._subs))

    @property
    def subscriber_count(self) -> int:
        return len(self._subs)

    def publish(self, event_type: str, data: dict[str, Any], session_id: int | None = None) -> None:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event type {event_type}")
        msg = {"type": event_type, "session_id": session_id, "data": data,
               "ts": datetime.now(timezone.utc).isoformat()}
        self.published += 1
        for q in list(self._subs.values()):
            if q.full():
                try:
                    q.get_nowait()
                    self.dropped += 1
                except asyncio.QueueEmpty:  # pragma: no cover - race
                    pass
            q.put_nowait(msg)
