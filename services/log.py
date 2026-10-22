"""Журнал приложения: консоль + файл с ротацией (рядом с БД).

F1_HUB_LOG=off отключает запись в файл (используется в тестах).
"""
import logging
import logging.handlers
import os
import sys
import threading

from . import db

_lock = threading.Lock()
_configured = False
_log_file = None


def log_path():
    """Путь к файлу журнала (или None, если файловый журнал отключён)."""
    setup()
    return _log_file


def setup():
    global _configured, _log_file
    with _lock:
        if _configured:
            return
        root = logging.getLogger("f1hub")
        root.setLevel(logging.INFO)
        root.propagate = False
        fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
        if sys.stderr is not None:  # в оконной сборке .exe (--noconsole) консоли нет
            console = logging.StreamHandler()
            console.setFormatter(fmt)
            root.addHandler(console)
        if os.environ.get("F1_HUB_LOG") != "off":
            try:
                path = db.db_path().parent / "f1_hub.log"
                path.parent.mkdir(parents=True, exist_ok=True)
                handler = logging.handlers.RotatingFileHandler(
                    path, maxBytes=256 * 1024, backupCount=2, encoding="utf-8")
                handler.setFormatter(fmt)
                root.addHandler(handler)
                _log_file = str(path)
            except OSError as exc:  # нет прав на запись — работаем только с консолью
                root.warning("файл журнала недоступен: %s", exc)
        _configured = True


def get(name):
    setup()
    return logging.getLogger(f"f1hub.{name}")
