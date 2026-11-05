@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
set "RUN=%~dp0.run"

echo === Launcher: stop ===

rem 1) Graceful: ask Launcher to shut down (saves logs, closes the database cleanly).
powershell -NoProfile -Command ^
  "try { Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/system/shutdown' -Headers @{ 'X-Launcher-Request' = '1' } -TimeoutSec 3 | Out-Null; Write-Host 'Graceful shutdown requested...' } catch { Write-Host 'Launcher did not answer (maybe not running).' }"

rem 2) Wait up to 10 s for port 8000 to be released.
powershell -NoProfile -Command ^
  "$d=(Get-Date).AddSeconds(10); while((Get-Date) -lt $d){ if(-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)){ exit 0 }; Start-Sleep -Milliseconds 300 }; exit 1"
if errorlevel 1 (
  echo Launcher did not stop in time - forcing.
  call :kill launcher 8000
) else (
  echo Launcher stopped.
)
if exist "%RUN%\launcher.pid" del /q "%RUN%\launcher.pid" >nul 2>nul

rem Legacy cleanup: processes left by the previous version (backend + Vite on 5173).
call :kill backend 0
call :kill frontend 5173

if /i not "%~1"=="/nopause" pause
exit /b 0

:kill
rem %1 = pid-file name, %2 = port (0 = none)
if exist "%RUN%\%1.pid" (
  set /p PID=<"%RUN%\%1.pid"
  call :tree %1
  del /q "%RUN%\%1.pid" >nul 2>nul
)
if not "%2"=="0" powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort %2 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Write-Host ('Stopping listener on port %2, PID ' + $_.OwningProcess); taskkill /PID $_.OwningProcess /T /F | Out-Null }"
exit /b 0

:tree
if defined PID (
  echo Stopping %1 ^(PID %PID%^)
  taskkill /PID %PID% /T /F >nul 2>nul
)
set "PID="
exit /b 0
