"""Engine / session factory and migration bootstrap."""
from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import BACKEND_DIR

_engine: Engine | None = None
SessionLocal: sessionmaker[Session] = sessionmaker(autoflush=False, expire_on_commit=False)


def _sqlite_pragmas(dbapi_conn, _record) -> None:  # pragma: no cover - driver hook
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


def init_engine(database_url: str) -> Engine:
    """Create (or replace) the global engine."""
    global _engine
    if database_url.startswith("sqlite:///") and ":memory:" not in database_url:
        Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False, "timeout": 10},
        pool_pre_ping=True,
    )
    if _engine.dialect.name == "sqlite":
        event.listen(_engine, "connect", _sqlite_pragmas)
    SessionLocal.configure(bind=_engine)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("database engine is not initialised")
    return _engine


def _alembic_config(database_url: str):
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    cfg.attributes["configure_logger"] = False
    return cfg


def sqlite_path(database_url: str) -> Path | None:
    if database_url.startswith("sqlite:///") and ":memory:" not in database_url:
        return Path(database_url.removeprefix("sqlite:///"))
    return None


def pending_migrations(database_url: str) -> tuple[str | None, str]:
    """(current revision, head revision) of the database."""
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(_alembic_config(database_url))
    head = script.get_current_head() or ""
    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
    finally:
        engine.dispose()
    return current, head


def backup_sqlite(src: Path, backup_dir: Path, label: str) -> Path:
    """Consistent copy of a live SQLite database using the SQLite backup API."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backup_dir / f"{src.stem}-{stamp}-{label}{src.suffix}"
    source = sqlite3.connect(src)
    try:
        target = sqlite3.connect(dest)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    return dest


def run_migrations(database_url: str, backup_dir: Path | None = None) -> Path | None:
    """Apply Alembic migrations up to head (idempotent).

    If an existing SQLite database needs migrating, a backup is written first
    and is restored automatically when the migration fails. Backups are never
    deleted by the application. Returns the backup path (if one was made).
    """
    from alembic import command

    path = sqlite_path(database_url)
    current, head = pending_migrations(database_url)
    backup: Path | None = None
    if path is not None and path.exists() and path.stat().st_size > 0 and current != head:
        backup = backup_sqlite(path, backup_dir or path.parent / "backups", f"pre-{head}")
        _log().info("database backup before migration %s -> %s: %s", current, head, backup)
    try:
        command.upgrade(_alembic_config(database_url), "head")
    except Exception:
        if backup is not None and path is not None:
            if _engine is not None:
                _engine.dispose()
            for suffix in ("-wal", "-shm"):
                Path(str(path) + suffix).unlink(missing_ok=True)
            shutil.copyfile(backup, path)
            _log().error("migration failed; database restored from %s", backup)
        raise
    return backup


def _log():
    from app.logging_config import get_logger

    return get_logger("db")


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for background (non-request) code."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
