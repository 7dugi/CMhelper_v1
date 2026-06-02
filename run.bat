@echo off
chcp 65001 > nul
title CMhelper v1

echo.
echo  ==========================================
echo       CMhelper v1  -  Starting...
echo  ==========================================
echo.

:: ─── Kill any previous instances on these ports ─────────────────────────
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8001 "') do (
    taskkill /F /PID %%a > nul 2>&1
)

:: ─── Backend ─────────────────────────────────────────────────────────────
echo  [1/3] Installing Python packages (first run may take a moment)...
pip install -r "%~dp0CMhelper_web\backend\requirements.txt" -q --no-warn-script-location 2>nul

echo  [2/3] Starting Backend  (http://localhost:8001) ...
start "CMhelper-Backend" cmd /k "cd /d "%~dp0CMhelper_web\backend" && uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"

timeout /t 4 /nobreak > nul

:: ─── Frontend ─────────────────────────────────────────────────────────────
echo  [3/3] Starting Frontend (http://localhost:5173) ...
start "CMhelper-Frontend" cmd /k "cd /d "%~dp0CMhelper_web\frontend" && npm run dev"

timeout /t 5 /nobreak > nul
start "" "http://localhost:5173"

echo.
echo  ==========================================
echo    OK  Frontend  : http://localhost:5173
echo    OK  API Docs  : http://localhost:8001/docs
echo  ==========================================
echo.
echo  Close the two black terminal windows to stop.
pause
