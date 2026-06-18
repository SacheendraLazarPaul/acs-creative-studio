@echo off
title ACS - Rebuilding UI
cd /d "%~dp0\frontend"

echo Rebuilding frontend...
if not exist "node_modules" call npm install
call npm run build
if errorlevel 1 ( echo Build FAILED! & pause & exit /b 1 )

echo Done! Starting server...
cd ..
start http://localhost:7860
timeout /t 2 /nobreak >nul
cd backend
python app.py
