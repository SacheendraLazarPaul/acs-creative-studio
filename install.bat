@echo off
title ACS - Installer
cd /d "%~dp0"
color 0A

echo.
echo  ========================================
echo   ACS - AI Creative Studio  ^|  Installer
echo  ========================================
echo.

:: ── Check Python ──────────────────────────────────────────────────────────
echo [1/6] Checking Python...
set "PY="
for %%v in (312 311 310 313) do (
    if not defined PY (
        if exist "C:\Python%%v\python.exe"                             set "PY=C:\Python%%v\python.exe"
        if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe"
    )
)
if not defined PY (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    echo.
    echo  [!] Python not found.
    echo      Download from: https://www.python.org/downloads/
    echo      Install Python 3.10, 3.11 or 3.12 and run this installer again.
    echo.
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('"%PY%" --version 2^>^&1') do echo      Found: %%v

:: ── Check Node.js ─────────────────────────────────────────────────────────
echo.
echo [2/6] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [!] Node.js not found.
    echo      Download from: https://nodejs.org/  (LTS version)
    echo      Install Node.js and run this installer again.
    echo.
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo      Found: Node.js %%v

:: ── Check Ollama ──────────────────────────────────────────────────────────
echo.
echo [3/6] Checking Ollama...
ollama --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [!] Ollama not found.
    echo      Download from: https://ollama.com/download
    echo      Install Ollama and run this installer again.
    echo.
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('ollama --version 2^>^&1') do echo      Found: %%v

:: ── Install Python packages ────────────────────────────────────────────────
echo.
echo [4/6] Installing Python packages (this may take 5-10 minutes first time)...
echo      Please wait...
"%PY%" -m pip install --quiet --upgrade pip
"%PY%" -m pip install --quiet -r backend\requirements.txt
if errorlevel 1 (
    echo.
    echo  [!] Python package install failed.
    echo      Try running as Administrator or check your internet connection.
    echo.
    pause & exit /b 1
)
echo      Done.

:: ── Build frontend ────────────────────────────────────────────────────────
echo.
echo [5/6] Building the user interface...
cd frontend
if not exist "node_modules" (
    echo      Installing UI packages...
    call npm install --silent
    if errorlevel 1 (
        echo  [!] npm install failed. Check your internet connection.
        cd ..
        pause & exit /b 1
    )
)
call npm run build >nul 2>&1
if errorlevel 1 (
    echo  [!] UI build failed.
    cd ..
    pause & exit /b 1
)
cd ..
echo      Done.

:: ── Pull default AI model ──────────────────────────────────────────────────
echo.
echo [6/6] Setting up AI model...
echo      Checking if a text model is already downloaded...
ollama list 2>nul | findstr /i "dolphin llama mistral gemma" >nul
if errorlevel 1 (
    echo.
    echo  No AI model found. Downloading dolphin3:8b (4.9 GB)...
    echo  This is a one-time download. Please wait...
    echo.
    ollama pull dolphin3:8b
    if errorlevel 1 (
        echo  [!] Model download failed. You can download it later from the app.
    )
) else (
    echo      AI model already installed.
)

:: ── Save python path for launcher ──────────────────────────────────────────
echo "%PY%"> "%~dp0\.python_path"

:: ── Create desktop shortcut ────────────────────────────────────────────────
echo.
echo Creating desktop shortcut...
set "SHORTCUT=%USERPROFILE%\Desktop\ACS - AI Creative Studio.lnk"
set "TARGET=%~dp0ACS.bat"
set "ICON=%~dp0frontend\public\favicon.ico"
powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath='%TARGET%'; $s.WorkingDirectory='%~dp0'; if(Test-Path '%ICON%'){$s.IconLocation='%ICON%'}; $s.Save()" >nul 2>&1
echo      Shortcut created on Desktop.

:: ── Done ──────────────────────────────────────────────────────────────────
echo.
echo  ========================================
echo   Installation complete!
echo  ========================================
echo.
echo   To launch ACS:
echo    - Double-click "ACS - AI Creative Studio" on your Desktop
echo    - Or run ACS.bat in this folder
echo.
set /p LAUNCH="   Launch ACS now? (Y/N): "
if /i "%LAUNCH%"=="Y" call ACS.bat
