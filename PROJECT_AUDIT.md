# PROJECT AUDIT — Launcher → локальная платформа мониторинга Dota 2

Дата: 2026-11-05 · Ветка: `claude/dota-match-lab` (коммит `962545c`) · Статус: **аудит, изменений кода нет**

Целевая машина: Windows 11 Pro x64, Ryzen 5 5600X (6C/12T), 32 GB DDR4, RTX 3050 8 GB,
NVMe 512 GB + HDD 1 TB. Единственный ПК, параллельно работают Chrome, Claude Code, Steam,
Dota 2, Discord, Telegram.

---

## 0. Краткий вывод

Текущий проект — это **симулятор** 5v5 с собственным AI ботов. Он работает и покрыт тестами,
но по новой постановке его ядро (симулятор + AI, ~3 400 строк backend) **не нужно**: требуется
наблюдать за *настоящими* Steam и Dota 2, а не подменять игру моделью.

Инфраструктурный слой (FastAPI-каркас, БД и миграции, логирование, WebSocket-шина,
обработка ошибок, UI-оболочка, компоненты, тестовая обвязка) — **качественный и переиспользуемый**,
это примерно 40% кода.

Ключевое ограничение платформы: **на одном Windows-ПК поддерживается один авторизованный
клиент Steam и один процесс Dota 2**. Поэтому 10 слотов могут быть только *логическими*:
не более одного слота привязано к локальному клиенту. Остальные слоты — это встроенные боты
Dota в локальном лобби, наблюдаемые через Game State Integration (если зритель — вы),
или клиенты на других ПК (опциональный агент в будущем), или просто не привязанные слоты.

---

## 1. Текущая архитектура

```
Browser ──► Vite dev server (Node, :5173) ──proxy──► FastAPI (Python, :8000)
                                                       ├─ api/*            REST + WS /ws/events
                                                       ├─ services/        players, sessions, analytics, settings, event_bus
                                                       ├─ game/simulator   движок 5v5 (карта, крипы, башни, Рошан)
                                                       ├─ game/adapters    GameAdapter, MockGameAdapter, DotaTestAdapter(заглушка)
                                                       ├─ game/match.py    MatchController (10 ботов + 2 Team AI)
                                                       ├─ ai/              Utility AI: lane/farming/economy/items/combat/objective/team
                                                       └─ db/              SQLAlchemy + SQLite(WAL) + Alembic
```

Размер: backend ~5 600 строк (`app/`), frontend ~3 700 строк (`src/`), тесты: 81 pytest,
25 Vitest, 3 Playwright.

| Слой | Файлы | Назначение |
|------|-------|-----------|
| Каркас | `main.py`, `config.py`, `state.py`, `errors.py`, `api/ratelimit.py` | app factory, `DML_*` конфиг, единый формат ошибок, rate limit |
| Логи | `logging_config.py` | JSON-логи в stdout, ротируемый файл и таблицу `system_logs` (фоновый поток) |
| БД | `db/models.py`, `db/session.py`, `alembic/` | 8 таблиц, WAL, UTC-даты, миграции при старте |
| Сервисы | `services/*` | Player Manager, Session Manager (asyncio-раннер), Analytics, Settings, EventBus |
| Игра | `game/*`, `ai/*` | симулятор и боты — **заменяемое ядро** |
| API | `api/*` | health/meta, players, sessions, matches, analytics, logs, settings, ws |
| Frontend | `src/pages/*` (9 стр.), `components/ui.tsx`, `Layout.tsx`, `hooks/*`, `api/*` | React 18 + TS + Tailwind + Recharts |
| Запуск | `install.bat`, `start.bat`, `stop.bat` | venv, npm, запуск двух скрытых процессов, PID-файлы |

---

## 2. Что работает (проверено)

