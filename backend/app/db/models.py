"""SQLAlchemy ORM models.

String enums are stored as plain strings (portable across SQLite versions and
readable in DB browsers); allowed values live in :mod:`app.domain`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Stores UTC datetimes; SQLite drops tzinfo, so it is re-attached on load."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    pass


class Player(Base):
    """A test participant controlled by the bot AI. Never linked to Steam."""

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    team: Mapped[str] = mapped_column(String(16), index=True)
    slot: Mapped[int] = mapped_column(Integer, default=1)
    role: Mapped[str] = mapped_column(String(32))
    hero: Mapped[str] = mapped_column(String(64))
    bot_difficulty: Mapped[str] = mapped_column(String(16), default="hard")
    status: Mapped[str] = mapped_column(String(16), default="ready", index=True)
    # AI personality parameters, all in [0, 1]
    aggression: Mapped[float] = mapped_column(Float, default=0.5)
    farming_priority: Mapped[float] = mapped_column(Float, default=0.5)
    team_coordination: Mapped[float] = mapped_column(Float, default=0.5)
    risk_tolerance: Mapped[float] = mapped_column(Float, default=0.5)
    objective_priority: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow
    )

    participations: Mapped[list[MatchParticipant]] = relationship(back_populates="player")


class MatchSession(Base):
    __tablename__ = "match_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="created", index=True)
    environment: Mapped[str] = mapped_column(String(32), default="mock")
    map: Mapped[str] = mapped_column(String(64), default="lab_map_v1")
    scenario: Mapped[str] = mapped_column(String(32), default="balanced")
    game_mode: Mapped[str] = mapped_column(String(32), default="standard")
    seed: Mapped[int] = mapped_column(Integer, default=0)
    speed: Mapped[float] = mapped_column(Float, default=20.0)
    max_game_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    winner: Mapped[str | None] = mapped_column(String(16))
    win_condition: Mapped[str | None] = mapped_column(String(32))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    radiant_score: Mapped[int] = mapped_column(Integer, default=0)
    dire_score: Mapped[int] = mapped_column(Integer, default=0)
    events_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    participants: Mapped[list[MatchParticipant]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="MatchParticipant.id"
    )
    statistics: Mapped[list[PlayerStatistics]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    events: Mapped[list[MatchEvent]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class MatchParticipant(Base):
    __tablename__ = "match_participants"
    __table_args__ = (UniqueConstraint("session_id", "player_id", name="uq_participant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("match_sessions.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    team: Mapped[str] = mapped_column(String(16))
    hero: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(32))
    # Snapshot of the AI profile used for this session (reproducibility).
    ai_profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    session: Mapped[MatchSession] = relationship(back_populates="participants")
    player: Mapped[Player] = relationship(back_populates="participations")


class PlayerStatistics(Base):
    __tablename__ = "player_statistics"
    __table_args__ = (UniqueConstraint("session_id", "player_id", name="uq_player_stats"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("match_sessions.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    team: Mapped[str] = mapped_column(String(16), default="")
    hero: Mapped[str] = mapped_column(String(64), default="")
    kills: Mapped[int] = mapped_column(Integer, default=0)
    deaths: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    last_hits: Mapped[int] = mapped_column(Integer, default=0)
    denies: Mapped[int] = mapped_column(Integer, default=0)
    gpm: Mapped[float] = mapped_column(Float, default=0)
    xpm: Mapped[float] = mapped_column(Float, default=0)
    net_worth: Mapped[int] = mapped_column(Integer, default=0)
    hero_damage: Mapped[int] = mapped_column(Integer, default=0)
    tower_damage: Mapped[int] = mapped_column(Integer, default=0)
    healing: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    items: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_final: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped[MatchSession] = relationship(back_populates="statistics")
    player: Mapped[Player] = relationship()


class StatSnapshot(Base):
    """Per-minute time series used for "dynamics" charts."""

    __tablename__ = "stat_snapshots"
    __table_args__ = (Index("ix_snapshot_session_time", "session_id", "game_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("match_sessions.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    game_time: Mapped[float] = mapped_column(Float)
    gold: Mapped[int] = mapped_column(Integer)
    net_worth: Mapped[int] = mapped_column(Integer)
    xp: Mapped[int] = mapped_column(Integer)
    level: Mapped[int] = mapped_column(Integer)
    kills: Mapped[int] = mapped_column(Integer)
    deaths: Mapped[int] = mapped_column(Integer)
    assists: Mapped[int] = mapped_column(Integer)
    last_hits: Mapped[int] = mapped_column(Integer)
    denies: Mapped[int] = mapped_column(Integer)


class MatchEvent(Base):
    __tablename__ = "match_events"
    __table_args__ = (Index("ix_event_session_time", "session_id", "game_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("match_sessions.id", ondelete="CASCADE"))
    player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id", ondelete="SET NULL"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    game_time: Mapped[float] = mapped_column(Float, default=0)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    session: Mapped[MatchSession] = relationship(back_populates="events")


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    component: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, index=True
    )


class AppSetting(Base):
    """Runtime-editable settings (Settings page). Value is JSON."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow
    )
