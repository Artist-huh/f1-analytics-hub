@echo off
rem ===== F1 Analytics Hub: build a single-file dist\F1AnalyticsHub.exe =====
rem flet pack = PyInstaller + the Flet desktop client inside the .exe (no Python needed on the target PC).
rem Keep this file ASCII-only: cmd.exe misparses UTF-8 batch files with non-ASCII text.
cd /d "%~dp0"

set "PY=python"
set "FLET=flet"
if exist "venv\Scripts\python.exe" (
    set "PY=venv\Scripts\python.exe"
    set "FLET=venv\Scripts\flet.exe"
)

echo [1/4] Installing dependencies
"%PY%" -m pip install -q -r requirements.txt pyinstaller || goto :fail

echo [2/4] Running tests
set "F1_HUB_LOG=off"
"%PY%" -m unittest discover -s tests -t . || goto :fail
set "F1_HUB_LOG="

echo [3/4] Refreshing the bundled data snapshot (needs internet; otherwise data\seed.json is kept)
"%PY%" -m services.seed export --refresh || echo Snapshot not refreshed - using the existing data\seed.json

echo [4/4] Building
"%FLET%" pack main.py -y --name F1AnalyticsHub --icon assets\icon.ico ^
    --add-data "assets;assets" "data;data" ^
    --product-name "F1 Analytics Hub" --file-description "F1 Analytics Hub" ^
    --product-version "2.2.0" --file-version "2.2.0.0" ^
    --company-name "F1 Hub" --copyright "MIT License" ^
    --pyinstaller-build-args=--exclude-module=PIL ^
    --pyinstaller-build-args=--exclude-module=psutil ^
    --pyinstaller-build-args=--exclude-module=tkinter ^
    --pyinstaller-build-args=--exclude-module=tests ^
    --pyinstaller-build-args=--collect-all=desktop_notifier ^
    --pyinstaller-build-args=--collect-submodules=winrt ^
    --pyinstaller-build-args=--collect-all=faster_whisper ^
    --pyinstaller-build-args=--collect-binaries=ctranslate2 ^
    --pyinstaller-build-args=--exclude-module=onnxruntime || goto :fail

echo.
echo Done: dist\F1AnalyticsHub.exe
exit /b 0

:fail
echo Build stopped because of an error.
exit /b 1
