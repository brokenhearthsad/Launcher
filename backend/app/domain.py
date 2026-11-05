"""Domain enumerations shared by API, persistence, simulator and AI."""
from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class Team(StrEnum):
    RADIANT = "radiant"
    DIRE = "dire"

    @property
    def enemy(self) -> Team:
        return Team.DIRE if self is Team.RADIANT else Team.RADIANT


class Role(StrEnum):
    CARRY = "carry"
    MID = "mid"
    OFFLANE = "offlane"
    SOFT_SUPPORT = "soft_support"
    HARD_SUPPORT = "hard_support"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class PlayerStatus(StrEnum):
    OFFLINE = "offline"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    FINISHED = "finished"


class SessionStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    STOPPED = "stopped"
    ERROR = "error"


ACTIVE_SESSION_STATUSES = (SessionStatus.RUNNING.value, SessionStatus.PAUSED.value)
TERMINAL_SESSION_STATUSES = (
    SessionStatus.FINISHED.value,
    SessionStatus.STOPPED.value,
    SessionStatus.ERROR.value,
)


class Environment(StrEnum):
    MOCK = "mock"
    DOTA_TEST = "dota_test"


class Scenario(StrEnum):
    BALANCED = "balanced"
    RADIANT_ADVANTAGE = "radiant_advantage"
    DIRE_ADVANTAGE = "dire_advantage"
    AGGRESSIVE = "aggressive"
    DEFENSIVE = "defensive"


class GameMode(StrEnum):
    STANDARD = "standard"
    TURBO = "turbo"
    MID_ONLY = "mid_only"


DEFAULT_LANE_FOR_ROLE = {
    Role.CARRY: "safe",
    Role.HARD_SUPPORT: "safe",
    Role.MID: "mid",
    Role.OFFLANE: "off",
    Role.SOFT_SUPPORT: "off",
}
