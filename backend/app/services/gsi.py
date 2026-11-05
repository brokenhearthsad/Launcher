"""Receives Dota 2 GSI payloads, keeps the live state, journals lifecycle events
and aggregates one ``gsi_matches`` row per match.

Cost per update: one ``json.loads`` + a few comparisons on the event loop
(well under a millisecond for typical 5-20 KB payloads). Database writes
happen only on lifecycle events and at most every ``MATCH_FLUSH`` seconds,
in a worker thread.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete

from app.db.models import AppSetting, GsiMatch
from app.db.session import session_scope
from app.integrations.gsi.parser import PayloadError, parse
from app.integrations.gsi.tracker import GsiEvent, GsiTracker
from app.logging_config import get_logger
from app.services import events

log = get_logger("gsi")
TOKEN_KEY = "gsi_token"
MAX_BODY = 512 * 1024
MATCH_FLUSH = 30.0
ERROR_EVENT_INTERVAL = 60.0


def load_or_create_token() -> str:
    """Per-installation secret shared with Dota 2 via the GSI cfg. Never logged."""
    with session_scope() as db:
        row = db.get(AppSetting, TOKEN_KEY)
        if row is not None and isinstance(row.value, dict) and row.value.get("token"):
            return str(row.value["token"])
        token = secrets.token_urlsafe(24)
        if row is None:
            db.add(AppSetting(key=TOKEN_KEY, value={"token": token}))
        else:
            row.value = {"token": token}
        return token


def mask(token: str) -> str:
    return "•" * 8 + token[-4:]


class GsiRejected(Exception):
    def __init__(self, status: int, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


class GsiService:
    def __init__(self, state: Any):
        self.state = state
        self.token = load_or_create_token()
        self.tracker = GsiTracker(stale_seconds=state.runtime.gsi_stale_seconds)
        self.match: dict[str, Any] | None = None  # in-memory aggregate of the current match
        self._match_flushed = 0.0
        self._last_publish = 0.0
        self._last_error_event = -ERROR_EVENT_INTERVAL
        self._suppressed_errors = 0
        self._last_reject_log = 0.0
        self._lock = asyncio.Lock()
        self._purge_old()

    # ------------------------------------------------------------------ intake
    async def receive(self, body: bytes, client_host: str) -> None:
        if client_host not in ("127.0.0.1", "::1", "localhost", "testclient"):
            self._reject_log(f"non-local client {client_host}")
            raise GsiRejected(403, "GSI is accepted from this computer only")
        if len(body) > MAX_BODY:
            await self._format_error(f"payload too large ({len(body)} bytes)")
            raise GsiRejected(413, "payload too large")
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError) as exc:
            await self._format_error(f"invalid JSON: {exc.__class__.__name__}")
            raise GsiRejected(400, "invalid JSON") from exc
        auth = payload.get("auth") if isinstance(payload, dict) else None
        token = auth.get("token") if isinstance(auth, dict) else None
        if not isinstance(token, str) or not hmac.compare_digest(token, self.token):
            self.tracker.rejected += 1
            self._reject_log("missing or wrong token")  # the received value is never logged
            raise GsiRejected(401, "invalid token")
        try:
            snap = parse(payload)
        except PayloadError as exc:
            await self._format_error(str(exc))
            raise GsiRejected(400, str(exc)) from exc
        async with self._lock:
            self.tracker.stale_seconds = self.state.runtime.gsi_stale_seconds
            evs = self.tracker.apply(snap, time.monotonic(), time.time())
            if snap.problems:
                await self._format_error("; ".join(snap.problems[:5]), count_only=True)
            await self._handle_events(evs, snap)
            if self.match is not None and time.monotonic() - self._match_flushed > MATCH_FLUSH:
                await asyncio.to_thread(self._flush_match)
            self._publish()

    def _reject_log(self, why: str) -> None:
        if time.monotonic() - self._last_reject_log > ERROR_EVENT_INTERVAL:
            self._last_reject_log = time.monotonic()
            log.warning("GSI request rejected: %s", why)

    async def _format_error(self, detail: str, count_only: bool = False) -> None:
        if not count_only:
            self.tracker.format_errors += 1
        now = time.monotonic()
        if now - self._last_error_event < ERROR_EVENT_INTERVAL:
            self._suppressed_errors += 1
            return
        self._last_error_event = now
        extra = f" (ещё {self._suppressed_errors} за минуту)" if self._suppressed_errors else ""
        self._suppressed_errors = 0
        await asyncio.to_thread(events.record, self.state.bus, "gsi", "format_error",
                                f"Ошибка формата данных GSI: {detail[:300]}{extra}", severity="warning")

    async def _handle_events(self, evs: list[GsiEvent], snap) -> None:
        ended = False
        for ev in evs:
            if ev.type == "game_started":
                await asyncio.to_thread(self._start_match, ev)
            elif ev.type == "game_ended" and self.match is not None:
                if snap.has_map:
                    self._aggregate(snap)  # final scoreboard is in the ending payload
                self._finish_match(ev)
                await asyncio.to_thread(self._flush_match)
                self.match = None
                ended = True
            await asyncio.to_thread(events.record, self.state.bus, "gsi", ev.type, ev.message,
                                    data=ev.data, severity=ev.severity)
        if not ended:
            self._aggregate(snap)

    # ------------------------------------------------------------------ watchdog
    def interval(self) -> float:
        return 5.0

    async def watchdog(self) -> None:
        async with self._lock:
            self.tracker.stale_seconds = self.state.runtime.gsi_stale_seconds
            evs = self.tracker.check_stale(time.monotonic())
            if evs and self.match is not None:
                await asyncio.to_thread(self._flush_match)
            for ev in evs:
                await asyncio.to_thread(events.record, self.state.bus, "gsi", ev.type, ev.message,
                                        severity=ev.severity)
            if evs:
                self._publish(force=True)

    # ------------------------------------------------------------------ match aggregation
    def _start_match(self, ev: GsiEvent) -> None:
        if self.match is not None:  # a new match id without an end: close the previous one
            self.match["result"] = "ended"
            self.match["ended_at"] = datetime.now(timezone.utc)
            self._flush_match()
        now = datetime.now(timezone.utc)
        with session_scope() as db:
            row = GsiMatch(match_id=ev.data.get("match_id"), started_at=now, last_update_at=now,
                           map_name=ev.data.get("map"), hero=ev.data.get("hero"))
            db.add(row)
            db.flush()
            self.match = {"id": row.id, "match_id": row.match_id, "started_at": now, "updates": 0, "result": "in_progress"}
        self._match_flushed = time.monotonic()

    def _aggregate(self, snap) -> None:
        m = self.match
        if m is None:
            return
        m["updates"] += 1
        m["last_update_at"] = datetime.now(timezone.utc)
        for src, dst in (("map_name", "map_name"), ("hero_internal", "hero"), ("hero_name", "hero_name"),
                         ("team", "team"), ("game_time", "game_time"), ("radiant_score", "radiant_score"),
                         ("dire_score", "dire_score"), ("kills", "kills"), ("deaths", "deaths"),
                         ("assists", "assists"), ("last_hits", "last_hits"), ("denies", "denies"),
                         ("gpm", "gpm"), ("xpm", "xpm"), ("win_team", "win_team")):
            value = getattr(snap, src)
            if value is not None:
                m[dst] = value
        if snap.hero_level is not None:
            m["max_level"] = max(m.get("max_level") or 0, snap.hero_level)

    def _finish_match(self, ev: GsiEvent) -> None:
        m = self.match
        assert m is not None
        m["ended_at"] = datetime.now(timezone.utc)
        win = ev.data.get("win_team")
        if win:
            m["win_team"] = win
            m["result"] = ("win" if win == m.get("team") else "loss") if m.get("team") else "ended"
        else:
            m["result"] = "left" if "вышел" in ev.message else "ended"

    def _flush_match(self) -> None:
        m = self.match
        if m is None:
            return
        with session_scope() as db:
            row = db.get(GsiMatch, m["id"])
            if row is not None:
                for k, v in m.items():
                    if k != "id" and hasattr(row, k):
                        setattr(row, k, v)
        self._match_flushed = time.monotonic()

    def _purge_old(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.state.runtime.gsi_retention_days)
        with session_scope() as db:
            db.execute(delete(GsiMatch).where(GsiMatch.started_at < cutoff))

    async def shutdown(self) -> None:
        async with self._lock:
            if self.match is not None:
                await asyncio.to_thread(self._flush_match)

    # ------------------------------------------------------------------ views
    def view(self) -> dict[str, Any]:
        t = self.tracker
        now = time.monotonic()
        freshness = t.freshness(now)
        env = self.state.environment.snapshot() if self.state.environment and self.state.environment.polled_at else None
        dota_running = env["dota"]["process"]["running"] if env else None
        if freshness == "never":
            status = "waiting"
        elif freshness == "stale":
            status = "stale"
        else:
            status = "live" if freshness == "fresh" else "delayed"
        snap = t.snapshot.to_dict() if (t.snapshot is not None and freshness != "stale") else None
        age = None if t.last_update is None else round(now - t.last_update, 1)
        return {
            "status": status, "freshness": freshness, "dota_running": dota_running,
            "last_update": t.last_update_wall, "age_seconds": age,
            "stale_after_seconds": t.stale_seconds, "updates": t.updates, "format_errors": t.format_errors,
            "rejected": t.rejected, "in_match": t.in_match, "snapshot": snap,
            "last_snapshot_time": t.last_update_wall if t.snapshot is not None else None,
            "match": {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in self.match.items()}
            if self.match else None,
        }

    def _publish(self, force: bool = False) -> None:
        if self.state.bus.subscriber_count == 0:
            return
        now = time.monotonic()
        if not force and now - self._last_publish < 1.0 / max(0.1, self.state.runtime.ws_publish_hz):
            return
        self._last_publish = now
        self.state.bus.publish("gsi_updated", self.view())
