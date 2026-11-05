from __future__ import annotations

import csv
import io
import json

from app.db.models import MatchSession, PlayerStatistics
from app.db.session import session_scope
from app.services import analytics


def test_rates_and_kda():
    assert analytics.per_minute(600, 120) == 300.0
    assert analytics.per_minute(100, 0) == 0.0
    assert analytics.kda(5, 0, 5) == 10.0
    assert analytics.kda(2, 4, 2) == 1.0


def test_live_player_stats_derives_from_snapshot():
    snap = {"time": 300.0, "heroes": [{
        "player_id": 1, "name": "A", "team": "radiant", "hero": "axe", "kills": 2, "deaths": 1, "assists": 3,
        "last_hits": 20, "denies": 2, "gold_earned": 1500, "xp": 2500, "net_worth": 2100, "hero_damage": 900,
        "tower_damage": 100, "healing": 0, "level": 7, "items": ["boots_of_speed"]}]}
    row = analytics.live_player_stats(snap)[0]
    assert row["gpm"] == 300.0 and row["xpm"] == 500.0 and row["kda"] == 5.0


def _seed(client):
    """Insert two explicit finished matches (test fixtures, not simulated data)."""
    players = client.get("/api/players").json()
    with session_scope() as db:
        for sid, winner, dur in ((1001, "radiant", 1800.0), (1002, "dire", 2400.0)):
            db.add(MatchSession(id=sid, name=f"m{sid}", status="finished", winner=winner, duration_seconds=dur,
                                seed=sid, radiant_score=10, dire_score=8))
            for i, p in enumerate(players):
                db.add(PlayerStatistics(session_id=sid, player_id=p["id"], team=p["team"], hero=p["hero"],
                                        kills=i, deaths=1, assists=2, gpm=400 + i, xpm=500, net_worth=10000 + i,
                                        tower_damage=100 * i, hero_damage=1000, is_final=1))
    return players


def test_aggregates(client):
    players = _seed(client)
    teams = {t["team"]: t for t in client.get("/api/analytics/teams").json()}
    assert teams["radiant"]["matches"] == 2 and teams["radiant"]["wins"] == 1 and teams["radiant"]["win_rate"] == 0.5
    # radiant players have indices 0..4 => kills 0+1+2+3+4 = 10 per match
    assert teams["radiant"]["avg_kills"] == 10
    pl = client.get("/api/analytics/players", params={"player_id": players[1]["id"]}).json()
    assert len(pl) == 1 and pl[0]["matches"] == 2 and pl[0]["avg_kills"] == 1 and pl[0]["kda"] == 3.0
    only_radiant = client.get("/api/analytics/players", params={"team": "radiant"}).json()
    assert {r["team"] for r in only_radiant} == {"radiant"}
    sessions = client.get("/api/analytics/sessions", params=[("session_id", 1002)]).json()
    assert len(sessions) == 1 and sessions[0]["duration_minutes"] == 40.0 and sessions[0]["winner"] == "dire"
    ov = client.get("/api/analytics/overview").json()
    assert ov["matches"]["finished"] == 2 and ov["matches"]["avg_duration_seconds"] == 2100.0
    assert ov["matches"]["radiant_wins"] == 1 and ov["matches"]["dire_wins"] == 1


def test_empty_aggregates_have_no_invented_values(client):
    teams = client.get("/api/analytics/teams").json()
    assert all(t["matches"] == 0 and t["win_rate"] is None for t in teams)
    assert client.get("/api/analytics/players").json() == []
    ov = client.get("/api/analytics/overview").json()
    assert ov["matches"]["avg_duration_seconds"] is None and ov["last_match"] is None


def test_export_csv_and_json(client):
    _seed(client)
    r = client.get("/api/analytics/export", params={"format": "csv"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 20 and rows[0]["session_id"] == "1001"
    r = client.get("/api/analytics/export", params={"format": "json", "team": "dire"})
    data = json.loads(r.text)
    assert data["count"] == 10 and all(x["team"] == "dire" for x in data["rows"])
    assert client.get("/api/analytics/export", params={"format": "xml"}).status_code == 422
