"""Проверка APK на Android-устройстве или эмуляторе через adb (запускается в CI).

    python tools/android_smoke.py build/apk/f1-analytics-hub.apk out_dir

Ставит приложение, проходит знакомство первого запуска (команда, пилоты, уведомления), ждёт главный
экран, проходит вкладки нижнего меню и делает скриншоты,
проверяет системную кнопку «назад», тестовое уведомление и виджет на главный экран, сохраняет logcat.
Элементы ищутся по тексту в дереве доступности (uiautomator dump) — Flutter его заполняет,
поэтому координаты не зашиты. Код выхода 1 — приложение не запустилось или упало.
"""
import re
import subprocess
import sys
import time
from pathlib import Path

PACKAGE = "com.f1hub.f1_analytics_hub"
ACTIVITY = f"{PACKAGE}/.MainActivity"
TABS = ["Чемпионат", "Календарь", "Пилоты", "Ещё"]


def adb(*args, check=True, timeout=120):
    res = subprocess.run(["adb", *args], capture_output=True, timeout=timeout)
    if check and res.returncode != 0:
        raise RuntimeError(f"adb {' '.join(args)}: {res.stderr.decode(errors='replace')}")
    return res.stdout.decode("utf-8", errors="replace")


def dump():
    """XML дерева доступности текущего экрана."""
    adb("shell", "uiautomator", "dump", "/sdcard/ui.xml", check=False)
    return adb("shell", "cat", "/sdcard/ui.xml", check=False)


def find(xml, label):
    """Центр первого элемента, у которого text или content-desc содержит label."""
    for m in re.finditer(r'<node [^>]*>', xml):
        node = m.group(0)
        text = " ".join(re.findall(r'(?:text|content-desc)="([^"]*)"', node))
        if label in text:
            b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', node)
            if b:
                x1, y1, x2, y2 = map(int, b.groups())
                return (x1 + x2) // 2, (y1 + y2) // 2
    return None


def wait_for(label, timeout=240):
    return wait_any([label], timeout)[1]


def wait_any(labels, timeout=240):
    """Первый из labels, появившийся на экране, и XML экрана (или None, None)."""
    end = time.time() + timeout
    while time.time() < end:
        xml = dump()
        if "isn't responding" in xml or "не отвечает" in xml:
            # зависание системного приложения эмулятора (лаунчер) закрывает экран — ждём, а не закрываем
            print("системное окно «не отвечает» — нажимаем «Wait»")
            tap("Wait", xml) or tap("Подождать", xml)
            time.sleep(2)
            continue
        for label in labels:
            if find(xml, label):
                return label, xml
        time.sleep(3)
    return None, None


def onboarding(out, failures):
    """Первый запуск: Ferrari -> «Дальше» (пилоты Ferrari отмечены сами) -> «Дальше» -> «Готово»."""
    shot(out, "00a_welcome_team")
    for step, label in (("команда", "Ferrari"), ("к пилотам", "Дальше"), ("к уведомлениям", "Дальше")):
        if not tap(label):
            failures.append(f"знакомство: не нажалось «{label}» ({step})")
            return
        time.sleep(3)
    shot(out, "00b_welcome_notify")
    if not tap("Готово"):
        failures.append("знакомство: нет кнопки «Готово»")


def driver_page(out, failures):
    """Пилоты -> первая карточка: страница пилота открывается поверх (фото «перелетает»),
    системная «назад» возвращает на список."""
    point = find(dump(), "Найдено")
    if not point:
        failures.append("страница пилота: нет списка пилотов")
        return
    adb("shell", "input", "tap", str(point[0]), str(point[1] + 260))
    if not wait_for("СТАТИСТИКА СЕЗОНА", timeout=30):
        failures.append("страница пилота не открылась")
        return
    shot(out, "04b_driver_page")
    adb("shell", "input", "keyevent", "4")
    time.sleep(3)
    if wait_for("Найдено", timeout=20):
        print("страница пилота: открылась поверх списка, «назад» вернул на список")
    else:
        failures.append("«назад» со страницы пилота не вернул на список")


def tap(label, xml=None):
    point = find(xml or dump(), label)
    if not point:
        return False
    adb("shell", "input", "tap", str(point[0]), str(point[1]))
    return True