| Функция | Статус |
|---------|--------|
| Backend запуск, миграции, сид 10 участников | ✅ (тесты + запуск у вас: «Backend is up») |
| REST API, пагинация, валидация, коды ошибок, rate limit | ✅ |
| WebSocket с троттлингом (4 Гц), drop-oldest очереди, ping, переподключение на клиенте | ✅ |
| Жизненный цикл сессии (start/pause/resume/speed/stop), recovery после падения | ✅ — но для *симулятора* |
| Симулятор 5v5 + 10 ботов, детерминизм по seed | ✅ — **не нужен по новой постановке** |
| Аналитика, экспорт CSV/JSON | ✅ — на данных симулятора |
| Логи в БД с фильтрами, страница Settings (уровни логов, VACUUM, purge) | ✅ |
| Frontend: 9 страниц, тёмная тема, адаптивность | ✅ (скриншоты, e2e) |
| `install.bat` | ✅ после исправлений (нашёл ваш Python, установил) |
| `start.bat` | ⚠️ исправлен (IPv4 для Vite) — **подтверждения запуска у вас пока нет** |

## 3. Что является заглушкой или не соответствует новой задаче

| Компонент | Проблема |
|-----------|----------|
| `game/adapters/dota_test.py` | Чистая заглушка: все методы бросают `AdapterNotSupportedError` |
| `game/simulator/*`, `ai/*`, `game/match.py`, `game/catalog.py` | Подменяют Dota 2 моделью — прямо противоречит требованию «не подменяй» |
| «Players» = боты | Нет связи ни с процессами, ни со Steam; статусы ставятся программой, а не наблюдаются |
| Мониторинг ресурсов | **Отсутствует полностью** (нет psutil, GPU, температур) |
| Обнаружение Steam/Dota | **Отсутствует** |
| Диагностика окружения | Отсутствует (только `/api/health` самого backend) |
| Bot Configuration, Match Control, Live Match | Завязаны на симулятор |

## 4. Обнаруженные проблемы

1. **Архитектурное несоответствие**: центр системы — симулятор; новая система должна строиться
   вокруг *наблюдателей* (watchers) реального окружения.
2. **Лишний Node-процесс в рантайме**: frontend запускается через Vite dev server (`npm run dev`):
   +1 процесс `node.exe`, ~150–250 MB RAM и файловый watcher. Для конечного пользователя не нужен —
   достаточно собранной статики, которую раздаёт FastAPI.
3. **Два скрытых процесса, принудительное завершение**: `stop.bat` использует `taskkill /F`; нет
   корректного завершения (сессии помечаются `error` при следующем старте).
4. **Нет управления приоритетом**: backend работает с обычным приоритетом; при всплесках (симуляция
   на x1000 загружала ядро на 100%) мог конкурировать с Dota 2.
5. **Windows-скрипты не тестировались на Windows при разработке** — уже потребовались 2 исправления
   (поиск Python, IPv6/localhost). Нужен ручной чек-лист на вашей машине.
6. **Модель данных** (`Player` с весами AI, `MatchParticipant.ai_profile`, `StatSnapshot` из симулятора)
   не подходит для слотов, процессов и метрик.
7. **Документация** (README, BOT_AI.md, API.md) описывает симулятор — потребует переписывания.
8. **Тесты на ~70% проверяют симулятор** и уйдут вместе с ним.

---

## 5. Ответы на ключевые вопросы

### 5.1 Как организовать десять логических слотов

Слот — запись в БД, а не процесс. Статус слота **вычисляется** из наблюдений, а не задаётся вручную.

```
ClientSlot
  id 1..10, team (radiant/dire), position 1..5, label
  binding: none | local_client | in_game_bot | remote_agent (будущее)
  expected_hero (опционально), notes
  observed_status (вычисляется): unbound | offline | steam_running | steam_logged_in
                                 | dota_running | in_menu | in_lobby | in_game | spectating | error
  last_seen_at, last_error
```

Правила:
- **Только один слот** может иметь `binding = local_client` (ограничение платформы, проверяется в БД).
- `in_game_bot` — слот, соответствующий встроенному боту Dota в **вашем** локальном лобби
  (лобби создаётся вами вручную в клиенте Dota). Данные о таких слотах доступны только если
  ваш клиент — **наблюдатель/зритель** лобби (GSI отдаёт `allplayers` только зрителю).
