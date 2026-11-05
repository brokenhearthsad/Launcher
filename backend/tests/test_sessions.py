from __future__ import annotations

from tests.conftest import make_settings, wait_for

FAST = {"speed": 1000, "max_game_seconds": 600, "seed": 7}


def _create(client, **kw):
    body = {"name": "t", **FAST, **kw}
    r = client.post("/api/sessions", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _status(client, sid):
    return client.get(f"/api/sessions/{sid}").json()["status"]


def test_create_session_assigns_ten_participants(client):
    s = _create(client)
    assert s["status"] == "created" and s["environment"] == "mock" and s["seed"] == 7
    parts = s["participants"]
    assert len(parts) == 10
    assert sum(p["team"] == "radiant" for p in parts) == 5
    assert all(p["ai_profile"]["bot_difficulty"] for p in parts)


def test_random_seed_assigned(client):
    r = client.post("/api/sessions", json={"name": "x"})
    assert r.json()["seed"] > 0


def test_lineup_validation(client):
    players = client.get("/api/players").json()
    nine = [{"player_id": p["id"]} for p in players[:9]]
    r = client.post("/api/sessions", json={"participants": nine})
    assert r.status_code == 422 and "exactly 10" in r.json()["error"]["message"]
    dup = [{"player_id": p["id"], "hero": "axe"} for p in players[:2]] + [{"player_id": p["id"]} for p in players[2:]]
    r = client.post("/api/sessions", json={"participants": dup})
    assert r.status_code == 422 and "hero" in r.json()["error"]["message"]
    twice = [{"player_id": players[0]["id"]}] * 10
    assert client.post("/api/sessions", json={"participants": twice}).status_code == 422


def test_offline_players_are_excluded(client):
    pid = client.get("/api/players").json()[0]["id"]
    client.put(f"/api/players/{pid}", json={"status": "offline"})
    r = client.post("/api/sessions", json={"name": "x"})
    assert r.status_code == 422  # only 9 available


def test_custom_assignment_swaps_teams(client):
    players = client.get("/api/players").json()
    parts = []
    for p in players:
        team = {"radiant": "dire", "dire": "radiant"}[p["team"]]
        parts.append({"player_id": p["id"], "team": team})
    s = _create(client, participants=parts)
    by_id = {p["player_id"]: p for p in s["participants"]}
    assert by_id[players[0]["id"]]["team"] != players[0]["team"]


def test_full_lifecycle_pause_resume_finish(client):
    s = _create(client, speed=50, max_game_seconds=900)
    sid = s["id"]
    assert client.post(f"/api/sessions/{sid}/start").json()["status"] == "running"
    assert client.post(f"/api/sessions/{sid}/start").status_code == 409
    players = client.get("/api/players").json()
    assert {p["status"] for p in players} == {"running"}
    wait_for(lambda: (client.get(f"/api/sessions/{sid}").json()["live"] or {}).get("time", 0) > 5)
    assert client.post(f"/api/sessions/{sid}/pause").json()["status"] == "paused"
    assert client.post(f"/api/sessions/{sid}/pause").status_code == 409
    assert {p["status"] for p in client.get("/api/players").json()} == {"paused"}
    t1 = client.get(f"/api/sessions/{sid}").json()["live"]["time"]
    import time
    time.sleep(0.5)
    t2 = client.get(f"/api/sessions/{sid}").json()["live"]["time"]
    assert t1 == t2, "game time must not advance while paused"
    assert client.post(f"/api/sessions/{sid}/resume").json()["status"] == "running"
    assert client.post(f"/api/sessions/{sid}/speed", json={"speed": 1000}).json()["speed"] == 1000
    wait_for(lambda: _status(client, sid) == "finished", timeout=90)
    s = client.get(f"/api/sessions/{sid}").json()
    assert s["win_condition"] in ("ancient_destroyed", "time_limit")
    assert s["duration_seconds"] > 0 and s["events_count"] > 0 and s["finished_at"]
    assert {p["status"] for p in client.get("/api/players").json()} == {"finished"}


def test_stop_running_session(client):
    sid = _create(client, speed=20)["id"]
    client.post(f"/api/sessions/{sid}/start")
    wait_for(lambda: (client.get(f"/api/sessions/{sid}").json()["live"] or {}).get("time", 0) > 2)
    r = client.post(f"/api/sessions/{sid}/stop")
    assert r.status_code == 200 and r.json()["status"] == "stopped"
    s = client.get(f"/api/sessions/{sid}").json()
    assert s["winner"] is None and s["win_condition"] == "stopped"
    stats = client.get(f"/api/sessions/{sid}/statistics").json()
    assert stats["source"] == "stored" and len(stats["players"]) == 10
    assert client.post(f"/api/sessions/{sid}/stop").status_code == 409


def test_stop_created_session(client):
    sid = _create(client)["id"]
    assert client.post(f"/api/sessions/{sid}/stop").json()["status"] == "stopped"
    assert client.post(f"/api/sessions/{sid}/start").status_code == 409


def test_players_cannot_join_two_active_sessions(client):
    a = _create(client, speed=5)["id"]
    b = _create(client, speed=5)["id"]
    client.post(f"/api/sessions/{a}/start")
    r = client.post(f"/api/sessions/{b}/start")
    assert r.status_code == 409
    client.post(f"/api/sessions/{a}/stop")


def test_locked_fields_while_running(client):
    sid = _create(client, speed=5)["id"]
    client.post(f"/api/sessions/{sid}/start")
    pid = client.get("/api/players").json()[0]["id"]
    assert client.put(f"/api/players/{pid}", json={"hero": "luna"}).status_code == 409
    assert client.put(f"/api/players/{pid}", json={"aggression": 0.2}).status_code == 200
    client.post(f"/api/sessions/{sid}/stop")


def test_dota_test_environment_reports_not_supported(client):
    sid = _create(client, environment="dota_test")["id"]
    r = client.post(f"/api/sessions/{sid}/start")
    assert r.status_code == 501
    body = r.json()["error"]
    assert body["code"] == "not_supported" and body["details"]["notes"]
    assert _status(client, sid) == "created"


def test_unknown_session(client):
    assert client.get("/api/sessions/999").status_code == 404
    assert client.post("/api/sessions/999/start").status_code == 404
    assert client.post("/api/sessions/999/pause").status_code == 409


def test_sessions_pagination(client):
    for _ in range(3):
        _create(client)
    page = client.get("/api/sessions", params={"page": 1, "page_size": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert client.get("/api/sessions", params={"page_size": 500}).status_code == 422


def test_capacity_limit(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(make_settings(tmp_path, max_concurrent_sessions=1))
    with TestClient(app) as c:
        a = c.post("/api/sessions", json={"speed": 2}).json()["id"]
        c.post(f"/api/sessions/{a}/start")
        # second lineup with fresh players is impossible (only 10 exist), so capacity triggers first
        b = c.post("/api/sessions", json={"speed": 2}).json()["id"]
        r = c.post(f"/api/sessions/{b}/start")
        assert r.status_code == 429 and r.json()["error"]["code"] == "capacity_exceeded"
        c.post(f"/api/sessions/{a}/stop")


def test_rate_limit(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(make_settings(tmp_path, api_rate_limit_per_minute=10))
    with TestClient(app) as c:
        codes = [c.get("/api/players").status_code for _ in range(12)]
        assert codes[:10] == [200] * 10 and codes[-1] == 429
        assert c.get("/api/health").status_code == 200  # exempt
