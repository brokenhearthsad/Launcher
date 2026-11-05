"""Match Manager: session lifecycle, background runners and result persistence.

One backend process manages every session. Each running session is an
``asyncio`` task that advances the simulator in small batches inside a
worker thread (``asyncio.to_thread``), so the event loop - and therefore the
API and WebSockets - stays responsive. Ten bots are plain objects inside that
task; no extra processes are spawned.

Throttling:
* simulation speed  = game seconds per wall-clock second (``speed``);
* UI publication    = ``ws_publish_hz`` snapshots per second, regardless of
  how many internal ticks happened in between;
* DB persistence    = events and live statistics flushed every 2 seconds.
"""
from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.profile import BotProfile
from app.db.models import MatchEvent, MatchParticipant, MatchSession, Player, PlayerStatistics, StatSnapshot
from app.db.session import session_scope
from app.domain import (
    ACTIVE_SESSION_STATUSES,
    DEFAULT_LANE_FOR_ROLE,
    Difficulty,
    GameMode,
    PlayerStatus,
    Role,
    Scenario,
    SessionStatus,
    Team,
)
from app.errors import CapacityError, ConflictError, NotFoundError, NotSupportedError, ValidationFailed
from app.game.actions import AdapterError
from app.game.adapters.base import MatchSetup
from app.game.adapters.registry import ADAPTERS, create_adapter
from app.game.match import BotActionRecord, MatchController
from app.game.simulator.engine import GameEvent, HeroSetup, MatchConfig
from app.logging_config import get_logger
from app.schemas import RuntimeSettings, SessionCreate
from app.services import analytics
from app.services.event_bus import EventBus

log = get_logger("session")

