@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Dota 2 Match Lab - install

echo === Dota 2 Match Lab: installation ===
echo Folder: %CD%
echo.

if not exist "backend\requirements-dev.txt" (
  echo [ERROR] Project files were not found next to install.bat.
  echo         Download the WHOLE project ^(branch claude/dota-match-lab^), extract the archive
  echo         and run install.bat from the extracted folder. The folder must contain
  echo         "backend" and "frontend" subfolders.
  goto :fail
)

rem ---- find Python 3.12+ ------------------------------------------------------
set "PY="
for %%C in ("py -3.13" "py -3.12" "py -3" "python" "python3") do (
  if not defined PY (
    %%~C -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul && set "PY=%%~C"
  )
)
if not defined PY (
  echo [ERROR] Python 3.12 or newer was not found.
  echo         Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH",
  echo         then close this window and run install.bat again.
  goto :fail
)
echo Python: %PY%
%PY% --version

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js was not found. Install Node.js 20 LTS or newer from https://nodejs.org/
  echo         then close this window and run install.bat again.
  goto :fail
)
echo Node.js:
node --version
echo.

echo [1/4] Creating Python virtual environment...
if not exist "backend\.venv\Scripts\python.exe" (
  %PY% -m venv backend\.venv
  if errorlevel 1 goto :fail
)

echo [2/4] Installing backend dependencies (may take a few minutes)...
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
if errorlevel 1 goto :fail

if not exist "backend\.env" copy /y "backend\.env.example" "backend\.env" >nul
if not exist "frontend\.env" copy /y "frontend\.env.example" "frontend\.env" >nul

echo [3/4] Installing frontend dependencies (may take a few minutes)...
pushd frontend
call npm install --no-audit --no-fund
if errorlevel 1 (
  popd
  goto :fail
)
popd

echo [4/4] Creating database...
pushd backend
.venv\Scripts\python.exe -c "from app.config import get_settings; from app.db.session import init_engine, run_migrations; s=get_settings(); init_engine(s.database_url); run_migrations(s.database_url); print('database ready:', s.database_url)"
if errorlevel 1 (
  popd
  goto :fail
)
popd

echo.
echo ==========================================================
echo   Installation complete. Now run start.bat
echo ==========================================================
if /i not "%~1"=="/nopause" pause
exit /b 0

:fail
echo.
echo Installation FAILED. Read the messages above; see also TROUBLESHOOTING.md.
if /i not "%~1"=="/nopause" pause
exit /b 1
