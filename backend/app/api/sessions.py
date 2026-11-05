from __future__ import annotations

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.api.deps import DB, PageQ, PageSizeQ, State
from app.db.models import MatchEvent, MatchSession, Player, PlayerStatistics
from app.domain import SessionStatus
from app.errors import NotFoundError
from app.schemas import (
    EventOut,
    Page,
    ParticipantOut,
    PlayerStatsOut,
    SessionCreate,
    SessionDetail,
    SessionOut,
    SpeedUpdate,
)
from app.services import analytics

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _get(db, session_id: int) -> MatchSession:
    s = db.get(MatchSession, session_id)
    if s is None:
        raise NotFoundError(f"session {session_id} not found")
    return s


def _detail(db, s: MatchSession, state) -> SessionDetail:
    names = {p.id: p.name for p in db.scalars(select(Player))}
    parts = [ParticipantOut.model_validate(p).model_copy(update={"player_name": names.get(p.player_id)})
             for p in s.participants]
    base = SessionOut.model_validate(s).model_dump()
    return SessionDetail(**base, participants=parts, live=state.manager.live_snapshot(s.id))


@router.get("", response_model=Page[SessionOut])
def list_sessions(db: DB, page: PageQ = 1, page_size: PageSizeQ = 25,
                  status_filter: SessionStatus | None = Query(None, alias="status")):
    q = select(MatchSession)
    cq = select(func.count()).select_from(MatchSession)
    if status_filter:
        q = q.where(MatchSession.status == status_filter.value)
        cq = cq.where(MatchSession.status == status_filter.value)
    total = db.scalar(cq) or 0
    items = db.scalars(q.order_by(MatchSession.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=[SessionOut.model_validate(s) for s in items], total=total, page=page, page_size=page_size)


@router.post("", response_model=SessionDetail, status_code=status.HTTP_201_CREATED)
def create_session(data: SessionCreate, db: DB, state: State):
    s = state.manager.create_session(db, data)
    return _detail(db, s, state)


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: int, db: DB, state: State):
    return _detail(db, _get(db, session_id), state)


@router.post("/{session_id}/start", response_model=SessionOut)
async def start_session(session_id: int, state: State):
    return await state.manager.start(session_id)


@router.post("/{session_id}/pause", response_model=SessionOut)
async def pause_session(session_id: int, state: State):
    return await state.manager.pause(session_id)


@router.post("/{session_id}/resume", response_model=SessionOut)
async def resume_session(session_id: int, state: State):
    return await state.manager.resume(session_id)


@router.post("/{session_id}/stop", response_model=SessionOut)
async def stop_session(session_id: int, state: State):
    return await state.manager.stop(session_id)


@router.post("/{session_id}/speed", response_model=SessionOut)
async def set_speed(session_id: int, data: SpeedUpdate, state: State):
    return await state.manager.set_speed(session_id, data.speed)


@router.get("/{session_id}/statistics")
def session_statistics(session_id: int, db: DB, state: State) -> dict:
    s = _get(db, session_id)
    live = state.manager.live_snapshot(session_id)
    if live is not None:
        rows = analytics.live_player_stats(live)
        source = "live"
    else:
        names = {p.id: p.name for p in db.scalars(select(Player))}
        stats = db.scalars(select(PlayerStatistics).where(PlayerStatistics.session_id == session_id)
                           .order_by(PlayerStatistics.team.desc(), PlayerStatistics.player_id)).all()
        rows = []
        for st in stats:
            d = PlayerStatsOut.model_validate(st).model_dump()
            d["player_name"] = names.get(st.player_id)
            d["kda"] = analytics.kda(st.kills, st.deaths, st.assists)
            rows.append(d)
        source = "stored" if rows else "none"
    teams = {}
    for team in ("radiant", "dire"):
        tr = [r for r in rows if r["team"] == team]
        teams[team] = {
            "kills": sum(r["kills"] for r in tr), "deaths": sum(r["deaths"] for r in tr),
            "assists": sum(r["assists"] for r in tr), "net_worth": sum(r["net_worth"] for r in tr),
            "tower_damage": sum(r["tower_damage"] for r in tr), "hero_damage": sum(r["hero_damage"] for r in tr),
        }
    return {
        "session_id": session_id, "status": s.status, "source": source,
        "game_time": live["time"] if live else s.duration_seconds,
        "winner": s.winner, "players": rows, "teams": teams,
        "timeline": analytics.timeline(db, session_id)["points"] if live is None else [],
    }


@router.get("/{session_id}/events", response_model=Page[EventOut])
def session_events(session_id: int, db: DB, page: PageQ = 1, page_size: PageSizeQ = 100,
                   event_type: str | None = Query(None, max_length=32)):
    _get(db, session_id)
    q = select(MatchEvent).where(MatchEvent.session_id == session_id)
    cq = select(func.count()).select_from(MatchEvent).where(MatchEvent.session_id == session_id)
    if event_type:
        q = q.where(MatchEvent.event_type == event_type)
        cq = cq.where(MatchEvent.event_type == event_type)
    total = db.scalar(cq) or 0
    items = db.scalars(q.order_by(MatchEvent.game_time, MatchEvent.id).offset((page - 1) * page_size)
                       .limit(page_size)).all()
    return Page(items=[EventOut.model_validate(e) for e in items], total=total, page=page, page_size=page_size)


@router.get("/{session_id}/timeline")
def session_timeline(session_id: int, db: DB) -> dict:
    _get(db, session_id)
    return analytics.timeline(db, session_id)
