# Troubleshooting

| Symptom | Fix |
|---------|-----|
| `install.bat`: Python not found / wrong version | Install Python 3.12+ with "Add to PATH"; reopen the terminal; `py -3.12 --version` |
| `install.bat`: Node not found | Install Node.js 20 LTS; reopen the terminal |
| pip SSL / proxy errors | Configure `pip config set global.proxy ...` or your corporate CA, then rerun |
| `start.bat`: "Port 8000/5173 is already in use" | Run `stop.bat`; otherwise `netstat -ano \| findstr :8000` and end that PID |
| Backend did not become healthy | See `.run\backend.err.log`; common causes: locked DB file, bad `backend\.env` value |
| Panel shows "Backend is unreachable" | Backend not running or wrong `VITE_BACKEND_URL` in `frontend\.env`; check http://127.0.0.1:8000/api/health |
| Sidebar shows "Disconnected — retrying" | WebSocket lost; it reconnects automatically with back-off. Check backend is up |
| Start returns "players … already in an active session" | Stop the other session first (each participant can be in one active session) |
| Start returns 429 capacity | Raise *Max concurrent sessions* in Settings or stop a session |
| Start of `dota_test` returns 501 | Expected: the Dota 2 adapter is not implemented. Use the local simulator |
| Session shows `error: interrupted` | The backend was killed while running; start a new session |
| Edit of hero/team rejected (409) | Participant is in a running/paused session; stop it first |
| Analytics empty | Only finished sessions are counted; enable *Include stopped* or finish a match |
| Database corrupted / reset wanted | `stop.bat`, delete `backend\data\match_lab.db*`, start again (migrations + seed run automatically) |
| Too many logs / large DB | Settings → Purge logs, Vacuum database; disable storing ability events |
| Playwright cannot find a browser | `cd frontend && npx playwright install chromium` |

Logs: UI *Logs* page, `backend\logs\app.jsonl` (JSON lines), `.run\*.log` (process output).
