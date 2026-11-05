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

Перед любой незавершённой миграцией существующей БД создаётся копия через SQLite backup API;
при ошибке база восстанавливается из неё. Откат 0002 не поддерживается — используйте копию
или ветку `archive/v1-simulator`.

## Нагрузка

- Один цикл без активного ожидания; чтения psutil/NVML/файлов — в рабочем потоке.
- Полный перебор процессов только пока Steam или Dota 2 не найдены; найденные проверяются по PID.
- В БД пишется одна строка метрик в минуту; хранится `metrics_retention_days` (14) дней.
- Рассылка метрик по WebSocket — только когда открыта страница Launcher.
