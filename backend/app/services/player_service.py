"""Player Manager: CRUD and status transitions for test participants."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Player
from app.domain import PlayerStatus
from app.errors import ConflictError, NotFoundError
from app.logging_config import get_logger
from app.schemas import PlayerCreate, PlayerUpdate

log = get_logger("players")

LOCKED_STATUSES = (PlayerStatus.RUNNING.value, PlayerStatus.PAUSED.value)
LOCKED_FIELDS = ("team", "role", "hero", "slot", "status")


def list_players(db: Session, team: str | None = None) -> list[Player]:
    q = select(Player).order_by(Player.team.desc(), Player.slot, Player.id)
    if team:
        q = q.where(Player.team == team)
    return list(db.scalars(q))


def get_player(db: Session, player_id: int) -> Player:
    p = db.get(Player, player_id)
    if p is None:
        raise NotFoundError(f"player {player_id} not found")
    return p


def create_player(db: Session, data: PlayerCreate) -> Player:
    p = Player(**data.model_dump(mode="json"))
    db.add(p)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(f"player name '{data.name}' already exists") from exc
    db.refresh(p)
    log.info("player created: %s (%s %s %s)", p.name, p.team, p.role, p.hero)
    return p


def update_player(db: Session, player_id: int, data: PlayerUpdate) -> Player:
    p = get_player(db, player_id)
    changes = data.model_dump(exclude_unset=True, exclude_none=True, mode="json")
    if p.status in LOCKED_STATUSES:
        locked = [f for f in changes if f in LOCKED_FIELDS]
        if locked:
            raise ConflictError(f"cannot change {', '.join(locked)} while the player is in an active session")
    for k, v in changes.items():
        setattr(p, k, v)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("player name already exists") from exc
    db.refresh(p)
    log.info("player %s updated: %s", p.name, ", ".join(sorted(changes)) or "no changes")
    return p


def delete_player(db: Session, player_id: int) -> None:
    p = get_player(db, player_id)
    if p.status in LOCKED_STATUSES:
        raise ConflictError("cannot delete a player that is in an active session")
    db.delete(p)
    db.commit()
    log.info("player deleted: %s", p.name)


def set_status(db: Session, player_ids: list[int], status: PlayerStatus) -> list[Player]:
    players = list(db.scalars(select(Player).where(Player.id.in_(player_ids))))
    for p in players:
        p.status = status.value
    db.commit()
    return players
