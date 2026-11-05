# Testing

| Suite | Location | Command | Count |
|-------|----------|---------|-------|
| Backend (pytest) | `backend/tests` | `cd backend && .venv\Scripts\python -m pytest` | 81 |
| Lint (ruff) | backend | `.venv\Scripts\ruff check app tests` | — |
| Frontend unit (Vitest + Testing Library) | `frontend/src/test` | `cd frontend && npm test` | 25 |
| Type check | frontend | `npm run typecheck` | — |
| End-to-end (Playwright) | `frontend/e2e` | `npm run e2e` | 3 |

## Backend coverage

* `test_api_players.py` — health, meta, 10 seeded players in 2 teams, edit/validation/create/delete.
* `test_sessions.py` — lineup validation, offline players, custom assignment, full lifecycle
  (start → pause (time frozen) → resume → speed → finish), stop, conflicts, locked fields,
  `dota_test` → 501, pagination, capacity limit, rate limit.
* `test_history_logs_settings.py` — history, events, timeline, log filters, settings roundtrip & effect, DB maintenance.
* `test_websocket.py` — hello/ping, streamed lifecycle events, throttling, drop-oldest queue.
* `test_analytics.py` — formulas, live stats, aggregates on explicit fixtures, empty-data behaviour, CSV/JSON export.
* `test_database.py` — schema/indexes/FKs from migrations, cascades, unique constraints, UTC datetimes, idempotent seed.
* `test_ai.py` — Lane, Farming, Combat, Economy, Item AI, Decision Engine, BotBrain cycle, Team AI.
* `test_simulator.py` — engine invariants, determinism, full match with farming/items/fights/towers,
  role differences, modes, scenarios, settings → behaviour, adapter pause/stop/validation, fog of war, DotaTestAdapter.
* `test_integration.py` — **main criterion**: create session → assign 10 → start → WebSocket events →
  natural finish without intervention → statistics consistency → persisted events/stats/snapshots → history/overview/export.

## Frontend

* Component tests (badges, slider, dialogs, helpers), navigation through all nine pages, Dashboard
  rendering & error state, Match Control (create with 10 participants, team counters, stop confirmation,
  pause, unavailable environment), WebSocket provider (dispatch, pong, reconnect with back-off).
* Playwright (`npm run e2e`) starts backend (with `data/e2e.db`) and Vite automatically, or reuses running
  servers (`E2E_NO_SERVERS=1`). Scenarios: dashboard/players, persisting bot settings, full match through the
  UI (create → start → live → pause/resume → finish → history details).
  If Playwright browsers are missing: `npx playwright install chromium`.

## Manual check

1. `start.bat`, open http://localhost:5173 → Dashboard shows *Online*, 10 participants.
2. Players: 5 Radiant + 5 Dire cards; edit one and save.
3. Bot Configuration: move a slider, save, reload → value persists.
4. Match Control: *Create session* → *Start* → *Live*: clock runs, heroes move on the map, events appear.
5. Pause → clock stops; Resume; set speed x1000; match finishes with a winner.
6. Match History → Details: 10 rows; Analytics shows charts; export CSV.
7. Logs shows `session N started/finished` entries.
