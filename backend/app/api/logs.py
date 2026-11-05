from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import distinct, func, select

from app.api.deps import DB, PageQ, PageSizeQ
from app.db.models import SystemLog
from app.schemas import LogOut, Page

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=Page[LogOut])
def list_logs(db: DB, page: PageQ = 1, page_size: PageSizeQ = 50,
              level: list[str] | None = Query(None, description="DEBUG/INFO/WARNING/ERROR/CRITICAL"),
              component: str | None = Query(None, max_length=64),
              search: str | None = Query(None, max_length=200),
              since: datetime | None = None):
    conds = []
    if level:
        conds.append(SystemLog.level.in_([lv.upper() for lv in level]))
    if component:
        conds.append(SystemLog.component == component)
    if search:
        conds.append(SystemLog.message.ilike(f"%{search}%"))
    if since:
        conds.append(SystemLog.timestamp >= since)
    total = db.scalar(select(func.count()).select_from(SystemLog).where(*conds)) or 0
    rows = db.scalars(select(SystemLog).where(*conds).order_by(SystemLog.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=[LogOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/components")
def components(db: DB) -> list[str]:
    return sorted(db.scalars(select(distinct(SystemLog.component))).all())