- `remote_agent` — будущий лёгкий агент на *другом* ПК со своим Steam (единственный поддерживаемый
  способ иметь несколько настоящих клиентов). В первой версии не реализуется, только резерв в модели.
- Привязка слота к Steam: хранится только публичный SteamID/имя профиля для отображения.
  **Никаких логинов, паролей, токенов Steam.**

### 5.2 Как обнаруживать настоящие процессы Steam и Dota 2 (только пассивно)

| Источник | Что даёт | Стоимость |
|----------|---------|-----------|
| `psutil.process_iter(['pid','name','exe','create_time'])` | `steam.exe`, `steamwebhelper.exe`, `dota2.exe` (`…\steamapps\common\dota 2 beta\game\bin\win64\dota2.exe`), CPU/RAM этих процессов | ~5–20 мс на скан; скан раз в 5 с, между сканами — опрос по сохранённым PID |
| Реестр `HKCU\Software\Valve\Steam` (`winreg`, stdlib) | `SteamPath`, `SteamExe`, `RunningAppID`; `…\ActiveProcess\pid`, `ActiveUser` (0 = не авторизован); `…\Apps\570\Running`, `Updating`, `Installed` | <1 мс |
| `steamapps\libraryfolders.vdf`, `appmanifest_570.acf` | где установлена Dota, buildid, флаги обновления (StateFlags) | чтение файла при изменении mtime |
| `config\loginusers.vdf` | имя профиля/SteamID последнего входа (публичные данные) | редко |
| **Dota 2 Game State Integration** | официальный push JSON от клиента на `http://127.0.0.1:<port>/gsi`: `map` (game_state, clock, score, win_team, matchid), `player`, `hero`, `items`, `abilities`, `buildings`; для зрителя — `allplayers` | 0 опроса: клиент сам шлёт POST ~раз в 0.1–1 с, мы троттлим |
| `console.log` (запуск с `-condebug`) | опциональный хвост лога для диагностики ошибок клиента | tail при изменении |

Чего **не делаем**: чтение памяти процесса, инъекция DLL, эмуляция ввода, перехват трафика,
автоматическое создание лобби/поиска через Game Coordinator, запуск нескольких экземпляров Steam.

Запуск игры — только через официальный протокол `steam://rungameid/570` (по кнопке пользователя).

### 5.3 Мониторинг ресурсов

| Метрика | Источник | Примечание |
|---------|---------|-----------|
| CPU общий и по ядрам, частота | `psutil.cpu_percent(percpu=True)`, `cpu_freq()` | неблокирующий режим (`interval=None`) |
| RAM, swap | `psutil.virtual_memory()`, `swap_memory()` | |
| CPU/RAM процессов Steam/Dota/Discord/Chrome/наш backend | `psutil.Process.cpu_percent()`, `memory_info().rss` | только по отслеживаемым PID |
| Диски NVMe/HDD: заполненность, I/O | `psutil.disk_usage`, `disk_io_counters(perdisk=True)` | |
| GPU: загрузка, VRAM, температура, мощность, частоты | **NVML** (`nvidia-ml-py`, официальные биндинги NVIDIA) | в процессе, без порождения процессов; RTX 3050 поддерживается |
| GPU — fallback | `nvidia-smi --query-gpu=... --format=csv` | только если NVML недоступен; запуск процесса ~50–100 мс, поэтому не чаще раза в 5 с |
| GPU по процессам (кто грузит видеокарту) | Windows Performance Counters `\GPU Engine(*)\Utilization Percentage`, `\GPU Process Memory(*)\Dedicated Usage` через PDH (`pywin32`) | |
| Температура CPU (Ryzen Tctl) | **Штатно в Windows недоступна.** `MSAcpi_ThermalZoneTemperature` (WMI) требует админа и обычно возвращает фиктивное ACPI-значение | Опционально: чтение из запущенного LibreHardwareMonitor (WMI `root\LibreHardwareMonitor` или его web-JSON). Если нет — показываем «недоступно», **не выдумываем** |
| Температура дисков (SMART) | требует прав администратора | вне первой версии |

