@echo off
title J.A.R.V.I.S. System Boot

echo.
echo  ╔═══════════════════════════════════════════════════╗
echo  ║   J.A.R.V.I.S. — JUST A RATHER VERY              ║
echo  ║               INTELLIGENT SYSTEM                   ║
echo  ╚═══════════════════════════════════════════════════╝
echo.

:: Copy .env if not present
if not exist backend\.env (
    if exist .env.example (
        copy .env.example backend\.env >nul
        echo [SETUP] Copied .env.example to backend\.env
        echo [SETUP] Please edit backend\.env with your API keys, then re-run.
        pause
        start notepad backend\.env
        exit /b
    )
)

:: Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org
    pause
    exit /b 1
)

:: Install dependencies
echo [BOOT] Installing Python dependencies...
pip install -r backend\requirements.txt --quiet

:: Launch backend
echo [BOOT] Starting J.A.R.V.I.S. backend on http://localhost:8000
echo [BOOT] Opening browser...
start "" "http://localhost:8000"

cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
