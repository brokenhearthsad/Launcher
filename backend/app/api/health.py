from __future__ import annotations

import time

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DB, State
from app.domain import Difficulty, Environment, GameMode, PlayerStatus, Role, Scenario, Team
from app.game.adapters.registry import adapter_infos
from app.game.catalog import HEROES, ITEMS, hero_options, item_options
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
        "active_sessions": len(state.manager.active_ids()),
        "websocket_clients": state.bus.subscriber_count,
        "uptime_seconds": round(time.time() - state.started_at, 1),
    }


@router.get("/meta")
def meta() -> dict:
    """Enumerations and catalog data for building forms in the UI."""
    return {
        "teams": [t.value for t in Team],
        "roles": [r.value for r in Role],
        "difficulties": [d.value for d in Difficulty],
        "player_statuses": [s.value for s in PlayerStatus],
        "scenarios": [s.value for s in Scenario],
        "game_modes": [m.value for m in GameMode],
        "environments": [
            {"name": i.name, "title": i.title, "description": i.description, "available": i.available,
             "is_simulation": i.is_simulation, "capabilities": i.capabilities, "notes": i.notes}
            for i in adapter_infos()
        ],
        "known_environments": [e.value for e in Environment],
        "heroes": hero_options(),
        "items": item_options(),
        "counts": {"heroes": len(HEROES), "items": len(ITEMS)},
    }
