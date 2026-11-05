from __future__ import annotations

import asyncio
import time

from app.integrations.processes import ProcessWatcher
from app.services.slots import compute_status
from tests.test_environment import FakeProc, make_layout


def test_ten_slots_five_per_team(client):
    slots = client.get("/api/slots").json()
    assert [s["id"] for s in slots] == list(range(1, 11))
    assert [s["name"] for s in slots[:2]] == ["Slot 1", "Slot 2"]
    assert sum(s["team"] == "radiant" for s in slots) == 5 and slots[9]["team"] == "dire"
    assert all(s["binding"] == "none" and s["status"] == "unbound" for s in slots)
    assert slots[0]["status_label"] == "Не привязан"


def test_rename_and_note_are_saved_and_journaled(client):
    r = client.put("/api/slots/3", json={"name": "  Тестовый слот ", "note": "мой основной клиент"})
    assert r.status_code == 200 and r.json()["name"] == "Тестовый слот"
    assert client.get("/api/slots/3").json()["note"] == "мой основной клиент"
    hist = client.get("/api/slots/3/history").json()
    types = [h["type"] for h in hist["items"]]
    assert "renamed" in types and "note_changed" in types
    assert client.get("/api/slots/4/history").json()["total"] == 0


def test_validation(client):
    assert client.put("/api/slots/1", json={"name": "   "}).status_code == 422
    assert client.put("/api/slots/1", json={"name": "x" * 65}).status_code == 422
    assert client.put("/api/slots/1", json={"binding": "remote_agent"}).status_code == 422
    assert client.get("/api/slots/11").status_code == 422
    assert client.get("/api/slots/0").status_code == 422


def test_only_one_slot_can_observe_the_local_client(client):
    assert client.put("/api/slots/2", json={"binding": "local_client"}).json()["binding"] == "local_client"
    r = client.put("/api/slots/7", json={"binding": "local_client"})
    assert r.status_code == 409 and "Slot 2" in r.json()["error"]["message"]
    client.put("/api/slots/2", json={"binding": "none"})
    assert client.put("/api/slots/7", json={"binding": "local_client"}).status_code == 200
    types = [h["type"] for h in client.get("/api/slots/2/history").json()["items"]]
    assert "bound" in types and "unbound" in types


def test_compute_status_from_observed_environment():
    env = {"steam": {"installed": True, "process": {"running": False}}, "dota": {"process": {"running": False}}}
    assert compute_status("none", env) == "unbound"
    assert compute_status("local_client", None) == "steam_not_installed"
    assert compute_status("local_client", env) == "steam_stopped"
    env["steam"]["process"]["running"] = True
    assert compute_status("local_client", env) == "steam_running"
    env["dota"]["process"]["running"] = True
    assert compute_status("local_client", env) == "dota_running"


def test_bound_slot_follows_real_processes_and_records_history(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.conftest import make_settings

    steam, _ = make_layout(tmp_path)
    with TestClient(create_app(make_settings(tmp_path, steam_path=steam))) as c:
        lab = c.app.state.lab
        table: dict[int, tuple[str, float]] = {}
        lab.environment.watcher = ProcessWatcher(lister=lambda: [(p, n, ct) for p, (n, ct) in table.items()],
                                                 opener=lambda pid: FakeProc(pid, table[pid][1]))
        asyncio.run(lab.environment.poll())
        c.put("/api/slots/1", json={"binding": "local_client"})
        assert c.get("/api/slots/1").json()["status"] == "steam_stopped"

        table[10] = ("steam.exe", time.time())
        asyncio.run(lab.environment.poll())
        s = c.get("/api/slots/1").json()
        assert s["status"] == "steam_running" and s["observed"]["steam_pid"] == 10
        table[20] = ("dota2.exe", time.time())
        asyncio.run(lab.environment.poll())
        assert c.get("/api/slots/1").json()["status"] == "dota_running"
        assert c.get("/api/slots/2").json()["status"] == "unbound"

        hist = [h for h in c.get("/api/slots/1/history").json()["items"] if h["type"] == "status_changed"]
        assert [h["data"]["to"] for h in hist][:2] == ["dota_running", "steam_running"]
