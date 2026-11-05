@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
set "RUN=%~dp0.run"

echo === Dota 2 Match Lab: stop ===
call :kill frontend 5173
call :kill backend 8000
echo Dota 2 Match Lab stopped.
if /i not "%~1"=="/nopause" pause
exit /b 0

:kill
rem %1 = name, %2 = port. Kills the recorded process tree, then anything still listening on the port.
if exist "%RUN%\%1.pid" (
  set /p PID=<"%RUN%\%1.pid"
  call :tree %1
  del /q "%RUN%\%1.pid" >nul 2>nul
)
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort %2 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Write-Host ('Stopping %1 listener PID ' + $_.OwningProcess); taskkill /PID $_.OwningProcess /T /F | Out-Null }"
exit /b 0

:tree
if defined PID (
  echo Stopping %1 ^(PID %PID%^)
  taskkill /PID %PID% /T /F >nul 2>nul
)
set "PID="
exit /b 0
