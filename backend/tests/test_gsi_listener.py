"""POST /gsi intake: auth, locality, validation, lifecycle journal, aggregation, staleness."""
from __future__ import annotations

import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.gsi import GsiRejected
from tests.conftest import make_settings
from tests.test_gsi_parser import load


def post(client, name_or_payload, token=None):
    payload = load(name_or_payload) if isinstance(name_or_payload, str) else name_or_payload
    payload = json.loads(json.dumps(payload))
    payload.setdefault("auth", {})["token"] = token if token is not None else client.app.state.lab.gsi.token
    return client.post("/gsi", content=json.dumps(payload), headers={"Content-Type": "application/json"})


def gsi_events(client):
    items = client.get("/api/events", params={"source": "gsi", "page_size": 100}).json()["items"]
    return [e["type"] for e in reversed(items)]


def test_waiting_before_any_data(client):
    st = client.get("/api/gsi/state").json()
    assert st["status"] == "waiting" and st["snapshot"] is None and st["last_update"] is None


def test_valid_payload_updates_state(client):
    assert post(client, "playing").json() == {"ok": True}
    st = client.get("/api/gsi/state").json()
    assert st["status"] == "live" and st["freshness"] == "fresh" and st["age_seconds"] < 5
    snap = st["snapshot"]
    assert snap["hero_name"] == "Anti-Mage" and snap["hero_level"] == 11 and snap["game_state_label"] == "Игра идёт"
    assert snap["radiant_score"] == 7 and len(snap["items"]) == 3


def test_token_is_required_and_never_logged(client, settings):
    real = client.app.state.lab.gsi.token
    assert len(real) >= 24
    assert post(client, "playing", token="TEST-TOKEN").status_code == 401
    bad = load("playing")
    del bad["auth"]
    assert client.post("/gsi", json=bad).status_code == 401
    st = client.get("/api/gsi/state").json()
    assert st["rejected"] == 2 and st["snapshot"] is None
    from app.logging_config import get_db_handler
    get_db_handler().flush()
    logs = json.dumps(client.get("/api/logs", params={"page_size": 200}).json())
    assert real not in logs and "TEST-TOKEN" not in logs
    log_file = (settings.log_dir / "app.jsonl").read_text(encoding="utf-8")
    assert real not in log_file and "TEST-TOKEN" not in log_file


def test_only_local_clients(client):
    gsi = client.app.state.lab.gsi
    with pytest.raises(GsiRejected) as exc:
        asyncio.run(gsi.receive(b"{}", "192.168.1.50"))
    assert exc.value.status == 403


def test_invalid_json_and_size_are_rejected_and_journaled_once(client):
    for _ in range(3):
        assert client.post("/gsi", content=b"{not json", headers={"Content-Type": "application/json"}).status_code == 400
    assert client.post("/gsi", content=b"[1,2]").status_code == 401  # no auth in a list
    big = b'{"auth": {"token": "x"}, "pad": "' + b"a" * (600 * 1024) + b'"}'
    assert client.post("/gsi", content=big).status_code == 413
    assert gsi_events(client).count("format_error") == 1, "format errors are rate-limited in the journal"
    assert client.get("/api/gsi/state").json()["format_errors"] >= 4


def test_malformed_fields_are_dropped_not_invented(client):
    assert post(client, "malformed_types").status_code == 200
    snap = client.get("/api/gsi/state").json()["snapshot"]
    assert snap["hero_name"] == "Zeus" and snap["hero_level"] is None and snap["game_time"] is None
    assert snap["problems"] and "format_error" in gsi_events(client)


