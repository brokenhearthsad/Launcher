from __future__ import annotations

import time

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DB, State
from app.state import VERSION

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health(db: DB, state: State) -> dict:
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "version": VERSION,
        "database": "ok" if db_ok else "unavailable",
        "websocket_clients": state.bus.subscriber_count,
        "uptime_seconds": round(time.time() - state.started_at, 1),
        "frontend_built": (state.config.frontend_dist / "index.html").exists(),
    }
