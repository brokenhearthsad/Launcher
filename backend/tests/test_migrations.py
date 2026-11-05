"""Upgrading a v1 (simulator) database: backup first, drop old tables, keep logs/settings."""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db.session import init_engine, pending_migrations
from app.main import create_app
from tests.conftest import make_settings


def _make_v1_db(settings: Settings) -> None:
    from alembic import command
    from app.db.session import _alembic_config

    init_engine(settings.database_url)
    command.upgrade(_alembic_config(settings.database_url), "0001")
    path = settings.database_url.removeprefix("sqlite:///")
    con = sqlite3.connect(path)
    con.execute("INSERT INTO players (id, name, team, slot, role, hero, bot_difficulty, status, aggression, "
                "farming_priority, team_coordination, risk_tolerance, objective_priority, created_at, updated_at) "
                "VALUES (1, 'Radiant 1', 'radiant', 1, 'carry', 'axe', 'hard', 'ready', .5, .5, .5, .5, .5, "
                "'2026-01-01', '2026-01-01')")
    con.execute("INSERT INTO system_logs (level, component, message, timestamp) "
                "VALUES ('INFO', 'old', 'kept log', '2026-01-01 00:00:00')")
    con.commit()
    con.close()


def _tables(path) -> set[str]:
    con = sqlite3.connect(path)
    try:
        return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()


def test_upgrade_from_v1_makes_backup_and_keeps_infrastructure(tmp_path):
    s = make_settings(tmp_path)
    _make_v1_db(s)
    db_path = s.database_url.removeprefix("sqlite:///")
    assert pending_migrations(s.database_url)[0] == "0001"

    with TestClient(create_app(s)) as c:
        backups = list(s.backup_dir.glob("*.db"))
        assert len(backups) == 1 and "pre-0004" in backups[0].name
        # backup still contains the old simulator data
        old = sqlite3.connect(backups[0])
        assert old.execute("SELECT name FROM players").fetchone() == ("Radiant 1",)
        old.close()
        # migrated database: simulator tables gone, logs kept
        tables = _tables(db_path)
        assert "players" not in tables and "match_sessions" not in tables
        assert {"system_logs", "app_settings", "alembic_version"} <= tables
        assert any(log["message"] == "kept log" for log in c.get("/api/logs", params={"page_size": 200}).json()["items"])
        assert c.get("/api/settings").json()["database"]["last_backup"].endswith(backups[0].name)
    assert pending_migrations(s.database_url) == ("0004", "0004")

    # second start: nothing to migrate, no new backup
    with TestClient(create_app(s)):
        pass
    assert len(list(s.backup_dir.glob("*.db"))) == 1


def test_fresh_install_needs_no_backup(tmp_path):
    s = make_settings(tmp_path)
    with TestClient(create_app(s)):
        pass
    assert not s.backup_dir.exists() or not list(s.backup_dir.glob("*.db"))


def test_failed_migration_restores_original(tmp_path, monkeypatch):
    s = make_settings(tmp_path)
    _make_v1_db(s)
    db_path = s.database_url.removeprefix("sqlite:///")

    import alembic.command

    real_upgrade = alembic.command.upgrade

    def broken(cfg, rev):
        real_upgrade(cfg, rev)  # really drops the tables...
        raise RuntimeError("simulated failure after partial migration")

    monkeypatch.setattr(alembic.command, "upgrade", broken)
    with pytest.raises(RuntimeError):
        create_app(s)
    assert "players" in _tables(db_path), "original database must be restored from backup"
    assert pending_migrations(s.database_url)[0] == "0001"


def test_upgrade_from_phase1_backs_up_and_seeds_ten_slots(tmp_path):
    from alembic import command
    from app.db.session import _alembic_config

    s = make_settings(tmp_path)
    init_engine(s.database_url)
    command.upgrade(_alembic_config(s.database_url), "0002")
    db_path = s.database_url.removeprefix("sqlite:///")
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO system_logs (level, component, message, timestamp) "
                "VALUES ('INFO', 'phase1', 'phase1 log', '2026-01-01 00:00:00')")
    con.commit()
    con.close()
    with TestClient(create_app(s)):
        pass
    backups = list(s.backup_dir.glob("*pre-0004*.db"))
    assert len(backups) == 1
    con = sqlite3.connect(db_path)
    try:
        slots = con.execute("SELECT id, name, team, binding FROM client_slots ORDER BY id").fetchall()
        assert [r[0] for r in slots] == list(range(1, 11))
        assert slots[0] == (1, "Slot 1", "radiant", "none") and slots[9][2] == "dire"
        assert con.execute("SELECT count(*) FROM system_logs WHERE message='phase1 log'").fetchone() == (1,)
        assert {"events", "resource_samples"} <= _tables(db_path)
    finally:
        con.close()


def test_upgrade_from_phase2_keeps_slots_and_adds_gsi_matches(tmp_path):
    from alembic import command
    from app.db.session import _alembic_config

    s = make_settings(tmp_path)
    init_engine(s.database_url)
    command.upgrade(_alembic_config(s.database_url), "0003")
    db_path = s.database_url.removeprefix("sqlite:///")
    con = sqlite3.connect(db_path)
    con.execute("UPDATE client_slots SET name='Мой ПК', binding='local_client' WHERE id=1")
    con.commit()
    con.close()
    with TestClient(create_app(s)):
        pass
    assert len(list(s.backup_dir.glob("*pre-0004*.db"))) == 1
    con = sqlite3.connect(db_path)
    try:
        assert con.execute("SELECT name, binding FROM client_slots WHERE id=1").fetchone() == ("Мой ПК", "local_client")
        assert "gsi_matches" in _tables(db_path)
    finally:
        con.close()
