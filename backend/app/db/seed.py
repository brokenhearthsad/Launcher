"""Initial data: the ten default test participants (no Steam accounts involved)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Player
from app.domain import Difficulty, PlayerStatus, Role, Team

# (role, hero, difficulty, aggression, farming, coordination, risk, objective)
_RADIANT = [
    (Role.CARRY, "juggernaut", Difficulty.HARD, 0.40, 0.90, 0.45, 0.45, 0.45),
    (Role.MID, "shadow_fiend", Difficulty.HARD, 0.65, 0.75, 0.50, 0.55, 0.55),
    (Role.OFFLANE, "axe", Difficulty.HARD, 0.75, 0.50, 0.60, 0.65, 0.60),
    (Role.SOFT_SUPPORT, "earthshaker", Difficulty.HARD, 0.60, 0.30, 0.75, 0.50, 0.55),
    (Role.HARD_SUPPORT, "crystal_maiden", Difficulty.HARD, 0.35, 0.20, 0.85, 0.35, 0.50),
]
_DIRE = [
    (Role.CARRY, "phantom_assassin", Difficulty.HARD, 0.50, 0.85, 0.40, 0.55, 0.45),
    (Role.MID, "lina", Difficulty.HARD, 0.70, 0.70, 0.55, 0.50, 0.50),
    (Role.OFFLANE, "mars", Difficulty.HARD, 0.70, 0.45, 0.65, 0.60, 0.65),
    (Role.SOFT_SUPPORT, "mirana", Difficulty.HARD, 0.55, 0.35, 0.70, 0.50, 0.55),
    (Role.HARD_SUPPORT, "lion", Difficulty.HARD, 0.45, 0.20, 0.80, 0.40, 0.50),
]


def default_players() -> list[Player]:
    players = []
    for team, rows, label in ((Team.RADIANT, _RADIANT, "Radiant"), (Team.DIRE, _DIRE, "Dire")):
        for i, (role, hero, diff, agg, farm, coord, risk, obj) in enumerate(rows, start=1):
            players.append(Player(
                name=f"{label} {i}", team=team.value, slot=i, role=role.value, hero=hero,
                bot_difficulty=diff.value, status=PlayerStatus.READY.value, aggression=agg,
                farming_priority=farm, team_coordination=coord, risk_tolerance=risk, objective_priority=obj,
            ))
    return players


def seed_players(db: Session) -> int:
    """Create the default ten participants if the table is empty. Returns rows created."""
    count = db.scalar(select(func.count()).select_from(Player)) or 0
    if count:
        return 0
    players = default_players()
    db.add_all(players)
    db.commit()
    return len(players)
