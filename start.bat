@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Dota 2 Match Lab

set "ROOT=%~dp0"
set "RUN=%ROOT%.run"
set "BACKEND_URL=http://127.0.0.1:8000"
set "FRONTEND_URL=http://localhost:5173"
if not exist "%RUN%" mkdir "%RUN%"

rem ---- dependency checks -------------------------------------------------
if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERROR] Backend environment missing. Run install.bat first.
  exit /b 1
)
if not exist "frontend\node_modules" (
  echo [ERROR] Frontend dependencies missing. Run install.bat first.
  exit /b 1
)
where npm >nul 2>nul || (echo [ERROR] npm not found in PATH. & exit /b 1)

rem ---- port checks ------------------------------------------------------------
netstat -ano | findstr /r /c:":8000 .*LISTENING" >nul && (
  echo [ERROR] Port 8000 is already in use. Run stop.bat or free the port.
  exit /b 1
)
netstat -ano | findstr /r /c:":5173 .*LISTENING" >nul && (
  echo [ERROR] Port 5173 is already in use. Run stop.bat or free the port.
  exit /b 1
)

rem ---- start backend (one process for all sessions and all 10 bots) --------
echo Starting backend...
powershell -NoProfile -Command ^
  "$p = Start-Process -FilePath '%ROOT%backend\.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port','8000' -WorkingDirectory '%ROOT%backend' -WindowStyle Hidden -RedirectStandardOutput '%RUN%\backend.out.log' -RedirectStandardError '%RUN%\backend.err.log' -PassThru; $p.Id | Out-File -Encoding ascii '%RUN%\backend.pid'"
if errorlevel 1 (echo [ERROR] Could not start the backend. & exit /b 1)

call :wait "%BACKEND_URL%/api/health" 60 || (
  echo [ERROR] Backend did not become healthy. Last log lines:
  powershell -NoProfile -Command "Get-Content '%RUN%\backend.err.log' -Tail 20"
  call "%ROOT%stop.bat" >nul
  exit /b 1
)
echo Backend is up.

rem ---- start frontend -------------------------------------------------------------
echo Starting frontend...
powershell -NoProfile -Command ^
  "$p = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c','npm run dev' -WorkingDirectory '%ROOT%frontend' -WindowStyle Hidden -RedirectStandardOutput '%RUN%\frontend.out.log' -RedirectStandardError '%RUN%\frontend.err.log' -PassThru; $p.Id | Out-File -Encoding ascii '%RUN%\frontend.pid'"
if errorlevel 1 (echo [ERROR] Could not start the frontend. & call "%ROOT%stop.bat" >nul & exit /b 1)

call :wait "%FRONTEND_URL%" 60 || (
  echo [ERROR] Frontend did not start. Last log lines:
  powershell -NoProfile -Command "Get-Content '%RUN%\frontend.out.log' -Tail 20"
  call "%ROOT%stop.bat" >nul
  exit /b 1
)

echo.
echo ==========================================================
echo   Dota 2 Match Lab is running
echo   Web panel : %FRONTEND_URL%
echo   Backend   : %BACKEND_URL%
echo   API docs  : %BACKEND_URL%/docs
echo   Logs      : %RUN%\*.log and backend\logs\app.jsonl
echo   Stop with : stop.bat
echo ==========================================================
start "" "%FRONTEND_URL%"
exit /b 0

rem ---- helpers -------------------------------------------------------------------------
:wait
rem %1 = url, %2 = timeout seconds
powershell -NoProfile -Command ^
  "$deadline=(Get-Date).AddSeconds(%~2); while((Get-Date) -lt $deadline){ try { $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 '%~1'; if($r.StatusCode -eq 200){ exit 0 } } catch {}; Start-Sleep -Milliseconds 500 }; exit 1"
exit /b %errorlevel%
