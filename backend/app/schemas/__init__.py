"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain import Difficulty, Environment, GameMode, PlayerStatus, Role, Scenario, Team
from app.game.catalog import HEROES

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- players
class AIParams(BaseModel):
    bot_difficulty: Difficulty = Difficulty.HARD
    aggression: float = Field(0.5, ge=0.0, le=1.0)
    farming_priority: float = Field(0.5, ge=0.0, le=1.0)
    team_coordination: float = Field(0.5, ge=0.0, le=1.0)
    risk_tolerance: float = Field(0.5, ge=0.0, le=1.0)
    objective_priority: float = Field(0.5, ge=0.0, le=1.0)


def _check_hero(v: str | None) -> str | None:
    if v is not None and v not in HEROES:
        raise ValueError(f"unknown hero '{v}'")
    return v


class PlayerCreate(AIParams):
    name: str = Field(min_length=1, max_length=64)
    team: Team
    role: Role
    hero: str
    slot: int = Field(1, ge=1, le=5)
    status: PlayerStatus = PlayerStatus.READY

    _hero = field_validator("hero")(_check_hero)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v

    @field_validator("status")
    @classmethod
    def _settable_status(cls, v: PlayerStatus) -> PlayerStatus:
        if v not in (PlayerStatus.READY, PlayerStatus.OFFLINE):
            raise ValueError("status can only be set to 'ready' or 'offline' manually")
        return v


class PlayerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    team: Team | None = None
    role: Role | None = None
    hero: str | None = None
    slot: int | None = Field(None, ge=1, le=5)
    status: PlayerStatus | None = None
    bot_difficulty: Difficulty | None = None
    aggression: float | None = Field(None, ge=0.0, le=1.0)
    farming_priority: float | None = Field(None, ge=0.0, le=1.0)
    team_coordination: float | None = Field(None, ge=0.0, le=1.0)
    risk_tolerance: float | None = Field(None, ge=0.0, le=1.0)
    objective_priority: float | None = Field(None, ge=0.0, le=1.0)

    _hero = field_validator("hero")(_check_hero)

    @field_validator("status")
    @classmethod
    def _settable_status(cls, v: PlayerStatus | None) -> PlayerStatus | None:
        if v is not None and v not in (PlayerStatus.READY, PlayerStatus.OFFLINE):
            raise ValueError("status can only be set to 'ready' or 'offline' manually")
        return v


class PlayerOut(ORM):
    id: int
    name: str
    team: str
    slot: int
    role: str
    hero: str
    bot_difficulty: str
    status: str
    aggression: float
    farming_priority: float
    team_coordination: float
    risk_tolerance: float
    objective_priority: float
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- sessions
class ParticipantIn(BaseModel):
    player_id: int
    team: Team | None = None
    hero: str | None = None
    role: Role | None = None

    _hero = field_validator("hero")(_check_hero)


class SessionCreate(BaseModel):
    name: str = Field("Test session", min_length=1, max_length=128)
    environment: Environment = Environment.MOCK
    scenario: Scenario = Scenario.BALANCED
    game_mode: GameMode = GameMode.STANDARD
    seed: int | None = Field(None, ge=0, le=2_147_483_647)
    speed: float | None = Field(None, ge=1.0, le=1000.0, description="game seconds per real second")
    max_game_seconds: int | None = Field(None, ge=300, le=7200)
    participants: list[ParticipantIn] | None = Field(
        None, description="defaults to all non-offline players with their configured team/hero/role"
    )

    @model_validator(mode="after")
    def _unique(self) -> SessionCreate:
        if self.participants is not None:
            ids = [p.player_id for p in self.participants]
            if len(ids) != len(set(ids)):
                raise ValueError("a player can only be assigned once")
        return self


class SpeedUpdate(BaseModel):
    speed: float = Field(ge=1.0, le=1000.0)


class ParticipantOut(ORM):
    id: int
    player_id: int
    team: str
    hero: str
    role: str
    ai_profile: dict[str, Any]
    player_name: str | None = None


class SessionOut(ORM):
    id: int
    name: str
    status: str
    environment: str
    map: str
    scenario: str
    game_mode: str
    seed: int
    speed: float
    max_game_seconds: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    winner: str | None
    win_condition: str | None
    duration_seconds: float | None
    radiant_score: int
    dire_score: int
    events_count: int
    error_message: str | None


class SessionDetail(SessionOut):
    participants: list[ParticipantOut]
    live: dict[str, Any] | None = None


class PlayerStatsOut(ORM):
    player_id: int
    player_name: str | None = None
    team: str
    hero: str
    kills: int
    deaths: int
    assists: int
    last_hits: int
    denies: int
    gpm: float
    xpm: float
    net_worth: int
    hero_damage: int
    tower_damage: int
    healing: int
    level: int
    items: list[str]
    is_final: bool


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class HistoryItem(BaseModel):
    id: int
    name: str
    status: str
    scenario: str
    game_mode: str
    seed: int
    created_at: datetime
    finished_at: datetime | None
    winner: str | None
    win_condition: str | None
    duration_seconds: float | None
    radiant_score: int
    dire_score: int
    events_count: int


class LogOut(ORM):
    id: int
    level: str
    component: str
    message: str
    timestamp: datetime


class EventOut(ORM):
    id: int
    session_id: int
    player_id: int | None
    event_type: str
    event_data: dict[str, Any]
    game_time: float
    timestamp: datetime


# --------------------------------------------------------------------------- settings
class RuntimeSettings(BaseModel):
    default_speed: float = Field(20.0, ge=1.0, le=1000.0)
    max_game_seconds: int = Field(3600, ge=300, le=7200)
    snapshot_interval: int = Field(60, ge=10, le=600)
    tick_seconds: float = Field(0.5, ge=0.25, le=1.0)
    ws_publish_hz: float = Field(4.0, gt=0, le=20)
    ui_refresh_seconds: int = Field(5, ge=1, le=120)
    log_level: str = Field("INFO", pattern="^(DEBUG|INFO|WARNING|ERROR)$")
    db_log_level: str = Field("INFO", pattern="^(DEBUG|INFO|WARNING|ERROR)$")
    max_concurrent_sessions: int = Field(2, ge=1, le=8)
    persist_ability_events: bool = True


class RuntimeSettingsUpdate(BaseModel):
    default_speed: float | None = Field(None, ge=1.0, le=1000.0)
    max_game_seconds: int | None = Field(None, ge=300, le=7200)
    snapshot_interval: int | None = Field(None, ge=10, le=600)
    tick_seconds: float | None = Field(None, ge=0.25, le=1.0)
    ws_publish_hz: float | None = Field(None, gt=0, le=20)
    ui_refresh_seconds: int | None = Field(None, ge=1, le=120)
    log_level: str | None = Field(None, pattern="^(DEBUG|INFO|WARNING|ERROR)$")
    db_log_level: str | None = Field(None, pattern="^(DEBUG|INFO|WARNING|ERROR)$")
    max_concurrent_sessions: int | None = Field(None, ge=1, le=8)
    persist_ability_events: bool | None = None


class PurgeRequest(BaseModel):
    older_than_days: int = Field(7, ge=0, le=3650)

