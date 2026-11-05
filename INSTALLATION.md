# Installation

## Requirements

| Tool | Version | Notes |
|------|---------|-------|
| Windows | 10 / 11 | Linux/macOS work with the manual commands below |
| Python | 3.12 or newer | "Add python.exe to PATH" during install; `py` launcher is used if present |
| Node.js | 20 LTS or newer | includes npm |

No Docker, database server or Steam installation is needed. SQLite is embedded.

## Automatic (Windows)

```bat
install.bat
start.bat
```

`install.bat`:
1. checks Python ≥ 3.12 and Node.js;
2. creates `backend\.venv` and installs `backend\requirements-dev.txt`;
3. copies `backend\.env.example` → `backend\.env` and `frontend\.env.example` → `frontend\.env` (if missing);
4. runs `npm install` in `frontend`;
5. applies Alembic migrations, creating `backend\data\match_lab.db`.
   The ten default participants are created on the first backend start.

`start.bat` checks dependencies and free ports (8000, 5173), starts the backend (one process),
waits for `/api/health`, starts the Vite dev server, waits for it and opens http://localhost:5173.
Process IDs and console output go to `.run\`. `stop.bat` stops both process trees.

## Manual commands

Backend:
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```
Migrations run automatically on startup. To run them explicitly: `alembic upgrade head`.

Frontend:
```bash
cd frontend
npm install
npm run dev          # http://localhost:5173, proxies /api and /ws to the backend
npm run build        # production bundle in dist/ (serve with: npm run preview)
```

## Configuration

`backend/.env` (all optional, prefix `DML_`): host/port, `DATABASE_URL`, CORS origins, log levels,
`MAX_CONCURRENT_SESSIONS`, `WS_PUBLISH_HZ`, `API_RATE_LIMIT_PER_MINUTE`, simulator defaults.
Most runtime values can also be changed on the **Settings** page and are stored in the database.

`frontend/.env`: `VITE_BACKEND_URL` — where the dev server proxies API/WebSocket calls.

No secrets are required or stored. Never put Steam credentials into this project.

## Using the lab

- **Add participants**: Players → *Add participant* (name, team, role, hero, status).
- **Configure bots**: Bot Configuration → choose a participant → difficulty + sliders → *Save*
  (optionally "apply to whole team", presets).
- **Create a test session**: Match Control → set scenario, mode, seed, speed, time limit,
  tick the 10 participants (5 per team, unique heroes) → *Create session* → *Start*.
- **Watch**: Live Match (or the *Live* link next to the session).
- **Statistics**: Analytics (filters + export) and Match History → *Details*.
- **Logs**: Logs page (filter by level/component/text) or `backend/logs/app.jsonl`.
