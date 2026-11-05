# API (PHASE 3)

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
| GET | `/api/monitoring/current` | снимок: cpu, memory, disks, disk_io, network, gpu, cpu_temp, `interval_seconds`, `mode` |
| GET | `/api/monitoring/recent?seconds=` | точки из памяти (до 1 ч) |
| GET | `/api/monitoring/history?hours=` | агрегаты за минуту из SQLite |
| GET | `/api/environment` | Steam (установка, библиотеки, вход да/нет, процесс), Dota 2 (папка, сборка, состояние, процесс) |
| POST | `/api/environment/refresh` | перечитать файлы и процессы сейчас (ничего не запускает) |
| GET | `/api/events?source=&type=&slot_id=&page=` | журнал событий |
| GET | `/api/slots`, `/api/slots/{1..10}` | слоты со статусом |
| PUT | `/api/slots/{id}` | `{name?, note?, binding?: none\|local_client}`; второй `local_client` → 409 |
| GET | `/api/slots/{id}/history` | история слота |
| POST | `/gsi` | приём Dota 2 GSI: только loopback, токен в `auth.token`; 200 / 400 (JSON) / 401 (токен) / 403 (не локально) / 413 (> 512 КБ) |
| GET | `/api/gsi/state` | `status` (waiting/live/delayed/stale), `freshness`, `last_update`, `age_seconds`, счётчики, `snapshot` (или null), текущий `match` |
| GET | `/api/gsi/matches?result=&page=` | агрегированная история матчей |
| GET | `/api/gsi/config` | проверка установки + `plan` (действие, текущий/новый текст с маской токена, `plan_id`), `launch_option`, `backups` |
| POST | `/api/gsi/install` | `{plan_id, confirm: true}` + заголовок `X-Launcher-Request: 1`; 409 если файл изменился после предпросмотра |
| POST | `/api/gsi/uninstall` | `{confirm: true}` + заголовок; только файл Launcher; создаёт копию |
| GET | `/api/gsi/backups` | резервные копии cfg |
| POST | `/api/gsi/restore` | `{name, confirm: true}` + заголовок; текущий файл сначала копируется |
| WS | `/ws/events` | `gsi_updated` (не чаще `ws_publish_hz`, последнее обновление доставляется всегда), `hello`, `metrics_updated`, `environment_updated`, `slot_updated`, `event_created`, `settings_updated`, `system_error`, `shutdown`, `ping`/`pong` |
| GET | `/*` | интерфейс из `frontend/dist` |

Коды: 403 `forbidden`, 404 `not_found`, 409 `conflict`, 422 `validation_error`, 429 `rate_limited`,
400 — недопустимый заголовок `Host`.

Недоступный показатель передаётся как `null` (у GPU и температуры CPU — `available: false` и `reason`).
`503 monitoring_disabled` — если мониторинг выключен (`DML_MONITORING_ENABLED=false`).

Поля снимка GSI, которых нет в текущем контексте игры (меню, выбор героя, наблюдатель), равны `null`.
SteamID, account id и имя игрока из пакета не сохраняются и не возвращаются.
