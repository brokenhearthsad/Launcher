from __future__ import annotations

import json
import sys
import threading
import time
import types
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.monitoring import gpu as gpu_mod
from app.monitoring.gpu import GpuCollector, parse_smi
from app.monitoring.lhm import LhmReader, parse_cpu_temperature
from app.monitoring.store import MetricsStore
from app.monitoring.system import SystemCollector
from app.schemas import RuntimeSettings
from app.services.event_bus import EventBus
from tests.conftest import make_settings, wait_for

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "lhm_ryzen.json").read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------- psutil
def test_system_collector_reads_real_metrics_and_rates(tmp_path):
    col = SystemCollector([str(tmp_path), "Z:\\definitely-missing"])
    first = col.sample()
    assert first["network"]["rx_kbps"] is None, "rates need two samples - never invented"
    time.sleep(0.2)
    s = col.sample()
    assert 0 <= s["cpu"]["percent"] <= 100 and s["cpu"]["logical_cores"] >= 1
    assert s["memory"]["total_mb"] > 0 and 0 < s["memory"]["percent"] <= 100
    assert s["disks"][0]["available"] and s["disks"][0]["total_gb"] > 0
    assert s["disks"][1] == {"mount": "Z:\\definitely-missing", "available": False}
    assert s["network"]["rx_kbps"] is not None and s["network"]["rx_kbps"] >= 0


# ----------------------------------------------------------------------------- GPU
def test_parse_smi_handles_not_supported_fields():
    out = "NVIDIA GeForce RTX 3050, 37, 2150, 8192, 58, [N/A]\n"
    assert parse_smi(out) == {"name": "NVIDIA GeForce RTX 3050", "util_percent": 37.0, "mem_used_mb": 2150.0,
                              "mem_total_mb": 8192.0, "temp_c": 58.0, "power_w": None}
    assert parse_smi("") is None


def test_gpu_unavailable_reports_reason(monkeypatch):
    monkeypatch.setitem(sys.modules, "pynvml", None)  # import fails
    monkeypatch.setattr(gpu_mod.shutil, "which", lambda _n: None)
    monkeypatch.setattr(gpu_mod.sys, "platform", "linux")
    g = GpuCollector()
    s = g.sample()
    assert s["available"] is False and "nvidia-smi not found" in s["reason"]


def test_gpu_via_nvml(monkeypatch):
    fake = types.SimpleNamespace(
        NVML_TEMPERATURE_GPU=0,
        nvmlInit=lambda: None, nvmlShutdown=lambda: None, nvmlDeviceGetCount=lambda: 1,
        nvmlDeviceGetHandleByIndex=lambda i: "h",
        nvmlDeviceGetUtilizationRates=lambda h: SimpleNamespace(gpu=41),
        nvmlDeviceGetMemoryInfo=lambda h: SimpleNamespace(used=3 * 1048576 * 1024, total=8 * 1048576 * 1024),
        nvmlDeviceGetName=lambda h: b"NVIDIA GeForce RTX 3050",
        nvmlDeviceGetTemperature=lambda h, t: 63,
        nvmlDeviceGetPowerUsage=lambda h: 71500,
    )
    monkeypatch.setitem(sys.modules, "pynvml", fake)
    g = GpuCollector()
    s = g.sample()
    assert g.source == "nvml" and s == {"available": True, "source": "nvml", "name": "NVIDIA GeForce RTX 3050",
                                        "util_percent": 41.0, "mem_used_mb": 3072, "mem_total_mb": 8192,
                                        "temp_c": 63.0, "power_w": 71.5}


def test_gpu_falls_back_to_nvidia_smi_and_rate_limits(monkeypatch):
    monkeypatch.setitem(sys.modules, "pynvml", None)
    monkeypatch.setattr(gpu_mod.shutil, "which", lambda _n: "/usr/bin/nvidia-smi")
    calls = []

    def fake_run(*a, **k):
        calls.append(a)
        return SimpleNamespace(returncode=0, stdout="RTX 3050, 10, 500, 8192, 45, 20.5", stderr="")

    monkeypatch.setattr(gpu_mod.subprocess, "run", fake_run)
    g = GpuCollector()
    assert g.sample()["util_percent"] == 10.0 and g.sample()["source"] == "nvidia-smi"
    assert len(calls) == 1, "nvidia-smi must not be spawned on every sample"


