"""Общая часть дымовых тестов интерфейса (сами тесты — tests/test_ui_*.py).

Вместо настоящего Flet подставляется «всеядная» заглушка, которая запоминает дерево
элементов. Тесты ловят опечатки, неверные ключи данных и логические ошибки на каждом
экране и в каждом обработчике. Совместимость с реальным Flet они НЕ проверяют —
это делается запуском приложения.
"""
import asyncio
import glob
import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock


# ---------------------------------------------------------------- поддельный flet
class _Attr:
    """ft.Padding.symmetric(...), ft.FontWeight.BOLD и т.п. — и вызываемое, и значение."""
    def __init__(self, name):
        self.name = name

    def __call__(self, *a, **kw):
        return Ctl(self.name, *a, **kw)

    def __repr__(self):
        return self.name


class _Meta(type):
    def __getattr__(cls, item):
        if item.startswith("__"):
            raise AttributeError(item)
        return _Attr(f"{cls.__name__}.{item}")


class Ctl(metaclass=_Meta):
    def __init__(self, *args, **kw):
        self.args, self.kw = args, kw
        for k, v in kw.items():
            setattr(self, k, v)
        if args and not hasattr(self, "value") and not isinstance(args[0], (list, tuple)):
            self.value = args[0]

    def update(self):
        self.updated = getattr(self, "updated", 0) + 1

    def children(self):
        seen = set()
        values = list(self.args) + [v for k, v in vars(self).items() if k not in ("args", "kw")]
        for v in values:
            for x in (v if isinstance(v, (list, tuple)) else [v]):
                if isinstance(x, Ctl) and id(x) not in seen:
                    seen.add(id(x))
                    yield x


def walk(node):
    yield node
    for ch in node.children():
        yield from walk(ch)


def texts(node):
    return [str(n.value) for n in walk(node)
            if type(n).__name__ == "Text" and getattr(n, "value", None) not in (None, "")]


