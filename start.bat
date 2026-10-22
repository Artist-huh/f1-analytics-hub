@echo off
rem ===== F1 Analytics Hub launcher (development mode) =====
rem Keep this file ASCII-only: cmd.exe misparses UTF-8 batch files with non-ASCII text.
cd /d "%~dp0"
echo ========================================
echo   F1 Analytics Hub - Launcher
echo ========================================
echo.

set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"

"%PY%" --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

"%PY%" -c "import flet, requests" >nul 2>&1
if errorlevel 1 (
    echo [!] Installing dependencies from requirements.txt ...
    "%PY%" -m pip install -q -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Could not install dependencies
        pause
        exit /b 1
    )
)

echo Starting the app...
"%PY%" main.py
if errorlevel 1 (
    echo.
    echo [ERROR] The app exited with an error. See %USERPROFILE%\.ferrari_leclerc_hub\f1_hub.log
    pause
)
