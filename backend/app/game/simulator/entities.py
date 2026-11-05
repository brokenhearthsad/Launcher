"""Mutable simulation entities.

The engine owns and mutates these objects. Bots receive them through the
adapter's perception views and must treat them as read-only: every change to
the world goes through ``GameAdapter.execute_action``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain import Role, Team
from app.game.catalog import HeroSpec, ItemSpec
from app.game.simulator.map import Vec


def armor_multiplier(armor: float) -> float:
    """Physical damage multiplier for a given armor value (Dota-like curve)."""
    return 1.0 - (0.06 * armor) / (1.0 + 0.06 * abs(armor))


@dataclass(eq=False)
class Unit:
    uid: str
    kind: str  # hero | creep | tower | neutral | roshan
    team: Team | None
    pos: Vec
    max_hp: float
    hp: float
    armor: float
    damage: float
    attack_range: float
    attack_interval: float
    next_attack: float = 0.0
    alive: bool = True
    target_uid: str | None = None
    # attacker uid -> last game time it dealt damage (assists / aggro)
    damage_log: dict[str, float] = field(default_factory=dict)

    @property
    def hp_frac(self) -> float:
        return self.hp / self.max_hp if self.max_hp > 0 else 0.0


@dataclass(eq=False)
class Creep(Unit):
    lane: str = "mid"
    s: float = 0.0  # arc-length position along lane (from Radiant ancient)
    move_speed: float = 2.0
    creep_type: str = "melee"
    bounty_gold: int = 40
    bounty_xp: int = 57
    aggro_until: float = 0.0


@dataclass(eq=False)
class Tower(Unit):
    tier: str = "t1"  # t1 | t2 | t3 | t4 | ancient
    lane: str = "base"
    s: float = 0.0
    vulnerable: bool = False


@dataclass(eq=False)
class NeutralCamp(Unit):
    camp_id: str = ""
    camp_type: str = "small"
    side: Team | None = None
    home: Vec = (0.0, 0.0)
    bounty_gold: int = 60
    bounty_xp: int = 80


@dataclass(eq=False)
class Roshan(Unit):
    respawn_at: float = 0.0
    kills: int = 0


@dataclass
class Ward:
    team: Team
    pos: Vec
    expires_at: float
    owner_uid: str


@dataclass
class Order:
    kind: str  # move | attack | cast | use_item | hold
    target_uid: str | None = None
    pos: Vec | None = None
    ability: str | None = None
    item: str | None = None
    once: bool = False  # attack once, then hold (used for last hits / denies)
    hp_threshold: float | None = None  # wait until target hp <= threshold
    expires_at: float = 0.0


@dataclass
class ItemSlot:
    spec: ItemSpec
    charges: int = 0
    ready_at: float = 0.0


@dataclass(eq=False)
class Hero(Unit):
    player_id: int = 0
    name: str = ""
    spec: HeroSpec | None = None
    role: Role = Role.CARRY
    lane: str = "mid"
    level: int = 1
    xp: float = 0.0
    gold: float = 0.0
    mana: float = 0.0
    max_mana: float = 0.0
    move_speed: float = 1.9
    hp_regen: float = 1.0
    mana_regen: float = 1.0
    magic_resist: float = 0.25
    creep_damage: float = 0.0
    lifesteal: float = 0.0
    crit: float = 0.0
    evasion: float = 0.0
    armor_reduction: float = 0.0
    proc_damage: float = 0.0
    cast_range_bonus: float = 0.0
    ult_amp: float = 0.0
    items: list[ItemSlot] = field(default_factory=list)
    pending: list[tuple[float, ItemSpec]] = field(default_factory=list)  # courier deliveries
    ability_ready_at: dict[str, float] = field(default_factory=dict)
    order: Order = field(default_factory=lambda: Order("hold"))
    # timed effects (absolute game time)
    stunned_until: float = 0.0
    slowed_until: float = 0.0
    slow_amount: float = 0.0
    immune_until: float = 0.0
    buff_until: float = 0.0
    buff_damage: float = 0.0
    lifesteal_until: float = 0.0
    regen_until: float = 0.0
    regen_rate: float = 0.0
    shield: float = 0.0
    shield_until: float = 0.0
    channel_until: float = 0.0
    channel_target: Vec | None = None
    respawn_at: float = 0.0
    has_aegis: bool = False
    last_hero_damage_taken_at: float = -999.0
    # statistics
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    last_hits: int = 0
    denies: int = 0
    gold_earned: float = 0.0
    hero_damage: float = 0.0
    tower_damage: float = 0.0
    healing: float = 0.0
    streak: int = 0
    last_action: str = "spawn"
    # Scenario multipliers (set by engine)
    gold_mult: float = 1.0
    xp_mult: float = 1.0
    damage_mult: float = 1.0

    # --------------------------------------------------------------- helpers
    def ability_level(self, index: int) -> int:
        if index >= 3:
            return 0 if self.level < 6 else (1 if self.level < 12 else (2 if self.level < 18 else 3))
        return min(4, (self.level + 1) // 2)

    def ability_index(self, key: str) -> int:
        assert self.spec is not None
        for i, a in enumerate(self.spec.abilities):
            if a.key == key:
                return i
        return -1

    def item(self, key: str) -> ItemSlot | None:
        for slot in self.items:
            if slot.spec.key == key:
                return slot
        return None

    @property
    def item_keys(self) -> list[str]:
        return [s.spec.key for s in self.items]

    @property
    def net_worth(self) -> int:
        items = sum(s.spec.cost * (max(1, s.charges) if s.spec.charges else 1) for s in self.items)
        return int(self.gold + items + sum(spec.cost for _, spec in self.pending))

    def is_stunned(self, now: float) -> bool:
        return now < self.stunned_until

    def is_immune(self, now: float) -> bool:
        return now < self.immune_until

    def current_speed(self, now: float) -> float:
        slow = self.slow_amount if now < self.slowed_until else 0.0
        return self.move_speed * (1.0 - slow)

    def summary(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "uid": self.uid,
            "name": self.name,
            "hero": self.spec.key if self.spec else "",
            "hero_name": self.spec.name if self.spec else "",
            "team": self.team.value if self.team else None,
            "role": self.role.value,
            "lane": self.lane,
            "alive": self.alive,
            "respawn_in": 0,
            "pos": [round(self.pos[0], 2), round(self.pos[1], 2)],
            "hp": round(self.hp),
            "max_hp": round(self.max_hp),
            "mana": round(self.mana),
            "max_mana": round(self.max_mana),
            "level": self.level,
            "xp": round(self.xp),
            "gold": int(self.gold),
            "gold_earned": int(self.gold_earned),
            "net_worth": self.net_worth,
            "items": self.item_keys,
            "kills": self.kills,
            "deaths": self.deaths,
            "assists": self.assists,
            "last_hits": self.last_hits,
            "denies": self.denies,
            "hero_damage": int(self.hero_damage),
            "tower_damage": int(self.tower_damage),
            "healing": int(self.healing),
            "has_aegis": self.has_aegis,
            "action": self.last_action,
        }
