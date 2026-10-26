#!/bin/sh
# shoot.sh <папка> <имя> <SHOT> [WIDTH] [HEIGHT] — снять экран приложения в <папка>/<имя>.png
# Пример: sh shoot.sh "$TMP/shots" home tab0          LIT=3 sh shoot.sh "$TMP/shots" lights tab0
# WAIT — сколько секунд ждать отрисовки (по умолчанию 22: первый запуск окна Flet медленный)
D="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$D/../../../.." && pwd)"
OUT="$1"; NAME="$2"
mkdir -p "$OUT"
SHOT="$3" WIDTH="${4:-440}" HEIGHT="${5:-880}" F1_HUB_LOG=off \
    "$REPO/venv/Scripts/python.exe" "$D/launch.py" >"$OUT/$NAME.log" 2>&1 &
PID=$!
sleep "${WAIT:-22}"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w "$D/capture.ps1")" \
    -Out "$(cygpath -w "$OUT/$NAME.png")"
kill $PID 2>/dev/null
taskkill //F //IM flet.exe >/dev/null 2>&1
wait $PID 2>/dev/null
