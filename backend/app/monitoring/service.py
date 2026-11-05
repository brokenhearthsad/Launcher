"""Adaptive background monitoring loop (one asyncio task, blocking reads in a worker thread).

Interval: ``monitor_active_interval`` while at least one Launcher page is open
(WebSocket subscriber), ``monitor_idle_interval`` otherwise. Additional
watchers (Steam/Dota processes, slots) register as jobs with their own
interval so there is still only one loop and no busy polling.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete

from app.db.models import ResourceSample
from app.db.session import session_scope
from app.logging_config import get_logger
from app.monitoring.gpu import GpuCollector
from app.monitoring.lhm import LhmReader
from app.monitoring.store import MetricsStore
from app.monitoring.system import SystemCollector

log = get_logger("monitor")


@dataclass
class Job:
    name: str
    interval: Callable[[], float]
    run: Callable[[], Awaitable[None]]
    next_at: float = 0.0
    errors: int = field(default=0)


class MonitorService:
    def __init__(self, state: Any):
        self.state = state
        self.store = MetricsStore()
        self.system = SystemCollector(state.config.monitored_drives)
        self.gpu: GpuCollector | None = None
        self.lhm = LhmReader()
        self.jobs: list[Job] = []
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self._last_purge = 0.0
        self.add_job("metrics", self._metrics_interval, self.collect_once)

    # ------------------------------------------------------------------ scheduling
    @property
    def active(self) -> bool:
        return self.state.bus.subscriber_count > 0

    def _metrics_interval(self) -> float:
        rt = self.state.runtime
        return rt.monitor_active_interval if self.active else rt.monitor_idle_interval

    def add_job(self, name: str, interval: Callable[[], float], run: Callable[[], Awaitable[None]]) -> None:
        self.jobs.append(Job(name, interval, run))

    def wake(self) -> None:
        """Run every job soon (e.g. a page was just opened)."""
        for j in self.jobs:
            j.next_at = 0.0

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="monitor")

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        await asyncio.to_thread(self._flush_minute)
        if self.gpu is not None:
            self.gpu.close()

    async def _loop(self) -> None:
        self.gpu = await asyncio.to_thread(GpuCollector)
        log.info("monitoring started (gpu: %s)", self.gpu.source or "unavailable")
        while not self._stopping.is_set():
            now = time.monotonic()
            for job in self.jobs:
                if now >= job.next_at:
                    try:
                        await job.run()
                        job.errors = 0
                    except Exception:  # noqa: BLE001 - a failing job must not stop monitoring
                        job.errors += 1
                        if job.errors in (1, 10, 100):
                            log.exception("monitor job '%s' failed (%d times)", job.name, job.errors)
                    job.next_at = time.monotonic() + job.interval()
            sleep = max(0.2, min(j.next_at for j in self.jobs) - time.monotonic())
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=sleep)
            except TimeoutError:
                pass

    # ------------------------------------------------------------------ metrics
    def _read(self) -> dict[str, Any]:
        snap = self.system.sample()
        snap["ts"] = time.time()
        snap["gpu"] = self.gpu.sample() if self.gpu else {"available": False, "reason": "initialising"}
        rt = self.state.runtime
        snap["cpu_temp"] = (self.lhm.read(rt.lhm_url) if rt.lhm_enabled
                            else {"available": False, "reason": "LibreHardwareMonitor integration is disabled"})
        return snap

    async def collect_once(self) -> dict[str, Any]:
        snap = await asyncio.to_thread(self._read)
        self.store.add(snap)
        if self.active:
            self.state.bus.publish("metrics_updated", snap)
        if self.store.minute_due():
            await asyncio.to_thread(self._flush_minute)
        return snap

    def _flush_minute(self) -> None:
        row = self.store.take_minute()
        if row is None:
            return
        with session_scope() as db:
            db.add(ResourceSample(**row))
            if time.time() - self._last_purge > 3600:
                cutoff = datetime.now(timezone.utc) - timedelta(days=self.state.runtime.metrics_retention_days)
                db.execute(delete(ResourceSample).where(ResourceSample.ts < cutoff))
                self._last_purge = time.time()
