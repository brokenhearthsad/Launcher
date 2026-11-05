@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "RUN=%~dp0.run"

call :kill frontend 5173
call :kill backend 8000
echo Dota 2 Match Lab stopped.
exit /b 0

:kill
rem %1 = name, %2 = port. Kills the recorded process tree, then anything still listening on the port.
if exist "%RUN%\%1.pid" (
  set /p PID=<"%RUN%\%1.pid"
  call :tree %1
  del /q "%RUN%\%1.pid" >nul 2>nul
)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":%2 .*LISTENING"') do (
  echo Stopping %1 listener PID %%p
  taskkill /PID %%p /T /F >nul 2>nul
)
exit /b 0

:tree
if defined PID (
  echo Stopping %1 ^(PID %PID%^)
  taskkill /PID %PID% /T /F >nul 2>nul
)
set "PID="
exit /b 0
