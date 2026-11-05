from __future__ import annotations

from tests.conftest import wait_for


def _finished_session(client, seed=3):
    sid = client.post("/api/sessions", json={"speed": 1000, "max_game_seconds": 600, "seed": seed}).json()["id"]
    client.post(f"/api/sessions/{sid}/start")
    wait_for(lambda: client.get(f"/api/sessions/{sid}").json()["status"] == "finished", timeout=90)
    return sid


def test_history_and_events(client):
    sid = _finished_session(client)
    hist = client.get("/api/matches/history").json()
    assert hist["total"] == 1
    item = hist["items"][0]
    assert item["id"] == sid and item["events_count"] > 0 and item["duration_seconds"] >= 600 - 1
    ev = client.get(f"/api/sessions/{sid}/events", params={"page_size": 10}).json()
    assert ev["total"] == item["events_count"] and len(ev["items"]) == 10
    kills = client.get(f"/api/sessions/{sid}/events", params={"event_type": "hero_killed"}).json()
    assert all(e["event_type"] == "hero_killed" for e in kills["items"])
    assert client.get("/api/matches/history", params={"winner": "nobody"}).status_code == 422
    tl = client.get(f"/api/sessions/{sid}/timeline").json()
    assert len(tl["points"]) >= 10 and "net_worth_diff" in tl["points"][0]


def test_logs_filtering(client):
    client.post("/api/sessions", json={"name": "logged"})
    import time
    time.sleep(0.4)  # db log writer is asynchronous
    from app.logging_config import get_db_handler
    get_db_handler().flush()
    logs = client.get("/api/logs").json()
    assert logs["total"] > 0
    comps = client.get("/api/logs/components").json()
    assert "session" in comps
    only = client.get("/api/logs", params={"component": "session"}).json()["items"]
    assert only and all(r["component"] == "session" for r in only)
    found = client.get("/api/logs", params={"search": "logged"}).json()["items"]
    assert found
    assert client.get("/api/logs", params={"level": "ERROR"}).json()["total"] == 0


def test_settings_roundtrip(client):
    s = client.get("/api/settings").json()
    assert s["runtime"]["ws_publish_hz"] > 0 and s["database"]["dialect"] == "sqlite"
    r = client.put("/api/settings", json={"default_speed": 77, "log_level": "DEBUG"})
    assert r.status_code == 200 and r.json()["default_speed"] == 77
    assert client.get("/api/settings").json()["runtime"]["default_speed"] == 77
    # new sessions use the new default speed
    assert client.post("/api/sessions", json={}).json()["speed"] == 77
    assert client.put("/api/settings", json={"log_level": "LOUD"}).status_code == 422
    import logging
    assert logging.getLogger("dml").level == logging.DEBUG
    client.put("/api/settings", json={"log_level": "INFO"})


def test_database_maintenance(client):
    assert "size_after" in client.post("/api/settings/database/vacuum").json()
    assert client.post("/api/settings/database/purge-logs", json={"older_than_days": 0}).status_code == 200
