"""Event journal: persisted to the ``events`` table and pushed to open pages."""
from __future__ import annotations

from typing import Any

from app.db.models import Event
from app.db.session import session_scope
from app.logging_config import get_logger

log = get_logger("events")


def record(bus: Any, source: str, type_: str, message: str, *, data: dict[str, Any] | None = None,
           slot_id: int | None = None, severity: str = "info") -> dict[str, Any]:
    """Store one event (call from a worker thread or sync code) and publish it."""
    with session_scope() as db:
        ev = Event(source=source, type=type_, message=message, data=data or {}, slot_id=slot_id, severity=severity)
        db.add(ev)
        db.flush()
        out = {"id": ev.id, "ts": ev.ts.isoformat(), "source": source, "type": type_, "severity": severity,
               "slot_id": slot_id, "message": message, "data": data or {}}
    log.info("%s/%s: %s", source, type_, message)
    if bus is not None:
        bus.publish("event_created", out)
    return out
