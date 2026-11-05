from __future__ import annotations


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["database"] == "ok"


def test_meta_lists_catalog_and_environments(client):
    body = client.get("/api/meta").json()
    assert len(body["heroes"]) >= 20
    envs = {e["name"]: e for e in body["environments"]}
    assert envs["mock"]["available"] is True and envs["mock"]["is_simulation"] is True
    assert envs["dota_test"]["available"] is False


def test_ten_players_seeded_in_two_teams(client):
    players = client.get("/api/players").json()
    assert len(players) == 10
    radiant = [p for p in players if p["team"] == "radiant"]
    dire = [p for p in players if p["team"] == "dire"]
    assert [p["name"] for p in radiant] == [f"Radiant {i}" for i in range(1, 6)]
    assert [p["name"] for p in dire] == [f"Dire {i}" for i in range(1, 6)]
    assert {p["role"] for p in radiant} == {"carry", "mid", "offlane", "soft_support", "hard_support"}
    assert all(p["status"] == "ready" for p in players)
    # every bot has its own personality
    assert len({(p["aggression"], p["farming_priority"], p["team_coordination"]) for p in players}) > 5


def test_filter_by_team(client):
    assert len(client.get("/api/players", params={"team": "dire"}).json()) == 5


def test_update_ai_settings_persist(client):
    pid = client.get("/api/players").json()[0]["id"]
    r = client.put(f"/api/players/{pid}", json={"aggression": 0.9, "bot_difficulty": "expert", "hero": "sven"})
    assert r.status_code == 200
    got = client.get(f"/api/players/{pid}").json()
    assert got["aggression"] == 0.9 and got["bot_difficulty"] == "expert" and got["hero"] == "sven"


def test_update_validation(client):
    pid = client.get("/api/players").json()[0]["id"]
    assert client.put(f"/api/players/{pid}", json={"aggression": 1.5}).status_code == 422
    assert client.put(f"/api/players/{pid}", json={"hero": "not_a_hero"}).status_code == 422
    assert client.put(f"/api/players/{pid}", json={"status": "running"}).status_code == 422
    err = client.put(f"/api/players/{pid}", json={"role": "wizard"}).json()
    assert err["error"]["code"] == "validation_error"


def test_create_and_delete_player(client):
    body = {"name": "Spare", "team": "dire", "role": "mid", "hero": "puck", "status": "offline"}
    r = client.post("/api/players", json=body)
    assert r.status_code == 201
    pid = r.json()["id"]
    assert client.post("/api/players", json=body).status_code == 409  # duplicate name
    assert client.delete(f"/api/players/{pid}").status_code == 204
    assert client.get(f"/api/players/{pid}").status_code == 404


def test_unknown_player_404(client):
    r = client.get("/api/players/9999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
