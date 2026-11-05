"""Bot personality and difficulty parameters."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from app.domain import Difficulty, Role, Scenario


@dataclass(frozen=True)
class DifficultyParams:
    reaction_time: float  # seconds between decisions
    decision_noise: float  # std-dev of gaussian noise added to utility scores
    last_hit_error: float  # relative error of creep-damage estimation
    ability_skill: float  # probability to notice a good ability usage
    predicts_creep_damage: bool


DIFFICULTY: dict[Difficulty, DifficultyParams] = {
    Difficulty.EASY: DifficultyParams(1.5, 0.12, 0.30, 0.55, False),
    Difficulty.MEDIUM: DifficultyParams(1.0, 0.07, 0.15, 0.8, False),
    Difficulty.HARD: DifficultyParams(0.5, 0.035, 0.06, 0.95, True),
    Difficulty.EXPERT: DifficultyParams(0.5, 0.012, 0.02, 1.0, True),
}


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


@dataclass(frozen=True)
class BotProfile:
    player_id: int
    name: str
    role: Role
    difficulty: Difficulty = Difficulty.HARD
    aggression: float = 0.5
    farming_priority: float = 0.5
    team_coordination: float = 0.5
    risk_tolerance: float = 0.5
    objective_priority: float = 0.5

    @property
    def params(self) -> DifficultyParams:
        return DIFFICULTY[self.difficulty]

    @property
    def is_core(self) -> bool:
        return self.role in (Role.CARRY, Role.MID, Role.OFFLANE)

    @property
    def is_support(self) -> bool:
        return not self.is_core

    def with_scenario(self, scenario: Scenario) -> BotProfile:
        """Apply scenario-level personality offsets (aggressive/defensive)."""
        if scenario is Scenario.AGGRESSIVE:
            return self._shift(aggression=0.25, risk_tolerance=0.2, objective_priority=0.1)
        if scenario is Scenario.DEFENSIVE:
            return self._shift(aggression=-0.25, risk_tolerance=-0.2, farming_priority=0.1)
        return self

    def _shift(self, **deltas: float) -> BotProfile:
        data = asdict(self)
        for k, d in deltas.items():
            data[k] = _clamp(data[k] + d)
        return BotProfile(**data)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["role"] = self.role.value
        d["difficulty"] = self.difficulty.value
        return d
