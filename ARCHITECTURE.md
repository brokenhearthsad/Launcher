# Architecture

```
 Browser (React, :5173)                          Backend process (FastAPI, :8000)
 ┌──────────────────────┐   REST /api/*   ┌──────────────────────────────────────────────────┐
 │ pages ─ api/client   │ ──────────────▶ │ api/* routers ─▶ services (players, sessions,    │
 │ LiveEventsProvider   │ ◀── WS /ws ──── │                 analytics, settings)             │
 └──────────────────────┘   events        │   │                    │                         │
                                          │   ▼                    ▼                         │
                                          │ SessionManager ── asyncio task per session        │
                                          │   └─ MatchController (to_thread batches)          │
                                          │        ├─ 10 × BotBrain (utility AI)              │
                                          │        ├─ 2 × TeamAI                              │
                                          │        └─ GameAdapter ─▶ MockGameAdapter ─▶ Engine│
                                          │                       └▶ DotaTestAdapter (n/a)    │
                                          │ EventBus (throttled WS fan-out)                   │
                                          │ SQLAlchemy ─▶ SQLite (WAL) ◀─ Alembic migrations │
                                          │ JSON logging ─▶ stdout, logs/app.jsonl, system_logs│
                                          └──────────────────────────────────────────────────┘
```

## Backend modules (`backend/app`)

| Path | Responsibility |
|------|----------------|
| `main.py` | App factory: logging, DB engine, migrations, seeding, recovery, middleware, error handlers |
| `config.py` | Environment configuration (`DML_*`) |
| `domain.py` | Enumerations shared by every layer |
| `db/models.py` | ORM models: Player, MatchSession, MatchParticipant, PlayerStatistics, StatSnapshot, MatchEvent, SystemLog, AppSetting |
| `db/session.py`, `alembic/` | Engine, sessions, migrations |
| `db/seed.py` | Ten default participants |
| `api/*` | HTTP/WebSocket routers (thin; no business logic) |
| `services/player_service.py` | Player Manager: CRUD, locking during active sessions |
| `services/session_manager.py` | Match Manager: lifecycle, background runner, throttled publishing, persistence, crash recovery |
| `services/analytics.py` | Analytics Engine: live stats, aggregates, timelines, CSV/JSON export |
| `services/event_bus.py` | Bounded per-client queues for WebSocket fan-out |
| `game/catalog.py` | Heroes, abilities, items, builds, XP table (simplified test model) |
| `game/simulator/` | Map geometry, entities, deterministic engine |
| `game/adapters/` | `GameAdapter` interface, `MockGameAdapter`, `DotaTestAdapter`, registry |
| `game/match.py` | `MatchController`: ties adapter, bots and team AIs together (no I/O) |
| `ai/` | Bot AI subsystems (see BOT_AI.md) |

Rules followed: game logic does not know about HTTP/DB; the UI only displays values computed by
the backend (KDA, GPM, aggregates are computed once, in `services/analytics.py`).

## Session lifecycle

`created → running ⇄ paused → finished | stopped | error`

* **start**: validates the lineup (10 participants, 5 per team, unique heroes, no offline players,
  nobody already in an active session), checks the adapter is available and the concurrency limit,
  snapshots each bot's AI profile into `match_participants.ai_profile`, sets players to *running*.
* **runner loop** (asyncio task, 20 Hz scheduler): accumulates `speed × wall-time` of game time and runs
  that many engine ticks (≤120 per batch) in a worker thread; publishes a snapshot at `ws_publish_hz`;
  flushes events and live stats to SQLite every 2 s.
* **finish**: natural end (ancient destroyed or time limit) → `finished` with winner; operator stop →
  `stopped`, no winner, partial stats kept. Exceptions → `error` with message; other sessions unaffected.
* **shutdown**: active sessions are stopped gracefully. If the process is killed, the next start marks
  them `error` ("interrupted") and resets participant statuses.

## Simulator

* 100×100 map, three lanes (polylines), 11 towers + ancient per team, 10 neutral camps, Roshan, wards, fog of war.
* Fixed time step (`tick_seconds`, default 0.5 s of game time); wall-clock independent, so speed is a
  pure scheduling parameter (x1 … x1000).
* One `random.Random(seed)` for the engine, one derived RNG per bot; deterministic iteration order;
  team processing order alternates each tick to avoid first-mover bias. Same seed + config ⇒ same match.
* Scenarios: `balanced`, `radiant_advantage` / `dire_advantage` (gold ×1.25, XP ×1.2, damage ×1.1 for one
  team), `aggressive` / `defensive` (personality offsets). Modes: `standard`, `turbo` (×2 gold/XP, shorter
  respawn, weaker towers), `mid_only`.
* Win: ancient destroyed, or at the time limit by surviving structures → net worth → kills (`time_limit`).

## Performance

* Single backend process; ten bots are objects inside one task. A full 40–50 minute match takes
  ~5–8 s of CPU at maximum speed.
* UI updates are throttled (default 4 Hz) independent of tick rate; slow WebSocket clients drop oldest
  messages instead of blocking the simulator.
* Concurrency limit (`max_concurrent_sessions`, default 2), REST rate limit (default 240 req/min/client).
* Polling pages pause while the browser tab is hidden.

## Adding a game adapter

1. Implement `app.game.adapters.base.GameAdapter` (all abstract methods). `get_player_state` must return a
   fog-of-war filtered `Perception`; `advance()` either steps a simulation or waits for the real game.
2. Provide an `AdapterInfo` (`available`, `is_simulation`, capabilities, notes).
3. Register it in `app/game/adapters/registry.py` and add the name to `domain.Environment`.
4. Raise `AdapterNotSupportedError(operation, reason)` for anything the environment cannot do — the API
   turns it into HTTP 501 with the reason.
5. Add tests mirroring `tests/test_simulator.py`. Do not advertise support until verified end-to-end.

## Dota 2 integration research

Status: **not implemented**. Findings that shaped the `DotaTestAdapter` boundary:

| Interface | What it allows | Limitation for this project |
|-----------|----------------|-----------------------------|
| Bot Scripting API (Lua `scripts/vscripts/bots`) | Custom bots in local lobbies / practice | Sandboxed, no network/file I/O → cannot be driven by this backend in real time |
| Game State Integration (GSI) | Client POSTs JSON state to a local HTTP endpoint | Read-only; no commands |
| Workshop Tools custom game (server Lua vscripts) | Custom game logic in a local lobby; can make HTTP requests | Candidate bridge (game polls backend for actions). Requires an addon and manual verification |
| Console commands in local lobby (`dota_bot_populate`, `host_timescale`, cheats) | Local testing utilities | Not a control API |

Out of scope by design: public matchmaking, ranked play, input injection, memory reading, anti-cheat or
detection evasion, MMR manipulation.

## Technical risks and open items

| Risk | Mitigation / status |
|------|---------------------|
| No official external control API for real Dota 2 bots | Adapter abstraction; simulator first; integration remains research |
| Simulator realism (economy numbers lower than real games, simplified abilities/items) | Documented as a test model; tunable constants in `catalog.py` / `engine.py` |
| CPU-bound simulation inside an async server | Batched `asyncio.to_thread`, bounded batch size, throttled publishing |
| SQLite write contention | WAL mode, batched flushes every 2 s, background log writer |
| `.bat` scripts were authored for Windows but could not be executed in the Linux CI/dev container used to build this project | Manual commands documented; please report issues |
| Kill via `stop.bat` is forceful | Startup recovery marks interrupted sessions; use the UI *Stop* first for clean results |
