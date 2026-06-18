@echo off
title ACS - AI Creative Studio
cd /d "%~dp0"

:: ── Find Python ───────────────────────────────────────────────────────────
set "PY="
if exist "%~dp0.python_path" (
    set /p PY=<"%~dp0.python_path"
    set "PY=%PY:"=%"
)
if not defined PY (
    for %%v in (312 311 310 313) do (
        if not defined PY (
            if exist "C:\Python%%v\python.exe"                             set "PY=C:\Python%%v\python.exe"
            if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe"
        )
    )
)
if not defined PY set "PY=python"

:: ── Check installed ────────────────────────────────────────────────────────
if not exist "backend\app.py" (
    echo  [!] ACS is not installed correctly.
    echo      Please run install.bat first.
    pause & exit /b 1
)
if not exist "frontend\dist\index.html" (
    echo  [!] Frontend not built.
    echo      Please run install.bat first.
    pause & exit /b 1
)

:: ── Start Ollama silently if not running ──────────────────────────────────
curl -s http://localhost:11434 >nul 2>&1
if errorlevel 1 (
    echo  Starting Ollama...
    start "" /min "C:\Users\%USERNAME%\AppData\Local\Programs\Ollama\ollama app.exe" 2>nul
    timeout /t 3 /nobreak >nul
)

:: ── Open browser then start backend ───────────────────────────────────────
start "" http://localhost:7860
echo  ACS is starting... the browser will open automatically.
echo  (Close this window to stop ACS)
echo.
"%PY%" backend\app.py
