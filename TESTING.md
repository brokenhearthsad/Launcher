# Тестирование

| Набор | Команда | Тестов |
|-------|---------|--------|
| Backend (pytest) | `cd backend && .venv\Scripts\python -m pytest` | 21 |
| Линтер | `cd backend && .venv\Scripts\ruff check app tests` | — |
| Frontend (Vitest) | `cd frontend && npm test` | 20 |
| Проверка типов | `cd frontend && npm run typecheck` | — |
| E2E (Playwright, production-режим) | `cd frontend && npm run build && npm run e2e` | 3 |

Backend: миграция старой базы v1 (копия создаётся, содержит старые данные, таблицы симулятора удалены,
логи сохранены, повторный запуск не делает копию), восстановление базы при сбое миграции, раздача
интерфейса и SPA-маршрутов, защита от выхода из папки, `Host`-заголовок, rate limit, остановка
(заголовок, отсутствие раннера, `should_exit`), ресурсы процесса, логи и их переживание
переконфигурации logging (регрессия), настройки, WebSocket.

## Ручная проверка PHASE 1 на Windows

1. `stop.bat` (на случай, если запущена старая версия) → `install.bat` → «Installation complete».
2. Убедиться, что в `backend\data\backups\` появилась копия `match_lab-…-pre-0002.db` (если база была).
3. `start.bat` → открывается http://localhost:8000, страница «Обзор», статус «Работает».
4. Диспетчер задач: один `python.exe` Launcher, `node.exe` нет; память < 150 МБ; ЦП ≈ 0 %.
5. «Логи» → обновить страницу (F5) — страница открывается (SPA).
6. «Настройки» → изменить интервал → «Сохранить» → обновить — значение сохранилось.
7. `stop.bat` → «Launcher stopped»; повторный `start.bat` работает.
