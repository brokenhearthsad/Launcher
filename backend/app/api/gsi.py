"""GSI endpoint (Dota 2 -> Launcher, read-only) and state/history API."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import DB, PageQ, PageSizeQ, State
from app.db.models import GsiMatch
from app.errors import AppError
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
                result: str | None = Query(None, pattern="^(in_progress|win|loss|ended|left|interrupted)$")) -> dict:
    conds = [GsiMatch.result == result] if result else []
    total = db.scalar(select(func.count()).select_from(GsiMatch).where(*conds)) or 0
    rows = db.scalars(select(GsiMatch).where(*conds).order_by(GsiMatch.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    cols = [c.name for c in GsiMatch.__table__.columns]
    items = [{c: (getattr(r, c).isoformat() if hasattr(getattr(r, c), "isoformat") else getattr(r, c)) for c in cols}
             for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}



# ----------------------------------------------------------------------------- configuration (files)
class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


def _guard(header: str | None) -> None:
    # Custom header => cross-site pages cannot trigger file changes (CORS preflight).
    if header != "1":
        raise ForbiddenError("this action is accepted only from the Launcher interface")


class InstallRequest(BaseModel):
    plan_id: str = Field(min_length=64, max_length=256)
    confirm: bool = False


class ConfirmRequest(BaseModel):
    confirm: bool = False


class RestoreRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    confirm: bool = False


async def _ready(state) -> None:
    """The installer needs the Dota 2 path discovered by the environment service."""
    if state.environment.polled_at == 0:
        await state.environment.poll()


@router.get("/api/gsi/config")
async def gsi_config(state: State) -> dict:
    """Read-only check + the exact plan that ``install`` would apply."""
    await _ready(state)
    return await asyncio.to_thread(state.gsi_installer.check)


@router.post("/api/gsi/install")
async def gsi_install(data: InstallRequest, state: State, x_launcher_request: str | None = Header(None)) -> dict:
    _guard(x_launcher_request)
    await _ready(state)
    return await asyncio.to_thread(state.gsi_installer.install, data.plan_id, data.confirm)


@router.post("/api/gsi/uninstall")
async def gsi_uninstall(data: ConfirmRequest, state: State, x_launcher_request: str | None = Header(None)) -> dict:
    _guard(x_launcher_request)
    await _ready(state)
    return await asyncio.to_thread(state.gsi_installer.uninstall, data.confirm)


@router.get("/api/gsi/backups")
def gsi_backups(state: State) -> list[dict]:
    return state.gsi_installer.backups()


@router.post("/api/gsi/restore")
async def gsi_restore(data: RestoreRequest, state: State, x_launcher_request: str | None = Header(None)) -> dict:
    _guard(x_launcher_request)
    await _ready(state)
    return await asyncio.to_thread(state.gsi_installer.restore, data.name, data.confirm)
