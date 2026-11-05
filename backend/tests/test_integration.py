"""End-to-end: create -> assign 10 -> run -> events -> statistics -> finish -> persisted results.

The match runs to its natural end (ancient destroyed or the 60-minute time
limit) with no manual intervention.
"""
from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select

from app.db.models import MatchEvent, PlayerStatistics, StatSnapshot
from app.db.session import session_scope


def test_full_match_without_manual_intervention(client):
    players = client.get("/api/players").json()
    participants = [{"player_id": p["id"]} for p in players]
    s = client.post("/api/sessions", json={"name": "integration", "seed": 2024, "speed": 1000,
                                           "participants": participants}).json()
    sid = s["id"]
    assert len(s["participants"]) == 10

    received: Counter = Counter()
    kills_seen = 0
    with client.websocket_connect("/ws/events") as ws:
        ws.receive_json()  # hello
        assert client.post(f"/api/sessions/{sid}/start").status_code == 200
        while True:
            msg = ws.receive_json()
            if msg.get("session_id") not in (sid, None):
                continue
            received[msg["type"]] += 1
            if msg["type"] == "match_event":
                kills_seen += sum(1 for e in msg["data"]["events"] if e["type"] == "hero_killed")
            if msg["type"] == "session_finished":
                final = msg["data"]
                break

    assert final["status"] == "finished"
    assert final["win_condition"] in ("ancient_destroyed", "time_limit")
    for t in ("session_started", "statistics_updated", "bot_action", "match_event", "player_updated"):
        assert received[t] > 0, t
    assert kills_seen > 0

    session = client.get(f"/api/sessions/{sid}").json()
    assert session["status"] == "finished" and session["live"] is None
    if session["win_condition"] == "ancient_destroyed":
        assert session["winner"] in ("radiant", "dire")

    stats = client.get(f"/api/sessions/{sid}/statistics").json()
    assert stats["source"] == "stored" and len(stats["players"]) == 10
    rows = stats["players"]
    assert all(r["is_final"] for r in rows)
    # consistency: team kill totals never exceed the opposing team's deaths
    assert stats["teams"]["radiant"]["kills"] <= stats["teams"]["dire"]["deaths"]
    assert stats["teams"]["dire"]["kills"] <= stats["teams"]["radiant"]["deaths"]
    assert session["radiant_score"] == stats["teams"]["dire"]["deaths"]
    assert all(r["gpm"] > 0 and r["xpm"] > 0 and r["net_worth"] > 600 for r in rows)
    minutes = session["duration_seconds"] / 60
    for r in rows:
        # GPM >= passive income share and consistent with recorded net worth bounds
        assert r["gpm"] * minutes >= r["net_worth"] * 0.5

    with session_scope() as db:
        n_events = db.scalar(select(func.count()).select_from(MatchEvent).where(MatchEvent.session_id == sid))
        n_stats = db.scalar(select(func.count()).select_from(PlayerStatistics)
                            .where(PlayerStatistics.session_id == sid))
        n_snaps = db.scalar(select(func.count()).select_from(StatSnapshot).where(StatSnapshot.session_id == sid))
    assert n_events == session["events_count"] > 100
    assert n_stats == 10 and n_snaps >= 10 * int(minutes)

    history = client.get("/api/matches/history").json()
    assert history["items"][0]["id"] == sid
    overview = client.get("/api/analytics/overview").json()
    assert overview["matches"]["finished"] == 1 and overview["last_match"]["id"] == sid
    export = client.get("/api/analytics/export", params={"format": "csv"}).text.strip().splitlines()
    assert len(export) == 11  # header + 10 players
    assert {p["status"] for p in client.get("/api/players").json()} == {"finished"}