def shot(out, name):
    data = subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True, timeout=60).stdout
    (out / f"{name}.png").write_bytes(data)
    print("скриншот:", name)


def foreground():
    out = adb("shell", "dumpsys", "activity", "activities", check=False)
    return PACKAGE in "".join(ln for ln in out.splitlines() if "mResumedActivity" in ln or "topResumedActivity" in ln)


def main():
    apk, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    failures = []
    adb("install", "-r", "-g", str(apk), timeout=600)            # -g: выдать разрешения (уведомления)
    adb("logcat", "-c", check=False)
    adb("shell", "am", "start", "-n", ACTIVITY)
    started = time.time()
    first, xml = wait_any(["Добро пожаловать", "F1 Hub"], timeout=300)   # первый запуск распаковывает Python
    print(f"первый экран: {first or 'НЕТ'} за {time.time() - started:.0f} с")
    if first == "Добро пожаловать":
        onboarding(out, failures)
        xml = wait_for("F1 Hub", timeout=60)
    print(f"главный экран: {'да' if xml else 'НЕТ'} за {time.time() - started:.0f} с")
    shot(out, "01_home")
    if not xml:
        failures.append("главный экран не появился")
    else:
        for i, tab in enumerate(TABS, start=2):
            if tap(tab):
                time.sleep(4)
                shot(out, f"{i:02d}_{tab}")
            else:
                failures.append(f"нет вкладки «{tab}»")
            if tab == "Пилоты":
                driver_page(out, failures)
        # «Ещё» -> Настройки -> тестовое уведомление
        if tap("Настройки"):
            time.sleep(4)
            shot(out, "06_settings")
            for _ in range(3):
                if tap("Проверить уведомление"):
                    break
                adb("shell", "input", "swipe", "540", "1800", "540", "700", "300", check=False)
                time.sleep(2)
            time.sleep(4)
            notes = adb("shell", "dumpsys", "notification", "--noredact", check=False)
            if f"pkg={PACKAGE}" in notes:
                print("уведомление: показано")
            else:
                failures.append("тестовое уведомление не появилось")
            adb("shell", "cmd", "statusbar", "expand-notifications", check=False)
            time.sleep(2)
            shot(out, "07_notification")
            adb("shell", "cmd", "statusbar", "collapse", check=False)
            time.sleep(1)
        # системная «назад»: подэкран -> вкладка -> «Главная» -> выход
        for _ in range(2):
            adb("shell", "input", "keyevent", "4")
            time.sleep(3)
        shot(out, "08_after_back")
        if not find(dump(), "F1 Hub"):
            failures.append("«назад» не вернул на главную")
        adb("shell", "input", "keyevent", "4")
        time.sleep(3)
        if foreground():
            failures.append("«назад» на главной не закрыл приложение")
        else:
            print("«назад»: подэкран -> вкладка -> главная -> выход")
    log = adb("logcat", "-d", check=False)
    (out / "logcat.txt").write_text(log, encoding="utf-8")
    crashes = [ln for ln in log.splitlines() if "FATAL EXCEPTION" in ln or "Traceback" in ln]
    if crashes:
        failures.append(f"в logcat ошибки: {crashes[:3]}")
    app_warnings = [ln for ln in log.splitlines() if "flet.python" in ln and
                    ("не запрошено" in ln or "не отправлено" in ln)]
    if app_warnings:
        failures.append(f"уведомления на Android: {app_warnings[:2]}")
    # виджет на главный экран: провайдер зарегистрирован, приложение передало ему данные
    widgets = adb("shell", "dumpsys", "appwidget", check=False)
    if "F1WidgetProvider" in widgets:
        print("виджет: провайдер зарегистрирован")
    else:
        failures.append("виджет F1 Hub не зарегистрирован в системе")
    widget_log = [ln for ln in log.splitlines() if "F1Widget" in ln or "виджет" in ln]
    if any("данные виджета обновлены" in ln for ln in widget_log):
        print("виджет: данные получены")
    else:
        failures.append(f"виджет не получил данные: {widget_log[-3:]}")
    if failures:
        print("ПРОБЛЕМЫ:\n  " + "\n  ".join(failures))
        return 1
    print("всё в порядке")
    return 0


if __name__ == "__main__":
    sys.exit(main())