def make_fake_flet(name="flet"):
    mod = types.ModuleType(name)

    def __getattr__(attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        return type(attr, (Ctl,), {})
    mod.__getattr__ = __getattr__
    mod.run = lambda *a, **k: None
    return mod


class FakePage:
    def __init__(self, width=430):
        self.window = Ctl()
        self.width = width
        self.added, self.updates = [], 0
        self.navigation_bar = None
        self.dialogs = []

    def add(self, *c):
        self.added += c

    def update(self, *c):
        self.updates += 1

    def show_dialog(self, dialog):
        self.dialogs.append(dialog)

    def pop_dialog(self):
        return self.dialogs.pop() if self.dialogs else None


# flet подменяем ДО импорта интерфейса
sys.modules["flet"] = make_fake_flet()
sys.modules["flet.canvas"] = sys.modules["flet"].canvas = make_fake_flet("flet.canvas")
for _m in [m for m in sys.modules if m == "ui" or m.startswith("ui.") or m == "main"]:
    del sys.modules[_m]

import design_system  # noqa: E402
import main as app  # noqa: E402
from services import db, jolpica, media  # noqa: E402
from services import f1_api as api  # noqa: E402
from tests.test_data_layer import router  # noqa: E402
from ui import components  # noqa: E402
from ui.fmt import fmt_countdown, plural  # noqa: E402
from ui.screens import calendar, compare, driver_detail, drivers  # noqa: E402
from ui.state import AppState  # noqa: E402


def fill_db():
    """Реальные парсеры + подставной API (без OpenF1 и картинок), затем календарь с будущими датами."""
    with mock.patch.object(jolpica._session, "get", router()), mock.patch.object(jolpica, "MIN_INTERVAL", 0), \
            mock.patch.object(media, "refresh_refs", return_value=True), \
            mock.patch.object(media, "prefetch", return_value=None):
        assert api.refresh_all(force=True)
    now = time.time()

    def race(rnd, name, circuit, locality, start, country="Italy"):
        return {"round": str(rnd), "race_name": name, "circuit": circuit, "locality": locality, "country": country,
                "date": "2026-01-01", "start_ts": start,
                "sessions": [{"key": "Qualifying", "ts": start - 86400}, {"key": "Race", "ts": start}]}
    rows = [
        race(1, "Australian Grand Prix", "Albert Park", "Melbourne", now - 90 * 86400, "Australia"),
        race(2, "Chinese Grand Prix", "Shanghai", "Shanghai", now - 80 * 86400, "China"),
        race(3, "Japanese Grand Prix", "Suzuka", "Suzuka", now - 70 * 86400, "Japan"),
        race(4, "Italian Grand Prix", "Autodromo Nazionale di Monza", "Monza", now + 3 * 86400 + 5 * 3600 + 600),
        race(5, "Singapore Grand Prix", "Marina Bay", "Marina Bay", now + 10 * 86400, "Singapore"),
    ]
    db.save_schedule("2026", rows)


def add_podium():
    """Полный подиум на этапе 3 (в общих фикстурах у гонок подиум неполный)."""
    rows = [r for r in db.load_season_results() if r["round"] != "3"]
    podium = (("1", "leclerc", "Ferrari"), ("2", "antonelli", "Mercedes"), ("3", "lawson", "Racing Bulls"))
    for pos, did, team in podium:
        rows.append({"driver_id": did, "round": "3", "race_name": "Japanese GP", "circuit": "Suzuka",
                     "country": "Japan", "locality": "Suzuka", "date": "2026-04-05", "position": pos, "grid": pos,
                     "points": {"1": "25", "2": "18", "3": "15"}[pos], "status": "Finished", "team": team,
                     "fastest_rank": ""})
    db.save_season_results("2026", "3", rows)


def click_all(node, state):
    """Нажимает каждый on_click / on_select / on_change в дереве — обработчики не должны падать."""
    n = 0
    for c in list(walk(node)):
        for name in ("on_click", "on_select", "on_change"):
            fn = getattr(c, name, None)
            if callable(fn):
                ev = Ctl(control=Ctl(value=getattr(c, "value", None)))
                fn(ev)
                n += 1
    return n


def reset_design():
    """Тема, размер текста и «меньше движения» — общие для процесса. test_handlers нажимал «Очень крупный»
    и оставлял ×1.3 всем следующим тестам (они проверяли не тот размер, что думали)."""
    if design_system.FONT_SCALE != 1.0 or design_system.THEME != "dark" or design_system.REDUCE_MOTION:
        from ui import theming
        design_system.apply_reduce_motion(False)
        theming.apply("dark", None, font_scale=1.0)
        app.refresh_screens()


def join_workers(timeout=5.0):
    """Дождаться фоновых потоков экранов (ручное обновление, загрузка результатов):
    иначе поток может открыть временную БД, пока тест её удаляет (WinError 32)."""
    for t in threading.enumerate():
        if t is not threading.current_thread() and t.name.startswith(("f1-manual-refresh", "f1-results-")):
            t.join(timeout)


def clickable(tree, label):
    """Элементы с обработчиком on_click, внутри которых есть текст label (или это кнопка с такой подписью)."""
    return [n for n in walk(tree) if callable(getattr(n, "on_click", None))
            and (label in texts(n) or getattr(n, "value", None) == label)]


class UiTestCase(unittest.TestCase):
    """База тестов интерфейса: заглушка Flet, временная БД, страница-подделка."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["F1_HUB_DB"] = os.path.join(self.tmp.name, "ui.db")
        seed_env = mock.patch.dict(os.environ, {"F1_HUB_SEED": os.path.join(self.tmp.name, "no-seed.json"),
                                                "FLET_APP_STORAGE_DATA": self.tmp.name})   # модели радио и т. п.
        seed_env.start()   # снимок и встроенные картинки из data/ тестам не видны
        self.addCleanup(seed_env.stop)
        from services import archive
        offline = mock.patch.object(archive, "get",
                                    lambda key, fetch, ttl=None, on_done=None, force=False: db.load_archive(key)[0])
        offline.start()    # история и трассы: только кэш, без фоновых запросов в сеть
        self.addCleanup(offline.stop)
        from services import radio
        mock.patch.object(radio, "download_models").start()             # «Скачать модели» — без сети и диска
        from services import live
        self.live_refresh = mock.patch.object(live, "refresh").start()   # live-тайминг: без запросов к OpenF1
        self.addCleanup(mock.patch.stopall)
        live._state.update(data=None, error=None, loading=False, error_at=0.0, locked=False)
        api._state.update(error=None, fail_until=0.0)
        media.clear_memory()
        db.set_setting("onboarded", "1")   # знакомство при первом запуске — в своём тесте
        self.page = FakePage()
        self.state = AppState(self.page)
        self.renders = []
        self.state.render = lambda: self.renders.append(1)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.environ.pop, "F1_HUB_DB", None)
        self.addCleanup(api.shutdown)
        self.addCleanup(reset_design)   # тест нажал «Очень крупный» или тему — следующие не должны это унаследовать
        self.addCleanup(join_workers)   # раньше остальных cleanup: потоки ещё под моками

    def all_screens(self):
        yield from ((f"tab{i}", b) for i, b in enumerate(app.TABS))
        yield from app.SUBS.items()

    def build(self, name):
        return dict(self.all_screens())[name](self.state)

    def _main_with_loop(self):
        fill_db()
        page = FakePage()
        tasks = []
        page.run_task = tasks.append
        with mock.patch.object(api, "start_background_refresh", return_value=mock.Mock()), \
             mock.patch("threading.Thread.start"):
            app.main(page)
        startup, tasks[:] = list(tasks), []          # стартовые задачи (проверка настроек системы) — сразу
        for task in startup:
            asyncio.run(task())
        return page, tasks
