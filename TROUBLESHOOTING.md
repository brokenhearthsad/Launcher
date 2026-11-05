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
| «Ожидание GSI», хотя Dota 2 запущена | Dota 2 читает cfg при старте — перезапустите её после установки; проверьте параметр запуска `-gamestateintegration`; «Проверить конфигурацию» должна показать «установлена и актуальна» |
| GSI: «отклонено» растёт | Файл cfg содержит старый токен (база Launcher была пересоздана) — «Установить GSI» обновит файл |
| GSI «Нет данных (GSI молчит)» во время игры | Обновлений нет > 40 с: игра свёрнута/зависла или закрыта; порог — «gsi_stale_seconds» |
| «Установить GSI» недоступна | Конфигурация уже актуальна, либо Dota 2 не найдена (раздел «Steam и Dota 2») |
| Нужно вернуть свой старый cfg | «Состояние игры» → «Резервные копии» → «Восстановить»; файлы в `backend\data\gsi_backups\` |
| 400 Bad Request | Открывайте именно http://localhost:8000 или http://127.0.0.1:8000 |

Логи: страница «Логи», `backend\logs\app.jsonl`, `.run\launcher.*.log`.
