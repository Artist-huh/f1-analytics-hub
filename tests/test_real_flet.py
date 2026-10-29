"""Все экраны на настоящем Flet (в отдельном процессе).

test_ui_smoke подменяет Flet «всеядной» заглушкой — она принимает любые аргументы, поэтому опечатку
в имени параметра (например, radius= у Container) не видит. Здесь экраны строятся настоящими элементами
Flet: их конструкторы проверяют аргументы. Данные — встроенный снимок data/seed.json, сеть не нужна.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCRIPT = r'''
import json, sys, time, traceback
sys.path.insert(0, ".")
from unittest import mock
from services import f1_api, live, archive
f1_api.bootstrap()                                   # снимок data/seed.json в пустую БД
live.refresh = lambda on_done=None: None             # без сети
archive.get = lambda key, fetch, ttl=None, on_done=None, force=False: None
import main as app
from ui.state import AppState


class Page:
    width, height = 430, 900
    def __init__(self):
        self.window = mock.Mock()
    def update(self, *a): pass
    def run_task(self, *a, **k): pass
    def show_dialog(self, *a): pass


state = AppState(Page())
state.load()
state.render = lambda: None
state.ui["driver_id"] = state.standings[0]["driver_id"] if state.standings else None
if state.schedule:
    state.ui["circuit"] = state.schedule[0]
    state.ui["strat_race"] = state.schedule[0]
if state.constructors:
    state.ui["team"] = state.constructors[0]["name"]
errors = []
import dataclasses
import flet as ft


def validate(tree, name):
    """Проверка полей, как перед отправкой на экран (BaseControl._before_update_safe -> validate):
    конструктор принимает, например, opacity=None, а падает приложение только при показе."""
    seen, stack = set(), [tree]
    while stack:
        obj = stack.pop()
        if isinstance(obj, (list, tuple)):
            stack.extend(obj)
            continue
        if not isinstance(obj, ft.BaseControl) or id(obj) in seen:
            continue
        seen.add(id(obj))
        try:
            obj._before_update_safe()
        except Exception as exc:
            errors.append(f"{name}: {type(obj).__name__}: {exc}")
        for f in dataclasses.fields(obj):              # поля Flet лежат во внутреннем _values, vars() их не видит
            if not f.name.startswith("_"):
                v = getattr(obj, f.name, None)
                if isinstance(v, (ft.BaseControl, list, tuple)):
                    stack.append(v)


screens = [(f"tab{i}", b) for i, b in enumerate(app.TABS)] + list(app.SUBS.items())
for name, build in screens:
    try:
        validate(build(state), name)
    except Exception:
        errors.append(f"{name}: {traceback.format_exc(limit=3)}")
# Live Timing с живым снимком: таблица, трасса, радио, мини-карточка — настоящими элементами
from ui.screens import live_table
row = {"position": 1, "code": "LEC", "number": 16, "name": "Charles Leclerc", "team": "Ferrari", "colour": "#ED1131",
       "gap": "", "interval": "", "tyre": "H", "tyre_age": 11, "pits": 1, "laps": 30, "last": "1:37.2",
       "best": "1:36.9", "sectors": ["overall", "personal", "none"], "in_pit": True}
live._state["data"] = {
    "session": {"name": "Race", "type": "Race", "country": "USA", "location": "Austin", "circuit": "Austin",
                "start": time.time() - 600, "end": time.time() + 3600, "year": 2026},
    "live": True, "racing": True, "lap": 30, "total_laps": 56, "track": "Сейфти-кар", "updated": time.time(),
    "messages": [{"time": time.time(), "text": "SAFETY CAR DEPLOYED", "flag": "YELLOW", "lap": 30}],
    "radio": [{"driver": "16", "url": "https://example.invalid/r.mp3", "ts": time.time()}],
    "weather": {"air": 29.3, "track": 39.1, "humidity": 25.0, "wind": 2.1, "rain": True},
    "drivers": {"16": {"code": "LEC", "team": "Ferrari", "colour": "ED1131"}}, "circuit_key": 9,
    "positions": {"16": {"x": 100, "y": 200, "status": "OnTrack"}}, "rows": [row], "source": "F1"}
archive.get = lambda key, fetch, ttl=None, on_done=None, force=False: (
    {"x": [0, 1000, 1000, 0], "y": [0, 0, 1000, 1000], "rotation": 0, "corners": [(1, 1000, 0)]}
    if key.startswith("track:") else None)
state.sub = "live"
for view in ("table", "track", "radio"):
    state.ui["live_view"] = view
    try:
        validate(app.SUBS["live"](state), f"live/{view}")
    except Exception:
        errors.append(f"live/{view}: {traceback.format_exc(limit=3)}")
try:
    validate(live_table.driver_card(state, row, live._state["data"]), "driver_card")
except Exception:
    errors.append(f"driver_card: {traceback.format_exc(limit=3)}")
print(json.dumps({"screens": len(screens), "errors": errors}, ensure_ascii=False))
'''


class RealFletTest(unittest.TestCase):
    def test_every_screen_builds_with_real_flet(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, F1_HUB_DB=os.path.join(tmp, "real.db"), F1_HUB_LOG="off",
                       FLET_APP_STORAGE_DATA=tmp, PYTHONIOENCODING="utf-8")
            env.pop("F1_HUB_SEED", None)
            res = subprocess.run([sys.executable, "-c", SCRIPT], cwd=ROOT, env=env, capture_output=True,
                                 text=True, encoding="utf-8", timeout=180)
        self.assertEqual(res.returncode, 0, res.stderr[-2000:])
        report = json.loads(res.stdout.strip().splitlines()[-1])
        self.assertGreater(report["screens"], 15)
        self.assertEqual(report["errors"], [], "\n".join(report["errors"]))


if __name__ == "__main__":
    unittest.main()
