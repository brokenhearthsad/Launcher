# API reference

Base URL `http://127.0.0.1:8000`. Interactive docs: `/docs` (Swagger), `/redoc`.
Errors use one shape: `{"error": {"code": "...", "message": "...", "details": ...}}`.

| Code | Meaning |
|------|---------|
| 400/422 | validation error (`validation_error`, `validation_failed`) |
| 404 | `not_found` |
| 409 | `conflict` (wrong state, duplicate, locked) |
| 429 | `rate_limited` or `capacity_exceeded` (too many concurrent sessions) |
| 501 | `not_supported` (e.g. `dota_test` environment) |

## System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | status, version, DB check, active sessions, WS clients, uptime |
| GET | `/api/meta` | enums, environments (with availability), heroes, items |

## Players
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/players?team=radiant\|dire` | list |
| POST | `/api/players` | create (`name, team, role, hero, slot, status(ready/offline), bot_difficulty, aggression…`) → 201 |
| GET | `/api/players/{id}` | one |
| PUT/PATCH | `/api/players/{id}` | partial update; team/role/hero/slot/status locked (409) while in an active session |
| DELETE | `/api/players/{id}` | 204; 409 while in an active session |

AI parameters are floats in `[0, 1]`; `bot_difficulty ∈ easy|medium|hard|expert`.

## Sessions
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/sessions?page=&page_size=&status=` | paginated list |
| POST | `/api/sessions` | create: `name, environment(mock\|dota_test), scenario, game_mode, seed?, speed? (1–1000), max_game_seconds? (300–7200), participants?[]` → 201 |
| GET | `/api/sessions/{id}` | detail + participants + `live` snapshot while active |
| POST | `/api/sessions/{id}/start` | start (409 wrong state/busy players, 429 capacity, 501 unavailable env) |
| POST | `/api/sessions/{id}/pause` · `/resume` | pause / resume |
| POST | `/api/sessions/{id}/stop` | stop (active → `stopped`, keeps partial stats; created → `stopped`) |
| POST | `/api/sessions/{id}/speed` | `{"speed": 1–1000}` while active |
| GET | `/api/sessions/{id}/statistics` | per-player rows + team totals; `source = live\|stored\|none`; stored timeline |
| GET | `/api/sessions/{id}/events?page=&page_size=&event_type=` | persisted match events |
| GET | `/api/sessions/{id}/timeline` | per-minute snapshots (team net worth/XP, per player NW/LH) |

`participants` omitted = all non-offline players with their configured team/hero/role. Each item:
`{player_id, team?, hero?, role?}`.

## History, analytics, logs, settings
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/matches/history?page=&page_size=&winner=radiant\|dire\|none&scenario=&status=` | finished/stopped/error sessions |
| GET | `/api/analytics/overview` | counts, wins, avg duration, errors, last match |
| GET | `/api/analytics/players` | per-participant aggregates |
| GET | `/api/analytics/teams` | per-team aggregates |
| GET | `/api/analytics/sessions` | per-session summary (durations, team kills/NW) |
| GET | `/api/analytics/export?format=csv\|json` | download per-player rows |
| GET | `/api/logs?page=&page_size=&level=&component=&search=&since=` | system logs (repeat `level`) |
| GET | `/api/logs/components` | distinct components |
| GET/PUT | `/api/settings` | runtime settings (PUT partial) + backend/DB info |
| POST | `/api/settings/database/vacuum` | VACUUM SQLite |
| POST | `/api/settings/database/purge-logs` | `{"older_than_days": n}` |

Analytics filters (players/teams/sessions/export): `session_id` (repeatable), `team`, `player_id`,
`scenario`, `include_stopped`. Only `finished` sessions are included by default. Empty data yields
`null`/empty results, never placeholder numbers.

## WebSocket `/ws/events`

Server → client messages: `{"type", "session_id", "data", "ts"}`.

| type | data |
|------|------|
| `hello` | `{active_sessions}` on connect |
| `session_created` / `session_started` / `session_paused` / `session_resumed` | `{id, ...}` |
| `session_finished` | `{id, status, winner, win_condition, duration}` |
| `player_updated` | `{player_ids, status? , action?}` |
| `statistics_updated` | full live snapshot: time, score, net_worth, heroes, towers, creeps, roshan, wards, directives, statistics |
| `match_event` | `{events: [{type, time, player_id, data}]}` (kills, towers, Roshan, levels, purchases…) |
| `bot_action` | `{actions: [{player_id, time, action, source, score, ok, reason}]}` — latest per bot since last publish |
| `system_error` | `{component, message}` |
| `ping` | keep-alive every 20 s when idle; clients may send `{"type":"ping"}` and receive `pong` |

Publication rate is `ws_publish_hz` (default 4/s) regardless of simulation speed.
