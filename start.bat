@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Launcher

set "ROOT=%~dp0"
set "RUN=%ROOT%.run"
set "URL=http://localhost:8000"
set "HEALTH=http://127.0.0.1:8000/api/health"
if not exist "%RUN%" mkdir "%RUN%"

echo === Launcher: start ===
echo Folder: %CD%
echo.

if not exist "backend\app\main.py" (
  echo [ERROR] Project files were not found next to start.bat. Extract the whole project first.
  goto :fail
)
if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERROR] Launcher is not installed. Run install.bat first and wait for "Installation complete".
  goto :fail
)
if not exist "frontend\dist\index.html" (
  echo [ERROR] The web interface is not built. Run install.bat again.
  goto :fail
)

call :port_busy 8000
if not errorlevel 1 (
  echo [ERROR] Port 8000 is already in use. If Launcher is already running, open %URL%
  echo         otherwise run stop.bat and then start.bat again.
  goto :fail
)

rem One Python process serves the interface, the API and WebSocket. Node.js is not used.
echo Starting Launcher...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Start-Process -FilePath '%ROOT%backend\.venv\Scripts\python.exe' -ArgumentList '-m','app' -WorkingDirectory '%ROOT%backend' -WindowStyle Hidden -RedirectStandardOutput '%RUN%\launcher.out.log' -RedirectStandardError '%RUN%\launcher.err.log' -PassThru; $p.Id | Out-File -Encoding ascii '%RUN%\launcher.pid'"
if errorlevel 1 (
  echo [ERROR] Could not start Launcher.
  goto :fail
)
call :wait "%HEALTH%" 60
if errorlevel 1 (
  echo [ERROR] Launcher did not start. Last lines of .run\launcher.err.log:
  powershell -NoProfile -Command "Get-Content -Path '%RUN%\launcher.err.log' -Tail 25"
  call "%ROOT%stop.bat" /nopause >nul
  goto :fail
)

echo.
echo ==========================================================
echo   Launcher is running (one python.exe process)
echo   Panel    : %URL%
echo   API docs : %URL%/docs
echo   Logs     : .run\launcher.*.log and backend\logs\app.jsonl
echo   Stop     : stop.bat  or  Settings - "Stop Launcher"
echo ==========================================================
start "" "%URL%"
echo You can close this window - Launcher keeps running in the background.
if /i not "%~1"=="/nopause" pause
exit /b 0

:fail
echo.
echo Start FAILED. Read the messages above; see also TROUBLESHOOTING.md.
if /i not "%~1"=="/nopause" pause
exit /b 1

:port_busy
rem errorlevel 0 = something listens on port %1
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %1 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
exit /b %errorlevel%

:wait
rem %1 = url, %2 = timeout seconds
powershell -NoProfile -Command ^
  "$deadline=(Get-Date).AddSeconds(%~2); while((Get-Date) -lt $deadline){ try { $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 '%~1'; if($r.StatusCode -eq 200){ exit 0 } } catch {}; Start-Sleep -Milliseconds 500 }; exit 1"
exit /b %errorlevel%
