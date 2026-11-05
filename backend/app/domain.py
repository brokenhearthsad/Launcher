"""Domain enumerations shared by every layer."""
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
