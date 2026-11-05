@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Dota 2 Match Lab

set "ROOT=%~dp0"
set "RUN=%ROOT%.run"
set "BACKEND_URL=http://127.0.0.1:8000"
set "FRONTEND_URL=http://localhost:5173"
if not exist "%RUN%" mkdir "%RUN%"

echo === Dota 2 Match Lab: start ===
echo Folder: %CD%
echo.

rem ---- dependency checks -------------------------------------------------
if not exist "backend\app\main.py" (
  echo [ERROR] Project files were not found next to start.bat. Extract the whole project first.
  goto :fail
)
if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERROR] Backend is not installed. Run install.bat first and wait for "Installation complete".
  goto :fail
)
if not exist "frontend\node_modules" (
  echo [ERROR] Frontend is not installed. Run install.bat first and wait for "Installation complete".
  goto :fail
)
where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm was not found in PATH. Reinstall Node.js and reopen the window.
  goto :fail
)

rem ---- port checks (PowerShell works on any Windows language) ---------------
call :port_busy 8000 && (
  echo [ERROR] Port 8000 is already in use. Run stop.bat, then start.bat again.
  goto :fail
)
call :port_busy 5173 && (
  echo [ERROR] Port 5173 is already in use. Run stop.bat, then start.bat again.
  goto :fail
)

rem ---- start backend (one process for all sessions and all 10 bots) --------
echo [1/2] Starting backend...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Start-Process -FilePath '%ROOT%backend\.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port','8000' -WorkingDirectory '%ROOT%backend' -WindowStyle Hidden -RedirectStandardOutput '%RUN%\backend.out.log' -RedirectStandardError '%RUN%\backend.err.log' -PassThru; $p.Id | Out-File -Encoding ascii '%RUN%\backend.pid'"
if errorlevel 1 (
  echo [ERROR] Could not start the backend.
  goto :fail
)
call :wait "%BACKEND_URL%/api/health" 60
if errorlevel 1 (
  echo [ERROR] Backend did not start. Last lines of .run\backend.err.log:
  powershell -NoProfile -Command "Get-Content -Path '%RUN%\backend.err.log' -Tail 25"
  call "%ROOT%stop.bat" /nopause >nul
  goto :fail
)
echo       Backend is up: %BACKEND_URL%

rem ---- start frontend -------------------------------------------------------------
echo [2/2] Starting frontend...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c','npm run dev' -WorkingDirectory '%ROOT%frontend' -WindowStyle Hidden -RedirectStandardOutput '%RUN%\frontend.out.log' -RedirectStandardError '%RUN%\frontend.err.log' -PassThru; $p.Id | Out-File -Encoding ascii '%RUN%\frontend.pid'"
if errorlevel 1 (
  echo [ERROR] Could not start the frontend.
  call "%ROOT%stop.bat" /nopause >nul
  goto :fail
)
call :wait "http://127.0.0.1:5173" 90
if errorlevel 1 (
  echo [ERROR] Frontend did not start. Last lines of .run\frontend.out.log / .err.log:
  powershell -NoProfile -Command "Get-Content -Path '%RUN%\frontend.out.log' -Tail 15; Get-Content -Path '%RUN%\frontend.err.log' -Tail 15"
  call "%ROOT%stop.bat" /nopause >nul
  goto :fail
)

echo.
echo ==========================================================
echo   Dota 2 Match Lab is running
echo   Web panel : %FRONTEND_URL%
echo   Backend   : %BACKEND_URL%
echo   API docs  : %BACKEND_URL%/docs
echo   Logs      : .run\*.log and backend\logs\app.jsonl
echo   Stop with : stop.bat
echo ==========================================================
start "" "%FRONTEND_URL%"
echo You can close this window - the lab keeps running in the background.
if /i not "%~1"=="/nopause" pause
exit /b 0

:fail
echo.
echo Start FAILED. Read the messages above; see also TROUBLESHOOTING.md.
if /i not "%~1"=="/nopause" pause
exit /b 1

rem ---- helpers -------------------------------------------------------------------------
:port_busy
rem exit code 0 if something listens on port %1
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %1 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
exit /b %errorlevel%

:wait
rem %1 = url, %2 = timeout seconds
powershell -NoProfile -Command ^
  "$deadline=(Get-Date).AddSeconds(%~2); while((Get-Date) -lt $deadline){ try { $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 '%~1'; if($r.StatusCode -eq 200){ exit 0 } } catch {}; Start-Sleep -Milliseconds 500 }; exit 1"
exit /b %errorlevel%
