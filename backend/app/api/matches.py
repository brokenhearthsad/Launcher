from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import DB, PageQ, PageSizeQ
from app.db.models import MatchSession
from app.domain import Scenario, SessionStatus
from app.schemas import HistoryItem, Page

router = APIRouter(prefix="/api/matches", tags=["matches"])

HISTORY_STATUSES = (SessionStatus.FINISHED.value, SessionStatus.STOPPED.value, SessionStatus.ERROR.value)


@router.get("/history", response_model=Page[HistoryItem])
def history(db: DB, page: PageQ = 1, page_size: PageSizeQ = 20,
            winner: str | None = Query(None, pattern="^(radiant|dire|none)$"),
            scenario: Scenario | None = None,
            status: SessionStatus | None = None):
    conds = [MatchSession.status.in_(HISTORY_STATUSES)]
    if status is not None:
        conds.append(MatchSession.status == status.value)
    if winner == "none":
        conds.append(MatchSession.winner.is_(None))
    elif winner:
        conds.append(MatchSession.winner == winner)
    if scenario:
        conds.append(MatchSession.scenario == scenario.value)
    total = db.scalar(select(func.count()).select_from(MatchSession).where(*conds)) or 0
    rows = db.scalars(select(MatchSession).where(*conds)
                      .order_by(MatchSession.finished_at.desc().nullslast(), MatchSession.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    items = [HistoryItem.model_validate(r, from_attributes=True) for r in rows]
    return Page(items=items, total=total, page=page, page_size=page_size)
