"""Steam / Dota 2 environment state: installation (files, registry) + processes.

Installation data is re-read every 60 s or when Steam starts/stops; processes
are polled by the shared monitor loop. Changes are journaled as events.
"""
from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Callable
from typing import Any

from app.integrations import steam as steam_mod
from app.integrations.processes import ProcessWatcher
from app.logging_config import get_logger
from app.services import events

log = get_logger("environment")
INSTALL_REFRESH = 60.0
LABELS = {"steam": "Steam", "dota": "Dota 2"}


class EnvironmentService:
    def __init__(self, state: Any, watcher: ProcessWatcher | None = None,
                 discover: Callable[[Any], dict[str, Any]] | None = None):
        self.state = state
        self.watcher = watcher or ProcessWatcher()
        self._discover = discover or steam_mod.discover
        self.install: dict[str, Any] | None = None
        self.install_checked_at = 0.0
        self.polled_at = 0.0
        self.listeners: list[Callable[[dict[str, Any]], None]] = []
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ scheduling
    def interval(self) -> float:
        rt = self.state.runtime
        watched = self.state.bus.subscriber_count > 0
        return rt.process_scan_interval if watched else max(rt.process_scan_interval, rt.monitor_idle_interval)

    async def refresh_install(self) -> None:
        self.install = await asyncio.to_thread(self._discover, self.state.config.steam_path)
        self.install_checked_at = time.monotonic()

    async def poll(self) -> None:
        async with self._lock:
            if self.install is None or time.monotonic() - self.install_checked_at > INSTALL_REFRESH:
                await self.refresh_install()
            changes = await asyncio.to_thread(self.watcher.poll)
            if any(key == "steam" for key, _, _ in changes):
                await self.refresh_install()  # signed-in flag / paths may change with Steam
            elif sys.platform == "win32" and self.install is not None:
                reg = await asyncio.to_thread(steam_mod.read_registry)
                self.install["signed_in"] = reg.get("signed_in")
            self.polled_at = time.time()
            for key, kind, details in changes:
                await asyncio.to_thread(self._journal, key, kind, details)
            snap = self.snapshot()
            if changes:
                for fn in self.listeners:
                    fn(snap)
            if changes or self.state.bus.subscriber_count > 0:
                self.state.bus.publish("environment_updated", snap)

    def _journal(self, key: str, kind: str, details: dict[str, Any]) -> None:
        verb = "запущен" if kind == "started" else "остановлен"
        events.record(self.state.bus, key, f"process_{kind}", f"{LABELS[key]} {verb} (PID {details['pid']})",
                      data=details)

    # ------------------------------------------------------------------ view
    def snapshot(self) -> dict[str, Any]:
        inst = self.install or {"steam": {"installed": False}, "dota": {"installed": False}, "signed_in": None,
                                "registry_available": False, "platform": sys.platform}
        procs = self.watcher.status()
        return {
            "steam": {**inst["steam"], "process": procs["steam"], "signed_in": inst.get("signed_in")},
            "dota": {**inst["dota"], "process": procs["dota"]},
            "registry_available": inst.get("registry_available", False),
            "platform": inst.get("platform", sys.platform),
            "checked_at": self.polled_at or None,
        }
