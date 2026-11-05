"""Optional CPU temperature from LibreHardwareMonitor's local web server.

Windows does not expose Ryzen temperatures without a kernel driver.
LibreHardwareMonitor (run by the user, Options -> Remote Web Server -> Run,
default port 8085) publishes its sensor tree as JSON; we read it from
localhost only. If it is not running, the temperature is "Нет данных".
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any

MIN_INTERVAL = 5.0
_NUM = re.compile(r"-?\d+(?:[.,]\d+)?")
# Preference order of CPU temperature sensor names (AMD first, then Intel).
PREFERRED = ("tctl/tdie", "tctl", "tdie", "package", "cpu (tctl", "core (tctl", "ccd", "core max", "core average")


def _value(text: str) -> float | None:
    m = _NUM.search(text or "")
    return float(m.group().replace(",", ".")) if m else None


def _walk(node: dict[str, Any], path: tuple[str, ...] = ()):
    yield node, path
    for child in node.get("Children", []) or []:
        yield from _walk(child, path + (str(node.get("Text", "")),))


def parse_cpu_temperature(tree: dict[str, Any]) -> tuple[float | None, str | None]:
    """Return (°C, sensor name) of the best CPU temperature sensor in an LHM tree."""
    candidates: list[tuple[int, float, str]] = []
    for node, path in _walk(tree):
        sid = str(node.get("SensorId", "")).lower()
        text = str(node.get("Text", ""))
        value = str(node.get("Value", ""))
        is_temp = node.get("Type") == "Temperature" or "/temperature/" in sid or "°c" in value.lower()
        if not is_temp:
            continue
        in_cpu = sid.startswith(("/amdcpu", "/intelcpu")) or any(
            ("cpu" in p.lower() or "ryzen" in p.lower() or "intel core" in p.lower()) and "gpu" not in p.lower()
            for p in path)
        if not in_cpu:
            continue
        v = _value(value)
        if v is None or not (0 < v < 125):
            continue
        low = text.lower()
        rank = next((i for i, key in enumerate(PREFERRED) if key in low), len(PREFERRED))
        candidates.append((rank, v, text))
    if not candidates:
        return None, None
    rank, v, text = min(candidates, key=lambda c: (c[0], -c[1]))
    return v, text


class LhmReader:
    def __init__(self) -> None:
        self._cache: tuple[float, str, dict[str, Any]] | None = None

    def read(self, url: str) -> dict[str, Any]:
        now = time.monotonic()
        if self._cache and self._cache[1] == url and now - self._cache[0] < MIN_INTERVAL:
            return self._cache[2]
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:  # noqa: S310 - URL validated as loopback
                tree = json.loads(resp.read(2_000_000).decode("utf-8", "replace"))
            temp, sensor = parse_cpu_temperature(tree)
            result = ({"available": True, "temp_c": temp, "sensor": sensor} if temp is not None
                      else {"available": False, "reason": "LibreHardwareMonitor: CPU temperature sensor not found"})
        except (urllib.error.URLError, OSError, ValueError) as exc:
            result = {"available": False, "reason": f"LibreHardwareMonitor not reachable at {url}: {exc}"}
        self._cache = (now, url, result)
        return result
