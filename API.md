# API (PHASE 1)

База: `http://localhost:8000`. Интерактивно: `/docs`. Ошибки: `{"error": {"code", "message", "details?"}}`.

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/health` | статус, версия, БД, клиенты WS, uptime, собран ли интерфейс |
| GET | `/api/system/process` | RAM (`rss_mb`, `private_mb`), CPU % (доля всей машины), потоки, дочерние процессы Launcher |
| POST | `/api/system/shutdown` | корректная остановка; нужен заголовок `X-Launcher-Request: 1`, только с локального адреса → 202 |
| GET | `/api/logs?page=&page_size=&level=&component=&search=&since=` | логи (повторяемый `level`) |
| GET | `/api/logs/components` | список компонентов |
| GET / PUT | `/api/settings` | `runtime` (ws_publish_hz, ui_refresh_seconds, log_level, db_log_level) + сведения о сервере и БД (путь, размер, папка копий, последняя копия) |
| POST | `/api/settings/database/vacuum` | сжатие SQLite |
| POST | `/api/settings/database/purge-logs` | `{"older_than_days": n}` |
| WS | `/ws/events` | `hello`, `settings_updated`, `system_error`, `shutdown`, `ping`/`pong` |
| GET | `/*` | интерфейс из `frontend/dist` |

Коды: 403 `forbidden`, 404 `not_found`, 409 `conflict`, 422 `validation_error`, 429 `rate_limited`,
400 — недопустимый заголовок `Host`.