def test_full_lifecycle_journal_and_single_aggregated_row(client):
    for name in ("menu", "hero_selection", "playing", "playing", "playing", "post_game", "menu"):
        assert post(client, name).status_code == 200
    assert gsi_events(client) == ["connected", "first_state", "phase_changed", "phase_changed", "game_started",
                                  "phase_changed", "game_ended"]
    matches = client.get("/api/gsi/matches").json()
    assert matches["total"] == 1, "one row per match, not per update"
    m = matches["items"][0]
    assert m["match_id"] == "9000000001" and m["result"] == "win" and m["team"] == "radiant"
    assert m["hero_name"] == "Anti-Mage" and m["max_level"] == 25 and m["kills"] == 9 and m["gpm"] == 690
    assert m["ended_at"] and m["updates"] == 4
    assert client.get("/api/gsi/state").json()["match"] is None
    assert client.get("/api/gsi/matches", params={"result": "nope"}).status_code == 422


def test_staleness_hides_data_and_journals_once(client):
    post(client, "playing")
    gsi = client.app.state.lab.gsi
    gsi.tracker.last_update -= 30
    assert client.get("/api/gsi/state").json()["status"] == "delayed"
    gsi.tracker.last_update -= 100
    asyncio.run(gsi.watchdog())
    asyncio.run(gsi.watchdog())
    st = client.get("/api/gsi/state").json()
    assert st["status"] == "stale" and st["snapshot"] is None and st["freshness"] == "stale"
    assert gsi_events(client).count("stale") == 1
    post(client, "playing")
    assert client.get("/api/gsi/state").json()["status"] == "live"
    assert gsi_events(client).count("connected") == 2


def test_stale_threshold_is_a_setting(client):
    assert client.put("/api/settings", json={"gsi_stale_seconds": 15}).status_code == 200
    post(client, "playing")
    gsi = client.app.state.lab.gsi
    gsi.tracker.last_update -= 20
    asyncio.run(gsi.watchdog())
    assert client.get("/api/gsi/state").json()["status"] == "stale"


def test_gsi_is_not_rate_limited(tmp_path):
    with TestClient(create_app(make_settings(tmp_path, api_rate_limit_per_minute=10))) as c:
        codes = [post(c, "playing").status_code for _ in range(30)]
        assert set(codes) == {200}


def test_websocket_push_is_throttled(client):
    with client.websocket_connect("/ws/events") as ws:
        ws.receive_json()
        t0 = time.monotonic()
        for _ in range(20):
            post(client, "playing")
        n = 0
        client.app.state.lab.bus.publish("system_error", {"end": True})
        while True:
            msg = ws.receive_json()
            if msg["type"] == "system_error":
                break
            n += msg["type"] == "gsi_updated"
        elapsed = time.monotonic() - t0
        assert 1 <= n <= int(elapsed * 4) + 2


def test_token_persists_across_restarts(tmp_path):
    s = make_settings(tmp_path)
    with TestClient(create_app(s)) as c:
        first = c.app.state.lab.gsi.token
    with TestClient(create_app(s)) as c:
        assert c.app.state.lab.gsi.token == first


def test_last_update_is_always_delivered(client):
    """Throttling must not swallow the final state of a burst (trailing publish)."""
    with client.websocket_connect("/ws/events") as ws:
        ws.receive_json()
        for name in ("menu", "hero_selection", "playing"):
            post(client, name)
        last = None
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            msg = ws.receive_json()
            if msg["type"] == "gsi_updated":
                last = msg["data"]
                if last["snapshot"] and last["snapshot"]["hero_name"] == "Anti-Mage":
                    break
        assert last is not None and last["snapshot"]["hero_name"] == "Anti-Mage"


def test_new_match_is_visible_immediately_and_dangling_matches_are_closed(tmp_path):
    s = make_settings(tmp_path)
    with TestClient(create_app(s)) as c:
        post(c, "playing")
        m = c.get("/api/gsi/matches").json()["items"][0]
        assert m["result"] == "in_progress" and m["hero_name"] == "Anti-Mage" and m["game_time"] == 754
    with TestClient(create_app(s)) as c:  # restart during the match
        m = c.get("/api/gsi/matches").json()["items"][0]
        assert m["result"] == "interrupted"
