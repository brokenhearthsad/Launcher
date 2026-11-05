"""MockGameAdapter: fully functional adapter over the local simulator.

Results produced through this adapter are *simulations* and are labelled as
such everywhere (environment = "mock"). They are not Dota 2 matches.
"""
from __future__ import annotations

from typing import Any

from app.ai.perception import AbilityView, Perception, TeamView
from app.domain import GameMode, Team
from app.game.actions import Action, ActionResult, AdapterError
from app.game.adapters.base import AdapterInfo, GameAdapter, MatchOutcome, MatchSetup
from app.game.simulator.engine import GameEngine, GameEvent
from app.game.simulator.entities import Hero
from app.game.simulator.map import FOUNTAIN, dist

PERCEPTION_RADIUS = 14.0


class MockGameAdapter(GameAdapter):
    info = AdapterInfo(
        name="mock",
        title="Local simulator",
        description="Deterministic in-process 5v5 simulator (seeded). Results are simulations, not Dota 2 matches.",
        available=True,
        is_simulation=True,
        capabilities={"pause": True, "resume": True, "speed_control": True, "fog_of_war": True,
                      "deterministic": True},
    )

    def __init__(self) -> None:
        self._engine: GameEngine | None = None
        self._paused = False
        self._connected = False

    # ------------------------------------------------------------------ lifecycle
    def initialize(self, setup: MatchSetup) -> None:
        self._engine = GameEngine(setup.config, setup.heroes)
        self._paused = False

    def connect(self) -> None:
        self._require()
        self._connected = True

    @property
    def engine(self) -> GameEngine:
        return self._require()

    def _require(self) -> GameEngine:
        if self._engine is None:
            raise AdapterError("adapter is not initialised; call initialize() first")
        return self._engine

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    @property
    def paused(self) -> bool:
        return self._paused

    def stop(self) -> None:
        e = self._require()
        if not e.finished:
            e.force_finish("stopped")

    def advance(self) -> float:
        e = self._require()
        if not self._connected:
            raise AdapterError("adapter is not connected")
        if not self._paused:
            e.step()
        return e.time

    @property
    def game_time(self) -> float:
        return self._require().time

    @property
    def tick_seconds(self) -> float:
        return self._require().config.tick

    # ------------------------------------------------------------------ state
    def get_game_state(self) -> dict[str, Any]:
        return self._require().snapshot()

    def get_events(self) -> list[GameEvent]:
        return self._require().drain_events()

    def outcome(self) -> MatchOutcome:
        e = self._require()
        return MatchOutcome(e.finished, e.winner, e.win_condition, e.time, {t.value: v for t, v in e.score.items()})

    def timeline(self) -> list[dict[str, Any]]:
        return self._require().timeline

    def laning_phase(self) -> bool:
        e = self._require()
        return e.time < (300 if e.config.mode is GameMode.TURBO else 600)

    def get_player_state(self, player_id: int) -> Perception | None:
        e = self._require()
        me = e.hero_by_player(player_id)
        if me is None or not me.alive:
            return None
        assert me.team is not None
        team = me.team
        visible = e.visible_enemy_uids(team)
        mx, my = me.pos
        r2 = PERCEPTION_RADIUS * PERCEPTION_RADIUS
        ally_creeps, enemy_creeps = [], []
        for lane in e.lanes_active:
            for c in e.creeps[lane]:
                if (c.pos[0] - mx) ** 2 + (c.pos[1] - my) ** 2 <= r2:
                    (ally_creeps if c.team is team else enemy_creeps).append(c)
        abilities = []
        assert me.spec is not None
        for ab in me.spec.abilities:
            _spec, lvl, err = e.ability_state(me, ab.key)
            abilities.append(AbilityView(ab, lvl, err == "", err))
        enemies = [h for h in e.heroes if h.team is not team and h.alive and h.uid in visible]
        return Perception(
            time=e.time,
            me=me,
            allies=[h for h in e.heroes if h.team is team and h.alive and h is not me],
            enemies=enemies,
            ally_creeps=ally_creeps,
            enemy_creeps=enemy_creeps,
            ally_towers=[t for t in e.towers if t.team is team and t.alive],
            enemy_towers=[t for t in e.towers if t.team is not team and t.alive],
            camps=[c for c in e.camps if c.alive and dist(c.pos, me.pos) < 40],
            roshan=e.roshan if e.roshan.alive else None,
            wards=[w for w in e.wards if w.team is team],
            fountain=FOUNTAIN[team],
            enemy_fountain=FOUNTAIN[team.enemy],
            abilities=abilities,
            laning_phase=self.laning_phase(),
            all_allies=[h for h in e.heroes if h.team is team],
            enemy_hero_count_alive=sum(1 for h in e.heroes if h.team is not team and h.alive),
        )

    def get_team_state(self, team: Team) -> TeamView:
        e = self._require()
        visible = e.visible_enemy_uids(team)
        heroes: list[Hero] = [h for h in e.heroes if h.team is team]
        return TeamView(
            time=e.time,
            team=team,
            heroes=heroes,
            visible_enemies=[h for h in e.heroes if h.team is not team and h.alive and h.uid in visible],
            enemy_alive=sum(1 for h in e.heroes if h.team is not team and h.alive),
            ally_towers=[t for t in e.towers if t.team is team and t.alive],
            enemy_towers=[t for t in e.towers if t.team is not team and t.alive],
            roshan_alive=e.roshan.alive,
            enemy_creeps_by_lane={lane: [c for c in e.creeps[lane] if c.team is not team] for lane in e.lanes_active},
            net_worth=e.team_net_worth(team),
            enemy_net_worth_estimate=e.team_net_worth(team.enemy),
            laning_phase=self.laning_phase(),
        )

    def execute_action(self, player_id: int, action: Action) -> ActionResult:
        e = self._require()
        if self._paused:
            return ActionResult(False, "match is paused")
        return e.apply_action(player_id, action)
