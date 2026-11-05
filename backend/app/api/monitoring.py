"""Machine metrics: current snapshot, recent in-memory series, per-minute history."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DB, State
from app.db.models import ResourceSample
from app.errors import AppError

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


class MonitoringUnavailable(AppError):
    status_code = 503
    code = "monitoring_disabled"


def _monitor(state):
    if state.monitor is None:
        raise MonitoringUnavailable("monitoring is disabled (DML_MONITORING_ENABLED=false)")
    return state.monitor


@router.get("/current")
async def current(state: State) -> dict:
    """Latest snapshot. Collected now if nothing has been collected yet."""
    mon = _monitor(state)
    snap = mon.store.latest or await mon.collect_once()
    return {**snap, "interval_seconds": mon._metrics_interval(), "mode": "active" if mon.active else "idle"}


@router.get("/recent")
def recent(state: State, seconds: int = Query(900, ge=10, le=3600)) -> dict:
    """Raw samples kept in memory (not persisted)."""
    return {"points": _monitor(state).store.recent(seconds)}


@router.get("/history")
def history(db: DB, hours: int = Query(24, ge=1, le=24 * 365)) -> dict:
    """Per-minute aggregates from SQLite."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = db.scalars(select(ResourceSample).where(ResourceSample.ts >= since).order_by(ResourceSample.ts)).all()
    cols = [c.name for c in ResourceSample.__table__.columns if c.name != "id"]
    return {"points": [{c: getattr(r, c) for c in cols} for r in rows]}
