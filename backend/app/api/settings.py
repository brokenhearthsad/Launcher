from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import delete, text

from app.api.deps import DB, State
from app.db.models import SystemLog
from app.db.session import get_engine
from app.logging_config import get_logger
from app.schemas import PurgeRequest, RuntimeSettings, RuntimeSettingsUpdate
from app.services import settings_service
from app.state import VERSION

router = APIRouter(prefix="/api/settings", tags=["settings"])
log = get_logger("settings")


def _db_info(url: str) -> dict:
    info: dict = {"url": url, "dialect": get_engine().dialect.name}
    if url.startswith("sqlite:///"):
        path = Path(url.removeprefix("sqlite:///"))
        info["path"] = str(path)
        info["size_bytes"] = path.stat().st_size if path.exists() else 0
    return info


@router.get("")
def get_settings(state: State) -> dict:
    cfg = state.config
    return {
        "runtime": state.runtime.model_dump(),
        "backend": {"version": VERSION, "host": cfg.host, "port": cfg.port, "cors_origins": cfg.cors_origins,
                    "api_rate_limit_per_minute": cfg.api_rate_limit_per_minute, "log_dir": str(cfg.log_dir)},
        "database": _db_info(cfg.database_url),
    }


@router.put("", response_model=RuntimeSettings)
def update_settings(data: RuntimeSettingsUpdate, db: DB, state: State):
    state.runtime = settings_service.update(db, state.config, data)
    return state.runtime


@router.post("/database/vacuum")
def vacuum(state: State) -> dict:
    before = _db_info(state.config.database_url).get("size_bytes")
    with get_engine().connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT").execute(text("VACUUM"))
    after = _db_info(state.config.database_url).get("size_bytes")
    log.info("database vacuumed: %s -> %s bytes", before, after)
    return {"size_before": before, "size_after": after}


@router.post("/database/purge-logs")
def purge_logs(data: PurgeRequest, db: DB) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=data.older_than_days)
    res = db.execute(delete(SystemLog).where(SystemLog.timestamp < cutoff))
    db.commit()
    log.info("purged %d log rows older than %d days", res.rowcount, data.older_than_days)
    return {"deleted": res.rowcount}
