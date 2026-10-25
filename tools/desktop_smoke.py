"""Проверка готовой сборки для компьютера (CI): Windows .exe или macOS .app запускается и работает.

    python tools/desktop_smoke.py dist/F1AnalyticsHub.exe
    python3 tools/desktop_smoke.py dist/F1AnalyticsHub.app/Contents/MacOS/F1AnalyticsHub

База и журнал — во временной папке (F1_HUB_DB), чтобы не трогать данные пользователя. Проверяем:
Python-часть стартовала (в журнале появилась первая запись — это и есть время запуска), процесс жив
через WAIT секунд, в журнале нет трассировок и «Не удалось показать экран».
"""
import os
import signal
import subprocess
import sys
import tempfile
import time

WAIT = 60
STARTUP_LIMIT = 45      # до первой записи в журнале (onefile .exe распаковывается при каждом запуске)
FAIL_MARKERS = ("Traceback", "ошибка построения экрана")


def stop(proc):
    if proc.poll() is not None:
        return
    if os.name == "nt":                    # onefile .exe запускает дочерние процессы (Python, окно Flet)
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        os.killpg(proc.pid, signal.SIGKILL)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # консоль Windows в CI — cp1252
    exe = os.path.abspath(sys.argv[1])
    tmp = tempfile.mkdtemp(prefix="f1hub-smoke-")
    log_path = os.path.join(tmp, "f1_hub.log")
    env = dict(os.environ, F1_HUB_DB=os.path.join(tmp, "f1_hub.db"))
    started = time.time()
    kw = {"start_new_session": True} if os.name != "nt" else {}
    proc = subprocess.Popen([exe], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)

    failures, first_log = [], None
    while time.time() - started < WAIT:
        time.sleep(2)
        if first_log is None and os.path.exists(log_path) and os.path.getsize(log_path):
            first_log = time.time() - started
        if proc.poll() is not None:
            failures.append(f"приложение закрылось через {time.time() - started:.0f} с (код {proc.returncode})")
            break
    stop(proc)

    text = ""
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    print(text[-3000:])
    if first_log is None:
        failures.append("журнал не появился — Python-часть не запустилась")
    elif first_log > STARTUP_LIMIT:
        failures.append(f"запуск слишком долгий: {first_log:.0f} с (предел {STARTUP_LIMIT} с)")
    bad = [ln for ln in text.splitlines() if any(m in ln for m in FAIL_MARKERS)]
    if bad:
        failures.append(f"в журнале ошибки: {bad[:3]}")
    if failures:
        print("ПРОБЛЕМЫ:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print(f"запуск: первая запись в журнале через {first_log:.1f} с, приложение работает {WAIT} с без ошибок")


if __name__ == "__main__":
    main()
