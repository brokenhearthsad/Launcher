# Dota 2 Match Lab

Local platform for testing 5v5 game scenarios with ten AI-controlled participants
(Radiant ×5, Dire ×5), a web dashboard, a FastAPI backend, SQLite storage,
a deterministic match simulator and an analytics engine. Runs on one Windows 10/11 PC.

> **Important:** matches are played in the built-in **local simulator**
> (`environment = "mock"`). They are simplified simulations, not real Dota 2 games.
> No Steam accounts are used. Integration with a real Dota 2 test environment is
> **not implemented** — the `dota_test` adapter only reports why
> (see [ARCHITECTURE.md](ARCHITECTURE.md#dota-2-integration-research)).
> Public matchmaking, ranked games, anti-cheat evasion and similar are out of scope.

## Quick start (Windows)

```bat
install.bat   :: once: venv, pip/npm packages, database
start.bat     :: launches backend + frontend and opens the panel
stop.bat      :: stops both
```

| Component | Address |
|-----------|---------|
| Web panel | http://localhost:5173 |
| Backend | http://127.0.0.1:8000 |
| API docs (Swagger) | http://127.0.0.1:8000/docs |

Requirements: Python 3.12+, Node.js 20+. Details: [INSTALLATION.md](INSTALLATION.md).

## What you can do

1. **Players** — ten seeded participants (`Radiant 1…5`, `Dire 1…5`); edit name, team, role, hero, status; add/delete.
2. **Bot Configuration** — per-bot AI difficulty and five sliders (aggression, farming, coordination, risk, objectives).
   These values are snapshotted into a session at start and drive the utility AI.
3. **Match Control** — create a session (scenario, simulator mode, seed, speed, time limit, participant assignment),
   start / pause / resume / change speed / stop (with confirmation).
4. **Live Match** — score, clock, map, hero states, objectives, Team AI directives, event feed and the last
   decision of every bot, pushed over WebSocket.
5. **Analytics** — GPM/XPM, net worth, K/D/A, tower damage, durations, team comparison, net-worth timeline;
   filters by team/participant/session/scenario; CSV/JSON export.
6. **Match History**, **Logs**, **Settings** (simulator, update rate, logging, DB maintenance).

## Repository layout

```
backend/   FastAPI app, simulator, bot AI, SQLite + Alembic, pytest suite
frontend/  React + TypeScript + Vite + Tailwind + Recharts dashboard, Vitest + Playwright
*.bat      install / start / stop for Windows
*.md       documentation
```

## Documentation

- [INSTALLATION.md](INSTALLATION.md) — install & run, manual (non-.bat) commands
- [ARCHITECTURE.md](ARCHITECTURE.md) — components, data flow, adapters, adding a new adapter, risks
- [API.md](API.md) — REST and WebSocket reference
- [BOT_AI.md](BOT_AI.md) — how the bots think, how settings change behaviour
- [TESTING.md](TESTING.md) — test suites and how to run them
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — common problems
