# Архитектура

Целевая архитектура и этапы — [PROJECT_AUDIT.md](PROJECT_AUDIT.md). Здесь — то, что реализовано.

```
Chrome ──► http://localhost:8000 ──► один процесс python.exe (python -m app)
                                      ├─ uvicorn (без reload, log_config=None)
                                      ├─ FastAPI
                                      │   ├─ /api/health, /api/system/{process,shutdown}
                                      │   ├─ /api/logs, /api/settings, /ws/events
                                      │   └─ /*  → frontend/dist (SPA fallback на index.html)
                                      ├─ EventBus (ограниченные очереди на клиента, drop-oldest)
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

Перед любой незавершённой миграцией существующей БД создаётся копия через SQLite backup API;
при ошибке база восстанавливается из неё. Откат 0002 не поддерживается — используйте копию
или ветку `archive/v1-simulator`.
