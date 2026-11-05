"""GSI endpoint (Dota 2 -> Launcher, read-only) and state/history API."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.api.deps import DB, PageQ, PageSizeQ, State
from app.db.models import GsiMatch
from app.services.gsi import MAX_BODY, GsiRejected

router = APIRouter(tags=["gsi"])


@router.post("/gsi", include_in_schema=True, summary="Receiver for Dota 2 Game State Integration")
async def receive(request: Request, state: State):
    body = await request.body()
    if len(body) > MAX_BODY + 1:
        body = body[: MAX_BODY + 1]
    try:
        await state.gsi.receive(body, request.client.host if request.client else "")
    except GsiRejected as exc:
        return JSONResponse({"ok": False, "error": exc.reason}, status_code=exc.status)
    return {"ok": True}


@router.get("/api/gsi/state")
def gsi_state(state: State) -> dict:
    return state.gsi.view()


@router.get("/api/gsi/matches")
def gsi_matches(db: DB, page: PageQ = 1, page_size: PageSizeQ = 20,
                result: str | None = Query(None, pattern="^(in_progress|win|loss|ended|left)$")) -> dict:
    conds = [GsiMatch.result == result] if result else []
    total = db.scalar(select(func.count()).select_from(GsiMatch).where(*conds)) or 0
    rows = db.scalars(select(GsiMatch).where(*conds).order_by(GsiMatch.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    cols = [c.name for c in GsiMatch.__table__.columns]
    items = [{c: (getattr(r, c).isoformat() if hasattr(getattr(r, c), "isoformat") else getattr(r, c)) for c in cols}
             for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}
