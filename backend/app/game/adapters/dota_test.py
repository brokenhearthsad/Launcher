"""DotaTestAdapter: placeholder boundary for a future, *permitted* Dota 2 test setup.

Status: NOT IMPLEMENTED / NOT VERIFIED. Every operation raises
:class:`AdapterNotSupportedError` with the reason, and the API reports the
adapter as unavailable. Nothing here talks to Steam or the Dota 2 client.

Research summary (see ARCHITECTURE.md, "Dota 2 integration research"):

* Official Bot Scripting API (Lua, ``scripts/vscripts/bots``) runs bots inside
  the client for local lobbies / practice games. Its sandbox has no network or
  file I/O, so an external process cannot drive those bots in real time.
* Game State Integration (GSI) pushes JSON game state over HTTP from the
  client to a local endpoint. It is read-only: no commands can be sent back.
* Workshop Tools custom games (server-side Lua vscripts in a local lobby)
  can issue HTTP requests from the game server, which is the most plausible
  route for a bridge (game polls this backend for actions). This requires an
  addon and must be validated by hand before any support is claimed.

Explicitly out of scope: public matchmaking, ranked games, anti-cheat
circumvention, input injection or memory reading.
"""
from __future__ import annotations

from typing import Any, NoReturn

from app.ai.perception import Perception, TeamView
from app.domain import Team
from app.game.actions import Action, ActionResult, AdapterNotSupportedError
from app.game.adapters.base import AdapterInfo, GameAdapter, MatchOutcome, MatchSetup
from app.game.simulator.engine import GameEvent

REASON = (
    "the Dota 2 test-environment bridge is not implemented yet; it requires a Workshop Tools custom-game "
    "addon running in a local lobby (see ARCHITECTURE.md). Use the 'mock' environment."
)


class DotaTestAdapter(GameAdapter):
    info = AdapterInfo(
        name="dota_test",
        title="Dota 2 test environment (planned)",
        description="Interface for a future integration with a permitted local Dota 2 test lobby. Not available.",
        available=False,
        is_simulation=False,
        capabilities={"pause": False, "resume": False, "speed_control": False, "fog_of_war": False,
                      "deterministic": False},
        notes=[
            "Bot Scripting API (Lua) is sandboxed: no external control channel.",
            "Game State Integration is read-only (state out, no commands in).",
            "Workshop Tools custom game + HTTP polling bridge is the candidate design; unverified.",
            "Public matchmaking / ranked automation is out of scope and will not be implemented.",
        ],
    )

    def _unsupported(self, op: str) -> NoReturn:
        raise AdapterNotSupportedError(op, REASON)

    def initialize(self, setup: MatchSetup) -> None:
        self._unsupported("initialize")

    def connect(self) -> None:
        self._unsupported("connect")

    def get_game_state(self) -> dict[str, Any]:
        self._unsupported("get_game_state")

    def get_player_state(self, player_id: int) -> Perception | None:
        self._unsupported("get_player_state")

    def get_team_state(self, team: Team) -> TeamView:
        self._unsupported("get_team_state")

    def execute_action(self, player_id: int, action: Action) -> ActionResult:
        self._unsupported("execute_action")

    def advance(self) -> float:
        self._unsupported("advance")

    def pause(self) -> None:
        self._unsupported("pause")

    def resume(self) -> None:
        self._unsupported("resume")

    def stop(self) -> None:
        self._unsupported("stop")

    def get_events(self) -> list[GameEvent]:
        self._unsupported("get_events")

    def outcome(self) -> MatchOutcome:
        self._unsupported("outcome")

    def timeline(self) -> list[dict[str, Any]]:
        self._unsupported("timeline")

    @property
    def game_time(self) -> float:
        self._unsupported("game_time")

    @property
    def tick_seconds(self) -> float:
        self._unsupported("tick_seconds")

