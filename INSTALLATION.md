# Установка

## Требования

| Компонент | Версия | Зачем |
|-----------|--------|-------|
| Windows | 11 (10 тоже подойдёт) | |
| Python | 3.12+ | работа Launcher. При установке отметьте «Add python.exe to PATH» |
| Node.js | 20 LTS+ | **только** сборка интерфейса в `install.bat` |

## Автоматически

```bat
install.bat
start.bat
```

`install.bat`:
1. находит Python 3.12+ (`py -3.13`, `py -3.12`, `py -3`, `python`) и Node.js;
2. создаёт `backend\.venv`, ставит зависимости;
3. копирует `.env.example` → `.env`, если файлов ещё нет;
4. `npm install` + `npm run build` → `frontend\dist`;
5. применяет миграции. **Если база уже существует и её нужно обновить, сначала создаётся копия**
   в `backend\data\backups\match_lab-<дата>-pre-<версия>.db`. При ошибке миграции база
   автоматически восстанавливается из копии. Копии Launcher никогда не удаляет.

`start.bat` проверяет установку и свободный порт 8000, запускает **один** скрытый процесс
`python -m app`, ждёт `/api/health` и открывает http://localhost:8000. Вывод процесса — в `.run\`.

`stop.bat` сначала просит Launcher завершиться корректно (`POST /api/system/shutdown`), ждёт до 10 с
и только потом завершает процесс принудительно. Ту же остановку можно сделать в
«Настройки → Остановить Launcher».

## Вручную

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
cd ..\frontend && npm install && npm run build && cd ..\backend
python -m app                       # http://localhost:8000
```

Разработка интерфейса с горячей перезагрузкой: `python -m app` + `cd frontend && npm run dev`
(http://localhost:5173, проксирует `/api` и `/ws` на :8000).

## Настройки

`backend\.env` (префикс `DML_`): адрес/порт, путь к БД и папке копий, уровни логов,
`DML_LOWER_OWN_PRIORITY` (по умолчанию `false`: понижение приоритета **только самого Launcher**, по желанию).
Интервал обновления страниц, частота WebSocket и уровни логов меняются на странице «Настройки».

## Температура CPU (необязательно): LibreHardwareMonitor

Windows не отдаёт температуру Ryzen без драйвера, поэтому без LibreHardwareMonitor Launcher
показывает «Нет данных».

1. Скачайте LibreHardwareMonitor с https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases
   и запустите его (права администратора нужны самой программе, не Launcher).
2. В LibreHardwareMonitor: **Options → Remote Web Server → Run** (порт по умолчанию 8085).
3. В Launcher: **Настройки → Мониторинг → «Температура CPU из LibreHardwareMonitor»** → Сохранить.

Launcher обращается только к адресу на этом ПК (`http://127.0.0.1:8085/data.json`); другие адреса запрещены.

## Видеокарта NVIDIA

Данные берутся через NVML (входит в драйвер NVIDIA), иначе через `nvidia-smi`. Если драйвера нет,
показатели GPU — «Нет данных» с указанием причины.

## Steam и Dota 2

Steam ищется в реестре (`HKCU\Software\Valve\Steam\SteamPath`) и в стандартных папках, библиотеки — в
`steamapps\libraryfolders.vdf`, Dota 2 — по `appmanifest_570.acf`. Если Steam стоит в нестандартном месте
и не найден, укажите `DML_STEAM_PATH` в `backend\.env`.
Launcher **не запускает, не закрывает и не меняет приоритет** Steam и Dota 2, не читает пароли и токены.

## Dota 2 Game State Integration (GSI)

GSI — встроенный механизм Dota 2: игра сама отправляет снимки состояния на адрес из конфигурационного
файла. Launcher только принимает данные на `http://127.0.0.1:8000/gsi` (отдельный сервер не запускается).

1. Откройте **«Состояние игры» → «Конфигурация GSI»** и нажмите **«Проверить конфигурацию»**: Launcher
   покажет найденную папку Dota 2 и существующие GSI-файлы других программ (их он не изменяет).
2. **«Установить GSI»** → проверьте предпросмотр (текущий и новый файл, токен скрыт) → отметьте
   подтверждение → **«Подтвердить и установить»**. Создаётся только
   `game\dota\cfg\gamestate_integration\gamestate_integration_launcher.cfg`; если файл уже был, он сначала
   копируется в `backend\data\gsi_backups\`.
3. В Steam: Dota 2 → Свойства → **Параметры запуска** → добавьте `-gamestateintegration`
   (по данным сообщества, без него современные версии Dota 2 не отправляют GSI). Launcher это только проверяет.
4. **Перезапустите Dota 2.** Через несколько секунд статус станет «Данные поступают».

Удаление: «Удалить конфигурацию Launcher» (только файл, созданный Launcher; перед удалением — копия).
Восстановление: список «Резервные копии» → «Восстановить» (текущий файл тоже сохраняется в копию).
Токен GSI генерируется один раз, хранится в локальной базе и в cfg-файле Dota 2, в логах не появляется.
Полная ручная проверка — [GSI_CHECKLIST.md](GSI_CHECKLIST.md).
