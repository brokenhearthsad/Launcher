"""What a bot knows about the world at decision time.

Adapters build these views. The mock adapter passes simulator entities
directly (read-only by contract) to avoid copying hundreds of objects per tick;
a real-game adapter would construct equivalent objects from its data feed.
Only *visible* enemy heroes are included: bots do not see through fog of war.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.domain import Team
from app.game.catalog import AbilitySpec
from app.game.simulator.map import Vec, dist

if TYPE_CHECKING:  # pragma: no cover
    from app.game.simulator.entities import Creep, Hero, NeutralCamp, Roshan, Tower, Ward


@dataclass
class AbilityView:
    spec: AbilitySpec
    level: int
    ready: bool  # learned, off cooldown and affordable
    error: str = ""


@dataclass
class TeamDirective:
    kind: str = "farm"  # farm | push | defend | group | roshan | regroup
    lane: str | None = None
    target_uid: str | None = None
    rally: Vec | None = None
    participants: tuple[int, ...] = ()
    reason: str = ""

    def includes(self, player_id: int) -> bool:
        return not self.participants or player_id in self.participants


@dataclass
class Perception:
    time: float
    me: Hero
    allies: list[Hero]  # alive allies excluding me
    enemies: list[Hero]  # visible alive enemy heroes
    ally_creeps: list[Creep]
    enemy_creeps: list[Creep]
    ally_towers: list[Tower]
    enemy_towers: list[Tower]
    camps: list[NeutralCamp]
    roshan: Roshan | None
    wards: list[Ward]
    fountain: Vec
    enemy_fountain: Vec
    abilities: list[AbilityView]
    laning_phase: bool
    all_allies: list[Hero] = field(default_factory=list)  # including dead, for team logic
    enemy_hero_count_alive: int = 5

    @property
    def team(self) -> Team:
        assert self.me.team is not None
        return self.me.team

    def enemies_near(self, pos: Vec, radius: float) -> list[Hero]:
        return [e for e in self.enemies if dist(e.pos, pos) <= radius]

    def allies_near(self, pos: Vec, radius: float, include_me: bool = True) -> list[Hero]:
        out = [a for a in self.allies if dist(a.pos, pos) <= radius]
        if include_me and dist(self.me.pos, pos) <= radius:
            out.append(self.me)
        return out

    def enemy_towers_near(self, pos: Vec, radius: float) -> list[Tower]:
        return [t for t in self.enemy_towers if dist(t.pos, pos) <= radius and t.damage > 0]


@dataclass
class TeamView:
    """Team-level knowledge used by Team AI."""

    time: float
    team: Team
    heroes: list[Hero]  # all heroes of the team (alive or dead)
    visible_enemies: list[Hero]
    enemy_alive: int
    ally_towers: list[Tower]
    enemy_towers: list[Tower]
    roshan_alive: bool
    enemy_creeps_by_lane: dict[str, list[Creep]]
    net_worth: int
    enemy_net_worth_estimate: int
    laning_phase: bool
