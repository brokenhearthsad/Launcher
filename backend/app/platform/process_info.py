"""Resource usage of the Launcher process itself (psutil).

Only *our own* process is inspected here. Priorities of the user's processes
(Steam, Dota 2, Discord, ...) are never changed.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any

import psutil

from app.logging_config import get_logger

log = get_logger("platform")

_proc = psutil.Process(os.getpid())
_lock = threading.Lock()
# Prime cpu_percent so the first real reading is meaningful (non-blocking API).
_proc.cpu_percent(None)


def self_usage() -> dict[str, Any]:
    """RSS, CPU and thread count of this process. Cheap: a few syscalls."""
    with _lock:
        mem = _proc.memory_info()
        cpu = _proc.cpu_percent(None)  # since previous call, normalised below
        threads = _proc.num_threads()
        children = len(_proc.children(recursive=True))
    ncpu = psutil.cpu_count() or 1
    return {
        "pid": _proc.pid,
        "rss_mb": round(mem.rss / 1024 / 1024, 1),
        # Windows: private working set is what Task Manager shows as "Memory".
        "private_mb": round(getattr(mem, "private", mem.rss) / 1024 / 1024, 1),
        "cpu_percent": round(cpu / ncpu, 2),  # share of the whole machine, like Task Manager
        "threads": threads,
        "child_processes": children,
        "python": sys.version.split()[0],
        "uptime_seconds": round(time.time() - _proc.create_time(), 1),
    }


def lower_own_priority() -> bool:
    """Opt-in (``DML_LOWER_OWN_PRIORITY=true``): run the Launcher below normal priority."""
    try:
        if sys.platform == "win32":
            _proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            _proc.nice(10)
        log.info("launcher process priority lowered (own process only)")
        return True
    except (psutil.Error, OSError) as exc:  # pragma: no cover - platform specific
        log.warning("could not lower own priority: %s", exc)
        return False