# ----------------------------------------------------------------------------- LibreHardwareMonitor
def test_lhm_picks_ryzen_tctl_not_motherboard_or_gpu():
    assert parse_cpu_temperature(FIXTURE) == (61.4, "Core (Tctl/Tdie)")


def test_lhm_no_cpu_sensor():
    tree = {"Text": "Sensor", "Children": [{"Text": "NVIDIA", "Children": [
        {"Text": "GPU Core", "Value": "50 °C", "Type": "Temperature", "SensorId": "/gpu-nvidia/0/temperature/0"}]}]}
    assert parse_cpu_temperature(tree) == (None, None)


@pytest.fixture
def lhm_server():
    body = json.dumps(FIXTURE).encode()

    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/data.json"
    srv.shutdown()


def test_lhm_reader_over_http(lhm_server):
    r = LhmReader().read(lhm_server)
    assert r == {"available": True, "temp_c": 61.4, "sensor": "Core (Tctl/Tdie)"}


def test_lhm_reader_unreachable_is_no_data():
    r = LhmReader().read("http://127.0.0.1:9/data.json")
    assert r["available"] is False and "not reachable" in r["reason"]


# ----------------------------------------------------------------------------- store
def _snap(cpu, gpu=None, temp=None):
    return {"ts": time.time(), "cpu": {"percent": cpu}, "memory": {"percent": 40.0, "used_mb": 12000},
            "gpu": {"available": gpu is not None, "util_percent": gpu, "mem_used_mb": 1000, "temp_c": 50},
            "cpu_temp": {"available": temp is not None, "temp_c": temp},
            "network": {"rx_kbps": 10.0, "tx_kbps": 2.0}, "disk_io": {"read_kbps": None, "write_kbps": None}}


def test_store_minute_aggregate_keeps_missing_as_null():
    st = MetricsStore()
    st.add(_snap(10))
    st.add(_snap(30))
    row = st.take_minute()
    assert row["samples"] == 2 and row["cpu_avg"] == 20 and row["cpu_max"] == 30
    assert row["gpu_util_avg"] is None and row["cpu_temp_max"] is None and row["disk_read_kbps_avg"] is None
    assert st.take_minute() is None
    assert len(st.recent(60)) == 2


# ----------------------------------------------------------------------------- service
def test_adaptive_interval_and_publish_only_when_watched(tmp_path):
    import asyncio

    from app.monitoring.service import MonitorService

    bus = EventBus()
    state = SimpleNamespace(bus=bus, runtime=RuntimeSettings(), config=make_settings(tmp_path))
    mon = MonitorService(state)
    assert mon._metrics_interval() == 15.0 and not mon.active
    asyncio.run(mon.collect_once())
    assert bus.published == 0
    _, q = bus.subscribe()
    assert mon._metrics_interval() == 2.0
    asyncio.run(mon.collect_once())
    assert bus.published == 1 and q.get_nowait()["type"] == "metrics_updated"


def test_monitoring_api_and_history(tmp_path):
    s = make_settings(tmp_path, monitoring_enabled=True)
    with TestClient(create_app(s)) as c:
        cur = wait_for(lambda: c.get("/api/monitoring/current").json())
        assert {"cpu", "memory", "disks", "network", "gpu", "cpu_temp"} <= set(cur)
        assert cur["cpu_temp"]["available"] is False  # LHM disabled by default
        assert cur["mode"] == "idle"
        mon = c.app.state.lab.monitor
        mon.store._minute_started -= 61
        import asyncio
        asyncio.run(mon.collect_once())
        hist = c.get("/api/monitoring/history", params={"hours": 1}).json()["points"]
        assert len(hist) >= 1 and hist[-1]["samples"] >= 1 and hist[-1]["cpu_avg"] is not None
        assert c.get("/api/monitoring/recent", params={"seconds": 60}).json()["points"]


def test_monitoring_disabled_is_explicit(client):
    r = client.get("/api/monitoring/current")
    assert r.status_code == 503 and r.json()["error"]["code"] == "monitoring_disabled"


def test_lhm_url_must_be_loopback(client):
    assert client.put("/api/settings", json={"lhm_url": "http://example.com/data.json"}).status_code == 422
    ok = {"lhm_enabled": True, "lhm_url": "http://localhost:8085/data.json"}
    assert client.put("/api/settings", json=ok).status_code == 200