Пороговые предупреждения (настраиваемые): GPU ≥ 83 °C, CPU ≥ 90 °C (если доступна),
RAM ≥ 90%, VRAM ≥ 95%, свободное место < 10 GB, Dota «не отвечает».

### 5.4 Лёгкость для Ryzen 5 5600X / 32 GB

Целевой бюджет: **< 1% CPU в среднем, < 150 MB RAM, 1 процесс Python, 0 процессов Node в рантайме.**

1. **Один процесс**: FastAPI раздаёт собранный frontend (`dist/`) как статику; Vite/Node — только для разработки.
2. **Приоритет `BELOW_NORMAL`** для backend (`psutil.Process().nice(...)`) — Dota всегда важнее.
3. **Адаптивный опрос** (один планировщик asyncio, без потоков на каждый датчик):

   | Режим | Ресурсы | Процессы | GPU |
   |-------|---------|----------|-----|
   | Панель открыта | 2 с | 5 с | 2 с (NVML) |
   | Панель закрыта | 15 с | 15 с | 15 с |
   | Идёт матч Dota (энергосбережение) | 5 с | 10 с | 5 с |

4. **Ring buffer в памяти** (последние ~30 мин сырых точек) + запись в SQLite **агрегатов раз в минуту**
   (min/avg/max) — сотни строк в час, а не тысячи.
5. GSI-пакеты: обработка O(1), публикация в UI с троттлингом, в БД — только события (смена
   состояния игры, убийства, смерти, начало/конец матча) и минутные снимки.
6. Никаких WMI-запросов в горячем цикле (WMI медленный и сам грузит CPU через `WmiPrvSE.exe`).
7. Frontend: графики только видимой страницы, ограничение точек, остановка опроса в скрытой вкладке
   (уже реализовано в `useAsync`).
8. БД и логи на NVMe (объём мегабайты), ротация логов, автоочистка старых сырых метрик.

### 5.5 Ограничения интеграции с Dota 2 (честно)

| Ограничение | Последствие для проекта |
|-------------|-------------------------|
| Steam — однократный экземпляр на пользователя Windows; одновременная работа нескольких аккаунтов на одном ПК официально не поддерживается, а передача аккаунтов запрещена Steam Subscriber Agreement | 10 одновременных клиентов на вашем ПК — **невозможно и не будет реализовано**. 1 локальный клиент максимум |
| Dota 2 — один процесс на клиент Steam | один локальный «живой» слот |
| GSI — только чтение, только с точки зрения вашего клиента; данные о всех 10 игроках — только если вы зритель/наблюдатель | полная картина 10 слотов доступна в режиме зрителя/лобби с ботами |
| GSI требует cfg-файл в `…\dota 2 beta\game\dota\cfg\gamestate_integration\` и, по имеющимся данным, параметр запуска `-gamestateintegration` | установщик cfg по согласию пользователя + проверка в диагностике; **требует проверки на вашем ПК** |
| Нет официального API для управления лобби/ботами извне; Bot Scripting API (Lua) изолирован от сети и файлов | управление матчами — вручную в клиенте Dota; программа наблюдает |
| Поля GSI могут меняться с патчами | версионированный парсер, тесты на сохранённых пакетах, «неизвестное поле ≠ ошибка» |
| Steam Web API / история матчей требует ключ API пользователя | опционально, ключ — только в Windows Credential Manager, не в БД/коде |
| Античит (VAC) | только пассивные методы выше: список процессов, реестр, файлы, официальный GSI |

---

## 6. Предлагаемая архитектура

```
 Chrome ──► http://localhost:8000  (одна точка: UI-статика + REST + WS)
              │
 FastAPI (1 процесс, BELOW_NORMAL)
   ├─ api/                 REST + /ws/events + POST /gsi (токен из cfg)
   ├─ core/scheduler       единый asyncio-планировщик опросов, адаптивные интервалы
   ├─ monitoring/          system(psutil) · gpu(NVML → nvidia-smi) · perfcounters(PDH) · sensors(LHM, опц.)
   │                        → ring buffer → minute aggregates → alerts
   ├─ integrations/steam/  registry · library(vdf/acf) · process watcher
   ├─ integrations/dota/   gsi receiver · parser · cfg installer · console log (опц.)
   ├─ slots/               10 логических слотов, правила привязки, вычисление статуса
   ├─ sessions/            recorder: автостарт/стоп сессии по состоянию Dota (GSI/процесс)
   ├─ diagnostics/         проверки окружения, отчёты, рекомендации
   ├─ events/              нормализованные события (процесс запущен/упал, матч начат, порог превышен…)
   ├─ analytics/           история сессий, ресурсы во время матчей, статистика по GSI
   └─ db/ (SQLite + Alembic), logging, settings, event_bus   ← сохраняются
