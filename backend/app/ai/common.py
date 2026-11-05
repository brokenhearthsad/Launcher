"""Shared utility-AI primitives: candidates, memory and power estimates."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.game.actions import Action
from app.game.simulator.entities import armor_multiplier

if TYPE_CHECKING:  # pragma: no cover
    from app.ai.perception import Perception
    from app.ai.profile import BotProfile
    from app.game.simulator.entities import Hero


@dataclass
class Candidate:
    """A possible action with its raw utility in [0, 1] (before weighting)."""

    action: Action
    score: float
    source: str  # lane | farming | economy | items | combat | objective | team | survival
    reason: str = ""

    @property
    def key(self) -> str:
        a = self.action
        return f"{self.source}:{a.intent}:{a.target_uid or ''}:{a.ability or ''}:{a.item or ''}"


@dataclass
class BotMemory:
    last_intent: str = ""
    last_key: str = ""
    failures: dict[str, float] = field(default_factory=dict)  # candidate key -> blocked until
    retreat_until: float = 0.0
    last_hp: float = 0.0
    hp_trend: float = 0.0  # negative = losing HP since last decision
    decisions: int = 0
    successes: int = 0
    failed: int = 0
    wards_placed: int = 0
    lane_override: str | None = None
    lane_override_until: float = 0.0
    intents: dict[str, int] = field(default_factory=dict)

    def blocked(self, key: str, now: float) -> bool:
        until = self.failures.get(key)
        return until is not None and until > now


@dataclass
class SubsystemContext:
    perception: Perception
    profile: BotProfile
    memory: BotMemory


def hero_dps(h: Hero, target_armor: float = 3.0) -> float:
    return h.damage / max(0.2, h.attack_interval) * armor_multiplier(target_armor - h.armor_reduction)


def effective_hp(h: Hero) -> float:
    return (h.hp + h.shield) / armor_multiplier(h.armor)


def burst_damage(h: Hero, now: float, ready_only: bool = True) -> float:
    """Damage the hero can deliver from abilities right now (rough estimate)."""
    if h.spec is None:
        return 0.0
    total = 0.0
    for i, a in enumerate(h.spec.abilities):
        lvl = h.ability_level(i)
        if lvl <= 0:
            continue
        if ready_only and (now < h.ability_ready_at.get(a.key, 0) or h.mana < a.mana[lvl - 1]):
            continue
        total += a.damage[lvl - 1] * 0.75  # after typical magic resistance
    return total


def fight_power(h: Hero, now: float) -> float:
    """Scalar 'how much this hero matters in a fight in the next ~5 seconds'."""
    return hero_dps(h) * 5 + burst_damage(h, now) + effective_hp(h) * 0.35
