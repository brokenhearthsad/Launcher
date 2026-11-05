from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest
from fastapi.testclient import TestClient

from app.integrations import steam as steam_mod
from app.integrations.processes import ProcessWatcher
from app.integrations.vdf import VdfError, get_ci, loads
from app.main import create_app
from app.schemas import RuntimeSettings
from app.services.environment import EnvironmentService
from app.services.event_bus import EventBus
from tests.conftest import make_settings

LIBRARY_VDF = r'''
"libraryfolders"
{
	"0"
	{
		"path"		"C:\\Program Files (x86)\\Steam"
		"label"		""
		"apps"		{ "228980"		"426529977" }
	}
	"1"
	{
		"path"		"{LIB}"
		"apps"		{ "570"		"38912345678" }
	}
}
'''
MANIFEST = '''"AppState"
{
	"appid"		"570"
	"name"		"Dota 2"
	"StateFlags"		"4"
	"installdir"		"dota 2 beta"
	"LastUpdated"		"1762300000"
	"SizeOnDisk"		"38912345678"
	"buildid"		"20512345"
}
'''


def make_layout(tmp_path: Path, with_exe: bool = True) -> tuple[Path, Path]:
    steam = tmp_path / "Steam"
    lib = tmp_path / "SteamLibrary"
    (steam / "steamapps").mkdir(parents=True)
    (lib / "steamapps" / "common" / "dota 2 beta" / "game" / "bin" / "win64").mkdir(parents=True)
    (steam / "steamapps" / "libraryfolders.vdf").write_text(
        LIBRARY_VDF.replace("{LIB}", str(lib).replace("\\", "\\\\")), encoding="utf-8")
    (lib / "steamapps" / "appmanifest_570.acf").write_text(MANIFEST, encoding="utf-8")
    if with_exe:
        (lib / "steamapps" / "common" / "dota 2 beta" / "game" / "bin" / "win64" / "dota2.exe").write_bytes(b"MZ")
    return steam, lib


# ----------------------------------------------------------------------------- vdf
def test_vdf_parses_nested_blocks_escapes_and_comments():
    data = loads('// comment\n"a" { "path" "D:\\\\Games\\\\Steam" "n" { "x" "1" } unquoted value }')
    assert data == {"a": {"path": "D:\\Games\\Steam", "n": {"x": "1"}, "unquoted": "value"}}
    assert get_ci({"AppState": 1}, "appstate") == 1


@pytest.mark.parametrize("bad", ['"a" {', '"a" }', '"a" "b', '{ "x" "y" }'])
def test_vdf_rejects_malformed(bad):
    with pytest.raises(VdfError):
        loads(bad)


# ----------------------------------------------------------------------------- discovery
def test_discovers_steam_libraries_and_dota_in_second_library(tmp_path):
    steam, lib = make_layout(tmp_path)
    s = steam_mod.find_steam(steam, {})
    assert s.installed and s.source == "config" and s.libraries[0] == str(steam)
    assert str(lib) in s.libraries
    d = steam_mod.find_dota(s.libraries)
    assert d.installed and d.library == str(lib) and d.exe_exists
    assert d.buildid == "20512345" and d.state == ["fully_installed"] and d.size_gb == 38.9
    assert d.last_updated.startswith("2025-")


def test_registry_path_is_used(tmp_path):
    steam, _ = make_layout(tmp_path)
    s = steam_mod.find_steam(None, {"steam_path": str(steam)})
    assert s.installed and s.source == "registry"


def test_old_libraryfolders_format(tmp_path):
    steam = tmp_path / "Steam"
    (steam / "steamapps").mkdir(parents=True)
    (steam / "steamapps" / "libraryfolders.vdf").write_text('"LibraryFolders" { "TimeNextStatsReport" "1" '
                                                            '"1" "E:\\\\SteamLibrary" }', encoding="utf-8")
    libs, err = steam_mod.libraries(steam)
    assert err is None and libs == [str(steam), str(Path("E:\\SteamLibrary"))]


def test_not_installed_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(steam_mod.sys, "platform", "linux")
    s = steam_mod.find_steam(tmp_path / "nope", {})
    assert not s.installed and "not found" in s.error
    d = steam_mod.find_dota([str(tmp_path)])
    assert not d.installed and "appmanifest_570" in d.error


