# Архитектура

Целевая архитектура и этапы — [PROJECT_AUDIT.md](PROJECT_AUDIT.md). Здесь — то, что реализовано.

```
Chrome ──► http://localhost:8000 ──► один процесс python.exe (python -m app)
                                      ├─ uvicorn (без reload, log_config=None)
                                      ├─ FastAPI
                                      │   ├─ /api/health, /api/system/{process,shutdown}
                                      │   ├─ /api/logs, /api/settings, /ws/events
                                      │   └─ /*  → frontend/dist (SPA fallback на index.html)
                                      ├─ MonitorService: один цикл asyncio, задачи с интервалами
                                      │   ├─ metrics: psutil · NVML/nvidia-smi · LibreHardwareMonitor (опц.)
                                      │   └─ environment: процессы steam.exe/dota2.exe + файлы/реестр Steam
                                      ├─ SlotService (10 логических слотов, статус из наблюдения)
                                      ├─ GsiService: POST /gsi ◄── Dota 2 (тот же процесс и порт, только 127.0.0.1)
                                      │   parser → tracker (свежесть, фазы) → журнал events → gsi_matches (1 строка/матч)
                                      ├─ GsiInstaller: план → подтверждение → копия → запись cfg
                                      ├─ EventBus (потокобезопасный; ограниченные очереди, drop-oldest)
                                      ├─ JSON-логи → stdout, logs/app.jsonl, таблица system_logs (фоновый поток)
                                      └─ SQLite (WAL) + Alembic; копия перед миграцией
```

## Модули backend (`backend/app`)

| Путь | Назначение |
|------|-----------|
| `__main__.py` | production-запуск: uvicorn в процессе, ссылка на сервер для корректной остановки |
| `main.py` | фабрика приложения: логи, БД, миграции с копией, middleware, обработчики ошибок, раздача интерфейса |
| `config.py` | настройки `DML_*` |
| `db/session.py` | engine, сессии, `run_migrations()` с резервной копией и откатом |
| `db/models.py` | `SystemLog`, `AppSetting` (доменные таблицы добавляются на следующих этапах) |
| `api/frontend.py` | раздача `frontend/dist`, защита от выхода за пределы папки |
| `api/system.py` | ресурсы процесса Launcher; `shutdown` (заголовок `X-Launcher-Request`, только loopback) |
| `monitoring/system.py` | CPU (общая, по ядрам, частота), ОЗУ, диски, I/O, сеть (psutil, без подпроцессов) |
| `monitoring/gpu.py` | NVIDIA: NVML; запасной `nvidia-smi` не чаще раза в 5 с |
| `monitoring/lhm.py` | температура CPU из LibreHardwareMonitor (только loopback-адрес) |
| `monitoring/store.py` | кольцевой буфер в памяти + агрегаты за минуту → `resource_samples` |
| `monitoring/service.py` | адаптивный планировщик: 2 с при открытой странице, 15 с без неё |
| `integrations/vdf.py`, `integrations/steam.py` | разбор VDF/ACF, поиск Steam, библиотек и Dota 2 |
| `integrations/processes.py` | слежение за steam.exe / dota2.exe по PID + времени создания |
| `services/environment.py`, `services/events.py`, `services/slots.py` | состояние окружения, журнал событий, слоты |
| `integrations/gsi/parser.py` | терпимый разбор GSI: поля необязательны, неверные типы → «нет данных» + запись о проблеме; SteamID/имя не сохраняются |
| `integrations/gsi/tracker.py` | машина состояний: свежесть (fresh / delayed / stale) и события жизненного цикла |
| `integrations/gsi/heroes.py` | отображаемые имена героев из `npc_dota_hero_*` |
| `services/gsi.py` | приём `POST /gsi`: loopback, токен (hmac.compare_digest), лимит 512 КБ, журнал, агрегирование матчей, троттлинг WS |
| `services/gsi_installer.py` | проверка/план/установка/удаление/восстановление `gamestate_integration_launcher.cfg` |
| `platform/process_info.py` | RAM/CPU/потоки своего процесса (psutil); опциональное понижение **своего** приоритета |
| `logging_config.py`, `services/event_bus.py`, `services/settings_service.py`, `api/ws.py`, `api/logs.py`, `api/settings.py`, `api/ratelimit.py` | сохранённая инфраструктура |

## Безопасность локального сервера

- Слушает только `127.0.0.1`.
- `TrustedHostMiddleware`: принимаются только `Host: localhost` / `127.0.0.1` (защита от DNS rebinding).
- Остановка требует нестандартный заголовок → сторонний сайт не может вызвать её из браузера (CORS preflight).
- Секреты не хранятся; Steam-учётные данные не используются.

## Миграции

| Ревизия | Содержание |
|---------|-----------|
| 0001 | исходная схема (версия с симулятором) |
| 0002 | удаление таблиц симулятора; `system_logs` и `app_settings` сохраняются |
| 0003 | `client_slots` (+ 10 слотов), `events`, `resource_samples` |
| 0004 | `gsi_matches` — агрегированная история матчей по данным GSI |

Перед любой незавершённой миграцией существующей БД создаётся копия через SQLite backup API;
при ошибке база восстанавливается из неё. Откат 0002 не поддерживается — используйте копию
или ветку `archive/v1-simulator`.

## Нагрузка

- Один цикл без активного ожидания; чтения psutil/NVML/файлов — в рабочем потоке.
- Полный перебор процессов только пока Steam или Dota 2 не найдены; найденные проверяются по PID.
- В БД пишется одна строка метрик в минуту; хранится `metrics_retention_days` (14) дней.
- Рассылка метрик по WebSocket — только когда открыта страница Launcher.

## GSI: поток данных и защита

- Dota 2 → `POST http://127.0.0.1:8000/gsi` (throttle 0,5 с, heartbeat 30 с из cfg). Обработка — `json.loads`
  и несколько сравнений в event loop (< 1 мс); запись в БД — в рабочем потоке, только при событиях и раз в 30 с.
- Принимаются только loopback-клиенты и только пакеты с токеном этой установки; ответ игре не содержит команд.
- Устаревание: watchdog (каждые 5 с) — без обновлений дольше `gsi_stale_seconds` (40 с, больше heartbeat 30 с)
  данные скрываются, статус «Нет данных», событие `stale` (один раз).
- Журнал: `connected`, `first_state`, `game_started`, `phase_changed`, `game_ended`, `stale`, `format_error`
  (не чаще раза в минуту, с подсчётом пропущенных), `config_installed/removed/restored`.
- История: одна строка `gsi_matches` на матч; незавершённые при перезапуске помечаются `interrupted`;
  хранится `gsi_retention_days` (90) дней.
- Установщик пишет только свой файл; изменения — после предпросмотра (`plan_id` = хеш текущего + нового
  содержимого) и `confirm=true`, с заголовком `X-Launcher-Request`; перед заменой/удалением/восстановлением — копия.
