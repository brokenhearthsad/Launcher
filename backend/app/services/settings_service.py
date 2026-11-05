"""Runtime settings persisted in the ``app_settings`` table.

Defaults come from environment configuration (``app.config``); values saved
from the Settings page override them and take effect without a restart:
log levels immediately, simulator settings for newly created sessions,
publish rate and concurrency limits on the next session start.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import AppSetting
from app.logging_config import get_logger, set_levels
from app.schemas import RuntimeSettings, RuntimeSettingsUpdate

KEY = "runtime"
log = get_logger("settings")


def defaults(cfg: Settings) -> RuntimeSettings:
    return RuntimeSettings(
        default_speed=cfg.sim_default_speed,
        max_game_seconds=cfg.sim_max_game_seconds,
        snapshot_interval=cfg.sim_snapshot_interval,
        tick_seconds=cfg.sim_tick_seconds,
        ws_publish_hz=cfg.ws_publish_hz,
        log_level=cfg.log_level.upper(),
        db_log_level=cfg.db_log_level.upper(),
        max_concurrent_sessions=cfg.max_concurrent_sessions,
    )


def load(db: Session, cfg: Settings) -> RuntimeSettings:
    row = db.get(AppSetting, KEY)
    base = defaults(cfg).model_dump()
    if row is not None and isinstance(row.value, dict):
        base.update({k: v for k, v in row.value.items() if k in base})
    return RuntimeSettings(**base)


def update(db: Session, cfg: Settings, patch: RuntimeSettingsUpdate) -> RuntimeSettings:
    current = load(db, cfg).model_dump()
    changes = patch.model_dump(exclude_none=True)
    current.update(changes)
    validated = RuntimeSettings(**current)
    row = db.get(AppSetting, KEY)
    if row is None:
        db.add(AppSetting(key=KEY, value=validated.model_dump()))
    else:
        row.value = validated.model_dump()
    db.commit()
    apply(validated)
    log.info("runtime settings updated: %s", ", ".join(f"{k}={v}" for k, v in changes.items()) or "no changes")
    return validated


def apply(s: RuntimeSettings) -> None:
    set_levels(s.log_level, s.db_log_level)