def test_missing_executable_and_update_state(tmp_path):
    steam, lib = make_layout(tmp_path, with_exe=False)
    (lib / "steamapps" / "appmanifest_570.acf").write_text(MANIFEST.replace('"4"', '"1026"'), encoding="utf-8")
    d = steam_mod.find_dota(steam_mod.find_steam(steam, {}).libraries)
    assert d.installed and not d.exe_exists and d.state == ["update_required", "update_started"]


def test_registry_is_empty_off_windows(monkeypatch):
    monkeypatch.setattr(steam_mod.sys, "platform", "linux")
    assert steam_mod.read_registry() == {}


# ----------------------------------------------------------------------------- processes
class FakeProc:
    def __init__(self, pid, ctime):
        self.pid, self.ctime, self.alive = pid, ctime, True

    def is_running(self):
        return self.alive

    def create_time(self):
        if not self.alive:
            raise psutil.NoSuchProcess(self.pid)
        return self.ctime

    def cpu_percent(self, _=None):
        return 12.0

    def memory_info(self):
        return SimpleNamespace(rss=200 * 1048576)

    def oneshot(self):
        import contextlib
        return contextlib.nullcontext()


def test_process_watcher_start_stop_and_no_rescan_when_tracked():
    now = time.time()
    table = {101: ("steam.exe", now - 100), 102: ("steamwebhelper.exe", now - 90), 50: ("Steam.exe", now - 200)}
    procs: dict[int, FakeProc] = {}

    def opener(pid):
        procs[pid] = FakeProc(pid, table[pid][1])
        return procs[pid]

    w = ProcessWatcher(lister=lambda: [(p, n, c) for p, (n, c) in table.items()], opener=opener)
    changes = w.poll()
    assert changes == [("steam", "started", {"pid": 50, "started_at": now - 200})], "oldest steam.exe is main"
    assert w.status()["steam"]["pid"] == 50 and w.status()["steam"]["rss_mb"] == 200.0
    assert w.status()["dota"] == {"running": False}

    table[777] = ("dota2.exe", now)
    scans = w.full_scans
    assert w.poll() == [("dota", "started", {"pid": 777, "started_at": now})]
    assert w.full_scans == scans + 1
    w.poll()
    assert w.full_scans == scans + 1, "no full scan while everything is tracked"

    procs[777].alive = False
    del table[777]
    ch = w.poll()
    assert ch[0][0] == "dota" and ch[0][1] == "stopped" and ch[0][2]["pid"] == 777


def test_pid_reuse_is_detected():
    t0 = time.time() - 50
    table = {9: ("dota2.exe", t0)}
    w = ProcessWatcher(lister=lambda: [(p, n, c) for p, (n, c) in table.items()],
                       opener=lambda pid: FakeProc(pid, table[pid][1]))
    w.poll()
    w.tracked["dota"].proc.ctime = t0 + 30  # same PID, different process
    assert w.poll()[0][1] == "stopped"


# ----------------------------------------------------------------------------- service + API
def test_environment_service_journals_events(tmp_path):
    s = make_settings(tmp_path)
    with TestClient(create_app(s)) as c:
        table: dict[int, tuple[str, float]] = {}
        watcher = ProcessWatcher(lister=lambda: [(p, n, ct) for p, (n, ct) in table.items()],
                                 opener=lambda pid: FakeProc(pid, table[pid][1]))
        env = EnvironmentService(SimpleNamespace(bus=EventBus(), runtime=RuntimeSettings(), config=s),
                                 watcher=watcher, discover=lambda _p: {"steam": {"installed": False},
                                                                       "dota": {"installed": False}})
        asyncio.run(env.poll())
        table[5] = ("dota2.exe", time.time())
        asyncio.run(env.poll())
        ev = c.get("/api/events", params={"source": "dota"}).json()
        assert ev["total"] == 1 and ev["items"][0]["type"] == "process_started"
        assert "PID 5" in ev["items"][0]["message"]


def test_environment_api_with_fake_steam(tmp_path):
    steam, lib = make_layout(tmp_path)
    with TestClient(create_app(make_settings(tmp_path, steam_path=steam))) as c:
        env = c.get("/api/environment").json()
        assert env["steam"]["installed"] and env["steam"]["path"] == str(steam)
        assert env["dota"]["installed"] and env["dota"]["exe_exists"]
        assert env["steam"]["process"]["running"] in (True, False)
        assert c.post("/api/environment/refresh").status_code == 200
        assert c.get("/api/events", params={"slot_id": 11}).status_code == 422
