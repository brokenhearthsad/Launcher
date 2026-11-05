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
    # Adaptive monitoring: fast while a Launcher page is open, slow otherwise.
    monitor_active_interval: float = Field(2.0, ge=1.0, le=30.0)
    monitor_idle_interval: float = Field(15.0, ge=5.0, le=300.0)
    process_scan_interval: float = Field(5.0, ge=2.0, le=120.0)
    lhm_enabled: bool = False
    lhm_url: str = Field("http://127.0.0.1:8085/data.json", max_length=200, pattern=r"^http://(127\.0\.0\.1|localhost)(:\d+)?/")
    metrics_retention_days: int = Field(14, ge=1, le=365)


class RuntimeSettingsUpdate(BaseModel):
    ws_publish_hz: float | None = Field(None, gt=0, le=20)
    ui_refresh_seconds: int | None = Field(None, ge=1, le=120)
    log_level: str | None = Field(None, pattern=LEVEL_PATTERN)
    db_log_level: str | None = Field(None, pattern=LEVEL_PATTERN)
    monitor_active_interval: float | None = Field(None, ge=1.0, le=30.0)
    monitor_idle_interval: float | None = Field(None, ge=5.0, le=300.0)
    process_scan_interval: float | None = Field(None, ge=2.0, le=120.0)
    lhm_enabled: bool | None = None
    lhm_url: str | None = Field(None, max_length=200, pattern=r"^http://(127\.0\.0\.1|localhost)(:\d+)?/")
    metrics_retention_days: int | None = Field(None, ge=1, le=365)


class PurgeRequest(BaseModel):
    older_than_days: int = Field(7, ge=0, le=3650)
