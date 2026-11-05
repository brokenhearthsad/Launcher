"""SQLAlchemy ORM models.

Infrastructure: ``system_logs``, ``app_settings``.
Phase 2: ``client_slots`` (10 logical slots), ``events`` (process / slot /
monitoring history) and ``resource_samples`` (per-minute aggregates).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Stores UTC datetimes; SQLite drops tzinfo, so it is re-attached on load."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    pass


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    component: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, index=True
    )


class AppSetting(Base):
    """Runtime-editable settings (Settings page). Value is JSON."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow
    )


class ClientSlot(Base):
    """One of the ten *logical* slots. Not a Steam account and not a game client.

    ``binding`` is ``none`` or ``local_client`` (observe the Steam/Dota 2 client
    running on this PC). At most one slot can be bound to the local client.
    ``remote_agent`` is reserved for future multi-PC setups.
    """

    __tablename__ = "client_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # 1..10
    name: Mapped[str] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(Text, default="")
    team: Mapped[str] = mapped_column(String(16))  # radiant | dire
    binding: Mapped[str] = mapped_column(String(16), default="none")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class Event(Base):
    """Something observed or changed: process started/stopped, slot edited, ..."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_slot_ts", "slot_id", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    source: Mapped[str] = mapped_column(String(32), index=True)  # steam | dota | slot | monitor | system
    type: Mapped[str] = mapped_column(String(48), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="info")
    slot_id: Mapped[int | None] = mapped_column(ForeignKey("client_slots.id", ondelete="SET NULL"))
    message: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ResourceSample(Base):
    """Per-minute aggregate of machine metrics. NULL = metric unavailable."""

    __tablename__ = "resource_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    samples: Mapped[int] = mapped_column(Integer)
    cpu_avg: Mapped[float | None] = mapped_column(Float)
    cpu_max: Mapped[float | None] = mapped_column(Float)
    ram_pct_avg: Mapped[float | None] = mapped_column(Float)
    ram_used_mb_max: Mapped[float | None] = mapped_column(Float)
    gpu_util_avg: Mapped[float | None] = mapped_column(Float)
    gpu_mem_used_mb_max: Mapped[float | None] = mapped_column(Float)
    gpu_temp_max: Mapped[float | None] = mapped_column(Float)
    cpu_temp_max: Mapped[float | None] = mapped_column(Float)
    net_rx_kbps_avg: Mapped[float | None] = mapped_column(Float)
    net_tx_kbps_avg: Mapped[float | None] = mapped_column(Float)
    disk_read_kbps_avg: Mapped[float | None] = mapped_column(Float)
    disk_write_kbps_avg: Mapped[float | None] = mapped_column(Float)
