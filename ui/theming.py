"""Смена темы оформления на лету.

Экраны берут цвета через «from design_system import *» — значения копируются в модуль при
импорте. Поэтому после design_system.apply_theme() модули интерфейса перезагружаются
(importlib.reload), а main.refresh_screens() заново собирает таблицу экранов.
"""
import importlib
import pkgutil
import sys

import design_system as ds

# Порядок важен: компоненты и виджеты — раньше экранов; home — раньше экранов, которые из него импортируют.
FIRST = ["ui.components", "ui.widgets", "ui.screens.home"]


def _screen_modules():
    import ui.screens
    names = [f"ui.screens.{m.name}" for m in pkgutil.iter_modules(ui.screens.__path__)]
    return FIRST + sorted(n for n in names if n not in FIRST)


def apply(name="dark", team=None, font_scale=None):
    """Применить тему (и размер текста) и перезагрузить модули интерфейса. Возвращает итоговое имя темы."""
    if font_scale is not None:
        ds.apply_font_scale(font_scale)
    result = ds.apply_theme(name, team)
    for module in _screen_modules():
        if module in sys.modules:
            importlib.reload(sys.modules[module])
    return result