```

Поток данных: *источник → нормализованное событие/метрика → in-memory состояние → (троттлинг) WS
→ (агрегация) SQLite*. Источники изолированы: падение NVML не ломает psutil и GSI.

### Новая модель данных

| Таблица | Поля (кратко) |
|---------|---------------|
| `client_slots` | id, team, position, label, binding, expected_hero, steam_id (публичный, опц.), created/updated |
| `environment_state` | key/value последнего известного состояния Steam/Dota (путь, buildid, флаги) |
| `game_sessions` | id, source (gsi/process), match_id (если есть), started/ended, game_state, winner, radiant/dire score, duration |
| `session_slots` | session_id, slot_id, hero, team, итоговые K/D/A/LH/DN/GPM/XPM/NW (только из GSI) |
| `events` | id, session_id?, slot_id?, source (process/steam/gsi/monitor/diagnostics), type, severity, data JSON, ts |
| `resource_samples_1m` | ts, cpu avg/max, ram, gpu util, vram, gpu temp, cpu temp?, dota cpu/ram, disk |
| `process_samples_1m` | ts, process (steam/dota/discord/chrome/self), cpu, rss |
| `alerts` | id, rule, severity, value, threshold, started/resolved |
| `diagnostic_runs` | id, ts, results JSON |
| `system_logs`, `app_settings` | **без изменений** |

---

## 7. Сохраняемые модули

| Модуль | Изменения |
|--------|-----------|
| `backend/app/main.py`, `config.py`, `state.py`, `errors.py` | новый набор роутеров/сервисов, раздача статики |
| `backend/app/logging_config.py` | без изменений |
| `backend/app/db/session.py`, `alembic/` | новая миграция `0002` |
| `backend/app/services/event_bus.py`, `api/ws.py` | новые типы событий |
| `backend/app/services/settings_service.py`, `api/settings.py` | новые ключи (интервалы, пороги, пути) |
| `backend/app/api/logs.py`, `api/ratelimit.py`, `api/deps.py`, `api/health.py` | минимальные |
| `frontend/src/components/ui.tsx`, `Layout.tsx`, `hooks/useAsync.ts`, `hooks/LiveEvents.tsx`, `lib/format.ts`, `api/client.ts` (паттерн) | новый набор пунктов меню и эндпоинтов |
| `frontend/src/pages/Logs.tsx`, `Settings.tsx`, `History.tsx` (каркас) | адаптация |
| Тестовая инфраструктура (`conftest.py`, `test/utils.tsx`, Playwright config), `ruff.toml` | новые тесты |
| `install.bat`, `start.bat`, `stop.bat` | упрощение: один процесс, без Node в рантайме |

## 8. Удаляемые / заменяемые модули

| Модуль | Решение |
|--------|---------|
| `backend/app/game/simulator/*`, `game/match.py`, `game/catalog.py`, `game/adapters/*` | **удалить** (сохранить в git-теге `v1-simulator` для истории) |
| `backend/app/ai/*` (13 файлов) | **удалить** |
| `services/session_manager.py` | заменить на `sessions/recorder.py` |
| `services/player_service.py`, `db/seed.py` | заменить на `slots/service.py` (сид 10 пустых слотов) |
| `services/analytics.py` | переписать под реальные данные (формулы KDA/GPM сохранятся) |
| `db/models.py` | новая модель (см. §6); старые таблицы — удалить миграцией (данные симулятора не переносятся) |
| `api/players.py`, `api/sessions.py`, `api/matches.py`, `api/analytics.py` | заменить на `slots`, `environment`, `monitoring`, `sessions`, `analytics`, `diagnostics`, `gsi` |
| Frontend: `Players`, `BotConfig`, `MatchControl`, `LiveMatch`, `Analytics`, `MiniMap` | заменить: `Slots`, `Environment`, `Monitoring`, `LiveGame`, `Analytics`, `Diagnostics` |
| `BOT_AI.md` | удалить; README/API/ARCHITECTURE/TESTING переписать |
| Тесты симулятора/AI (`test_ai.py`, `test_simulator.py`, `test_integration.py` и др.) | удалить, написать новые |

## 9. Новые модули

**Backend** (`backend/app/`)

| Путь | Назначение |
|------|-----------|
| `core/scheduler.py` | планировщик задач опроса, адаптивные интервалы, режим «панель закрыта / идёт матч» |
| `platform/windows.py` | приоритет процесса, проверка ОС, admin-флаг, foreground-окно (опц.) |
| `monitoring/system.py` | psutil: CPU, RAM, диски, сеть |
| `monitoring/gpu.py` | NVML с fallback на `nvidia-smi` |
| `monitoring/perfcounters.py` | PDH: GPU по процессам |
| `monitoring/sensors.py` | температура CPU через LibreHardwareMonitor (опционально) |
| `monitoring/store.py` | ring buffer + минутная агрегация в SQLite |
| `monitoring/alerts.py` | правила порогов, гистерезис, события |
| `integrations/steam/registry.py`, `library.py`, `processes.py` | обнаружение Steam/Dota, установка, обновления, авторизация (флаг) |
| `integrations/vdf.py` | мини-парсер VDF/ACF (или пакет `vdf`) |
| `integrations/dota/gsi_receiver.py`, `gsi_models.py`, `gsi_parser.py`, `gsi_config.py` | приём, валидация, разбор, установка cfg |
| `integrations/dota/console_log.py` | опц. хвост `console.log` |
| `slots/service.py`, `slots/status.py` | слоты, привязка, вычисление статуса |
| `sessions/recorder.py` | автозапись игровых сессий |
| `diagnostics/checks.py` | Steam установлен/запущен/авторизован, Dota установлена/обновлена, GSI cfg и параметр запуска, порт, NVML, место на дисках, температуры |
| `events/service.py` | нормализация и хранение событий |
| `api/{slots,environment,monitoring,sessions,analytics,diagnostics,gsi}.py` | REST |

**Новые зависимости**: `psutil`, `nvidia-ml-py`, `pywin32` (PDH; `winreg` — stdlib). Все опциональны
в рантайме: при отсутствии модуль сообщает «недоступно».

**Frontend**: страницы `Dashboard`, `Slots`, `Environment` (Steam/Dota), `Monitoring` (CPU/RAM/GPU/VRAM/
температуры/процессы), `LiveGame` (GSI), `History`, `Analytics`, `Diagnostics`, `Logs`, `Settings`.

---

## 10. План миграции

1. Тег `v1-simulator` на текущем коммите; дальнейшая работа в той же ветке.
2. Удалить симулятор/AI и связанные тесты и страницы одним коммитом — проект должен
   собираться и запускаться (пустые страницы-заглушки **не** допускаются: удалённые пункты меню убираются).
3. Миграция Alembic `0002`: drop старых игровых таблиц, create новых. Существующая `match_lab.db`
   у вас содержит только тестовые данные симулятора — их **не переносим** (подтвердите).
4. FastAPI раздаёт `frontend/dist`; `start.bat` запускает **один** процесс и открывает `http://localhost:8000`.
5. Дальше — этапы §12, после каждого: тесты + ручная проверка на вашем ПК.

## 11. Технические риски

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Температура Ryzen недоступна без стороннего драйвера | высокая | опциональная интеграция с LibreHardwareMonitor; иначе явно «недоступно» |
| Параметр запуска `-gamestateintegration` / формат cfg изменился | средняя | диагностика + проверка на вашем ПК до опоры на GSI |
| GSI даёт данные только о вашем герое (не зритель) | высокая | честное отображение: остальные слоты «нет данных» |
| Ключи реестра Steam недокументированы | средняя | несколько источников (процесс + реестр + файлы), деградация без ошибок |
| NVML/драйвер NVIDIA отсутствует или старый | низкая | fallback `nvidia-smi`, затем «недоступно» |
| PDH-счётчики имеют локализованные имена на русской Windows | средняя | использовать `PdhAddEnglishCounter` |
| Антивирус ругается на скрытый запуск процессов из .bat / будущий .exe | низкая–средняя | без упаковщиков на первом этапе; видимое окно-лаунчер или трей |
| Нагрузка во время игры | низкая | бюджет §5.4, замер в Диспетчере задач как критерий приёмки |
| Скрипты .bat нельзя проверить в среде разработки (Linux) | высокая | ручной чек-лист на вашем ПК после каждого этапа |
| Ожидание «10 настоящих клиентов» | — | зафиксировано ограничение: 1 локальный клиент; остальные — боты лобби/зритель/удалённые агенты |

## 12. Этапы разработки

| # | Этап | Результат | Критерий приёмки |
|---|------|-----------|------------------|
| 1 | Очистка и фундамент | удалены симулятор/AI; один процесс; статика из FastAPI; приоритет BELOW_NORMAL; миграция 0002 | `start.bat` → панель на :8000, 1 процесс `python.exe`, < 100 MB |
| 2 | Слоты | CRUD 10 слотов, правило «один local_client», вычисляемый статус | страница Slots |
| 3 | Steam/Dota detection | процессы, реестр, установка, обновление, авторизация (флаг) | запуск/закрытие Steam и Dota отражается в UI ≤ 5 с |
| 4 | Мониторинг ресурсов | CPU/RAM/диски/процессы, NVML, PDH, пороги, история | графики; нагрузка программы < 1% CPU |
| 5 | GSI | cfg-установщик (по кнопке), приёмник, парсер, LiveGame | данные матча с ботами в UI |
| 6 | Сессии и события | автозапись сессий, журнал событий | история после матча |
| 7 | Диагностика | набор проверок с рекомендациями | отчёт на странице Diagnostics |
| 8 | Аналитика | ресурсы во время матчей, статистика по сессиям, экспорт | графики/CSV |
| 9 | Упаковка | обновлённые bat, автозапуск (опц.), трей (опц.), документация | установка с нуля по INSTALLATION.md |
| 10 | Тесты | pytest с фейками psutil/NVML/реестра и записанными GSI-пакетами, Vitest, Playwright; ручной Windows-чек-лист | всё зелёное |

## 13. Вопросы для подтверждения перед началом

1. Удаляем симулятор и AI ботов полностью (с тегом `v1-simulator` в git)?
2. Данные текущей `match_lab.db` можно не переносить?
3. Порт панели переносим на `http://localhost:8000` (один процесс), или оставить `:5173`?
4. Устанавливать ли LibreHardwareMonitor ради температуры CPU (или температура CPU не нужна)?
5. Нужен ли в будущем агент для других ПК (`remote_agent`), или 10 слотов остаются чисто логическими
   (1 локальный клиент + боты лобби)?
6. Разрешаете программе создавать файл GSI-конфига в папке Dota 2 (по кнопке, с вашим подтверждением)?
