"""Abstract game adapter.

The match runner and the bots only talk to the game through this interface,
so the local simulator can be swapped for another environment without
touching AI or application code. See ARCHITECTURE.md -> "Adding an adapter".

Methods are synchronous on purpose: the runner calls them in small batches
from a worker thread, keeping the asyncio event loop responsive.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.ai.perception import Perception, TeamView
from app.domain import Team
from app.game.actions import Action, ActionResult
from app.game.simulator.engine import GameEvent, HeroSetup, MatchConfig


@dataclass
class MatchSetup:
    config: MatchConfig
    heroes: list[HeroSetup]


@dataclass
class AdapterInfo:
    name: str
    title: str
    description: str
    available: bool
    is_simulation: bool
    capabilities: dict[str, bool] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class MatchOutcome:
    finished: bool
    winner: Team | None
    win_condition: str | None
    duration: float
    score: dict[str, int]


class GameAdapter(ABC):
    info: AdapterInfo

    @abstractmethod
    def initialize(self, setup: MatchSetup) -> None:
        """Prepare a match with the given configuration and participants."""

    @abstractmethod
    def connect(self) -> None:
        """Connect to the game environment (no-op for in-process simulators)."""

    @abstractmethod
    def get_game_state(self) -> dict[str, Any]:
        """Full observer snapshot (UI / statistics). Not used for bot decisions."""

    @abstractmethod
    def get_player_state(self, player_id: int) -> Perception | None:
        """Fog-of-war filtered perception for one bot; None while dead."""

    @abstractmethod
    def get_team_state(self, team: Team) -> TeamView:
        """Team-level knowledge for the Team AI coordinator."""

    @abstractmethod
    def execute_action(self, player_id: int, action: Action) -> ActionResult:
        """Submit one bot action; returns whether it was accepted and why not."""

    @abstractmethod
    def advance(self) -> float:
        """Advance by one step. Returns the new game time in seconds."""

    @abstractmethod
    def pause(self) -> None: ...

    @abstractmethod
    def resume(self) -> None: ...

    @abstractmethod
    def stop(self) -> None:
        """Terminate the match. Idempotent."""

    @abstractmethod
    def get_events(self) -> list[GameEvent]:
        """Return and clear events produced since the previous call."""

    @abstractmethod
    def outcome(self) -> MatchOutcome: ...

    @abstractmethod
    def timeline(self) -> list[dict[str, Any]]:
        """Periodic per-hero snapshots recorded during the match."""

    @property
    @abstractmethod
    def game_time(self) -> float: ...

    @property
    @abstractmethod
    def tick_seconds(self) -> float: ...
