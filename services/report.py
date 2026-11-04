"""Отчёт о проблеме: версия, система и конец журнала — без личных данных.

Ничего не отправляется само: кнопка в «Настройках» копирует отчёт и открывает страницу нового обращения
на GitHub с уже заполненным текстом, а отправляет его сам пользователь (бесплатно, без внешних сервисов).
"""
import getpass
import json
import os
import platform
import re
import sys
from urllib.parse import quote

from . import notify
from .version import VERSION

ISSUES = "https://github.com/Artist-huh/f1-analytics-hub/issues/new"
LOG_LINES = 60
MAX_URL = 7000          # GitHub и браузеры режут ссылки длиннее ~8 КБ: конец журнала укорачиваем под этот предел


def _platform():
    if notify.is_android():
        return "Android"
    if notify.is_ios():
        return "iPhone"
    # platform.release() называет Windows 11 «10» — номер сборки точнее (Windows 11 — сборки 22000 и выше)
    return f"{platform.system()} {platform.version()}"


def _short_path(path):
    """Короткое имя папки Windows (8.3, например A4F7~1): так записан TEMP, когда в имени кириллица."""
    if os.name != "nt" or not path:
        return ""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        n = ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, len(buf))
        return buf.value if 0 < n < len(buf) else ""
    except (OSError, AttributeError, ValueError):
        return ""


def _forms(value):
    """Как значение встречается в журнале: с \\ и с /, экранированным в JSON и закодированным в адресе."""
    out = set()
    for v in {value, value.replace("\\", "/")}:
        out |= {v, json.dumps(v, ensure_ascii=False)[1:-1], json.dumps(v)[1:-1], quote(v), quote(v, safe="")}
    return [f for f in out if len(f) >= 3]


def _mask(text, values, mask):
    for value in sorted(set(values), key=len, reverse=True):     # сначала длинные: путь целиком, потом части
        text = re.sub(re.escape(value), lambda m: mask, text, flags=re.IGNORECASE)
    return text


def sanitize(text):
    """Убрать то, что выдаёт человека: путь к домашней папке и имя пользователя (в путях к базе и журналу).
    Без учёта регистра (на Windows c:\\users и C:\\Users — одна папка), с коротким именем 8.3, с \\\\ из JSON
    и %XX из адресов (аудит, SEC-4)."""
    bundle = getattr(sys, "_MEIPASS", "")          # .exe: временная папка распаковки — внутри TEMP пользователя
    if bundle:
        text = _mask(text, _forms(bundle) + _forms(_short_path(bundle)), "<приложение>")   # SEC-9
    home = os.path.expanduser("~")
    if home and home != "~":
        text = _mask(text, _forms(home) + _forms(_short_path(home)), "~")
    try:
        user = getpass.getuser()
    except (OSError, KeyError, ImportError):    # на Android и в песочнице имени может не быть
        user = ""
    if len(user) >= 3:                          # короткое имя («a») заменило бы полстроки
        text = _mask(text, _forms(user), "<пользователь>")
    return text


def log_tail(path, lines=LOG_LINES):
    if not path:
        return "(журнал отключён)"
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            tail = f.readlines()[-lines:]
    except OSError as exc:
        return f"(журнал не прочитан: {exc.strerror or exc})"
    return "".join(tail).rstrip() or "(журнал пуст)"


def build(log_path, lines=LOG_LINES):
    """Текст отчёта (Markdown для GitHub)."""
    from importlib import metadata
    try:
        flet_version = metadata.version("flet")
    except metadata.PackageNotFoundError:
        flet_version = "?"
    head = [
        "**Что случилось:** _опишите, что вы делали и что пошло не так_",
        "",
        f"- Версия: {VERSION or '?'}",
        f"- Система: {_platform()}",
        f"- Python {platform.python_version()}, Flet {flet_version}",
    ]
    body = "\n".join(head) + "\n\n<details><summary>Журнал (последние строки)</summary>\n\n```\n"
    tail = log_tail(log_path, lines).replace("```", "`​``")   # ``` в журнале не закрывает блок кода
    return sanitize(body + tail + "\n```\n</details>\n")


def issue_url(body, title="Проблема в приложении"):
    return f"{ISSUES}?title={quote(title)}&body={quote(body)}"


def prepare(log_path):
    """-> (полный отчёт для буфера обмена, ссылка на новое обращение). В ссылку журнал входит, сколько влезет."""
    full = build(log_path)
    for lines in (LOG_LINES, 30, 15, 5, 0):
        url = issue_url(build(log_path, lines) if lines else build(None))
        if len(url) <= MAX_URL:
            return full, url
    return full, issue_url("")


if __name__ == "__main__":       # python -m services.report — посмотреть отчёт в консоли
    from . import log
    sys.stdout.write(build(log.log_path()))
