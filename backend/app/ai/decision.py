"""Utility-AI decision engine.

Pipeline per decision:
  1. subsystems propose :class:`Candidate` actions with raw utilities in [0, 1];
  2. utilities are weighted by the bot's personality per source;
  3. hysteresis rewards continuing the current intent (prevents jitter);
  4. recently failed candidates are suppressed;
  5. difficulty-dependent gaussian noise models human-like imperfection;
  6. the best *main* action and, independently, the best *shopping* action win.

Shopping (buy/sell) is a separate channel because it does not change the
hero's order in the game - a player can buy from the shop while fighting.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from app.ai.common import BotMemory, Candidate
from app.ai.profile import BotProfile

SHOP_SOURCES = ("economy",)


@dataclass
class Decision:
    main: Candidate | None
    shop: Candidate | None
    ranked: list[tuple[float, Candidate]] = field(default_factory=list)


class DecisionEngine:
    def __init__(self, profile: BotProfile, rng: random.Random):
        self.profile = profile
        self.rng = rng

    def source_weight(self, source: str) -> float:
        p = self.profile
        return {
            "combat": 0.7 + 0.6 * p.aggression,
            "farming": 0.7 + 0.6 * p.farming_priority,
            "objective": 0.7 + 0.6 * p.objective_priority,
            "team": 0.5 + 0.8 * p.team_coordination,
            "survival": 1.0 + 0.4 * (1 - p.risk_tolerance),
            "lane": 1.0,
            "items": 1.0,
            "economy": 1.0,
        }.get(source, 1.0)

    def score(self, c: Candidate, memory: BotMemory, now: float) -> float:
        s = c.score * self.source_weight(c.source)
        if memory.last_intent and c.action.intent == memory.last_intent:
            s += 0.04  # hysteresis
        if memory.blocked(c.key, now):
            s -= 0.6
        s += self.rng.gauss(0.0, self.profile.params.decision_noise)
        return s

    def decide(self, candidates: list[Candidate], memory: BotMemory, now: float) -> Decision:
        ranked = sorted(((self.score(c, memory, now), c) for c in candidates), key=lambda x: -x[0])
        main = next((c for s, c in ranked if c.source not in SHOP_SOURCES), None)
        shop = next((c for s, c in ranked if c.source in SHOP_SOURCES and s > 0.3), None)
        return Decision(main, shop, ranked)
