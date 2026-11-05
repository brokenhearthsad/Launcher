"""NVIDIA GPU metrics: NVML in-process first, ``nvidia-smi`` as fallback.

NVML (``nvidia-ml-py``, NVIDIA's official bindings) costs microseconds per
call. ``nvidia-smi`` spawns a process (~50-150 ms), so it is rate-limited.
If neither works the GPU is reported as unavailable with the reason.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from app.logging_config import get_logger

log = get_logger("monitor.gpu")
SMI_MIN_INTERVAL = 5.0
SMI_QUERY = "name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw"


def _num(v: str) -> float | None:
    v = v.strip()
    try:
        return float(v)
    except ValueError:
        return None  # "[N/A]", "[Not Supported]"


def parse_smi(output: str) -> dict[str, Any] | None:
    line = next((x for x in output.splitlines() if x.strip()), "")
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 6:
        return None
    return {"name": parts[0], "util_percent": _num(parts[1]), "mem_used_mb": _num(parts[2]),
            "mem_total_mb": _num(parts[3]), "temp_c": _num(parts[4]), "power_w": _num(parts[5])}


class GpuCollector:
    def __init__(self) -> None:
        self.source: str | None = None
        self.reason = ""
        self._nvml = None
        self._handle = None
        self._smi: str | None = None
        self._smi_cache: tuple[float, dict[str, Any]] | None = None
        self._init()

    def _init(self) -> None:
        try:
            import pynvml  # provided by nvidia-ml-py

            pynvml.nvmlInit()
            if pynvml.nvmlDeviceGetCount() < 1:
                raise RuntimeError("no NVIDIA GPU")
            self._nvml = pynvml
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.source = "nvml"
            return
        except Exception as exc:  # noqa: BLE001 - any NVML failure means "try fallback"
            self.reason = f"NVML: {exc}"
        smi = shutil.which("nvidia-smi")
        if smi is None and sys.platform == "win32":
            default = Path(r"C:\Windows\System32\nvidia-smi.exe")
            smi = str(default) if default.exists() else None
        if smi:
            self._smi = smi
            self.source = "nvidia-smi"
        else:
            self.reason += "; nvidia-smi not found"
            log.info("GPU metrics unavailable (%s)", self.reason)

    def sample(self) -> dict[str, Any]:
        if self.source == "nvml":
            try:
                return {"available": True, "source": "nvml", **self._nvml_read()}
            except Exception as exc:  # noqa: BLE001
                return {"available": False, "source": "nvml", "reason": f"NVML read failed: {exc}"}
        if self.source == "nvidia-smi":
            now = time.monotonic()
            if self._smi_cache and now - self._smi_cache[0] < SMI_MIN_INTERVAL:
                return self._smi_cache[1]
            result = self._smi_read()
            self._smi_cache = (now, result)
            return result
        return {"available": False, "source": None, "reason": self.reason}

    def _nvml_read(self) -> dict[str, Any]:
        n, h = self._nvml, self._handle
        util = n.nvmlDeviceGetUtilizationRates(h)
        mem = n.nvmlDeviceGetMemoryInfo(h)
        name = n.nvmlDeviceGetName(h)
        try:
            temp = float(n.nvmlDeviceGetTemperature(h, n.NVML_TEMPERATURE_GPU))
        except Exception:  # noqa: BLE001
            temp = None
        try:
            power = round(n.nvmlDeviceGetPowerUsage(h) / 1000, 1)
        except Exception:  # noqa: BLE001
            power = None
        return {"name": name.decode() if isinstance(name, bytes) else name, "util_percent": float(util.gpu),
                "mem_used_mb": round(mem.used / 1048576), "mem_total_mb": round(mem.total / 1048576),
                "temp_c": temp, "power_w": power}

    def _smi_read(self) -> dict[str, Any]:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            out = subprocess.run([self._smi, f"--query-gpu={SMI_QUERY}", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=5, creationflags=flags)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"available": False, "source": "nvidia-smi", "reason": str(exc)}
        parsed = parse_smi(out.stdout) if out.returncode == 0 else None
        if parsed is None:
            return {"available": False, "source": "nvidia-smi", "reason": (out.stderr or "no output").strip()[:200]}
        return {"available": True, "source": "nvidia-smi", **parsed}

    def close(self) -> None:
        if self._nvml is not None:
            try:
                self._nvml.nvmlShutdown()
            except Exception:  # noqa: BLE001
                pass
