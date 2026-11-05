from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Path
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select

from app.api.deps import DB, PageQ, PageSizeQ, State
from app.db.models import Event

router = APIRouter(prefix="/api/slots", tags=["slots"])
SlotId = Path(ge=1, le=10)


class SlotUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    note: str | None = Field(None, max_length=500)
    binding: Literal["none", "local_client"] | None = None

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v


@router.get("")
def list_slots(db: DB, state: State) -> list[dict]:
    return state.slots.list(db)


@router.get("/{slot_id}")
def get_slot(db: DB, state: State, slot_id: int = SlotId) -> dict:
    return state.slots.get(db, slot_id)


@router.put("/{slot_id}")
def update_slot(data: SlotUpdate, db: DB, state: State, slot_id: int = SlotId) -> dict:
    return state.slots.update(db, slot_id, data.model_dump(exclude_none=True))


@router.get("/{slot_id}/history")
def slot_history(db: DB, slot_id: int = SlotId, page: PageQ = 1, page_size: PageSizeQ = 50) -> dict:
    cond = Event.slot_id == slot_id
    total = db.scalar(select(func.count()).select_from(Event).where(cond)) or 0
    rows = db.scalars(select(Event).where(cond).order_by(Event.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{"id": e.id, "ts": e.ts.isoformat(), "type": e.type, "message": e.message, "data": e.data}
                      for e in rows], "total": total, "page": page, "page_size": page_size}
