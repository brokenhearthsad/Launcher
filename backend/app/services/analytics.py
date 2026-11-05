"""Analytics Engine.

All derived metrics are computed here, from recorded data only:
* live statistics from the simulator snapshot (``live_player_stats``);
* aggregates across stored sessions (players, teams, sessions, timelines);
* CSV/JSON export.

If a metric has no underlying data (e.g. no finished matches), it is returned
as ``None`` / empty instead of a placeholder value.
"""
from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import MatchEvent, MatchSession, Player, PlayerStatistics, StatSnapshot, SystemLog
from app.domain import SessionStatus


def per_minute(total: float, seconds: float) -> float:
    """Rate per game minute; 0 for an empty duration."""
    if seconds <= 0:
        return 0.0
    return round(total / (seconds / 60.0), 1)


def kda(kills: int, deaths: int, assists: int) -> float:
    return round((kills + assists) / max(1, deaths), 2)


def _avg(values: list[float]) -> float | None:
    return round(mean(values), 2) if values else None


# --------------------------------------------------------------------------- live
def live_player_stats(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    t = float(snapshot.get("time", 0.0))
    rows = []
    for h in snapshot.get("heroes", []):
        rows.append({
            "player_id": h["player_id"], "player_name": h["name"], "team": h["team"], "hero": h["hero"],
            "kills": h["kills"], "deaths": h["deaths"], "assists": h["assists"],
            "last_hits": h["last_hits"], "denies": h["denies"],
            "gpm": per_minute(h["gold_earned"], t), "xpm": per_minute(h["xp"], t),
            "net_worth": h["net_worth"], "hero_damage": h["hero_damage"], "tower_damage": h["tower_damage"],
            "healing": h["healing"], "level": h["level"], "items": list(h["items"]),
            "kda": kda(h["kills"], h["deaths"], h["assists"]),
        })
    return rows


# --------------------------------------------------------------------------- filters
@dataclass
class Filters:
    session_ids: list[int] | None = None
    team: str | None = None
    player_id: int | None = None
    scenario: str | None = None
    include_stopped: bool = False

    def statuses(self) -> tuple[str, ...]:
        if self.include_stopped:
            return (SessionStatus.FINISHED.value, SessionStatus.STOPPED.value)
        return (SessionStatus.FINISHED.value,)


def _sessions(db: Session, f: Filters) -> list[MatchSession]:
    q = select(MatchSession).where(MatchSession.status.in_(f.statuses()))
    if f.session_ids:
        q = q.where(MatchSession.id.in_(f.session_ids))
    if f.scenario:
        q = q.where(MatchSession.scenario == f.scenario)
    return list(db.scalars(q.order_by(MatchSession.id)))


def _stat_rows(db: Session, f: Filters) -> list[tuple[PlayerStatistics, MatchSession, Player]]:
    q = (select(PlayerStatistics, MatchSession, Player)
         .join(MatchSession, PlayerStatistics.session_id == MatchSession.id)
         .join(Player, PlayerStatistics.player_id == Player.id)
         .where(MatchSession.status.in_(f.statuses())))
    if f.session_ids:
        q = q.where(MatchSession.id.in_(f.session_ids))
    if f.team:
        q = q.where(PlayerStatistics.team == f.team)
    if f.player_id:
        q = q.where(PlayerStatistics.player_id == f.player_id)
    if f.scenario:
        q = q.where(MatchSession.scenario == f.scenario)
    return [tuple(r) for r in db.execute(q.order_by(MatchSession.id, Player.id)).all()]  # type: ignore[misc]


# --------------------------------------------------------------------------- overview
def overview(db: Session, active_ids: list[int]) -> dict[str, Any]:
    players = list(db.scalars(select(Player)))
    status_counts = dict(db.execute(select(MatchSession.status, func.count()).group_by(MatchSession.status)).all())
    finished = list(db.scalars(select(MatchSession).where(MatchSession.status == SessionStatus.FINISHED.value)))
    last = db.scalars(select(MatchSession).where(MatchSession.status.in_(
        (SessionStatus.FINISHED.value, SessionStatus.STOPPED.value, SessionStatus.ERROR.value)))
        .order_by(MatchSession.finished_at.desc().nullslast(), MatchSession.id.desc()).limit(1)).first()
    errors = db.scalar(select(func.count()).select_from(SystemLog).where(SystemLog.level.in_(("ERROR", "CRITICAL"))))
    durations = [s.duration_seconds for s in finished if s.duration_seconds]
    wins = defaultdict(int)
    for s in finished:
        wins[s.winner or "none"] += 1
    return {
        "players": {
            "total": len(players),
            "by_team": {t: sum(1 for p in players if p.team == t) for t in ("radiant", "dire")},
            "by_status": {st: sum(1 for p in players if p.status == st) for st in sorted({p.status for p in players})},
        },
        "sessions": {
            "total": sum(status_counts.values()),
            "by_status": status_counts,
            "active": len(active_ids),
            "active_ids": active_ids,
        },
        "matches": {
            "finished": len(finished),
            "radiant_wins": wins.get("radiant", 0),
            "dire_wins": wins.get("dire", 0),
            "no_winner": wins.get("none", 0),
            "avg_duration_seconds": _avg(durations),
            "avg_total_kills": _avg([s.radiant_score + s.dire_score for s in finished]),
        },
        "last_match": None if last is None else {
            "id": last.id, "name": last.name, "status": last.status, "winner": last.winner,
            "win_condition": last.win_condition, "duration_seconds": last.duration_seconds,
            "radiant_score": last.radiant_score, "dire_score": last.dire_score, "finished_at": last.finished_at,
        },
        "errors": errors or 0,
        "events_total": db.scalar(select(func.count()).select_from(MatchEvent)) or 0,
    }


# --------------------------------------------------------------------------- aggregates
def player_summary(db: Session, f: Filters) -> list[dict[str, Any]]:
    grouped: dict[int, list[tuple[PlayerStatistics, MatchSession, Player]]] = defaultdict(list)
    for row in _stat_rows(db, f):
        grouped[row[0].player_id].append(row)
    out = []
    for pid, rows in grouped.items():
        stats = [r[0] for r in rows]
        player = rows[0][2]
        wins = sum(1 for st, s, _ in rows if s.winner == st.team)
        k, d, a = (sum(x.kills for x in stats), sum(x.deaths for x in stats), sum(x.assists for x in stats))
        out.append({
            "player_id": pid, "player_name": player.name, "team": player.team, "role": player.role,
            "matches": len(rows), "wins": wins, "win_rate": round(wins / len(rows), 3),
            "avg_kills": _avg([x.kills for x in stats]), "avg_deaths": _avg([x.deaths for x in stats]),
            "avg_assists": _avg([x.assists for x in stats]), "kda": kda(k, d, a),
            "avg_gpm": _avg([x.gpm for x in stats]), "avg_xpm": _avg([x.xpm for x in stats]),
            "avg_net_worth": _avg([x.net_worth for x in stats]),
            "avg_last_hits": _avg([x.last_hits for x in stats]),
            "avg_hero_damage": _avg([x.hero_damage for x in stats]),
            "avg_tower_damage": _avg([x.tower_damage for x in stats]),
        })
    return sorted(out, key=lambda r: (r["team"] != "radiant", r["player_id"]))


def team_summary(db: Session, f: Filters) -> list[dict[str, Any]]:
    per_team_session: dict[str, dict[int, list[PlayerStatistics]]] = defaultdict(lambda: defaultdict(list))
    sessions: dict[int, MatchSession] = {}
    for st, s, _p in _stat_rows(db, Filters(f.session_ids, f.team, None, f.scenario, f.include_stopped)):
        per_team_session[st.team][s.id].append(st)
        sessions[s.id] = s
    out = []
    for team in ("radiant", "dire"):
        by_session = per_team_session.get(team, {})
        if not by_session:
            out.append({"team": team, "matches": 0, "wins": 0, "win_rate": None, "avg_kills": None,
                        "avg_deaths": None, "avg_net_worth": None, "avg_gpm": None, "avg_xpm": None,
                        "avg_tower_damage": None, "avg_hero_damage": None})
            continue
        wins = sum(1 for sid in by_session if sessions[sid].winner == team)
        out.append({
            "team": team, "matches": len(by_session), "wins": wins, "win_rate": round(wins / len(by_session), 3),
            "avg_kills": _avg([sum(x.kills for x in v) for v in by_session.values()]),
            "avg_deaths": _avg([sum(x.deaths for x in v) for v in by_session.values()]),
            "avg_net_worth": _avg([sum(x.net_worth for x in v) for v in by_session.values()]),
            "avg_gpm": _avg([mean(x.gpm for x in v) for v in by_session.values()]),
            "avg_xpm": _avg([mean(x.xpm for x in v) for v in by_session.values()]),
            "avg_tower_damage": _avg([sum(x.tower_damage for x in v) for v in by_session.values()]),
            "avg_hero_damage": _avg([sum(x.hero_damage for x in v) for v in by_session.values()]),
        })
    return out


def session_summary(db: Session, f: Filters) -> list[dict[str, Any]]:
    rows = _stat_rows(db, f)
    per: dict[int, dict[str, Any]] = {}
    for st, s, _p in rows:
        d = per.setdefault(s.id, {
            "session_id": s.id, "name": s.name, "scenario": s.scenario, "winner": s.winner,
            "duration_minutes": round((s.duration_seconds or 0) / 60, 1),
            "radiant_kills": 0, "dire_kills": 0, "radiant_net_worth": 0, "dire_net_worth": 0,
            "radiant_tower_damage": 0, "dire_tower_damage": 0, "kills": 0, "deaths": 0, "assists": 0,
            "_gpm": [], "_xpm": [],
        })
        d[f"{st.team}_kills"] += st.kills
        d[f"{st.team}_net_worth"] += st.net_worth
        d[f"{st.team}_tower_damage"] += st.tower_damage
        d["kills"] += st.kills
        d["deaths"] += st.deaths
        d["assists"] += st.assists
        d["_gpm"].append(st.gpm)
        d["_xpm"].append(st.xpm)
    out = []
    for d in per.values():
        d["avg_gpm"] = _avg(d.pop("_gpm"))
        d["avg_xpm"] = _avg(d.pop("_xpm"))
        out.append(d)
    return sorted(out, key=lambda r: r["session_id"])


def timeline(db: Session, session_id: int) -> dict[str, Any]:
    snaps = list(db.scalars(select(StatSnapshot).where(StatSnapshot.session_id == session_id)
                            .order_by(StatSnapshot.game_time, StatSnapshot.player_id)))
    teams = {pid: team for pid, team in db.execute(
        select(PlayerStatistics.player_id, PlayerStatistics.team).where(PlayerStatistics.session_id == session_id))}
    names = {p.id: p.name for p in db.scalars(select(Player))}
    points: dict[float, dict[str, Any]] = {}
    for sn in snaps:
        pt = points.setdefault(sn.game_time, {"minute": round(sn.game_time / 60, 1), "radiant_net_worth": 0,
                                              "dire_net_worth": 0, "radiant_xp": 0, "dire_xp": 0})
        team = teams.get(sn.player_id)
        if team:
            pt[f"{team}_net_worth"] += sn.net_worth
            pt[f"{team}_xp"] += sn.xp
        pt[f"nw_{sn.player_id}"] = sn.net_worth
        pt[f"lh_{sn.player_id}"] = sn.last_hits
    series = sorted(points.values(), key=lambda p: p["minute"])
    for pt in series:
        pt["net_worth_diff"] = pt["radiant_net_worth"] - pt["dire_net_worth"]
    return {"session_id": session_id, "points": series,
            "players": [{"player_id": pid, "name": names.get(pid, str(pid)), "team": t} for pid, t in teams.items()]}


# --------------------------------------------------------------------------- export
EXPORT_FIELDS = ["session_id", "session_name", "scenario", "game_mode", "seed", "winner", "duration_seconds",
                 "player_id", "player_name", "team", "hero", "kills", "deaths", "assists", "last_hits", "denies",
                 "gpm", "xpm", "net_worth", "hero_damage", "tower_damage", "healing", "level", "items", "won"]


def export_rows(db: Session, f: Filters) -> list[dict[str, Any]]:
    out = []
    for st, s, p in _stat_rows(db, f):
        out.append({
            "session_id": s.id, "session_name": s.name, "scenario": s.scenario, "game_mode": s.game_mode,
            "seed": s.seed, "winner": s.winner, "duration_seconds": s.duration_seconds,
            "player_id": p.id, "player_name": p.name, "team": st.team, "hero": st.hero,
            "kills": st.kills, "deaths": st.deaths, "assists": st.assists, "last_hits": st.last_hits,
            "denies": st.denies, "gpm": st.gpm, "xpm": st.xpm, "net_worth": st.net_worth,
            "hero_damage": st.hero_damage, "tower_damage": st.tower_damage, "healing": st.healing,
            "level": st.level, "items": "|".join(st.items or []), "won": s.winner == st.team,
        })
    return out


def to_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=EXPORT_FIELDS)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def to_json(rows: list[dict[str, Any]]) -> str:
    return json.dumps({"rows": rows, "count": len(rows)}, ensure_ascii=False, default=str, indent=2)


__all__ = ["Filters", "per_minute", "kda", "live_player_stats", "overview",
           "player_summary", "team_summary", "session_summary", "timeline", "export_rows", "to_csv", "to_json"]
