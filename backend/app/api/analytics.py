from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.api.deps import DB, State
from app.domain import Scenario, Team
from app.services import analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _filters(session_ids: list[int] | None, team: Team | None, player_id: int | None,
             scenario: Scenario | None, include_stopped: bool) -> analytics.Filters:
    return analytics.Filters(session_ids or None, team.value if team else None, player_id,
                             scenario.value if scenario else None, include_stopped)


SessionIds = Annotated[list[int] | None, Query(alias="session_id")]


@router.get("/overview")
def overview(db: DB, state: State) -> dict:
    return analytics.overview(db, state.manager.active_ids())


@router.get("/players")
def players(db: DB, session_ids: SessionIds = None, team: Team | None = None, player_id: int | None = None,
            scenario: Scenario | None = None, include_stopped: bool = False) -> list[dict]:
    return analytics.player_summary(db, _filters(session_ids, team, player_id, scenario, include_stopped))


@router.get("/teams")
def teams(db: DB, session_ids: SessionIds = None, scenario: Scenario | None = None,
          include_stopped: bool = False) -> list[dict]:
    return analytics.team_summary(db, _filters(session_ids, None, None, scenario, include_stopped))


@router.get("/sessions")
def sessions(db: DB, session_ids: SessionIds = None, team: Team | None = None, player_id: int | None = None,
             scenario: Scenario | None = None, include_stopped: bool = False) -> list[dict]:
    return analytics.session_summary(db, _filters(session_ids, team, player_id, scenario, include_stopped))


@router.get("/export")
def export(db: DB, format: Literal["csv", "json"] = "csv", session_ids: SessionIds = None,
           team: Team | None = None, player_id: int | None = None, scenario: Scenario | None = None,
           include_stopped: bool = False) -> Response:
    rows = analytics.export_rows(db, _filters(session_ids, team, player_id, scenario, include_stopped))
    if format == "json":
        return Response(analytics.to_json(rows), media_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="match_lab_stats.json"'})
    return Response(analytics.to_csv(rows), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="match_lab_stats.csv"'})
