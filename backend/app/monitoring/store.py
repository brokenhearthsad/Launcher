"""In-memory ring buffer of recent samples + per-minute aggregation for SQLite."""
from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

# Compact series kept in memory (latest ~30 min at the 2 s active interval).
SERIES_KEYS = ("cpu", "ram_pct", "gpu_util", "gpu_mem_mb", "gpu_temp", "cpu_temp",
               "net_rx_kbps", "net_tx_kbps", "disk_read_kbps", "disk_write_kbps")


def flatten(snapshot: dict[str, Any]) -> dict[str, float | None]:
    gpu = snapshot.get("gpu") or {}
    ok = gpu.get("available")
    temps = snapshot.get("cpu_temp") or {}
    return {
        "cpu": snapshot["cpu"]["percent"],
        "ram_pct": snapshot["memory"]["percent"],
        "ram_used_mb": snapshot["memory"]["used_mb"],
        "gpu_util": gpu.get("util_percent") if ok else None,
        "gpu_mem_mb": gpu.get("mem_used_mb") if ok else None,
        "gpu_temp": gpu.get("temp_c") if ok else None,
        "cpu_temp": temps.get("temp_c") if temps.get("available") else None,
        "net_rx_kbps": snapshot["network"]["rx_kbps"],
        "net_tx_kbps": snapshot["network"]["tx_kbps"],
        "disk_read_kbps": snapshot["disk_io"]["read_kbps"],
        "disk_write_kbps": snapshot["disk_io"]["write_kbps"],
    }


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _max(values: list[float]) -> float | None:
    return round(max(values), 2) if values else None


class MetricsStore:
    def __init__(self, maxlen: int = 900):
        self.series: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self.latest: dict[str, Any] | None = None
        self._minute: list[dict[str, float | None]] = []
        self._minute_started = time.time()

    def add(self, snapshot: dict[str, Any]) -> None:
        self.latest = snapshot
        flat = flatten(snapshot)
        self.series.append({"t": snapshot["ts"], **{k: flat[k] for k in SERIES_KEYS}})
        self._minute.append(flat)

    def minute_due(self, now: float | None = None) -> bool:
        return (now or time.time()) - self._minute_started >= 60 and bool(self._minute)

    def take_minute(self, now: float | None = None) -> dict[str, Any] | None:
        """Aggregate the buffered samples into one ``resource_samples`` row (or None)."""
        rows, self._minute = self._minute, []
        self._minute_started = now or time.time()
        if not rows:
            return None

        def col(key: str) -> list[float]:
            return [r[key] for r in rows if r[key] is not None]  # type: ignore[misc]

        return {
            "ts": datetime.now(timezone.utc), "samples": len(rows),
            "cpu_avg": _avg(col("cpu")), "cpu_max": _max(col("cpu")),
            "ram_pct_avg": _avg(col("ram_pct")), "ram_used_mb_max": _max(col("ram_used_mb")),
            "gpu_util_avg": _avg(col("gpu_util")), "gpu_mem_used_mb_max": _max(col("gpu_mem_mb")),
            "gpu_temp_max": _max(col("gpu_temp")), "cpu_temp_max": _max(col("cpu_temp")),
            "net_rx_kbps_avg": _avg(col("net_rx_kbps")), "net_tx_kbps_avg": _avg(col("net_tx_kbps")),
            "disk_read_kbps_avg": _avg(col("disk_read_kbps")), "disk_write_kbps_avg": _avg(col("disk_write_kbps")),
        }

    def recent(self, seconds: float) -> list[dict[str, Any]]:
        cutoff = time.time() - seconds
        return [p for p in self.series if p["t"] >= cutoff]
