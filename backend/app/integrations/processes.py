"""Passive tracking of steam.exe / dota2.exe (psutil). Never starts, stops or re-prioritises them."""
from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import psutil

TRACKED = {"steam": ("steam.exe",), "dota": ("dota2.exe",)}


@dataclass
class Tracked:
    pid: int
    create_time: float
    proc: Any  # psutil.Process

    def info(self, ncpu: int) -> dict[str, Any]:
        try:
            with self.proc.oneshot():
                rss = self.proc.memory_info().rss
                cpu = self.proc.cpu_percent(None) / ncpu
            return {"running": True, "pid": self.pid, "started_at": self.create_time,
                    "uptime_seconds": round(time.time() - self.create_time), "rss_mb": round(rss / 1048576, 1),
                    "cpu_percent": round(cpu, 2)}
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {"running": True, "pid": self.pid, "started_at": self.create_time,
                    "uptime_seconds": round(time.time() - self.create_time), "rss_mb": None, "cpu_percent": None}


def _default_lister() -> Iterable[tuple[int, str, float]]:
    for p in psutil.process_iter(["name", "create_time"]):
        name = p.info.get("name")
        if name:
            yield p.pid, name, p.info.get("create_time") or 0.0


class ProcessWatcher:
    """Keeps known PIDs; does a full process scan only while something is not running."""

    def __init__(self, lister: Callable[[], Iterable[tuple[int, str, float]]] | None = None,
                 opener: Callable[[int], Any] | None = None):
        self._list = lister or _default_lister
        self._open = opener or psutil.Process
        self.tracked: dict[str, Tracked | None] = {k: None for k in TRACKED}
        self.full_scans = 0
        self._ncpu = psutil.cpu_count() or 1

    def _alive(self, t: Tracked) -> bool:
        try:
            return t.proc.is_running() and abs(t.proc.create_time() - t.create_time) < 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            return False

    def poll(self) -> list[tuple[str, str, dict[str, Any]]]:
        """Update state; return changes as (key, 'started'|'stopped', details)."""
        changes: list[tuple[str, str, dict[str, Any]]] = []
        for key, t in list(self.tracked.items()):
            if t is not None and not self._alive(t):
                changes.append((key, "stopped", {"pid": t.pid,
                                                 "uptime_seconds": round(time.time() - t.create_time)}))
                self.tracked[key] = None
        missing = [k for k, t in self.tracked.items() if t is None]
        if missing:
            self.full_scans += 1
            wanted = {n.lower(): k for k in missing for n in TRACKED[k]}
            found: dict[str, tuple[int, float]] = {}
            for pid, name, ctime in self._list():
                key = wanted.get(name.lower())
                # The oldest matching process is the main one (steam.exe spawns helpers with other names).
                if key and (key not in found or ctime < found[key][1]):
                    found[key] = (pid, ctime)
            for key, (pid, ctime) in found.items():
                try:
                    proc = self._open(pid)
                    proc.cpu_percent(None)  # prime
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                self.tracked[key] = Tracked(pid, ctime, proc)
                changes.append((key, "started", {"pid": pid, "started_at": ctime}))
        return changes

    def status(self) -> dict[str, dict[str, Any]]:
        return {k: (t.info(self._ncpu) if t else {"running": False}) for k, t in self.tracked.items()}
