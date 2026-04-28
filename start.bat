@echo off
title Customer Retention AI Agent - Launcher
color 0A

echo.
echo  =========================================
echo   Customer Retention AI Agent
echo   Starting all services...
echo  =========================================
echo.

:: Kill anything already on port 8000 or 5173
echo  [1/4] Clearing ports 8000 and 5173...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 "') do (
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5173 "') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: Start backend
echo  [2/4] Starting backend (FastAPI on port 8000)...
start "AI Agent - Backend" cmd /k "cd /d "%~dp0backend" && uvicorn app.main:app --reload --port 8000"

:: Wait for backend to be ready
echo  [3/4] Starting frontend (Vite on port 5173)...
timeout /t 3 /nobreak >nul
start "AI Agent - Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

:: Wait then open browser
echo  [4/4] Opening browser in 5 seconds...
timeout /t 5 /nobreak >nul
start "" "http://localhost:5173"

echo.
echo  =========================================
echo   Both servers are running.
echo   App:     http://localhost:5173
echo   API:     http://localhost:8000/docs
echo.
echo   Close this window anytime.
echo   The two server windows run independently.
echo  =========================================
echo.
pause
