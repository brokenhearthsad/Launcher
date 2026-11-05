@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Dota 2 Match Lab - install

echo === Dota 2 Match Lab: installation ===
where py >nul 2>nul && (set "PY=py -3.12") || (set "PY=python")
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.12+ not found. Install it from https://www.python.org/downloads/ and tick "Add to PATH".
  goto :fail
)
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 (
  echo [ERROR] Python 3.12 or newer is required.
  %PY% --version
  goto :fail
)
where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js not found. Install Node.js 20 LTS or newer from https://nodejs.org/
  goto :fail
)

echo [1/4] Creating Python virtual environment...
if not exist "backend\.venv\Scripts\python.exe" (
  %PY% -m venv backend\.venv || goto :fail
)
echo [2/4] Installing backend dependencies...
backend\.venv\Scripts\python.exe -m pip install --upgrade pip >nul
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt || goto :fail

if not exist "backend\.env" copy /y "backend\.env.example" "backend\.env" >nul
if not exist "frontend\.env" copy /y "frontend\.env.example" "frontend\.env" >nul

echo [3/4] Installing frontend dependencies...
pushd frontend
call npm install --no-audit --no-fund || (popd & goto :fail)
popd

echo [4/4] Creating database (Alembic migrations + 10 default participants)...
pushd backend
.venv\Scripts\python.exe -c "from app.config import get_settings; from app.db.session import init_engine, run_migrations; s=get_settings(); init_engine(s.database_url); run_migrations(s.database_url); print('database ready:', s.database_url)" || (popd & goto :fail)
popd

echo.
echo Installation complete. Run start.bat to launch the lab.
exit /b 0

:fail
echo.
echo Installation failed. See TROUBLESHOOTING.md.
exit /b 1
