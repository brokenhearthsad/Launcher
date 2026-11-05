"""CPU, RAM, disks and network via psutil (cheap, no subprocesses)."""
from __future__ import annotations

import time
from typing import Any

import psutil


def _is_loopback(nic: str) -> bool:
    n = nic.lower()
    return n == "lo" or "loopback" in n or "pseudo-interface" in n


class SystemCollector:
    def __init__(self, drives: list[str]):
        self.drives = drives
        psutil.cpu_percent(None, percpu=True)  # prime: first call is meaningless
        self._last_t: float | None = None
        self._last_net: tuple[int, int] | None = None
        self._last_disk: tuple[int, int] | None = None
        self._cores = (psutil.cpu_count(logical=True), psutil.cpu_count(logical=False))

    def sample(self) -> dict[str, Any]:
        now = time.monotonic()
        per_core = psutil.cpu_percent(None, percpu=True)
        cpu = round(sum(per_core) / len(per_core), 1) if per_core else None
        try:
            freq = psutil.cpu_freq()
            freq_mhz = round(freq.current) if freq and freq.current else None
        except (OSError, NotImplementedError, AttributeError):
            freq_mhz = None
        vm = psutil.virtual_memory()

        disks = []
        for d in self.drives:
            try:
                u = psutil.disk_usage(d)
                disks.append({"mount": d, "available": True, "total_gb": round(u.total / 1e9, 1),
                              "used_gb": round(u.used / 1e9, 1), "free_gb": round(u.free / 1e9, 1),
                              "percent": round(u.percent, 1)})
            except (OSError, FileNotFoundError):
                disks.append({"mount": d, "available": False})

        net_rx = net_tx = None
        try:
            counters = psutil.net_io_counters(pernic=True)
            rx = sum(c.bytes_recv for n, c in counters.items() if not _is_loopback(n))
            tx = sum(c.bytes_sent for n, c in counters.items() if not _is_loopback(n))
        except OSError:
            rx = tx = None
        disk_r = disk_w = None
        try:
            io = psutil.disk_io_counters(perdisk=False)
            dr, dw = (io.read_bytes, io.write_bytes) if io else (None, None)
        except (OSError, RuntimeError):
            dr = dw = None

        if self._last_t is not None:
            dt = max(1e-3, now - self._last_t)
            if rx is not None and self._last_net is not None:
                net_rx = round(max(0, rx - self._last_net[0]) / 1024 / dt, 1)
                net_tx = round(max(0, tx - self._last_net[1]) / 1024 / dt, 1)
            if dr is not None and self._last_disk is not None:
                disk_r = round(max(0, dr - self._last_disk[0]) / 1024 / dt, 1)
                disk_w = round(max(0, dw - self._last_disk[1]) / 1024 / dt, 1)
        self._last_t = now
        self._last_net = (rx, tx) if rx is not None else None
        self._last_disk = (dr, dw) if dr is not None else None

        return {
            "cpu": {"percent": cpu, "per_core": [round(x, 1) for x in per_core], "freq_mhz": freq_mhz,
                    "logical_cores": self._cores[0], "physical_cores": self._cores[1]},
            "memory": {"total_mb": round(vm.total / 1048576), "used_mb": round((vm.total - vm.available) / 1048576),
                       "available_mb": round(vm.available / 1048576), "percent": round(vm.percent, 1)},
            "disks": disks,
            # Totals over all physical disks: psutil cannot map I/O to drive letters without WMI.
            "disk_io": {"read_kbps": disk_r, "write_kbps": disk_w},
            "network": {"rx_kbps": net_rx, "tx_kbps": net_tx},
        }
