from __future__ import annotations

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DB, State
from app.domain import Team
from app.schemas import PlayerCreate, PlayerOut, PlayerUpdate
from app.services import player_service

router = APIRouter(prefix="/api/players", tags=["players"])


@router.get("", response_model=list[PlayerOut])
def list_players(db: DB, team: Team | None = Query(None)) -> list:
    return player_service.list_players(db, team.value if team else None)


@router.post("", response_model=PlayerOut, status_code=status.HTTP_201_CREATED)
def create_player(data: PlayerCreate, db: DB, state: State):
    p = player_service.create_player(db, data)
    state.bus.publish("player_updated", {"player_ids": [p.id], "action": "created"})
    return p


@router.get("/{player_id}", response_model=PlayerOut)
def get_player(player_id: int, db: DB):
    return player_service.get_player(db, player_id)


@router.put("/{player_id}", response_model=PlayerOut)
@router.patch("/{player_id}", response_model=PlayerOut)
def update_player(player_id: int, data: PlayerUpdate, db: DB, state: State):
    p = player_service.update_player(db, player_id, data)
    state.bus.publish("player_updated", {"player_ids": [p.id], "action": "updated"})
    return p


@router.delete("/{player_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_player(player_id: int, db: DB, state: State) -> Response:
    player_service.delete_player(db, player_id)
    state.bus.publish("player_updated", {"player_ids": [player_id], "action": "deleted"})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
