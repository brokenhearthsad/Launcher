# Troubleshooting

| Симптом | Решение |
|---------|---------|
| Окно открывается и закрывается | Скачайте проект целиком (ветка `claude/dota-match-lab`, Code → Download ZIP), распакуйте, запускайте из распакованной папки: сначала `install.bat`, потом `start.bat` |
| «Python 3.12 or newer was not found» | Установите Python 3.12+ с галочкой «Add python.exe to PATH»; отключите псевдонимы Microsoft Store для python.exe |
| «The web interface is not built» | Запустите `install.bat` ещё раз (нужен Node.js только для сборки) |
| «Port 8000 is already in use» | Launcher уже запущен — откройте http://localhost:8000; иначе `stop.bat` |
| Launcher did not start | См. `.run\launcher.err.log` |
| Остались процессы старой версии (node / порт 5173) | `stop.bat` останавливает и их |
| Нужна старая база | Копии в `backend\data\backups\`. Остановите Launcher, замените `backend\data\match_lab.db` копией и используйте ветку `archive/v1-simulator` |
| Страница пишет «Интерфейс не собран» | `install.bat` (папка `frontend\dist` отсутствует) |
| GPU: «Нет данных» | Не загружен драйвер NVIDIA / нет `nvidia-smi`. Причина показана на странице «Система» |
| Температура CPU: «Нет данных» | Ожидаемо без LibreHardwareMonitor (INSTALLATION.md). Если включено — проверьте Remote Web Server на 8085 |
| Steam «Не найден» | Укажите папку в `backend\.env`: `DML_STEAM_PATH=D:\Steam`, перезапустите |
| Dota 2 не видна, хотя установлена | «Проверить сейчас»; проверьте, что библиотека есть в Steam → Настройки → Хранилище |
| Диск D: «Нет данных» | Диск не подключён или другая буква — `DML_MONITORED_DRIVES` в `backend\.env` |
| «локальный клиент уже привязан» | Снимите привязку с другого слота: на ПК один клиент Steam |
| 400 Bad Request | Открывайте именно http://localhost:8000 или http://127.0.0.1:8000 |

Логи: страница «Логи», `backend\logs\app.jsonl`, `.run\launcher.*.log`.
