from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.db.models import MatchEvent, MatchParticipant, MatchSession, Player, PlayerStatistics
from app.db.session import get_engine, session_scope

TABLES = {"players", "match_sessions", "match_participants", "player_statistics", "match_events",
          "system_logs", "stat_snapshots", "app_settings", "alembic_version"}


def test_migrations_create_schema(client):
    insp = inspect(get_engine())
    assert TABLES <= set(insp.get_table_names())
    idx = {i["name"] for i in insp.get_indexes("match_events")}
    assert "ix_event_session_time" in idx
    fks = insp.get_foreign_keys("match_participants")
    assert {fk["referred_table"] for fk in fks} == {"players", "match_sessions"}


def test_cascade_delete_session(client):
    sid = client.post("/api/sessions", json={}).json()["id"]
    with session_scope() as db:
        db.add(MatchEvent(session_id=sid, event_type="x", event_data={}))
    with session_scope() as db:
        db.delete(db.get(MatchSession, sid))
    with session_scope() as db:
        assert db.scalars(select(MatchParticipant).where(MatchParticipant.session_id == sid)).all() == []
        assert db.scalars(select(MatchEvent).where(MatchEvent.session_id == sid)).all() == []


def test_unique_statistics_per_player_and_session(client):
    sid = client.post("/api/sessions", json={}).json()["id"]
    pid = client.get("/api/players").json()[0]["id"]
    with pytest.raises(IntegrityError):
        with session_scope() as db:
            db.add_all([PlayerStatistics(session_id=sid, player_id=pid), PlayerStatistics(session_id=sid, player_id=pid)])


def test_datetimes_are_utc_aware(client):
    with session_scope() as db:
        p = db.scalars(select(Player)).first()
        assert p.created_at.tzinfo is not None
        assert p.created_at <= datetime.now(timezone.utc)
    assert client.get("/api/players").json()[0]["created_at"].endswith("Z") or "+00:00" in \
        client.get("/api/players").json()[0]["created_at"]


def test_seed_is_idempotent(client):
    from app.db.seed import seed_players
    with session_scope() as db:
        assert seed_players(db) == 0
