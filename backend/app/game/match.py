"""MatchController: drives one match = adapter + 10 bot brains + 2 team coordinators.

Pure synchronous logic with no database or network access, so it can be
used by the async session runner, by tests and by benchmarks alike.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.bot import BotBrain
from app.ai.profile import BotProfile
from app.ai.team import TeamAI
from app.domain import Team
from app.game.actions import Action, ActionResult
from app.game.adapters.base import GameAdapter, MatchSetup
from app.game.simulator.engine import GameEvent


@dataclass
class BotActionRecord:
    player_id: int
    time: float
    action: str
    source: str
    score: float
    ok: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"player_id": self.player_id, "time": round(self.time, 1), "action": self.action,
                "source": self.source, "score": self.score, "ok": self.ok, "reason": self.reason}


@dataclass
class StepResult:
    time: float
    events: list[GameEvent] = field(default_factory=list)
    actions: list[BotActionRecord] = field(default_factory=list)
    finished: bool = False


class MatchController:
    def __init__(self, adapter: GameAdapter, setup: MatchSetup, profiles: list[BotProfile]):
        if len(profiles) != 10:
            raise ValueError("exactly 10 bot profiles are required")
        self.adapter = adapter
        self.setup = setup
        scenario = setup.config.scenario
        self.profiles = {p.player_id: p.with_scenario(scenario) for p in profiles}
        hero_of = {h.player_id: h.hero_key for h in setup.heroes}
        team_of = {h.player_id: h.team for h in setup.heroes}
        self.team_of = team_of
        self.brains = {pid: BotBrain(prof, hero_of[pid], setup.config.seed) for pid, prof in self.profiles.items()}
        self.teams = {t: TeamAI(t, [p for pid, p in self.profiles.items() if team_of[pid] is t]) for t in Team}
        for pid, brain in self.brains.items():
            allies = [hero_of[o] for o in hero_of if team_of[o] is team_of[pid]]
            enemies = [hero_of[o] for o in hero_of if team_of[o] is not team_of[pid]]
            brain.items.adapt_build(enemies, allies)

    def start(self) -> None:
        self.adapter.initialize(self.setup)
        self.adapter.connect()

    @property
    def finished(self) -> bool:
        return self.adapter.outcome().finished

    def step(self) -> StepResult:
        """One decision round for ready bots, followed by one simulation tick."""
        now = self.adapter.game_time
        directives = {t: ai.update(self.adapter.get_team_state(t)) for t, ai in self.teams.items()}
        records: list[BotActionRecord] = []
        for pid in sorted(self.brains):
            brain = self.brains[pid]
            if not brain.ready(now):
                continue
            perception = self.adapter.get_player_state(pid)
            brain.schedule_next(now)
            if perception is None:
                continue  # dead: nothing to decide
            turn = brain.think(perception, directives[self.team_of[pid]])
            for action in turn.actions:
                result = self.adapter.execute_action(pid, action)
                brain.observe(action, result, now)
                records.append(self._record(pid, now, action, result))
        t = self.adapter.advance()
        return StepResult(t, self.adapter.get_events(), records, self.adapter.outcome().finished)

    @staticmethod
    def _record(pid: int, now: float, action: Action, result: ActionResult) -> BotActionRecord:
        return BotActionRecord(pid, now, action.describe(), action.source, action.score, result.ok,
                               result.reason or action.note)

    def run_to_end(self, max_steps: int | None = None) -> list[GameEvent]:
        """Headless helper for tests/benchmarks: run until the match ends."""
        events: list[GameEvent] = []
        n = 0
        while not self.finished and (max_steps is None or n < max_steps):
            events.extend(self.step().events)
            n += 1
        return events

    def team_directives(self) -> dict[str, dict[str, Any]]:
        return {t.value: {"kind": ai.directive.kind, "lane": ai.directive.lane, "target": ai.directive.target_uid,
                          "reason": ai.directive.reason} for t, ai in self.teams.items()}

    def bot_stats(self) -> dict[int, dict]:
        return {pid: b.stats() for pid, b in self.brains.items()}
