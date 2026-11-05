"""GSI state machine: freshness and game lifecycle transitions.

Pure logic (no I/O): ``apply`` returns the events that should be journaled.
Freshness uses a monotonic clock passed in by the caller, which keeps the
class deterministic and easy to test.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.integrations.gsi.parser import ENDED_STATES, GAME_STATES, IN_MATCH_STATES, GameSnapshot


@dataclass
class GsiEvent:
    type: str  # connected | first_state | game_started | phase_changed | game_ended | stale | format_error
    message: str
    severity: str = "info"
    data: dict[str, Any] = field(default_factory=dict)


def _label(state: str | None) -> str:
    return GAME_STATES.get(state or "", state or "нет данных")


class GsiTracker:
    def __init__(self, stale_seconds: float = 40.0, fresh_seconds: float = 5.0):
        self.stale_seconds = stale_seconds
        self.fresh_seconds = fresh_seconds
        self.snapshot: GameSnapshot | None = None
        self.last_update: float | None = None  # monotonic
        self.last_update_wall: float | None = None  # epoch, for display
        self.connected = False
        self.had_state = False
        self.in_match = False
        self.match_id: str | None = None
        self.updates = 0
        self.format_errors = 0
        self.rejected = 0

    # ------------------------------------------------------------------ freshness
    def freshness(self, now: float) -> str:
        """never | fresh | delayed | stale."""
        if self.last_update is None:
            return "never"
        age = now - self.last_update
        if age <= self.fresh_seconds:
            return "fresh"
        if age <= self.stale_seconds:
            return "delayed"
        return "stale"

    def check_stale(self, now: float) -> list[GsiEvent]:
        if self.connected and self.freshness(now) == "stale":
            self.connected = False
            return [GsiEvent("stale", f"GSI перестал передавать данные (нет обновлений {int(self.stale_seconds)} с)",
                             "warning")]
        return []

    # ------------------------------------------------------------------ updates
    def apply(self, snap: GameSnapshot, now: float, wall: float) -> list[GsiEvent]:
        events: list[GsiEvent] = []
        prev = self.snapshot
        self.updates += 1
        if not self.connected:
            self.connected = True
            events.append(GsiEvent("connected", "GSI подключился: Dota 2 передаёт данные"))
        if snap.has_map and not self.had_state:
            self.had_state = True
            events.append(GsiEvent("first_state", f"Получено первое состояние игры: {_label(snap.game_state)}",
                                   data={"game_state": snap.game_state}))

        new_state = snap.game_state if snap.has_map else None
        old_state = prev.game_state if (prev is not None and prev.has_map) else None
        if new_state != old_state and (new_state is not None or old_state is not None):
            if new_state is not None and old_state is not None:
                events.append(GsiEvent("phase_changed", f"Фаза: {_label(old_state)} → {_label(new_state)}",
                                       data={"from": old_state, "to": new_state}))
            elif new_state is not None:
                events.append(GsiEvent("phase_changed", f"Фаза: {_label(new_state)}",
                                       data={"from": None, "to": new_state}))

        entering = new_state in IN_MATCH_STATES
        match_changed = snap.match_id is not None and snap.match_id != self.match_id
        if entering and (not self.in_match or match_changed):
            self.in_match = True
            self.match_id = snap.match_id
            events.append(GsiEvent("game_started", "Началась игра" + (f" (матч {snap.match_id})" if snap.match_id else ""),
                                   data={"match_id": snap.match_id, "map": snap.map_name, "hero": snap.hero_internal}))
        elif self.in_match and (new_state in ENDED_STATES or snap.win_team is not None or not snap.has_map):
            self.in_match = False
            reason = ("победа " + snap.win_team) if snap.win_team else (
                "игрок вышел из матча" if not snap.has_map else _label(new_state))
            events.append(GsiEvent("game_ended", f"Игра завершилась: {reason}",
                                   data={"match_id": self.match_id, "win_team": snap.win_team,
                                         "game_time": (prev.game_time if prev else None) if not snap.has_map
                                         else snap.game_time}))
        if snap.problems:
            self.format_errors += 1
        self.snapshot = snap
        self.last_update = now
        self.last_update_wall = wall
        return events
