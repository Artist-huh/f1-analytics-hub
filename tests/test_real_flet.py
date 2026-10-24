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
screens = [(f"tab{i}", b) for i, b in enumerate(app.TABS)] + list(app.SUBS.items())
for name, build in screens:
    try:
        build(state)
    except Exception:
        errors.append(f"{name}: {traceback.format_exc(limit=3)}")
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
