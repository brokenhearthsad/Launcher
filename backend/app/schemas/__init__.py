"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

LEVEL_PATTERN = "^(DEBUG|INFO|WARNING|ERROR)$"


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class LogOut(ORM):
    id: int
    level: str
    component: str
    message: str
    timestamp: datetime


class RuntimeSettings(BaseModel):
    """Settings editable on the Settings page (stored in ``app_settings``)."""

    ws_publish_hz: float = Field(4.0, gt=0, le=20)
    ui_refresh_seconds: int = Field(5, ge=1, le=120)
    log_level: str = Field("INFO", pattern=LEVEL_PATTERN)
    db_log_level: str = Field("INFO", pattern=LEVEL_PATTERN)


class RuntimeSettingsUpdate(BaseModel):
    ws_publish_hz: float | None = Field(None, gt=0, le=20)
    ui_refresh_seconds: int | None = Field(None, ge=1, le=120)
    log_level: str | None = Field(None, pattern=LEVEL_PATTERN)
    db_log_level: str | None = Field(None, pattern=LEVEL_PATTERN)


class PurgeRequest(BaseModel):
    older_than_days: int = Field(7, ge=0, le=3650)
