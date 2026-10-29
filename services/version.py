"""Номер версии приложения. Единственный источник — pyproject.toml ([project] version).

Сборки кладут pyproject.toml рядом с кодом (flet pack — через --add-data, flet build — вместе с папкой
приложения), поэтому номер читается одинаково при запуске из исходников и в собранном приложении.
Скрипты сборки берут номер отсюда же: python -c "from services.version import VERSION; print(VERSION)".
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYPROJECT = os.path.join(ROOT, "pyproject.toml")


def read_version(path=PYPROJECT):
    """Первая строка version = "…" — это [project] version. Нет файла или строки — пустая строка."""
    try:
        with open(path, encoding="utf-8") as f:
            match = re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.MULTILINE)
    except OSError:
        return ""
    return match.group(1) if match else ""


VERSION = read_version()
