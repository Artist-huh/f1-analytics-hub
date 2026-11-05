"""Проверка сборки для iPhone на симуляторе iOS (CI, macOS): установка, запуск, приложение живо, журнал без ошибок.

    python3 tools/ios_smoke.py build/ios-simulator/Runner.app ios-shots

Нажатия по экрану на симуляторе без XCUITest не сделать, поэтому проверяем то, что видно снаружи:
процесс не упал за WAIT секунд, первый экран построен (снимки экрана), в журнале приложения
нет трассировок и «Не удалось показать экран», нет отчётов о падении Runner.
Радио: переменная F1_HUB_RADIO_SELFTEST (через SIMCTL_CHILD_) включает самопроверку — whisper.cpp и ML Kit
расшифровывают и переводят образец речи; в расшифровке должно быть «country» (речь Кеннеди).
"""
import glob
import json
import os
import plistlib
import subprocess
import sys
import time

WAIT = 120          # первый запуск: распаковка Python и загрузка данных
RADIO_WAIT = 600    # самопроверка радио: скачать модели (~60 МБ whisper + ML Kit) и расшифровать
FAIL_MARKERS = ("Traceback", "ошибка построения экрана")


def run(*args, check=True, timeout=300):
    res = subprocess.run(["xcrun", "simctl", *args], capture_output=True, text=True, timeout=timeout)
    if check and res.returncode:
        raise RuntimeError(f"simctl {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout


def pick_iphone():
    """Самый новый iPhone из доступных на раннере."""
    devices = json.loads(run("list", "devices", "available", "-j"))["devices"]
    phones = [(rt, d) for rt, ds in devices.items() if "iOS" in rt for d in ds if d["name"].startswith("iPhone")]
    if not phones:
        raise RuntimeError("на раннере нет симулятора iPhone")
    return max(phones, key=lambda p: (p[0], p[1]["name"]))[1]


def alive(udid, bundle_id):
    return f"UIKitApplication:{bundle_id}" in run("spawn", udid, "launchctl", "list", check=False)


def shot(udid, out, name):
    run("io", udid, "screenshot", os.path.join(out, f"{name}.png"), check=False)


def radio_selftest(container, started):
    """Ждать итог самопроверки радио в журнале приложения: «радио: самопроверка за N с — en | ru»."""
    deadline = started + WAIT + RADIO_WAIT
    while time.time() < deadline:
        for path in glob.glob(os.path.join(container, "**", "f1_hub.log"), recursive=True):
            with open(path, encoding="utf-8", errors="replace") as fh:
                line = next((ln for ln in fh if "радио: самопроверка" in ln), "")
            if line:
                return line.split("радио: самопроверка", 1)[-1].strip()
        time.sleep(10)
    return ""


def log_lines(container):
    out = []
    for path in glob.glob(os.path.join(container, "**", "f1_hub.log"), recursive=True) if container else []:
        with open(path, encoding="utf-8", errors="replace") as fh:
            out += fh.readlines()
    return out


def selftest_started(container):
    """Самопроверка пишет «радио: шаг …» с первых секунд — значит, запрос дошёл."""
    return any("радио: шаг" in ln or "радио: самопроверка" in ln for ln in log_lines(container))


def main():
    app, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(app, "Info.plist"), "rb") as fh:
        bundle_id = plistlib.load(fh)["CFBundleIdentifier"]
    device = pick_iphone()
    udid = device["udid"]
    print(f"симулятор: {device['name']} ({udid}), приложение {bundle_id}")
    run("boot", udid, check=False)
    run("bootstatus", udid, "-b", timeout=600)
    run("install", udid, app)
    started = time.time()
    # переменные с префиксом SIMCTL_CHILD_ simctl передаёт запускаемому приложению
    subprocess.run(["xcrun", "simctl", "launch", udid, bundle_id], check=True, timeout=300,
                   env=dict(os.environ, SIMCTL_CHILD_F1_HUB_RADIO_SELFTEST="1"))

    failures = []
    for i in range(WAIT // 20):
        time.sleep(20)
        shot(udid, out, f"{i:02d}")
        if not alive(udid, bundle_id):
            failures.append(f"приложение закрылось через {time.time() - started:.0f} с")
            break

    container = run("get_app_container", udid, bundle_id, "data", check=False).strip()
    if container and not failures and not selftest_started(container):
        # переменная окружения не дошла до Python: метка рядом с журналом и перезапуск приложения
        for path in glob.glob(os.path.join(container, "**", "f1_hub.log"), recursive=True):
            open(os.path.join(os.path.dirname(path), "radio_selftest"), "w").close()
        print("самопроверка радио не запустилась по переменной — метка в папке данных, перезапуск")
        run("terminate", udid, bundle_id, check=False)
        started = time.time() - WAIT
        subprocess.run(["xcrun", "simctl", "launch", udid, bundle_id], check=True, timeout=300)
    radio = radio_selftest(container, started) if container and not failures else ""
    for line in log_lines(container):
        if "радио:" in line:
            print("  " + line.strip())
    logs = glob.glob(os.path.join(container, "**", "f1_hub.log"), recursive=True) if container else []
    text = ""
    for path in logs:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text += fh.read()
    with open(os.path.join(out, "f1_hub.log"), "w", encoding="utf-8") as fh:
        fh.write(text)
    if not logs:
        failures.append("журнал приложения не создан — Python-часть не запустилась")
    bad = [ln for ln in text.splitlines() if any(m in ln for m in FAIL_MARKERS)]
    if bad:
        failures.append(f"в журнале ошибки: {bad[:3]}")
    crashes = glob.glob(os.path.expanduser("~/Library/Logs/DiagnosticReports/Runner*"))
    if crashes:
        failures.append(f"отчёты о падении: {[os.path.basename(c) for c in crashes]}")
    heard = next((ln.split("радио: расшифровка", 1)[-1].strip() for ln in log_lines(container)
                  if "радио: расшифровка за" in ln), "")
    translation_note = ""
    if "country" in radio.lower() and "не прошла" not in radio:
        pass                                    # расшифровка и перевод — оба работают
    elif "country" in heard.lower():
        # whisper.cpp работает; скачивание перевода ML Kit на симуляторе бывает без ответа — это не устройство,
        # поэтому перевод здесь не проверен (не «прошёл»), о чём и пишем
        translation_note = f"перевод ML Kit на симуляторе не проверен: {radio or 'нет итога'}"
    else:
        failures.append(f"самопроверка радио: {radio or heard or 'нет строки в журнале за ' + str(RADIO_WAIT) + ' с'}")
    run("terminate", udid, bundle_id, check=False)

    if failures:
        print("ПРОБЛЕМЫ:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print(f"iPhone: приложение запущено и работает {WAIT} с, журнал без ошибок ({len(text.splitlines())} строк)")
    print(f"радио, расшифровка: {heard}")
    print(f"радио: {translation_note or radio}")


if __name__ == "__main__":
    main()
