"""Shared FastAPI dependencies and helpers."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.state import LabState, get_state

DB = Annotated[Session, Depends(get_db)]
State = Annotated[LabState, Depends(get_state)]
PageQ = Annotated[int, Query(ge=1, le=100_000)]
PageSizeQ = Annotated[int, Query(ge=1, le=200)]
