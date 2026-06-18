@echo off
title AI Creative Studio - DEV
cd /d "%~dp0"

echo.
echo   DEV MODE (hot reload)
echo   =====================
echo   Backend  : http://localhost:7860  (API)
echo   Frontend : http://localhost:5173  (open THIS one)
echo.

:: locate python
set "PY="
if exist "C:\Python312\python.exe" set "PY=C:\Python312\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY set "PY=python"

:: start backend in its own window
start "ACS Backend" cmd /k ""%PY%" backend\app.py"

:: install frontend deps if needed, then run vite
cd frontend
if not exist "node_modules" (
  echo   [*] Installing frontend packages (first time)...
  call npm install
)
echo   [*] Starting Vite dev server...
timeout /t 3 /nobreak >nul
start http://localhost:5173
call npm run dev