LOOP_INTERVAL = 0.05  # scheduler resolution (s)
MAX_TICKS_PER_BATCH = 120  # bounds the time spent in one worker-thread call
FLUSH_INTERVAL = 2.0
LIVE_EVENT_TYPES = {
    "first_blood", "hero_killed", "tower_destroyed", "roshan_killed", "roshan_spawned", "aegis_used",
    "level_up", "item_purchased", "teleport", "game_start", "game_end", "item_sold",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Runner:
    session_id: int
    controller: MatchController
    speed: float
    publish_hz: float
    persist_ability_events: bool
    player_ids: list[int]
    task: asyncio.Task | None = None
    paused: bool = False
    resume_event: asyncio.Event = field(default_factory=asyncio.Event)
    stop_requested: bool = False
    snapshot: dict[str, Any] = field(default_factory=dict)
    pending_events: list[GameEvent] = field(default_factory=list)
    live_events: list[dict[str, Any]] = field(default_factory=list)
    latest_actions: dict[int, BotActionRecord] = field(default_factory=dict)
    events_persisted: int = 0
    started_monotonic: float = field(default_factory=time.monotonic)


class SessionManager:
    def __init__(self, bus: EventBus, settings_provider: Callable[[], RuntimeSettings]):
        self.bus = bus
        self.settings_provider = settings_provider
        self.runners: dict[int, Runner] = {}
        self._lock = asyncio.Lock()

    # ================================================================ creation
    def create_session(self, db: Session, data: SessionCreate) -> MatchSession:
        rs = self.settings_provider()
        players = {p.id: p for p in db.scalars(select(Player))}
        if data.participants is None:
            chosen = [(p, Team(p.team), p.hero, Role(p.role)) for p in players.values()
                      if p.status != PlayerStatus.OFFLINE.value]
        else:
            chosen = []
            for item in data.participants:
                p = players.get(item.player_id)
                if p is None:
                    raise NotFoundError(f"player {item.player_id} not found")
                chosen.append((p, item.team or Team(p.team), item.hero or p.hero, item.role or Role(p.role)))
        self._validate_lineup(chosen)
        seed = data.seed if data.seed is not None else random.SystemRandom().randint(1, 2_000_000_000)
        s = MatchSession(
            name=data.name, status=SessionStatus.CREATED.value, environment=data.environment.value,
            map="lab_map_v1", scenario=data.scenario.value, game_mode=data.game_mode.value, seed=seed,
            speed=data.speed or rs.default_speed, max_game_seconds=data.max_game_seconds or rs.max_game_seconds,
        )
        for p, team, hero, role in chosen:
            s.participants.append(MatchParticipant(player_id=p.id, team=team.value, hero=hero, role=role.value,
                                                   ai_profile=_profile_dict(p)))
        db.add(s)
        db.commit()
        db.refresh(s)
        log.info("session %d created: %s (%s, %s, seed %d)", s.id, s.name, s.scenario, s.game_mode, s.seed)
        self.bus.publish("session_created", {"id": s.id, "name": s.name}, s.id)
        return s

    @staticmethod
    def _validate_lineup(chosen: list[tuple[Player, Team, str, Role]]) -> None:
        if len(chosen) != 10:
            raise ValidationFailed(f"a session needs exactly 10 participants, got {len(chosen)}")
        for team in Team:
            n = sum(1 for _, t, _, _ in chosen if t is team)
            if n != 5:
                raise ValidationFailed(f"team {team.value} needs exactly 5 participants, got {n}")
        heroes = [h for _, _, h, _ in chosen]
        dupes = sorted({h for h in heroes if heroes.count(h) > 1})
        if dupes:
            raise ValidationFailed(f"each hero can be picked once per match: {', '.join(dupes)}")
        offline = [p.name for p, _, _, _ in chosen if p.status == PlayerStatus.OFFLINE.value]
        if offline:
            raise ValidationFailed(f"offline players cannot be assigned: {', '.join(offline)}")

    # ================================================================ control
    async def start(self, session_id: int) -> MatchSession:
        async with self._lock:
            rs = self.settings_provider()
            info = await asyncio.to_thread(self._prepare_start, session_id, rs)
            controller, s_speed, player_ids = info
            runner = Runner(session_id, controller, s_speed, rs.ws_publish_hz, rs.persist_ability_events,
                            player_ids)
            runner.resume_event.set()
            try:
                await asyncio.to_thread(controller.start)
            except AdapterError as exc:
                await asyncio.to_thread(self._mark_error, session_id, player_ids, str(exc))
                raise NotSupportedError(str(exc)) from exc
            runner.snapshot = await asyncio.to_thread(self._snapshot, runner)
            self.runners[session_id] = runner
            runner.task = asyncio.create_task(self._run(runner), name=f"session-{session_id}")
        s = await asyncio.to_thread(self._load, session_id)
        log.info("session %d started (speed x%.0f)", session_id, s.speed)
        self.bus.publish("session_started", {"id": session_id, "speed": s.speed}, session_id)
        self._publish_players(player_ids, PlayerStatus.RUNNING)
        return s

    def _prepare_start(self, session_id: int, rs: RuntimeSettings) -> tuple[MatchController, float, list[int]]:
        with session_scope() as db:
            s = db.get(MatchSession, session_id)
            if s is None:
                raise NotFoundError(f"session {session_id} not found")
            if s.status != SessionStatus.CREATED.value:
                raise ConflictError(f"session {session_id} is '{s.status}' and cannot be started")
            env = s.environment
            adapter_cls = ADAPTERS.get(env)
            if adapter_cls is None:
                raise ValidationFailed(f"unknown environment '{env}'")
            if not adapter_cls.info.available:
                log.warning("start refused for session %d: environment '%s' unavailable", session_id, env)
                raise NotSupportedError(
                    f"environment '{env}' is not available: {adapter_cls.info.description}",
                    details={"notes": adapter_cls.info.notes},
                )
            active = sum(1 for r in self.runners.values() if r.task and not r.task.done())
            if active >= rs.max_concurrent_sessions:
                raise CapacityError(f"maximum of {rs.max_concurrent_sessions} concurrent sessions reached")
            ids = [p.player_id for p in s.participants]
            busy = db.scalars(
                select(MatchParticipant.player_id).join(MatchSession)
                .where(MatchSession.status.in_(ACTIVE_SESSION_STATUSES), MatchParticipant.player_id.in_(ids))
            ).all()
            if busy:
                raise ConflictError(f"players {sorted(set(busy))} are already in an active session")
            players = {p.id: p for p in db.scalars(select(Player).where(Player.id.in_(ids)))}
            missing = [i for i in ids if i not in players]
            if missing:
                raise ValidationFailed(f"participants were deleted: {missing}")
            setups, profiles = [], []
            for part in s.participants:
                p = players[part.player_id]
                if p.status == PlayerStatus.OFFLINE.value:
                    raise ValidationFailed(f"player {p.name} is offline")
                part.ai_profile = _profile_dict(p)  # snapshot the AI configuration used for this run
                role = Role(part.role)
                setups.append(HeroSetup(p.id, p.name, Team(part.team), role, part.hero,
                                        DEFAULT_LANE_FOR_ROLE[role]))
                profiles.append(BotProfile(
                    p.id, p.name, role, Difficulty(p.bot_difficulty), p.aggression, p.farming_priority,
                    p.team_coordination, p.risk_tolerance, p.objective_priority,
                ))
            config = MatchConfig(seed=s.seed, scenario=Scenario(s.scenario), mode=GameMode(s.game_mode),
                                 tick=rs.tick_seconds, max_game_seconds=s.max_game_seconds,
                                 snapshot_interval=rs.snapshot_interval)
            controller = MatchController(create_adapter(env), MatchSetup(config, setups), profiles)
            s.status = SessionStatus.RUNNING.value
            s.started_at = utcnow()
            for p in players.values():
                p.status = PlayerStatus.RUNNING.value
            return controller, s.speed, ids

    async def pause(self, session_id: int) -> MatchSession:
        r = self._runner(session_id)
        if r.paused:
            raise ConflictError("session is already paused")
        r.paused = True
        r.resume_event.clear()
        r.controller.adapter.pause()
        await asyncio.to_thread(self._set_status, session_id, SessionStatus.PAUSED, PlayerStatus.PAUSED)
        log.info("session %d paused at %.0fs", session_id, r.controller.adapter.game_time)
        self.bus.publish("session_paused", {"id": session_id, "time": r.controller.adapter.game_time}, session_id)
        self._publish_players(r.player_ids, PlayerStatus.PAUSED)
        return await asyncio.to_thread(self._load, session_id)

    async def resume(self, session_id: int) -> MatchSession:
        r = self._runner(session_id)
        if not r.paused:
            raise ConflictError("session is not paused")
        r.controller.adapter.resume()
        r.paused = False
        r.resume_event.set()
        await asyncio.to_thread(self._set_status, session_id, SessionStatus.RUNNING, PlayerStatus.RUNNING)
        log.info("session %d resumed", session_id)
        self.bus.publish("session_resumed", {"id": session_id}, session_id)
        self._publish_players(r.player_ids, PlayerStatus.RUNNING)
        return await asyncio.to_thread(self._load, session_id)

    async def stop(self, session_id: int, wait: bool = True) -> MatchSession:
        r = self.runners.get(session_id)
        if r is None:
            s = await asyncio.to_thread(self._load, session_id)
            if s.status == SessionStatus.CREATED.value:
                await asyncio.to_thread(self._set_status, session_id, SessionStatus.STOPPED, None)
                return await asyncio.to_thread(self._load, session_id)
            raise ConflictError(f"session {session_id} is not running (status '{s.status}')")
        r.stop_requested = True
        r.resume_event.set()  # wake a paused runner so it can finish
        if wait and r.task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(r.task), timeout=15)
            except TimeoutError:
                log.error("session %d did not stop within 15s", session_id)
        return await asyncio.to_thread(self._load, session_id)

    async def set_speed(self, session_id: int, speed: float) -> MatchSession:
        r = self._runner(session_id)
        r.speed = speed
        await asyncio.to_thread(self._update_speed, session_id, speed)
        log.info("session %d speed set to x%.0f", session_id, speed)
        return await asyncio.to_thread(self._load, session_id)

    def _runner(self, session_id: int) -> Runner:
        r = self.runners.get(session_id)
        if r is None or r.task is None or r.task.done():
            raise ConflictError(f"session {session_id} is not active")
        return r

    # ================================================================ run loop
    async def _run(self, r: Runner) -> None:
        sid = r.session_id
        tick = r.controller.adapter.tick_seconds
        budget = 0.0
        last = time.monotonic()
        next_publish = last
        next_flush = last + FLUSH_INTERVAL
        finished_naturally = False
        try:
            while not r.stop_requested:
                if r.paused:
                    await r.resume_event.wait()
                    last = time.monotonic()
                    continue
                now = time.monotonic()
                budget = min(budget + (now - last) * r.speed, MAX_TICKS_PER_BATCH * tick * 2)
                last = now
                n = min(int(budget // tick), MAX_TICKS_PER_BATCH)
                if n > 0:
                    budget -= n * tick
                    finished_naturally = await asyncio.to_thread(self._advance, r, n)
                if finished_naturally:
                    break
                now = time.monotonic()
                if now >= next_publish:
                    self._publish_live(r)
                    next_publish = now + 1.0 / max(0.1, r.publish_hz)
                if now >= next_flush:
                    await asyncio.to_thread(self._flush, r, False)
                    next_flush = now + FLUSH_INTERVAL
                await asyncio.sleep(LOOP_INTERVAL)
            if not finished_naturally:
                await asyncio.to_thread(self._stop_adapter, r)
            await asyncio.to_thread(self._finalize, r, finished_naturally)
            self._publish_live(r)
            s = await asyncio.to_thread(self._load, sid)
            log.info("session %d %s: winner=%s condition=%s duration=%.0fs", sid, s.status, s.winner,
                     s.win_condition, s.duration_seconds or 0)
            self.bus.publish("session_finished", {"id": sid, "status": s.status, "winner": s.winner,
                                                  "win_condition": s.win_condition,
                                                  "duration": s.duration_seconds}, sid)
            self._publish_players(r.player_ids, PlayerStatus.FINISHED)
        except asyncio.CancelledError:
            await asyncio.to_thread(self._finalize_safe, r)
            raise
        except Exception as exc:  # noqa: BLE001 - isolate failures to this session
            log.exception("session %d crashed", sid)
            await asyncio.to_thread(self._mark_error, sid, r.player_ids, f"{type(exc).__name__}: {exc}")
            self.bus.publish("system_error", {"component": "session", "session_id": sid,
                                              "message": f"session crashed: {exc}"}, sid)
            self._publish_players(r.player_ids, PlayerStatus.ERROR)
        finally:
            self.runners.pop(sid, None)

    def _advance(self, r: Runner, n: int) -> bool:
        """Worker thread: run ``n`` simulation steps and refresh the snapshot."""
        c = r.controller
        finished = False
        for _ in range(n):
            res = c.step()
            r.pending_events.extend(res.events)
            for ev in res.events:
                if ev.type in LIVE_EVENT_TYPES:
                    r.live_events.append(_event_dict(ev))
            for a in res.actions:
                if a.source != "economy" or a.ok:
                    r.latest_actions[a.player_id] = a
            if res.finished:
                finished = True
                break
        r.snapshot = self._snapshot(r)
        return finished

    def _snapshot(self, r: Runner) -> dict[str, Any]:
        snap = r.controller.adapter.get_game_state()
        snap["directives"] = r.controller.team_directives()
        snap["speed"] = r.speed
        snap["paused"] = r.paused
        snap["environment"] = r.controller.adapter.info.name
        snap["is_simulation"] = r.controller.adapter.info.is_simulation
        snap["bots"] = {str(k): v for k, v in r.controller.bot_stats().items()}
        return snap

    def _stop_adapter(self, r: Runner) -> None:
        r.controller.adapter.stop()
        r.pending_events.extend(r.controller.adapter.get_events())
        r.snapshot = self._snapshot(r)

    # ================================================================ publication
    def _publish_live(self, r: Runner) -> None:
        sid = r.session_id
        if r.live_events:
            events, r.live_events = r.live_events[-50:], []
            self.bus.publish("match_event", {"events": events}, sid)
        if r.latest_actions:
            actions = [a.to_dict() for a in r.latest_actions.values()]
            r.latest_actions = {}
            self.bus.publish("bot_action", {"actions": actions}, sid)
        if r.snapshot:
            snap = dict(r.snapshot)
            snap.pop("bots", None)
            snap["statistics"] = analytics.live_player_stats(r.snapshot)
            self.bus.publish("statistics_updated", snap, sid)

    def _publish_players(self, ids: list[int], status: PlayerStatus) -> None:
        self.bus.publish("player_updated", {"player_ids": ids, "status": status.value})

    # ================================================================ persistence
    def _flush(self, r: Runner, final: bool) -> None:
        events, r.pending_events = r.pending_events, []
        rows = [
            MatchEvent(session_id=r.session_id, player_id=ev.player_id, event_type=ev.type,
                       event_data=ev.data, game_time=ev.time)
            for ev in events
            if r.persist_ability_events or ev.type not in ("ability_cast", "item_used")
        ]
        with session_scope() as db:
            if rows:
                db.add_all(rows)
            r.events_persisted += len(rows)
            s = db.get(MatchSession, r.session_id)
            if s is not None:
                s.events_count = r.events_persisted
                score = r.snapshot.get("score", {})
                s.radiant_score = score.get("radiant", 0)
                s.dire_score = score.get("dire", 0)
                s.duration_seconds = r.snapshot.get("time", 0.0)
            self._upsert_stats(db, r, final)

    def _upsert_stats(self, db: Session, r: Runner, final: bool) -> None:
        existing = {st.player_id: st for st in db.scalars(
            select(PlayerStatistics).where(PlayerStatistics.session_id == r.session_id))}
        for row in analytics.live_player_stats(r.snapshot):
            st = existing.get(row["player_id"])
            if st is None:
                st = PlayerStatistics(session_id=r.session_id, player_id=row["player_id"])
                db.add(st)
            for k in ("team", "hero", "kills", "deaths", "assists", "last_hits", "denies", "gpm", "xpm",
                      "net_worth", "hero_damage", "tower_damage", "healing", "level", "items"):
                setattr(st, k, row[k])
            st.is_final = 1 if final else 0

    def _finalize(self, r: Runner, natural: bool) -> None:
        self._flush(r, True)
        outcome = r.controller.adapter.outcome()
        timeline = r.controller.adapter.timeline()
        with session_scope() as db:
            snaps = [StatSnapshot(session_id=r.session_id, player_id=h["player_id"], game_time=point["time"],
                                  gold=h["gold"], net_worth=h["net_worth"], xp=h["xp"], level=h["level"],
                                  kills=h["kills"], deaths=h["deaths"], assists=h["assists"],
                                  last_hits=h["last_hits"], denies=h["denies"])
                     for point in timeline for h in point["heroes"]]
            db.add_all(snaps)
            s = db.get(MatchSession, r.session_id)
            if s is None:
                return
            s.status = (SessionStatus.FINISHED if natural else SessionStatus.STOPPED).value
            s.finished_at = utcnow()
            s.winner = outcome.winner.value if (natural and outcome.winner) else None
            s.win_condition = outcome.win_condition if natural else "stopped"
            s.duration_seconds = round(outcome.duration, 1)
            s.radiant_score = outcome.score.get("radiant", 0)
            s.dire_score = outcome.score.get("dire", 0)
            for p in db.scalars(select(Player).where(Player.id.in_(r.player_ids))):
                p.status = PlayerStatus.FINISHED.value

    def _finalize_safe(self, r: Runner) -> None:
        try:
            self._stop_adapter(r)
            self._finalize(r, False)
        except Exception:  # noqa: BLE001
            log.exception("failed to finalize session %d during shutdown", r.session_id)

    def _mark_error(self, session_id: int, player_ids: list[int], message: str) -> None:
        with session_scope() as db:
            s = db.get(MatchSession, session_id)
            if s is not None:
                s.status = SessionStatus.ERROR.value
                s.error_message = message[:2000]
                s.finished_at = utcnow()
            for p in db.scalars(select(Player).where(Player.id.in_(player_ids))):
                p.status = PlayerStatus.ERROR.value

    def _set_status(self, session_id: int, status: SessionStatus, player_status: PlayerStatus | None) -> None:
        with session_scope() as db:
            s = db.get(MatchSession, session_id)
            if s is None:
                raise NotFoundError(f"session {session_id} not found")
            s.status = status.value
            if status is SessionStatus.STOPPED:
                s.finished_at = utcnow()
                s.win_condition = "stopped"
            if player_status is not None:
                ids = [p.player_id for p in s.participants]
                for p in db.scalars(select(Player).where(Player.id.in_(ids))):
                    p.status = player_status.value

    def _update_speed(self, session_id: int, speed: float) -> None:
        with session_scope() as db:
            s = db.get(MatchSession, session_id)
            if s is not None:
                s.speed = speed

    def _load(self, session_id: int) -> MatchSession:
        with session_scope() as db:
            s = db.get(MatchSession, session_id)
            if s is None:
                raise NotFoundError(f"session {session_id} not found")
            db.expunge(s)
            return s

    # ================================================================ queries
    def live_snapshot(self, session_id: int) -> dict[str, Any] | None:
        r = self.runners.get(session_id)
        return dict(r.snapshot) if r and r.snapshot else None

    def active_ids(self) -> list[int]:
        return [sid for sid, r in self.runners.items() if r.task and not r.task.done()]

    # ================================================================ lifecycle
    def recover(self, db: Session) -> int:
        """Mark sessions left active by a previous process as interrupted."""
        stale = list(db.scalars(select(MatchSession).where(MatchSession.status.in_(ACTIVE_SESSION_STATUSES))))
        for s in stale:
            s.status = SessionStatus.ERROR.value
            s.error_message = "interrupted: the backend was restarted while the session was active"
            s.finished_at = utcnow()
        for p in db.scalars(select(Player).where(Player.status.in_(
                (PlayerStatus.RUNNING.value, PlayerStatus.PAUSED.value)))):
            p.status = PlayerStatus.READY.value
        db.commit()
        if stale:
            log.warning("marked %d interrupted session(s) as error", len(stale))
        return len(stale)

    async def shutdown(self) -> None:
        ids = list(self.runners)
        for sid in ids:
            try:
                await self.stop(sid, wait=True)
            except Exception:  # noqa: BLE001
                log.exception("error while stopping session %d", sid)


def _profile_dict(p: Player) -> dict[str, Any]:
    return {"bot_difficulty": p.bot_difficulty, "aggression": p.aggression, "farming_priority": p.farming_priority,
            "team_coordination": p.team_coordination, "risk_tolerance": p.risk_tolerance,
            "objective_priority": p.objective_priority}


def _event_dict(ev: GameEvent) -> dict[str, Any]:
    return {"type": ev.type, "time": ev.time, "player_id": ev.player_id, "data": ev.data}

