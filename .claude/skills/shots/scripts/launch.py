"""Запуск приложения сразу на нужном экране (для снимков).

Переменные окружения:
  SHOT   tab0..tab4 (Главная, Чемпионат, Календарь, Пилоты, Ещё) или sub:<имя> — live, compare, settings,
         driver_detail, team, history, title, predict, strategy, favorites, race_strategy, circuit
  WIDTH, HEIGHT  размер окна (по умолчанию 440×880 — телефон; 1100×800 — компьютер)
  LIT    превью стартовых огней на главной: сколько горит (0–5), независимо от даты гонки
  SCROLL прокрутить экран: end — до конца, число — на столько px вниз
  FROZEN=1  одинаковый снимок при каждом запуске (для сравнения с эталоном, tools/visual_check.py):
         данные — встроенный снимок data/seed.json во временной базе, сеть отключена, часы стоят на
         времени снимка плюс час
"""
import os
import sys
import threading

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, REPO)
os.chdir(REPO)


def freeze():
    """Режим FROZEN: до импорта приложения — своя пустая база (в неё загрузится data/seed.json), без сети,
    время — от момента снимка. Настройки и база пользователя не трогаются."""
    import json
    import tempfile
    import time

    os.environ["F1_HUB_DB"] = os.path.join(tempfile.mkdtemp(prefix="f1-frozen-"), "frozen.db")
    with open(os.path.join(REPO, "data", "seed.json"), encoding="utf-8") as f:
        t0 = json.load(f)["exported_at"] + 3600
    start, real_localtime, real_strftime = time.monotonic(), time.localtime, time.strftime
    time.time = lambda: t0 + (time.monotonic() - start)
    time.localtime = lambda secs=None: real_localtime(time.time() if secs is None else secs)
    time.strftime = lambda fmt, t=None: real_strftime(fmt, time.localtime() if t is None else t)

    import requests

    def offline(*args, **kwargs):
        raise requests.ConnectionError("FROZEN: сеть отключена для снимков")

    requests.adapters.HTTPAdapter.send = offline
    from services import f1live

    def no_stream(topics=None):
        raise f1live.F1LiveError("FROZEN: сеть отключена для снимков")

    f1live.fetch_state = no_stream


if os.environ.get("FROZEN"):
    freeze()

import flet as ft  # noqa: E402

import main as app  # noqa: E402

target = os.environ.get("SHOT", "tab0")
width = int(os.environ.get("WIDTH", "440"))
height = int(os.environ.get("HEIGHT", "880"))
holder = {}
orig_init = app.AppState.__init__


def init(self, page):
    orig_init(self, page)
    holder["state"] = self


app.AppState.__init__ = init


def wrapped(page):
    app.main(page)
    state = holder["state"]
    page.window.width, page.window.height = width, height
    page.update()
    if os.environ.get("THEME") or os.environ.get("FONT"):   # только на этот запуск, без сохранения
        import design_system as ds
        from ui import theming
        name, _, team = (os.environ.get("THEME") or ds.THEME).partition(":")
        if os.environ.get("FONT"):                          # FONT=1.3 — «Очень крупный» текст
            theming.apply(name, team or None, font_scale=os.environ["FONT"])
        state.on_theme_change(name, team or None)     # как в приложении: палитра, экраны и нижняя навигация
    if os.environ.get("LIT"):
        import ui.screens.home as home
        home.lights_lit = lambda seconds, live: int(os.environ["LIT"])

    def go():
        if target.startswith("tab"):
            state.open_tab(int(target[3:]))
        else:
            name = target.split(":", 1)[1]
            if name == "driver_detail" and state.standings:
                state.ui["driver_id"] = state.standings[0]["driver_id"]
            if name == "team" and state.constructors:
                state.ui["team"] = state.constructors[0]["name"]
            state.open_sub(name)
        state.render()
        if os.environ.get("SCROLL"):                     # прокрутка экрана: окно не бывает выше монитора
            threading.Timer(2.0, lambda: page.run_task(scroll)).start()

    async def scroll():
        """SCROLL=end — до конца, SCROLL=600 — на 600 px вниз. Прокручивается самая большая колонка экрана."""
        value = os.environ["SCROLL"]
        cols = [c for c in _walk(page) if isinstance(c, ft.Column) and c.scroll]
        if cols:
            await cols[-1].scroll_to(offset=-1 if value == "end" else float(value), duration=0)

    threading.Timer(2.0, lambda: app.run_on_ui(page, go)).start()


def _walk(node, seen=None):
    """Все элементы страницы: содержимое Flet 1.0 лежит в controls / content / views."""
    seen = seen if seen is not None else set()
    if node is None or id(node) in seen:
        return
    seen.add(id(node))
    yield node
    for attr in ("views", "controls", "content"):
        child = getattr(node, attr, None)
        for item in child if isinstance(child, list) else [child]:
            if isinstance(item, ft.BaseControl):
                yield from _walk(item, seen)


ft.run(wrapped, assets_dir=app.ASSETS_DIR)
