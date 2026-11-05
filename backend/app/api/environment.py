"""Steam / Dota 2 status (read-only) and the event journal."""
from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import DB, PageQ, PageSizeQ, State
from app.db.models import Event

router = APIRouter(tags=["environment"])


@router.get("/api/environment")
async def environment(state: State) -> dict:
    env = state.environment
    if env.polled_at == 0:
        await env.poll()
    return env.snapshot()


@router.post("/api/environment/refresh")
async def refresh(state: State) -> dict:
    """Re-read installation files and processes now (does not start or stop anything)."""
    await state.environment.refresh_install()
    await state.environment.poll()
    return state.environment.snapshot()


@router.get("/api/events")
def list_events(db: DB, page: PageQ = 1, page_size: PageSizeQ = 50,
                source: str | None = Query(None, max_length=32), type: str | None = Query(None, max_length=48),
                slot_id: int | None = Query(None, ge=1, le=10)) -> dict:
    conds = []
    if source:
        conds.append(Event.source == source)
    if type:
        conds.append(Event.type == type)
    if slot_id:
        conds.append(Event.slot_id == slot_id)
    total = db.scalar(select(func.count()).select_from(Event).where(*conds)) or 0
    rows = db.scalars(select(Event).where(*conds).order_by(Event.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{"id": e.id, "ts": e.ts.isoformat(), "source": e.source, "type": e.type,
                       "severity": e.severity, "slot_id": e.slot_id, "message": e.message, "data": e.data}
                      for e in rows], "total": total, "page": page, "page_size": page_size}
