"""Дымовые тесты интерфейса.

Вместо настоящего Flet подставляется «всеядная» заглушка, которая запоминает дерево
элементов. Тесты ловят опечатки, неверные ключи данных и логические ошибки на каждом
экране и в каждом обработчике. Совместимость с реальным Flet они НЕ проверяют —
это делается запуском приложения.
"""
import asyncio
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


class UiSmokeTest(unittest.TestCase):
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
        self.addCleanup(join_workers)   # раньше остальных cleanup: потоки ещё под моками

    def all_screens(self):
        yield from ((f"tab{i}", b) for i, b in enumerate(app.TABS))
        yield from app.SUBS.items()

    def build(self, name):
        return dict(self.all_screens())[name](self.state)

    # --- без данных и без сети: ни один экран не падает, везде понятный пустой экран
    def test_every_screen_renders_with_empty_db(self):
        self.state.load()
        for name, build in self.all_screens():
            with self.subTest(screen=name):
                t = texts(build(self.state))
                self.assertTrue(t, name)
                self.assertFalse(any("Не удалось показать" in x for x in t), name)
        self.assertIn("Данных пока нет", texts(self.build("tab0")))
        self.assertIn("Таблицы пока нет", texts(self.build("tab1")))
        self.assertIn("Календарь ещё не загружен", texts(self.build("tab2")))
        self.assertIn("Список пилотов пуст", texts(self.build("tab3")))
        self.assertIn("Пилот не выбран", texts(self.build("driver_detail")))
        self.assertIn("Не с кем сравнивать", texts(self.build("compare")))

    # --- с данными и на разной ширине окна (телефон, планшет, десктоп): экраны собираются без ошибок
    def test_every_screen_renders_with_data_on_all_widths(self):
        fill_db()
        add_podium()
        self.state.load()
        self.state.ui["driver_id"] = "leclerc"
        for width in (360, 412, 430, 900, 1400):
            self.page.width = width
            for name, build in self.all_screens():
                with self.subTest(screen=name, width=width):
                    t = texts(build(self.state))
                    self.assertTrue(t)
                    self.assertFalse(any("Не удалось" in x for x in t))

    def test_screen_reader_labels(self):
        """Экранный диктор: у картинок — подпись (или пометка «декоративная»), у кнопок-иконок и
        нажимаемых плашек без текста — подсказка, которую диктор и читает."""
        fill_db()
        add_podium()
        self.state.load()
        self.state.ui["driver_id"] = "leclerc"
        self.state.ui["circuit"] = self.state.schedule[0]
        with mock.patch.object(media, "source", side_effect=lambda url: url):   # картинки «есть»
            for name, build in self.all_screens():
                for n in walk(build(self.state)):
                    kind = type(n).__name__
                    with self.subTest(screen=name, control=kind):
                        if kind == "Image":
                            self.assertTrue(getattr(n, "semantics_label", None)
                                            or getattr(n, "exclude_from_semantics", False))
                        elif kind == "IconButton":
                            self.assertTrue(getattr(n, "tooltip", None), f"кнопка {getattr(n, 'value', '')}")
                        elif callable(getattr(n, "on_click", None)) and kind != "TextButton":
                            self.assertTrue(texts(n) or getattr(n, "tooltip", None), f"{kind} без подписи")

    def test_live_timing_always_on_home(self):
        from ui.screens import home
        fill_db()
        self.state.load()
        t = texts(self.build("tab0"))
        self.assertLess(t.index("Live Timing"), t.index("Сравнение"))            # первым, выше быстрого доступа
        self.assertTrue(any(x.startswith("Квалификация через") for x in t))    # ближайшая сессия
        race = self.state.schedule[3]
        with mock.patch.object(self.state, "live_now", return_value=(race, "Qualifying")):
            tree = self.build("tab0")
        self.assertIn("LIVE", texts(tree))
        self.assertIn("Сейчас: Квалификация", texts(tree))
        clickable(tree, "Сейчас: Квалификация")[0].on_click(Ctl())
        self.assertEqual(self.state.sub, "live")
        self.assertIsNone(home.next_session([], now=0))

    def test_card_size_scale(self):
        ds = design_system
        for size, (pad, radius) in ds.CARD_SIZES.items():
            c = components.AnimatedCard(Ctl(), size=size)
            self.assertEqual((c.padding, c.border_radius), (pad, radius))
        self.assertEqual(components.AnimatedCard(Ctl()).padding, ds.SPACE_SM)        # по умолчанию — m
        self.assertEqual(components.AnimatedCard(Ctl(), padding=3).padding, 3)       # явный отступ сильнее

    def test_font_scale_setting(self):
        self.addCleanup(design_system.apply_font_scale, 1.0)
        calls = []
        self.state.on_theme_change = lambda name, team: calls.append(name)
        self.state.sub = "settings"
        clickable(self.build("settings"), "Очень крупный")[0].on_click(Ctl())
        self.assertEqual(db.get_setting("font_scale"), "1.3")
        self.assertEqual(design_system.FONT_BODY, 18)
        self.assertEqual(calls, ["dark"])                                      # модули перезагружаются
        design_system.apply_font_scale("мусор")
        self.assertEqual(design_system.FONT_BODY, 14)

    def test_no_driver_is_special(self):
        """Приложение одинаково для всех пилотов: нигде нет блоков «про Леклера» и дуэли с ним."""
        fill_db()
        self.state.load()
        self.assertNotIn("duel", app.SUBS)
        self.state.ui["driver_id"] = "antonelli"
        for name, build in self.all_screens():
            with self.subTest(screen=name):
                joined = " ".join(texts(build(self.state)))
                self.assertNotIn("Леклер", joined)
                self.assertNotIn("Ferrari.", joined)

    def test_home_content(self):
        fill_db()
        self.state.load()
        t = texts(self.build("tab0"))
        for expected in ("F1 Hub", "Сезон 2026", "Этап 4 из 5", "Italian Grand Prix", "3 д 5 ч",
                         "Antonelli", "Mercedes", "3/5", "Leclerc"):
            self.assertIn(expected, t)
        self.assertNotIn("Andrea Kimi Antonelli", t)    # телефон: в строках таблицы — фамилии
        self.page.width = 900
        self.assertIn("Andrea Kimi Antonelli", texts(self.build("tab0")))   # десктоп: полное имя
        self.assertIsNotNone(self.state.countdown)        # отсчёт зарегистрирован для ticker
        self.assertEqual(self.state.countdown[1], "4")
        self.assertNotIn("Последняя гонка", t)             # подиум неполный — секцию не показываем

    def test_home_hero_start_grid(self):
        """Герой главной: стартовые огни по дням до гонки и контур трассы из расписания OpenF1 + MultiViewer."""
        import design_system as ds
        from services import track_map
        from ui.screens import home
        self.assertEqual([home.lights_lit(d * 86400 - 60, False) for d in (7, 6, 5, 3, 1)], [0, 0, 1, 3, 5])
        self.assertEqual(home.lights_lit(600, True), 0)                       # гонка идёт — огни погасли
        self.assertEqual(track_map.circuit_for([(1000, 9), (1000 + 7 * 86400, 65)], 1000 + 9 * 86400), 65)
        self.assertIsNone(track_map.circuit_for([(1000, 9)], 1000 + 6 * 86400))
        resp = mock.Mock(status_code=200, json=lambda: [
            {"meeting_name": "Pre-Season Testing", "circuit_key": 63, "date_start": "2026-02-11T07:00:00+00:00"},
            {"meeting_name": "Mexico City Grand Prix", "circuit_key": 65, "date_start": "2026-10-30T18:30:00+00:00"},
            {"meeting_name": "Broken", "circuit_key": 1, "date_start": None}])
        with mock.patch.object(track_map.requests, "get", return_value=resp):
            self.assertEqual([k for _, k in track_map.fetch_meetings(2026)], [65])   # без тестов и битых строк
        fill_db()
        self.state.load()

        def tips(tree):
            return [str(n.tooltip) for n in walk(tree) if isinstance(getattr(n, "tooltip", None), str)]

        tree = self.build("tab0")
        self.assertIn("Огни загораются по одному за каждый день до гонки: горит 2 из 5", tips(tree))   # 3 д 5 ч
        self.assertEqual(sum(1 for n in walk(tree) if getattr(n, "bgcolor", None) == ds.LIGHT_ON), 4)
        self.assertFalse([t for t in tips(tree) if t.startswith("Трасса")])  # контура ещё нет в кэше — без него
        race = self.state.next_race()
        db.save_archive(track_map.meetings_key(2026), [[race["start_ts"] - 2 * 86400, 39]])
        db.save_archive(track_map.outline_key(39), {"x": [0, 10, 20, 20, 10, 0, -5, -8, -5, 0],
                                                    "y": [0, 0, 5, 15, 20, 20, 15, 10, 5, 2], "rotation": 0})
        self.assertIn("Трасса: Autodromo Nazionale di Monza", tips(self.build("tab0")))
        self.page.width = 1100                       # компьютер: трасса справа от текста, а не над отсчётом
        rows = [n for n in walk(self.build("tab0")) if type(n).__name__ == "Row"
                and any(getattr(c, "tooltip", None) == "Трасса: Autodromo Nazionale di Monza" for c in n.children())]
        self.assertTrue(rows)

    def test_home_last_race_podium(self):
        fill_db()
        add_podium()
        self.state.load()
        tree = self.build("tab0")
        t = texts(tree)
        self.assertIn("Последняя гонка", t)
        self.assertIn("Этап 3, Japanese Grand Prix", t)
        avatars = [n for n in walk(tree)
                   if type(n).__name__ == "DriverAvatar" and callable(getattr(n, "on_click", None))]
        self.assertEqual(len(avatars), 3)
        avatars[1].on_click(Ctl())                           # P1 в центре
        self.assertEqual(self.state.ui["driver_id"], "leclerc")

    def test_home_buttons_navigate(self):
        fill_db()
        self.state.load()
        clickable(self.build("tab0"), "Избранное")[-1].on_click(Ctl())
        self.assertEqual(self.state.sub, "favorites")
        self.state.open_tab(0)
        clickable(self.build("tab0"), "Сравнение")[-1].on_click(Ctl())
        self.assertEqual(self.state.sub, "compare")
        self.state.open_tab(0)
        clickable(self.build("tab0"), "Antonelli")[0].on_click(Ctl())   # строка пилота (ниже — строка команды)
        self.assertEqual((self.state.sub, self.state.ui["driver_id"]), ("driver_detail", "antonelli"))

    def test_championship_tabs(self):
        fill_db()
        self.state.load()
        self.page.width = 900
        t = texts(self.build("tab1"))
        self.assertIn("Andrea Kimi Antonelli", t)
        self.assertIn("лидер", t)
        self.assertIn("−78", t)                           # отставание от лидера
        self.state.ui["champ"] = "teams"
        tree = self.build("tab1")
        t = texts(tree)
        self.assertIn("Mercedes", t)
        self.assertIn("Antonelli", t)                     # пилоты команды под названием
        self.assertTrue([n for n in walk(tree) if type(n).__name__ == "TeamLogo"])
        clickable(tree, "Ferrari")[0].on_click(Ctl())     # команда -> её страница
        self.assertEqual((self.state.sub, self.state.ui["team"]), ("team", "Ferrari"))
        self.state.close_sub()
        self.state.ui["champ"] = "favs"
        self.assertIn("Нет избранных пилотов", texts(self.build("tab1")))
        api.toggle_favorite("leclerc")
        self.state.load()
        favs = texts(self.build("tab1"))
        self.assertIn("Charles Leclerc", favs)
        self.assertNotIn("Andrea Kimi Antonelli", favs)

    def test_calendar_upcoming_past_and_dialog(self):
        fill_db()
        add_podium()
        self.state.load()
        t = texts(self.build("tab2"))
        self.assertIn("Ближайшая", t)
        self.assertIn("Квалификация", t)
        self.assertIn("Сезон 2026, пройдено 3 из 5", t)
        self.assertIn("Singapore Grand Prix", t)
        self.assertIn("5,793 км", t)                      # Монца опознана по названию автодрома
        self.state.ui["cal"] = "past"
        tree = self.build("tab2")
        self.assertIn("Победа: Leclerc", texts(tree))     # прошедший этап — победитель и подиум
        clickable(tree, "Japanese Grand Prix")[0].on_click(Ctl())
        self.assertEqual(len(self.page.dialogs), 1)       # модальное окно с подиумом и расписанием
        dialog = self.page.dialogs[0]
        dt = texts(dialog)
        self.assertIn("3. Japanese Grand Prix", dt)
        self.assertIn("Подиум", dt)
        self.assertIn("Liam Lawson", dt)
        clickable(dialog, "Charles Leclerc")[0].on_click(Ctl())   # из подиума — на страницу пилота
        self.assertEqual((self.state.sub, self.page.dialogs), ("driver_detail", []))

    def test_track_info_matching(self):
        def race(circuit, locality=""):
            return {"circuit": circuit, "locality": locality}
        self.assertEqual(calendar.track_info(race("Circuit of the Americas", "Austin")), ("5,513 км", 56))
        self.assertEqual(calendar.track_info(race("Las Vegas Strip Street Circuit", "Las Vegas"))[1], 50)
        self.assertEqual(calendar.track_info(race("Shanghai International Circuit"))[1], 56)
        self.assertIsNone(calendar.track_info(race("Madring", "Madrid")))   # незнакомая трасса — без выдумок

    def test_drivers_search_and_filter(self):
        fill_db()
        self.state.load()
        rows = self.state.standings
        self.assertEqual([d["driver_id"] for d in drivers.filter_drivers(rows, "LEC", None)], ["leclerc"])
        self.assertEqual([d["driver_id"] for d in drivers.filter_drivers(rows, "ferr", None)], ["leclerc"])
        self.assertEqual([d["driver_id"] for d in drivers.filter_drivers(rows, "", "Mercedes")], ["antonelli"])
        self.assertEqual(drivers.filter_drivers(rows, "xyz", None), [])
        tree = self.build("tab3")
        field = next(n for n in walk(tree) if type(n).__name__ == "TextField")
        grid = next(n for n in walk(tree) if type(n).__name__ == "ResponsiveRow")
        self.renders.clear()
        field.on_change(Ctl(control=Ctl(value="law")))
        self.assertEqual(self.renders, [])                # экран не перестраивается — поле ввода не теряет фокус
        self.assertEqual(grid.updated, 1)
        self.assertIn("LAWSON", texts(grid))
        self.assertNotIn("LECLERC", texts(grid))
        field.on_change(Ctl(control=Ctl(value="nobody")))
        self.assertIn("Пилоты не найдены", texts(grid))

    def test_driver_photos_flags_and_logos(self):
        fill_db()
        db.save_driver_media([{"code": "LEC", "ref": "chalec01", "number": "16", "team": "Ferrari", "headshot": ""}])
        self.state.load()
        lec = self.state.driver("leclerc")
        self.assertIn("/ferrari/chalec01/2026ferrarichalec01right.webp", self.state.photo(lec))
        self.assertIn("c_fill,g_north,w_300,h_375/q_auto:eco", self.state.photo(lec, "portrait"))
        self.assertIn("c_fill,g_north,w_480,h_600/q_auto:eco", self.state.photo(lec, "hero"))
        img = components.image("https://x/y.webp", height=184)
        self.assertEqual(img.cache_height, 184 * components.DECODE_SCALE)   # декодируется под экран
        self.assertIsNone(self.state.photo(self.state.driver("lawson")))      # нет в справочнике -> инициалы
        images = [str(n.src) for n in walk(self.build("tab1")) if type(n).__name__ == "Image"]
        self.assertTrue(any("chalec01" in src for src in images))
        self.assertTrue(any("flagcdn.com/w80/mc.png" in src for src in images))   # флаг Монако
        self.state.ui["champ"] = "teams"
        images = [str(n.src) for n in walk(self.build("tab1")) if type(n).__name__ == "Image"]
        self.assertTrue(any("2026mercedeslogowhite.webp" in src for src in images))
        self.assertEqual(self.state.flag(country="Italy")[1], "it")

    def test_driver_detail_and_summary(self):
        fill_db()
        self.state.load()
        s = driver_detail.season_summary(self.state.driver_results("leclerc"))
        self.assertEqual((s["podiums"], s["best"], s["dnf"]), (2, 2, 1))
        self.assertAlmostEqual(s["avg_gain"], 1.0)
        self.assertAlmostEqual(s["race_points"], 32.5)
        self.state.open_driver("leclerc")
        t = texts(self.build("driver_detail"))
        for expected in ("LECLERC", "Charles", "P4", "Поулы", "Быстрые круги", "Результаты гонок", "Japanese GP",
                         "Набор очков", "Этап 2, квал. P1, старт 4, 8 мар"):
            self.assertIn(expected, t)

    def test_every_driver_has_full_detail_page(self):
        """Любой пилот, не только «главный»: статистика и результаты без похода в сеть."""
        fill_db()
        self.state.load()
        for d in self.state.standings:
            with self.subTest(driver=d["driver_id"]):
                self.state.ui["driver_id"] = d["driver_id"]
                t = texts(self.build("driver_detail"))
                self.assertIn("Результаты гонок", t)
                self.assertNotIn("Результатов пока нет", t)

    def test_compare_defaults_metrics_and_leaders(self):
        fill_db()
        self.state.load()
        self.assertEqual(self.state.compare_ids(), ["antonelli", "leclerc"])   # по умолчанию — двое лидеров
        self.assertEqual(compare.leaders([10, 4], lower_is_better=True), {1})   # P4 лучше P10
        self.assertEqual(compare.leaders([3, 3], lower_is_better=False), set())
        self.state.ui["cmp"] = ["lawson", "leclerc"]
        drivers_ = [self.state.driver(i) for i in self.state.compare_ids()]
        self.assertEqual(compare.metric_values(self.state, drivers_, "position"), [10, 4])
        self.assertEqual(compare.metric_values(self.state, drivers_, "poles"), [0, 1])
        t = texts(self.build("compare"))
        for expected in ("Поулы", "Быстрые круги", "Средняя квалификация", "Гонки: кто финишировал выше",
                         "Квалификации", "Набор очков"):
            self.assertIn(expected, t)

    def test_compare_add_remove_and_presets(self):
        fill_db()
        self.state.load()
        clickable(self.build("compare"), "Добавить")[0].on_click(Ctl())
        clickable(self.page.dialogs[-1], "Liam Lawson")[0].on_click(Ctl())
        self.assertEqual(self.page.dialogs, [])
        self.assertEqual(self.state.compare_ids(), ["antonelli", "leclerc", "lawson"])
        self.assertIn("Кто чаще был впереди", texts(self.build("compare")))   # 3+ пилота — общий счёт
        remove = [n for n in walk(self.build("compare")) if getattr(n, "tooltip", None) == "Убрать из сравнения"]
        self.assertEqual(len(remove), 3)
        remove[0].on_click(Ctl())
        self.assertEqual(self.state.compare_ids(), ["leclerc", "lawson"])
        self.assertFalse([n for n in walk(self.build("compare")) if getattr(n, "tooltip",
                                                                            None) == "Убрать из сравнения"])
        clickable(self.build("compare"), "Топ-3")[0].on_click(Ctl())
        self.assertEqual(self.state.compare_ids(), ["antonelli", "leclerc", "lawson"])
        self.state.set_compare(["antonelli", "leclerc", "lawson", "norris", "x"])   # не больше четырёх
        self.assertEqual(len(self.state.ui["cmp"]), 4)

    def test_compare_from_driver_page(self):
        fill_db()
        self.state.load()
        self.state.open_driver("lawson")
        clickable(self.build("driver_detail"), "Сравнить")[0].on_click(Ctl())
        self.assertEqual((self.state.sub, self.state.compare_ids()[0]), ("compare", "lawson"))

    def test_favorites_add_dialog_and_stats(self):
        fill_db()
        self.state.load()
        tree = self.build("favorites")
        self.assertIn("Нет избранных пилотов", texts(tree))
        clickable(tree, "Добавить пилота")[0].on_click(Ctl())
        clickable(self.page.dialogs[-1], "Liam Lawson")[0].on_click(Ctl())
        self.assertEqual(self.page.dialogs, [])
        self.assertEqual(self.state.favorites, ["lawson"])
        api.toggle_favorite("leclerc")
        self.state.load()
        tree = self.build("favorites")
        t = texts(tree)
        self.assertIn("165", t)                                  # 39 + 126 — числа, а не строки
        self.assertIn("P4", t)
        clickable(tree, "Сравнить избранных")[0].on_click(Ctl())
        self.assertEqual((self.state.sub, self.state.compare_ids()), ("compare", ["lawson", "leclerc"]))
        api.toggle_favorite("antonelli")
        self.state.load()
        clickable(self.build("favorites"), "Добавить пилота")[0].on_click(Ctl())
        self.assertIn("Все пилоты уже в избранном!", texts(self.page.dialogs[-1]))   # уведомление

    def test_team_page(self):
        from ui.screens import team
        fill_db()
        self.state.load()
        s = team.team_stats(self.state, "Mercedes")
        self.assertEqual((s["wins"], s["podiums"], s["poles"], s["fastest_laps"], s["dnf"]), (2, 3, 2, 2, 0))
        s = team.team_stats(self.state, "Ferrari")
        self.assertEqual((s["wins"], s["podiums"], s["poles"], s["dnf"]), (0, 2, 1, 1))
        self.assertEqual(team.team_points_by_round(self.state, "Mercedes", [1, 2, 3]), [25, 51, 76])   # + спринт 8
        self.state.open_driver("leclerc")
        clickable(self.build("driver_detail"), "Ferrari")[0].on_click(Ctl())   # логотип у пилота -> команда
        self.assertEqual((self.state.sub, self.state.ui["team"]), ("team", "Ferrari"))
        t = texts(self.build("team"))
        for expected in ("FERRARI", "P2", "285", "Сезон команды", "Leclerc", "Набор очков"):
            self.assertIn(expected, t)
        self.state.ui["team"] = "Unknown"
        self.assertIn("Команда не выбрана", texts(self.build("team")))

    def test_history_screen(self):
        from services import archive
        fill_db()
        self.state.load()
        season_2025 = {"season": "2025", "rounds": "24", "standings": [
            {"position": "1", "points": "423", "wins": "7", "driver_id": "norris", "code": "NOR",
             "name": "Lando Norris",
             "team": "McLaren", "nationality": "British", "number": "4"},
            {"position": "2", "points": "421", "wins": "8", "driver_id": "verstappen", "code": "VER",
             "name": "Max Verstappen", "team": "Red Bull", "nationality": "Dutch", "number": "1"}],
            "constructors": [{"position": "1", "points": "833", "wins": "14", "name": "McLaren",
                              "constructor_id": "mclaren", "nationality": "British"}],
            "winners": [{"round": "1", "race_name": "Australian GP", "country": "Australia", "name": "Lando Norris",
                         "team": "McLaren", "driver_id": "norris"}]}
        db.save_archive(archive.season_key(2025), season_2025)
        t = texts(self.build("history"))
        for expected in ("Чемпион мира", "Lando Norris", "Кубок конструкторов: McLaren", "Личный зачёт",
                         "Победители гонок", "Больше всего побед: Lando Norris — 1"):
            self.assertIn(expected, t)
        with mock.patch.object(archive, "season", return_value=None), \
             mock.patch.object(archive, "loading", return_value=True):
            self.state.ui["hist_year"] = 1988
            self.assertIn("Загружаем сезон 1988…", texts(self.build("history")))
        rows = [{"season": "2025", "name": "Lando Norris", "team": "McLaren", "nationality": "British",
                 "constructor": "McLaren", "wins": "7"},
                {"season": "2024", "name": "Max Verstappen", "team": "Red Bull", "nationality": "Dutch",
                 "constructor": "McLaren", "wins": "9"}]
        with mock.patch.object(archive, "champions", return_value=rows):
            self.state.ui["hist_view"] = "champions"
            tree = self.build("history")
            t = texts(tree)
            self.assertIn("Рекорды", t)
            self.assertIn("2026: Andrea Kimi Antonelli", t)            # текущий сезон — лидер
            clickable(tree, "Max Verstappen")[0].on_click(Ctl())       # год -> сезон
            self.assertEqual((self.state.ui["hist_view"], self.state.ui["hist_year"]), ("season", 2024))

    def test_circuit_screen(self):
        from services import archive
        from ui.screens import circuit
        self.assertAlmostEqual(circuit.lap_seconds("1:21.046"), 81.046)
        self.assertIsNone(circuit.lap_seconds(""))
        data = {"winners": [{"season": "2004", "name": "Rubens Barrichello", "team": "Ferrari"},
                            {"season": "2019", "name": "Charles Leclerc", "team": "Ferrari", "driver_id": "leclerc"},
                            {"season": "2024", "name": "Charles Leclerc", "team": "Ferrari", "driver_id": "leclerc"}],
                "poles": [{"season": "2024", "name": "Lando Norris", "team": "McLaren", "time": "1:19.327"}],
                "fastest": [{"season": "2004", "name": "Rubens Barrichello", "time": "1:21.046"},
                            {"season": "2024", "name": "Lewis Hamilton", "time": "1:21.432"}]}
        s = circuit.circuit_summary(data)
        self.assertEqual((s["races"], s["first"], s["top_driver"], s["top_team"]),
                         (3, 2004, ("Charles Leclerc", 2), ("Ferrari", 3)))
        self.assertEqual(s["record"]["name"], "Rubens Barrichello")       # самый быстрый круг — по времени
        fill_db()
        db.save_schedule("2026", [dict(r, circuit_id="monza" if r["round"] == "4" else "x")
                                  for r in db.load_schedule()])
        db.save_archive(archive.circuit_key("monza"), data)
        self.state.load()
        clickable(self.build("tab2"), "Трасса и история")[0].on_click(Ctl())   # из карточки ближайшей гонки
        self.assertEqual((self.state.sub, self.state.ui["circuit"]["round"]), ("circuit", "4"))
        tree = self.build("circuit")
        t = texts(tree)
        for expected in ("Italian Grand Prix", "5,793 км", "53", "Первый Гран-при", "2004",
                         "Charles Leclerc — 2", "1:21.046 — Rubens Barrichello, 2004", "Последние победители",
                         "Последние поулы", "Расписание уик-энда"):
            self.assertIn(expected, t)
        track = [str(n.src) for n in walk(tree) if type(n).__name__ == "Image"]
        self.assertTrue(any("2026trackmonzawhiteoutline.webp" in src for src in track))

    def test_live_timing(self):
        from services import live
        session = {"session_name": "Race", "session_type": "Race"}
        drivers = [{"driver_number": 16, "name_acronym": "LEC", "full_name": "Charles LECLERC", "team_name": "Ferrari",
                    "team_colour": "ED1131"},
                   {"driver_number": 12, "name_acronym": "ANT", "full_name": "Kimi ANTONELLI", "team_name": "Mercedes",
                    "team_colour": "00D7B6"}]
        positions = [{"date": "2026-10-11T12:00:00", "driver_number": 16, "position": 2},
                     {"date": "2026-10-11T12:00:00", "driver_number": 12, "position": 1},
                     {"date": "2026-10-11T13:00:00", "driver_number": 16, "position": 1},      # обгон
                     {"date": "2026-10-11T13:00:00", "driver_number": 12, "position": 2}]
        intervals = [{"date": "2026-10-11T13:40:00", "driver_number": 12, "gap_to_leader": 2.5, "interval": 2.5},
                     {"date": "2026-10-11T13:40:00", "driver_number": 16, "gap_to_leader": 0.0, "interval": 0.0}]
        stints = [{"driver_number": 16, "stint_number": 1, "lap_start": 1, "lap_end": 20, "compound": "MEDIUM",
                   "tyre_age_at_start": 0},
                  {"driver_number": 16, "stint_number": 2, "lap_start": 21, "lap_end": 62, "compound": "HARD",
                   "tyre_age_at_start": 3},
                  {"driver_number": 12, "stint_number": 1, "lap_start": 1, "lap_end": 62, "compound": "HARD",
                   "tyre_age_at_start": 0}]
        pits = [{"driver_number": 16, "lap_number": 20}]
        table = live.build_table(session, drivers, positions, intervals, stints, pits)
        self.assertEqual([r["code"] for r in table["rows"]], ["LEC", "ANT"])
        lec, ant = table["rows"]
        self.assertEqual((lec["tyre"], lec["tyre_age"], lec["pits"], ant["gap"]), ("H", 44, 1, "+2.500"))
        self.assertEqual(live.fmt_gap("+1 LAP"), "+1 кр.")
        fill_db()
        self.state.load()
        tree = self.build("live")
        t = texts(tree)
        self.assertIn("Загружаем данные сессии…", t)
        kinds = {type(n).__name__ for n in walk(tree)}
        self.assertIn("Shimmer", kinds)                            # заготовка таблицы, а не круг загрузки
        self.assertNotIn("ProgressRing", kinds)
        self.live_refresh.assert_called()                          # экран сам запросил данные
        live._state["data"] = {"session": {"name": "Race", "type": "Race", "country": "Italy", "location": "Monza",
                                           "circuit": "Monza", "start": 0, "end": 0, "year": 2026},
                               "live": True, "racing": True, "rows": table["rows"], "lap": 62,
                               "messages": [{"time": 0, "text": "CHEQUERED FLAG", "flag": "CHEQUERED", "lap": 62}],
                               "updated": time.time()}
        tree = self.build("live")
        t = texts(tree)
        for expected in ("LIVE", "Гонка", "Monza 2026", "Сессия идёт, круг 62 из 53", "+2.500", "лидер",
                         "CHEQUERED FLAG", "44"):
            self.assertIn(expected, t)
        clickable(tree, "Интервал")[0].on_click(Ctl())
        self.assertEqual(self.state.ui["live_gap"], "interval")
        self.assertIn("Источник — OpenF1. Во время сессии бесплатный доступ закрыт; после сессии показан её итог.", t)
        # поток F1: сейфти-кар, радио сессии
        from services import radio
        live._state["data"].update(source="F1", track="Сейфти-кар", drivers={"16": {"code": "LEC", "colour": "ED1131"}},
                                   radio=[{"driver": "16", "url": "https://r/live1.mp3", "ts": 1030},
                                          {"driver": "16", "url": "https://r/live2.mp3", "ts": 1095}])
        live._state["data"]["session"]["start"] = 1000
        tree = self.build("live")
        self.assertIn("Сейфти-кар", texts(tree))
        self.assertIn("Источник — официальный live timing F1: данные идут и во время сессии.", texts(tree))
        clickable(tree, "Радио (2)")[0].on_click(Ctl())
        with mock.patch.object(radio, "supported", return_value=True), \
                mock.patch.object(radio, "models_ready", return_value=True), \
                mock.patch.object(radio, "request") as req:
            tree = self.build("live")
            stamps = [x for x in texts(tree) if x in ("1:35", "0:30")]
            self.assertEqual(stamps, ["1:35", "0:30"])                          # свежие — сверху
            clickable(tree, "Перевести новые (2)")[0].on_click(Ctl())
        self.assertEqual(req.call_count, 2)
        self.state.ui["live_view"] = "table"
        clickable(self.build("live"), "LEC")[0].on_click(Ctl())     # строка -> страница пилота
        self.assertEqual(self.state.ui["driver_id"], "leclerc")
        self.state.sub = None                                       # поток наблюдения завершится сам

    def test_race_analysis_tabs(self):
        from services import stats
        from ui.screens import race as race_screen
        laps = {"antonelli": [[1, 2, 100.0], [2, 1, 95.0], [3, 1, 95.5], [4, 1, 120.0], [5, 1, 95.2]],
                "leclerc": [[1, 1, 99.0], [2, 2, 95.4], [3, 2, 95.6], [4, 2, 95.9], [5, 2, 96.0]],
                "lawson": [[1, 3, 101.0], [2, 3, 97.0], [3, 3, 97.2], [4, 3, 97.1], [5, 3, 97.5]]}
        self.assertEqual([n for n, _ in stats.clean_laps(laps["antonelli"])], [2, 3, 5])   # без 1-го и пит-стопа
        self.assertEqual(stats.pace_summary(laps["antonelli"])["best"], 95.0)
        quali = [{"driver_id": "antonelli", "code": "ANT", "team": "Mercedes", "position": "1", "q3": "1:30.000",
                  "name": "Andrea Kimi Antonelli"},
                 {"driver_id": "leclerc", "code": "LEC", "team": "Ferrari", "position": "2", "q3": "1:30.250"},
                 {"driver_id": "lawson", "code": "LAW", "team": "Racing Bulls", "position": "3", "q2": "1:31.100"}]
        self.assertEqual([round(g, 3) for _, _, g in stats.quali_gaps(quali)], [0, 0.25, 1.1])
        fill_db()
        self.state.load()
        race = self.state.schedule[2]
        db.save_archive(race_screen.laps_key(race), laps)
        db.save_archive(race_screen.quali_key(race), quali)
        self.state.open_race_strategy(race)
        for view, expected in (("positions", "5 кругов"), ("pace", "быстрее всех"), ("quali", "+0.250")):
            with self.subTest(view=view):
                self.state.ui["race_view"] = view
                t = " ".join(texts(self.build("race_strategy")))
                self.assertIn(expected, t)
        self.state.ui["race_view"] = "pace"
        clickable(self.build("race_strategy"), "LAW")[0].on_click(Ctl())       # по умолчанию — тройка финиша
        self.assertEqual(self.state.ui["pace_ids"], ["antonelli", "leclerc"])  # нажатие снимает с графика
        clickable(self.build("race_strategy"), "LAW")[0].on_click(Ctl())
        self.assertIn("lawson", self.state.ui["pace_ids"])                    # и возвращает
        self.state.ui["race_view"] = "quali"
        self.assertIn("Поул: Andrea Kimi Antonelli — 1:30.000", texts(self.build("race_strategy")))

    def test_predictions_game(self):
        from services import predictions as pr
        full = pr.score({"pole": "ver", "p1": "ver", "p2": "lec", "p3": "ant"}, "ver", ["ver", "lec", "ant"])
        self.assertEqual(full["total"], pr.MAX_POINTS)
        swapped = pr.score({"pole": "lec", "p1": "lec", "p2": "ver", "p3": "nor"}, "ver", ["ver", "lec", "ant"])
        self.assertEqual(swapped["total"], 2 * pr.PODIUM_POINTS)               # двое на подиуме, но не на своих
        self.assertFalse(pr.score({"p1": "ver"}, None, None)["complete"])
        fill_db()
        add_podium()
        db.save_qualifying("2026", [{"driver_id": "leclerc", "round": "3", "position": "1"}])
        self.state.load()
        pr.save("2026", "3", {"pole": "leclerc", "p1": "leclerc", "p2": "lawson", "p3": "antonelli"})
        t = " ".join(texts(self.build("predict")))
        self.assertIn("14 из 25", t)                                            # 5 + 5 + 2 + 2
        self.assertIn("Italian Grand Prix", t)                                  # ближайший открытый этап
        for code in ("LEC", "ANT", "LAW", "ANT"):                                # поул, P1, P2, P3
            clickable(self.build("predict"), code)[-1].on_click(Ctl())
        draft = self.state.ui["predict_draft"]
        self.assertEqual([draft[k] for k in ("pole", "p1", "p2", "p3")], ["leclerc", None, "lawson", "antonelli"])
        self.assertEqual(self.state.ui["predict_slot"], "p1")                   # ANT ушёл с P1 — он и выбран
        clickable(self.build("predict"), "LEC")[-1].on_click(Ctl())
        self.assertEqual(draft["p1"], "leclerc")
        clickable(self.build("predict"), "Сохранить")[0].on_click(Ctl())
        self.assertEqual(pr.load("2026", "4")["p3"], "antonelli")
        self.assertIn("Прогноз сохранён", texts(self.build("predict")))
        self.assertEqual(pr.season_stats(pr.load_season("2026"), {"3": ["leclerc", "antonelli", "lawson"]},
                                         {"3": "leclerc"})["points"], 14)

    def test_team_radio_tab(self):
        from services import live, radio
        answers = {
            "sessions": [{"session_key": 9001, "session_name": "Race", "date_start": "2026-01-01T13:00:00+00:00"}],
            "team_radio": [{"driver_number": 12, "date": "2026-01-01T13:05:30+00:00", "recording_url": "https://r/2.mp3"},
                           {"driver_number": 16, "date": "2026-01-01T13:01:00+00:00", "recording_url": "https://r/1.mp3"}],
            "drivers": [{"driver_number": 12, "name_acronym": "ANT", "team_name": "Mercedes", "team_colour": "27F4D2"},
                        {"driver_number": 16, "name_acronym": "LEC", "team_name": "Ferrari", "team_colour": "E8002D"}],
        }
        with mock.patch.object(live, "_query", lambda endpoint, query: answers[endpoint]):
            data = radio.fetch_radio(2026, "2026-01-01")
        self.assertEqual([m["url"] for m in data["messages"]], ["https://r/1.mp3", "https://r/2.mp3"])   # по времени
        self.assertEqual(radio.split_sentences("Box box. Copy! OK"), ["Box box.", "Copy!", "OK"])
        self.assertEqual(radio._plain_english("Box this lap, box this lap. Keep pushing."),
                         "make a pit stop this lap. Keep attacking.")                   # жаргон и повтор
        self.assertEqual(radio._fix_russian("машина безопасности."), "Сейфти-кар.")
        import zipfile
        pkg = os.path.join(self.tmp.name, "en_ru.argosmodel")
        with zipfile.ZipFile(pkg, "w") as z:
            for name in ("model/model.bin", "model/config.json", "sentencepiece.model", "stanza/en/x.pt", "README.md"):
                z.writestr(f"translate-en_ru-1_9/{name}", b"x")
        with mock.patch.dict(os.environ, {"FLET_APP_STORAGE_DATA": self.tmp.name}):
            radio.extract_argos(pkg)
            got = sorted(str(p.relative_to(radio.argos_dir())).replace("\\", "/")
                         for p in radio.argos_dir().rglob("*") if p.is_file())
        self.assertEqual(got, ["model/config.json", "model/model.bin", "sentencepiece.model"])   # без stanza
        # модель токенизатора — байтами: по пути с кириллицей (C:\Users\Андрей) SentencePiece её не открывает
        fake_sp = mock.Mock()
        with mock.patch.dict(os.environ, {"FLET_APP_STORAGE_DATA": self.tmp.name}), \
                mock.patch.dict(sys.modules, {"sentencepiece": fake_sp, "ctranslate2": mock.Mock(),
                                              "faster_whisper": mock.Mock()}), \
                mock.patch.object(radio, "whisper_model", return_value="small.en"), \
                mock.patch.dict(radio._models, clear=True):
            radio._load_models()
        self.assertEqual(fake_sp.SentencePieceProcessor.call_args.kwargs, {"model_proto": b"x"})
        fill_db()
        self.state.load()
        race = self.state.schedule[2]
        self.state.open_race_strategy(race)
        self.state.ui["race_view"] = "radio"
        self.assertIn("Радио не загружено", texts(self.build("race_strategy")))
        db.save_archive(radio.radio_key(race), data)
        db.save_archive(radio.tx_key("https://r/1.mp3"), {"en": "Box this lap.", "ru": "Заезжай на этом круге."})
        with mock.patch.object(radio, "supported", return_value=True), \
                mock.patch.object(radio, "models_ready", return_value=True):
            t = texts(self.build("race_strategy"))
            self.assertIn("Заезжай на этом круге.", t)
            self.assertIn("5:30", t)                                            # от старта гонки
            with mock.patch.object(radio, "request") as req:
                clickable(self.build("race_strategy"), "Перевести")[0].on_click(Ctl())
            req.assert_called_once()
            self.assertEqual(req.call_args[0][0], "https://r/2.mp3")
            with mock.patch.object(radio, "request") as req:
                clickable(self.build("race_strategy"), "Перевести все на экране (1)")[0].on_click(Ctl())
            self.assertEqual([c[0][0] for c in req.call_args_list], ["https://r/2.mp3"])   # готовые — пропускаем
        clickable(self.build("race_strategy"), "ANT")[0].on_click(Ctl())        # только записи ANT
        self.assertIn("1 запись", texts(self.build("race_strategy")))
        fake_audio = types.SimpleNamespace(Audio=lambda **kw: Ctl(**kw), AudioState=Ctl())
        with mock.patch.dict(sys.modules, {"flet_audio": fake_audio}):
            play = [n for n in walk(self.build("race_strategy")) if getattr(n, "tooltip", "") == "Слушать: радио ANT"]
            play[0].on_click(Ctl())
        self.assertEqual(self.state.ui["radio_playing"], "https://r/2.mp3")
        with mock.patch.object(radio, "supported", return_value=True), \
                mock.patch.object(radio, "download_models") as dl:
            clickable(self.build("race_strategy"), "Лёгкая (~350 МБ)")[0].on_click(Ctl())
        self.assertEqual(dl.call_args[0][1], "base.en")
        with mock.patch.dict(os.environ, {"FLET_APP_STORAGE_DATA": self.tmp.name}):
            self.assertIsNone(radio.whisper_model())
            for name in ("base.en", "small.en"):
                (radio.models_dir() / f"whisper-{name}").mkdir(parents=True, exist_ok=True)
                (radio.models_dir() / f"whisper-{name}" / "model.bin").write_bytes(b"x")
            self.assertEqual(radio.whisper_model(), "small.en")                  # по умолчанию — точная
            db.set_setting("radio_model", "base.en")
            self.assertEqual(radio.whisper_model(), "base.en")                   # выбор пользователя
            self.assertTrue(radio.models_ready())                                # перевод распакован выше
        with mock.patch.object(radio, "supported", return_value=False):          # Android: без перевода
            self.assertIn("Перевод радио работает в версии для компьютера. Здесь — запись в оригинале.",
                          texts(self.build("race_strategy")))

    def test_first_run_onboarding(self):
        from ui.screens import welcome
        db.set_setting("onboarded", "0")
        self.assertFalse(welcome.needed(self.state))                            # без данных выбирать некого
        fill_db()
        self.state.load()
        self.assertTrue(welcome.needed(self.state))
        themes = []
        self.state.on_theme_change = lambda name, team: themes.append((name, team))
        self.state.sub = "welcome"
        clickable(self.build("welcome"), "Ferrari")[0].on_click(Ctl())
        clickable(self.build("welcome"), "Дальше")[0].on_click(Ctl())
        self.assertEqual(self.state.ui["welcome"]["drivers"], ["leclerc"])      # пилоты команды отмечены сами
        clickable(self.build("welcome"), "Liam Lawson")[0].on_click(Ctl())
        clickable(self.build("welcome"), "Дальше")[0].on_click(Ctl())
        switches = [n for n in walk(self.build("welcome")) if getattr(n, "tooltip", "") == "Напоминания о сессиях"]
        switches[0].on_change(Ctl(control=Ctl(value=False)))
        clickable(self.build("welcome"), "Готово")[0].on_click(Ctl())
        self.assertEqual(sorted(self.state.favorites), ["lawson", "leclerc"])
        self.assertEqual(themes, [("team", "Ferrari")])
        self.assertFalse(self.state.notifications_on("sessions"))
        self.assertTrue(self.state.notifications_on("results"))
        self.assertIsNone(self.state.sub)
        self.assertFalse(welcome.needed(self.state))                            # второй раз не показываем
        db.set_setting("onboarded", "0")
        clickable(self.build("welcome"), "Пропустить — настрою потом")[0].on_click(Ctl())
        self.assertEqual(db.get_setting("onboarded"), "1")

    def test_season_heatmap(self):
        from ui.screens import heatmap
        ds = design_system
        self.assertEqual(heatmap.cell_color("1"), (ds.POSITION_COLORS[1], ds.INK))
        self.assertEqual(heatmap.cell_color("4")[0], heatmap.POINTS_GREENS[0])
        self.assertEqual(heatmap.cell_color("15")[0], ds.SURFACE_ELEVATED)
        self.assertEqual(heatmap.cell_color("R")[0], ds.DANGER)
        self.assertIsNone(heatmap.cell_color("W")[0])                    # не стартовал — пустая клетка
        fill_db()
        self.state.load()
        rows, rounds = heatmap.season_grid(self.state)
        self.assertEqual(rounds, ["1", "2", "3"])
        self.assertEqual([d["driver_id"] for d, _ in rows], ["antonelli", "leclerc", "lawson"])
        self.assertEqual(rows[1][1], {"1": "3", "2": "R", "3": "2"})
        self.state.ui["champ"] = "heat"
        tree = self.build("tab1")
        t = texts(tree)
        for expected in ("ANT", "LEC", "R", "P1", "сход"):
            self.assertIn(expected, t)
        clickable(tree, "Квалификации")[0].on_click(Ctl())
        self.assertEqual(heatmap.season_grid(self.state, "quali")[0][1][1], {"1": "4", "2": "1", "3": "3"})
        tips = [n.tooltip for n in walk(self.build("tab1")) if getattr(n, "tooltip", None)]
        self.assertIn("Charles Leclerc", tips)      # код пилота: имя в подсказке (нажатия нет — строка 24 px < 48 dp)
        self.assertFalse(clickable(self.build("tab1"), "LEC"))

    def test_race_strategy(self):
        from services import live
        from ui.screens import race_strategy
        data = {"session_key": 1, "laps": 53,
                "drivers": {"16": {"code": "LEC", "team": "Ferrari", "colour": "ED1131"},
                            "12": {"code": "ANT", "team": "Mercedes", "colour": "00D7B6"}},
                "stints": [{"driver": "16", "n": 1, "start": 1, "end": 20, "tyre": "M", "age": 0},
                           {"driver": "16", "n": 2, "start": 21, "end": 53, "tyre": "H", "age": 3},
                           {"driver": "12", "n": 1, "start": 1, "end": 53, "tyre": "H", "age": 0}],
                "pits": [{"driver": "16", "lap": 20, "duration": 22.1}]}
        rows = live.strategy_rows(data, ["ANT", "LEC"])
        self.assertEqual([r["code"] for r in rows], ["ANT", "LEC"])          # порядок финиша
        self.assertEqual([s["laps"] for s in rows[1]["stints"]], [20, 33])
        self.assertEqual([p["lap"] for p in rows[1]["pits"]], [20])
        fill_db()
        self.state.load()
        race = self.state.schedule[2]                                         # Японский этап (прошёл)
        db.save_archive(race_strategy.strategy_key(race), data)
        self.state.open_race_strategy(race)
        t = texts(self.build("race_strategy"))
        for expected in ("53 круга, чаще всего — 0 пит-стопов", "средние", "жёсткие", "пит: 20", "без пит-стопов"):
            self.assertIn(expected, t)
        self.assertEqual(race_strategy.finishing_order(self.state, race), ["ANT", "LEC", "LAW"])
        self.state.ui["strat_race"] = self.state.schedule[1]                  # нет данных -> повтор загрузки
        self.assertIn("Стратегия не загружена", texts(self.build("race_strategy")))

    def test_openf1_locked_during_session(self):
        from services import live
        self.assertRaises(live.LockedError, live._check, "x", {"detail": "Live F1 session in progress. Global API "
                                                                         "access is restricted to authenticated users"})
        self.assertRaises(live.LiveError, live._check, "x", {"detail": "Too Many Requests"})
        live._state.update(data=None, error=live.LOCKED_TEXT, error_at=time.time(), locked=True)
        self.assertFalse(live.stale())                               # не стучимся каждые 3 секунды
        fill_db()
        self.state.load()
        self.assertIn("Доступ к данным закрыт до конца сессии", texts(self.build("live")))
        live._state.update(error_at=time.time() - live.LOCKED_PAUSE - 1)
        self.assertTrue(live.stale())                                # через 2 минуты — снова пробуем
        self.state.sub = None

    def test_live_table_updates_in_place(self):
        from services import live
        from ui.screens import live as live_screen
        from ui.screens import live_table as lt
        self.assertEqual((lt.gap_seconds("+1.234"), lt.gap_seconds(""), lt.gap_seconds("+1 кр.")), (1.234, 0.0, None))
        self.assertEqual(lt.flash_color(2.0, 1.5), design_system.SUCCESS)        # отрыв сократился
        self.assertEqual(lt.flash_color(1.5, 2.0), design_system.DANGER)
        self.assertIsNone(lt.flash_color(1.5, 1.52))                              # шум — не мигаем
        fill_db()
        self.state.load()

        def snap(order, gaps):
            return {"session": {"name": "Race", "type": "Race", "country": "USA", "location": "Austin",
                                "circuit": "Austin", "start": 0, "end": 0, "year": 2026},
                    "live": True, "racing": True, "lap": 30, "messages": [], "radio": [], "track": None,
                    "updated": time.time(),
                    "rows": [{"position": i, "code": c, "number": i, "name": c, "team": "", "colour": None,
                              "gap": g, "interval": g, "tyre": "M", "tyre_age": 5, "pits": 1}
                             for i, (c, g) in enumerate(zip(order, gaps, strict=True), start=1)]}
        live._state["data"] = snap(["LEC", "ANT", "LAW"], ["", "+2.000", "+5.000"])
        self.state.sub = "live"
        self.build("live")
        table = self.state.ui["live_table"]
        step = lt.row_height() + lt.ROW_GAP
        lec, ant = table.rows["LEC"]["box"], table.rows["ANT"]["box"]
        self.assertEqual((lec.top, ant.top), (0, step))
        # обгон: ANT впереди, LAW сократил отрыв -> строки меняются местами на месте, отрыв LAW подсвечен
        live._state["data"] = snap(["ANT", "LEC", "LAW"], ["", "+0.500", "+4.000"])
        with mock.patch("threading.Timer"):
            self.assertTrue(live_screen.update_in_place(self.state, live._state["data"]))
        self.assertIs(self.state.ui["live_table"], table)                       # та же таблица — анимация возможна
        self.assertEqual((ant.top, lec.top), (0, step))
        self.assertEqual(table.rows["LAW"]["gap"].value, "+4.000")
        self.assertIsNotNone(table.rows["LAW"]["gap_box"].bgcolor)
        renders = len(self.renders)
        with mock.patch.object(live_screen, "update_in_place", return_value=True):
            self.state.on_live_data()
        self.assertEqual(len(self.renders), renders)                             # без перерисовки экрана
        live._state["data"]["track"] = "Сейфти-кар"                              # структура изменилась
        self.assertFalse(live_screen.update_in_place(self.state, live._state["data"]))
        self.state.on_live_data()
        self.assertEqual(len(self.renders), renders + 1)

    def test_live_weather_sectors_favorites_card(self):
        from services import f1live, live
        self.assertEqual([f1live.sector_state(s) for s in ({"Value": "31.2", "OverallFastest": True},
                                                           {"Value": "31.2", "PersonalFastest": True},
                                                           {"Value": "31.2"}, {"Value": ""})],
                         ["overall", "personal", "normal", "none"])
        self.assertEqual(f1live.weather({"AirTemp": "29.3", "TrackTemp": "39.1", "Humidity": "25", "WindSpeed": "2.1",
                                         "Rainfall": "1"}),
                         {"air": 29.3, "track": 39.1, "humidity": 25.0, "wind": 2.1, "rain": True})
        fill_db()
        self.state.load()
        self.state.favorites = ["leclerc"]
        live._state["data"] = {
            "session": {"name": "Race", "type": "Race", "country": "USA", "location": "Austin", "circuit": "Austin",
                        "start": 0, "end": 0, "year": 2026},
            "live": True, "racing": True, "lap": 30, "messages": [], "radio": [], "track": None,
            "updated": time.time(), "weather": {"air": 29.3, "track": 39.1, "humidity": 25, "wind": 2.1, "rain": False},
            "rows": [{"position": 1, "code": "LEC", "number": 16, "name": "Charles Leclerc", "team": "Ferrari",
                      "colour": "#ED1131", "gap": "", "interval": "", "tyre": "H", "tyre_age": 11, "pits": 1,
                      "laps": 30, "last": "1:37.204", "best": "1:36.880", "sectors": ["overall", "personal", "none"]},
                     {"position": 2, "code": "ANT", "number": 12, "name": "Kimi Antonelli", "team": "Mercedes",
                      "colour": "#00D7B6", "gap": "+1.200", "interval": "+1.200", "tyre": "M", "tyre_age": 4,
                      "pits": 1, "laps": 30, "last": "1:37.5", "best": "1:37.1", "sectors": ["normal"] * 3}]}
        self.state.sub, self.state.ui["live_view"] = "live", "table"
        t = texts(self.build("live"))
        for expected in ("воздух 29°", "трасса 39°", "25 %", "2.1 м/с", "сухо"):
            self.assertIn(expected, t)
        rows = self.state.ui["live_table"].rows
        bars = rows["LEC"]["sectors"].data
        self.assertEqual([b.bgcolor for b in bars][:2], [design_system.SECTOR_OVERALL, design_system.SECTOR_PERSONAL])
        self.assertEqual([b.height for b in bars], [7, 5, 3])                    # не только цвет — ещё высота
        self.assertEqual(rows["LEC"]["sectors"].tooltip,                         # и текст для диктора
                         "Секторы: 1 — лучший в сессии, 2 — личный лучший, 3 — ещё не пройден")
        self.assertTrue(rows["LEC"]["favorite"])                                   # любимый — рамка цвета команды
        self.assertFalse(rows["ANT"]["favorite"])
        gesture = next(n for n in walk(rows["ANT"]["box"]) if type(n).__name__ == "GestureDetector")
        gesture.on_horizontal_drag_end(Ctl(primary_velocity=40))                   # случайное смещение — не свайп
        self.assertEqual(self.page.dialogs, [])
        gesture.on_horizontal_drag_end(Ctl(primary_velocity=-700))
        card = texts(self.page.dialogs[-1])
        for expected in ("P2 ANT", "+1.200", "1:37.5", "средние, 4 кр.", "30"):
            self.assertIn(expected, card)
        rows["LEC"]["box"].on_long_press(Ctl())                                    # компьютер: долгое нажатие
        self.assertIn("P1 LEC", texts(self.page.dialogs[-1]))

    def test_haptics_on_live_events(self):
        from services import live, notify
        def snap(track, order):
            return {"live": True, "track": track, "rows": [{"code": c, "position": i} for i, c in enumerate(order, 1)]}
        events = live.haptic_events(snap(None, ["VER", "LEC", "NOR"]), snap("Сейфти-кар", ["LEC", "VER", "NOR"]),
                                    {"LEC"})
        self.assertEqual(events, [("heavy", "Сейфти-кар"), ("medium", "LEC: P2 → P1")])
        self.assertEqual(live.haptic_events(snap("Сейфти-кар", ["LEC"]), snap("Сейфти-кар", ["LEC"]), {"LEC"}), [])
        self.assertEqual(live.haptic_events(None, snap("Сейфти-кар", ["LEC"])), [])      # первый снимок — тихо
        self.assertFalse(self.state.haptic("heavy"))                                     # компьютер — ничего
        tasks = []
        self.page.run_task = tasks.append
        fake = mock.Mock()
        with mock.patch.object(notify, "is_android", return_value=True), \
                mock.patch.object(sys.modules["flet"], "HapticFeedback", return_value=fake, create=True):
            self.assertTrue(self.state.haptic("heavy"))
            self.assertIs(tasks[-1], fake.heavy_impact)
            self.state.set_haptics(False)
            self.assertFalse(self.state.haptic("heavy"))                                 # выключено в настройках
            self.state.sub = "settings"
            self.assertIn("Вибрация", texts(self.build("settings")))
            self.state.set_haptics(True)
            live._state["data"] = snap("Красный флаг", ["LEC"])
            self.state._live_prev = snap(None, ["LEC"])
            n = len(tasks)
            self.state.on_live_data()
            self.assertEqual(tasks[n:], [fake.heavy_impact])                             # красный флаг — сильный отклик

    def test_iphone_is_a_phone(self):
        """На iPhone (FLET_PLATFORM=ios) — как на телефоне: вибрация есть, мини-виджета и окон нет."""
        from services import notify
        self.assertFalse(notify.is_mobile())
        self.assertIn("Мини-виджет", texts(self.build("tab4")))
        self.page.run_task = lambda fn: None
        with mock.patch.dict(os.environ, {"FLET_PLATFORM": "ios"}), \
                mock.patch.object(sys.modules["flet"], "HapticFeedback", return_value=mock.Mock(), create=True):
            self.assertTrue(notify.is_ios() and notify.is_mobile() and not notify.is_android())
            self.assertNotIn("Мини-виджет", texts(self.build("tab4")))
            self.assertTrue(self.state.haptic("light"))
            self.state.sub = "settings"
            self.assertIn("Вибрация", texts(self.build("settings")))

    def test_home_blocks_customizable(self):
        from services import radio
        from ui.screens import home_blocks as hb
        fill_db()
        add_podium()
        self.state.load()
        self.assertEqual([k for k, _ in hb.layout()], list(hb.BLOCKS))                # по умолчанию — все по порядку
        db.set_setting("home_blocks", json.dumps([{"key": "weather", "on": True}, {"key": "drivers", "on": False},
                                                  {"key": "устаревший", "on": True}]))
        lay = hb.layout()
        self.assertEqual(lay[:2], [("weather", True), ("drivers", False)])           # порядок пользователя
        self.assertEqual(len(lay), len(hb.BLOCKS))                                    # новые блоки — в конец
        db.save_archive(hb.WEATHER_KEY, {"weather": {"air": 22.0, "track": 31.0, "humidity": 40.0, "wind": 1.0,
                                                     "rain": True}, "place": "Austin", "session": "Practice 3"})
        last, _ = self.state.last_race()
        db.save_archive(radio.radio_key(last), {"start": 0, "drivers": {"16": {"code": "LEC", "colour": "ED1131"}},
                                                "messages": [{"driver": "16", "url": "https://r/x.mp3", "ts": 5}]})
        db.save_archive(radio.tx_key("https://r/x.mp3"), {"en": "Box", "ru": "Сделай пит-стоп."})
        with mock.patch.object(radio, "supported", return_value=True):
            t = texts(self.build("tab0"))
        self.assertEqual(t.index("Live Timing"), min(t.index(x) for x in ("Live Timing", "Погода на трассе")))
        self.assertLess(t.index("Погода на трассе"), t.index("Радио команд"))       # погода — первым блоком
        self.assertNotIn("Чемпионат пилотов", t)                                     # лидеры скрыты
        for expected in ("воздух 22°", "дождь", "Сделай пит-стоп.", "Радио команд"):
            self.assertIn(expected, t)
        self.assertTrue(any("прогноз ещё не сделан" in x for x in t))
        clickable(self.build("tab0"), "Настроить главную")[0].on_click(Ctl())
        self.assertEqual(self.state.sub, "home_edit")
        editor = self.build("home_edit")
        down = [n for n in walk(editor) if getattr(n, "tooltip", "") == "Погода на трассе: ниже"]
        down[0].on_click(Ctl())
        self.assertEqual([k for k, _ in hb.layout()][:2], ["drivers", "weather"])
        lst = next(n for n in walk(self.build("home_edit")) if type(n).__name__ == "ReorderableListView")
        lst.on_reorder(Ctl(old_index=0, new_index=2))
        self.assertEqual([k for k, _ in hb.layout()][:3], ["weather", "next_race", "drivers"])
        sw = [n for n in walk(self.build("home_edit")) if getattr(n, "tooltip", "") == "Лидеры: пилоты: показывать"]
        sw[0].on_change(Ctl(control=Ctl(value=True)))
        self.assertIn(("drivers", True), hb.layout())
        clickable(self.build("home_edit"), "Вернуть как было")[0].on_click(Ctl())
        self.assertEqual(hb.layout(), [(k, True) for k in hb.BLOCKS])

    def test_touch_targets_at_least_48dp(self):
        """Всё, на что нажимают, — не меньше 48 dp (минимум Android; у iOS — 44 pt). Высота оценивается по
        явной высоте, отступам и размерам текста/иконок; кнопки Flutter (IconButton, TextButton…) — 48 сами."""
        from services import live
        native = {"IconButton", "TextButton", "FilledTonalButton", "ElevatedButton", "OutlinedButton", "Switch",
                  "Checkbox", "Radio", "Dropdown", "TextField"}

        def pad_v(p):
            if isinstance(p, (int, float)):
                return 2 * p
            kind, kw = (p.args[0] if getattr(p, "args", None) else ""), getattr(p, "kw", {})
            if "symmetric" in str(kind):
                return 2 * kw.get("vertical", 0)
            if "only" in str(kind):
                return kw.get("top", 0) + kw.get("bottom", 0)
            if "all" in str(kind):
                return 2 * (p.args[1] if len(p.args) > 1 else 0)
            return 0

        def height(n):
            kind, h = type(n).__name__, getattr(n, "height", None)
            if isinstance(h, (int, float)):
                return h
            if kind in native:
                return 48
            if kind == "Text":
                return (getattr(n, "size", None) or 14) * 1.35
            if kind == "Icon":
                return getattr(n, "size", None) or 24
            kids = [c for c in n.children() if type(c).__name__ not in ("Padding", "Border", "LinearGradient",
                                                                        "Animation", "BoxShadow", "Alignment")]
            if kind == "Column":
                inner = sum(height(c) for c in kids) + (getattr(n, "spacing", 0) or 0) * max(0, len(kids) - 1)
            else:
                inner = max((height(c) for c in kids), default=0)
            return inner + pad_v(getattr(n, "padding", None) or 0)

        fill_db()
        add_podium()
        self.state.load()
        self.state.ui["driver_id"] = "leclerc"
        row = {"position": 1, "code": "LEC", "number": 16, "name": "", "team": "Ferrari", "colour": None, "gap": "",
               "interval": "", "tyre": "M", "tyre_age": 1, "pits": 0}
        live._state["data"] = {"session": {"name": "Race", "type": "Race", "country": "", "location": "", "circuit": "",
                                           "start": 0, "end": 0, "year": 2026},
                               "live": True, "racing": True, "lap": 1, "messages": [], "radio": [], "track": None,
                               "updated": time.time(), "rows": [row]}
        from ui.screens import calendar, heatmap, mini
        from ui.widgets import banner
        screens = list(self.all_screens()) + [("mini", mini.build)]

        def special():
            """Состояния, которых нет на экранах по умолчанию: плашка без сети, 3 пилота в сравнении, карта сезона."""
            self.state.status = dict(self.state.status, state="stale", error="timeout", updated_at=time.time())
            yield "banner", banner(self.state)
            self.state.set_compare([d["driver_id"] for d in self.state.standings[:3]])
            yield "compare3", app.SUBS["compare"](self.state)
            yield "heatmap", sys.modules["flet"].Column(heatmap.build_section(self.state))
            race, podium = self.state.last_race()
            calendar._show_race_details(self.state, race, podium)
            yield "race_dialog", self.page.dialogs[-1]

        small = []
        for name, tree in [(n, b(self.state)) for n, b in screens] + list(special()):
            for n in walk(tree):
                if callable(getattr(n, "on_click", None)) and type(n).__name__ not in native:
                    h = height(n)
                    if h < 47.5:
                        small.append(f"{name}: {type(n).__name__} ~{h:.0f}px {(texts(n) or [''])[0]!r}")
        self.assertEqual(small, [])

    def test_reduce_motion(self):
        """«Меньше движения»: ни одной анимации в интерфейсе; переключатель в настройках; системная настройка."""
        from services import live
        self.addCleanup(design_system.apply_reduce_motion, False)
        fill_db()
        self.state.load()
        live._state["data"] = {"session": {"name": "Race", "type": "Race", "country": "", "location": "", "circuit": "",
                                           "start": 0, "end": 0, "year": 2026},
                               "live": True, "racing": True, "lap": 1, "messages": [], "radio": [], "track": None,
                               "updated": time.time(),
                               "rows": [{"position": 1, "code": "LEC", "number": 16, "name": "", "team": "Ferrari",
                                         "colour": None, "gap": "", "interval": "", "tyre": "M", "tyre_age": 1,
                                         "pits": 0}]}
        anim_props = ("animate", "animate_position", "animate_opacity", "animate_offset", "animate_scale")

        def animated(tree):
            return [f"{type(n).__name__}.{p}" for n in walk(tree) for p in anim_props if getattr(n, p, None)]
        self.state.sub = "live"
        self.assertTrue(animated(self.build("live")))                            # обычный режим — анимации есть
        calls = []
        self.state.on_theme_change = lambda name, team: calls.append(name)
        self.state.sub = "settings"
        switch = [n for n in walk(self.build("settings")) if getattr(n, "tooltip", None) == "Меньше движения"][0]
        switch.on_change(Ctl(control=Ctl(value=True)))
        self.assertTrue(design_system.REDUCE_MOTION)
        self.assertEqual(db.get_setting("reduce_motion"), "1")
        self.assertEqual(calls, ["dark"])
        self.state.ui["driver_id"] = "leclerc"
        for name, build in list(self.all_screens()):
            self.state.sub = None if name.startswith("tab") else name
            with self.subTest(screen=name):
                tree = build(self.state)
                self.assertEqual(animated(tree), [])
                self.assertNotIn("Shimmer", {type(n).__name__ for n in walk(tree)})
        # системная настройка «Отключить анимацию» при первом запуске (пользователь сам не выбирал)
        design_system.apply_reduce_motion(False)
        with db._connect() as con:
            con.execute("DELETE FROM settings WHERE key='reduce_motion'")
        features = types.SimpleNamespace(disable_animations=True, reduce_motion=False)

        async def get_features():
            return features
        with mock.patch.object(sys.modules["flet"], "SemanticsService",
                               return_value=types.SimpleNamespace(get_accessibility_features=get_features),
                               create=True):
            self._main_with_loop()
        self.assertTrue(design_system.REDUCE_MOTION)

    def test_hero_tags_unique_per_screen(self):
        """Flutter падает, если на одном экране два Hero с одним тегом — проверяем все экраны."""
        fill_db()
        add_podium()
        self.state.load()
        self.state.favorites = [d["driver_id"] for d in self.state.standings]
        self.state.ui["driver_id"] = "leclerc"
        self.state.ui["team"] = "Ferrari"
        tagged = 0
        for name, build in self.all_screens():
            tags = [n.tag for n in walk(build(self.state)) if type(n).__name__ == "Hero"]
            tagged += len(tags)
            with self.subTest(screen=name):
                self.assertEqual(len(tags), len(set(tags)), tags)
        self.assertGreater(tagged, 5)

    def test_driver_page_opens_over_current_screen(self):
        page, tasks = self._main_with_loop()
        page.views = [Ctl()]                                   # навигатор: корневая страница
        page.navigation_bar.on_change(Ctl(control=Ctl(selected_index=3)))
        asyncio.run(tasks.pop()())
        root = page.added[0]
        drivers_screen = texts(root)
        card = clickable(root, "ANTONELLI")[0]
        card.on_click(Ctl())
        asyncio.run(tasks.pop()())
        self.assertEqual(len(page.views), 2)                   # страница пилота — поверх
        self.assertEqual(texts(page.added[0]), drivers_screen)  # экран под ней не перестроен (источник Hero)
        detail = page.views[1]
        self.assertIn("Antonelli", " ".join(texts(detail)))
        back = [n for n in walk(detail) if getattr(n, "tooltip", "") == "Назад (Esc)"][0]
        back.on_click(Ctl())
        asyncio.run(tasks.pop()())
        self.assertEqual(len(page.views), 1)                   # сняли — фото улетает обратно
        # системная «назад» Android: ответ Flutter (confirm_pop) — пока страница ещё зарегистрирована
        clickable(page.added[0], "ANTONELLI")[0].on_click(Ctl())
        asyncio.run(tasks.pop()())
        view = page.views[1]
        seen = []

        async def confirm_pop(allow):
            seen.append((allow, len(page.views)))
        asyncio.run(view.on_confirm_pop(Ctl(control=Ctl(confirm_pop=confirm_pop))))
        while tasks:
            asyncio.run(tasks.pop()())
        self.assertEqual(seen, [(False, 2)])                   # ответили до снятия страницы
        self.assertEqual(len(page.views), 1)

    def test_live_track_map(self):
        import base64
        import zlib

        from services import live, track_map
        from ui.screens import live as live_screen
        last = {"16": {"Status": "OnTrack", "X": 900, "Y": 400, "Z": 0},
                "1": {"Status": "OffTrack", "X": 100, "Y": 900, "Z": 0}}
        frames = {"Position": [{"Timestamp": "t0", "Entries": {"16": {"Status": "OnTrack", "X": 0, "Y": 0, "Z": 0}}},
                               {"Timestamp": "t1", "Entries": last}]}
        comp = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        z = base64.b64encode(comp.compress(json.dumps(frames).encode()) + comp.flush()).decode()
        positions = track_map.decode_positions(z)                            # формат Position.z потока F1
        self.assertEqual(positions["16"], {"x": 900, "y": 400, "status": "OnTrack"})   # последний кадр
        self.assertEqual(track_map.decode_positions("мусор"), {})
        outline = {"x": [0, 1000, 1000, 0], "y": [0, 0, 1000, 1000], "rotation": 0, "corners": [(1, 1000, 0)]}
        to_screen = track_map.project(outline, 300, 300, pad=10)
        self.assertEqual(tuple(round(v) for v in to_screen(0, 0)), (10, 290))   # ось Y вверх, поля по 10
        self.assertEqual(tuple(round(v) for v in to_screen(1000, 1000)), (290, 10))
        fill_db()
        self.state.load()
        db.save_archive(track_map.outline_key(9), outline)
        live._state["data"] = {"session": {"name": "Race", "type": "Race", "country": "USA", "location": "Austin",
                                           "circuit": "Austin", "start": 0, "end": 0, "year": 2026},
                               "live": True, "racing": True, "lap": 3, "messages": [], "radio": [], "track": None,
                               "updated": time.time(), "rows": [], "circuit_key": 9, "positions": positions,
                               "drivers": {"16": {"code": "LEC", "colour": "ED1131"},
                                           "1": {"code": "NOR", "colour": "F47600"}}}
        self.state.sub, self.state.ui["live_view"] = "live", "track"
        t = texts(self.build("live"))
        self.assertIn("Трасса", t)
        self.assertTrue(any(x.startswith("На трассе: 2.") for x in t))
        track = self.state.ui["live_track"]
        lec = track.dots["16"]
        before = (lec.left, lec.top)
        self.assertEqual(track.dots["1"].opacity, 0.45)                        # вне трассы — полупрозрачно
        live._state["data"]["positions"] = dict(positions, **{"16": {"x": 100, "y": 100, "status": "OnTrack"}})
        self.assertTrue(live_screen.update_in_place(self.state, live._state["data"]))
        self.assertIs(self.state.ui["live_track"], track)                     # те же точки — плавное движение
        self.assertNotEqual((lec.left, lec.top), before)

    def test_live_banner_when_session_runs(self):
        from services import live
        fill_db()
        self.state.load()
        race = self.state.schedule[3]
        quali = next(s for s in race["sessions"] if s["key"] == "Qualifying")
        self.assertEqual(live.session_is_live(self.state.schedule, now=quali["ts"] + 600), (race, "Qualifying"))
        self.assertIsNone(live.session_is_live(self.state.schedule, now=quali["ts"] - 600))
        with mock.patch.object(live, "session_is_live", return_value=(race, "Qualifying")):
            tree = self.build("tab0")
            self.assertIn("Сейчас: Квалификация", texts(tree))
            clickable(tree, "Сейчас: Квалификация")[0].on_click(Ctl())
        self.assertEqual(self.state.sub, "live")
        self.state.sub = None

    def test_notifications_flow(self):
        fill_db()
        self.state.load()
        sent = []
        self.state.notifier = mock.Mock(send=lambda *a: sent.append(a))
        race = self.state.schedule[3]                          # Италия: квалификация за сутки до гонки
        quali = next(s for s in race["sessions"] if s["key"] == "Qualifying")
        self.assertEqual(self.state.check_notifications(now=quali["ts"] - 1200), ["2026:4:Qualifying"])
        self.assertEqual(self.state.check_notifications(now=quali["ts"] - 600), [])   # повторно не шлём
        api.toggle_favorite("leclerc")
        self.state.load()
        self.state.check_notifications()                       # первый раз: старый итог только запоминаем
        self.assertEqual(len(sent), 1)
        api.set_setting("notif_results_seen", "2026:2:result")  # «вышли» новые результаты
        self.assertEqual(self.state.check_notifications(), ["2026:3:result"])
        self.assertEqual(sent[-1][1], "Итоги: Japanese GP")
        t = texts(self.build("settings"))
        self.assertIn("Уведомления".lower(), " ".join(t).lower())
        switches = [n for n in walk(self.build("settings"))
                    if type(n).__name__ == "Switch" and getattr(n, "tooltip", None) != "Меньше движения"]
        switches[0].on_change(Ctl(control=Ctl(value=False)))
        self.assertFalse(self.state.notifications_on("sessions"))
        self.assertEqual(self.state.check_notifications(now=quali["ts"] - 100), [])  # выключено

    def test_title_fight_screen(self):
        fill_db()
        self.state.load()
        self.assertEqual(self.state.season_left()[:2], (2, 0))      # этапы 4 и 5 впереди, спринтов нет
        t = texts(self.build("title"))
        self.assertIn("Чемпион мира", t)                            # отрыв 78 > 50 оставшихся очков
        self.assertIn("Остальные 2 уже не могут догнать лидера (204 очков).", t)
        self.state.ui["title_kind"] = "teams"
        t = texts(self.build("title"))
        self.assertIn("Может оформить титул", t)                     # 358 против 285 при 86 оставшихся
        self.assertIn("Для этого достаточно не уступить Ferrari.", t)
        home = self.build("tab0")
        self.assertIn("Antonelli — чемпион мира", texts(home))
        clickable(home, "Antonelli — чемпион мира")[0].on_click(Ctl())
        self.assertEqual(self.state.sub, "title")

    def test_settings_clear_requires_confirmation(self):
        fill_db()
        self.state.load()
        cleared = []
        self.state.clear_cache = lambda: cleared.append(1)
        clickable(self.build("settings"), "Очистить сохранённые данные")[0].on_click(Ctl())
        self.assertEqual(cleared, [])                            # без подтверждения ничего не стёрто
        clickable(self.page.dialogs[-1], "Отмена")[0].on_click(Ctl())
        self.assertEqual((cleared, self.page.dialogs), ([], []))
        clickable(self.build("settings"), "Очистить сохранённые данные")[0].on_click(Ctl())
        clickable(self.page.dialogs[-1], "Очистить")[-1].on_click(Ctl())
        self.assertEqual(cleared, [1])

    def test_strategy_defaults_to_next_race_track(self):
        fill_db()
        self.state.load()
        t = texts(app.SUBS["strategy"](self.state))
        self.assertIn("Monza", t)                         # ближайшая гонка — Монца
        self.assertIn("1 пит-стоп", t)

    def test_settings_content(self):
        fill_db()
        self.state.load()
        t = texts(app.SUBS["settings"](self.state))
        self.assertIn("данные свежие", t)
        self.assertIn("Jolpica F1 API", t)
        self.assertIn("О приложении", t)
        self.assertIn("Фото и логотипы", t)

    # --- обработчики нажатий не падают
    def test_handlers(self):
        fill_db()
        add_podium()
        self.state.load()
        with mock.patch.object(api, "start_background_refresh", return_value=mock.Mock()), \
             mock.patch.object(api, "refresh_all", return_value=True):
            for name, build in self.all_screens():
                with self.subTest(screen=name):
                    self.state.ui["driver_id"] = "leclerc"
                    n = click_all(build(self.state), self.state)
                    self.assertGreater(n, 0, name)
                    self.page.dialogs.clear()
            join_workers()   # потоки ручного обновления должны закончить под моками
        self.assertTrue(self.renders)

    def test_navigation_back_stack(self):
        fill_db()
        self.state.load()
        self.state.open_tab(4)
        self.state.open_sub("favorites")
        self.state.open_driver("leclerc")
        self.state.open_sub("compare")
        self.state.close_sub()
        self.assertEqual(self.state.sub, "driver_detail")
        self.state.close_sub()
        self.assertEqual(self.state.sub, "favorites")            # «назад» возвращает туда, откуда пришли
        self.state.close_sub()
        self.assertEqual((self.state.sub, self.state.tab), (None, 4))
        self.state.open_sub("settings")
        self.state.open_tab(1)
        self.state.close_sub()
        self.assertIsNone(self.state.sub)                        # смена вкладки сбрасывает историю

    def test_android_back_button(self):
        """Системная «назад»: подэкран -> вкладка -> «Главная» -> выход из приложения."""
        fill_db()
        self.state.load()
        self.state.open_tab(3)
        self.state.open_driver("leclerc")
        self.assertTrue(self.state.go_back())
        self.assertEqual((self.state.tab, self.state.sub), (3, None))
        self.assertTrue(self.state.go_back())
        self.assertEqual(self.state.tab, 0)
        self.assertFalse(self.state.go_back())                   # дальше — закрыть приложение

    def test_hotkeys(self):
        fill_db()
        self.state.load()
        with mock.patch.object(AppState, "refresh_now") as refresh:
            self.assertTrue(self.state.on_key("F5"))
            refresh.assert_called_once()
        self.state.open_sub("settings")
        self.assertTrue(self.state.on_key("F", ctrl=True))
        self.assertEqual((self.state.tab, self.state.sub), (3, None))
        field = next(n for n in walk(self.build("tab3")) if type(n).__name__ == "TextField")
        self.assertTrue(field.autofocus)                          # Ctrl+F ставит курсор в поиск
        field = next(n for n in walk(self.build("tab3")) if type(n).__name__ == "TextField")
        self.assertFalse(field.autofocus)                         # только один раз, не при каждой перерисовке
        self.assertTrue(self.state.on_key("K", ctrl=True))
        self.assertEqual(self.state.sub, "compare")
        self.assertTrue(self.state.on_key("Escape"))
        self.assertEqual((self.state.tab, self.state.sub), (3, None))
        self.assertFalse(self.state.on_key("Escape"))             # на вкладке «назад» некуда
        self.assertFalse(self.state.on_key("F"))                  # без Ctrl — обычный ввод

    def test_navigation_and_favorite_toggle(self):
        fill_db()
        self.state.load()
        self.state.open_sub("settings")
        self.assertEqual(self.state.sub, "settings")
        self.state.close_sub()
        self.assertIsNone(self.state.sub)
        self.state.toggle_favorite("norris")
        self.assertEqual(self.state.favorites, ["norris"])

    def test_team_colors(self):
        ds = design_system
        self.assertEqual(ds.get_team_color(""), ds.TEXT_DIM)      # неизвестная команда — нейтральный цвет
        self.assertEqual(ds.get_team_color("Racing Bulls"), ds.TEAMS["rb"]["color"])
        self.assertEqual(ds.get_team_color("RB F1 Team"), ds.TEAMS["rb"]["color"])
        self.assertEqual(ds.get_team_color("Red Bull"), ds.TEAMS["red_bull"]["color"])
        self.assertNotEqual(ds.get_team_color("Audi"), ds.TEXT_DIM)
        self.assertNotEqual(ds.get_team_color("Cadillac F1 Team"), ds.TEXT_DIM)
        self.assertEqual(ds.team_slug("Haas F1 Team"), "haasf1team")
        self.assertEqual(ds.F1_RED, "#E10600")

    def test_line_chart(self):
        chart = components.line_chart([("A", "#f00", [0, 25, 43]), ("B", "#f00", [0, 18, 30])], [1, 2, 3], 300)
        paths = [s for s in chart.shapes if type(s).__name__ == "Path"]
        self.assertEqual(len(paths), 2)
        self.assertIsNone(paths[0].paint.stroke_dash_pattern)
        self.assertEqual(paths[1].paint.stroke_dash_pattern, [6, 4])     # напарник того же цвета — пунктир
        self.assertEqual([components._nice_step(x) for x in (3, 11, 43, 120)], [5, 20, 50, 200])

    # --- оболочка: main() собирается, render перерисовывает и синхронизирует вкладку
    def test_main_shell(self):
        fill_db()
        page = FakePage()
        with mock.patch.object(api, "start_background_refresh", return_value=mock.Mock()):
            app.main(page)
        self.assertEqual(len(page.added), 1)
        self.assertEqual(len(page.navigation_bar.destinations), 5)
        shown = texts(page.added[0])
        self.assertIn("F1 Hub", shown)
        self.assertIn("Italian Grand Prix", shown)
        self.assertEqual(set(page.fonts), set(design_system.FONTS))

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

    def test_render_from_threads_goes_through_event_loop(self):
        """page.update() из фонового потока во Flet 0.80+ не доходит до окна — нужен run_task."""
        page, tasks = self._main_with_loop()
        on_change = page.navigation_bar.on_change
        updates = page.updates
        on_change(Ctl(control=Ctl(selected_index=2)))
        on_change(Ctl(control=Ctl(selected_index=3)))     # два запроса подряд сливаются в одну перерисовку
        self.assertEqual(len(tasks), 1)
        self.assertEqual(page.updates, updates)           # до выполнения в цикле событий окно не трогаем
        asyncio.run(tasks[0]())
        self.assertEqual(page.updates, updates + 1)
        self.assertEqual(page.navigation_bar.selected_index, 3)
        self.assertIn("Пилоты", texts(page.added[0]))

    def test_theme_switching(self):
        """Светлая тема и тема команды: палитра меняется, экраны перестраиваются, выбор сохраняется."""
        from ui import theming
        self.addCleanup(theming.apply, "dark")            # палитра — общая для всех тестов
        page, tasks = self._main_with_loop()
        page.navigation_bar.on_change(Ctl(control=Ctl(selected_index=4)))
        asyncio.run(tasks.pop()())
        clickable(page.added[0], "Настройки")[0].on_click(Ctl())     # меню «Ещё» -> настройки
        asyncio.run(tasks.pop()())
        clickable(page.added[0], "Светлая")[0].on_click(Ctl())
        self.assertEqual((design_system.THEME, design_system.BG, design_system.TEXT_PRIMARY),
                         ("light", "#F3F3F6", "#15151E"))
        self.assertEqual(page.bgcolor, "#F3F3F6")
        self.assertEqual(api.get_setting("theme"), "light")
        asyncio.run(tasks.pop()())
        clickable(page.added[0], "Команда")[0].on_click(Ctl())
        asyncio.run(tasks.pop()())
        self.assertEqual((design_system.THEME, design_system.THEME_TEAM), ("team", "Mercedes"))   # лидер Кубка
        self.assertEqual(design_system.F1_RED, design_system.TEAMS["mercedes"]["color"])
        clickable(page.added[0], "Ferrari")[0].on_click(Ctl())
        self.assertEqual(design_system.F1_RED, design_system.TEAMS["ferrari"]["color"])
        nav = page.navigation_bar.indicator_color             # фон под белой иконкой — притемнённый цвет команды
        self.assertEqual(nav, design_system.ACCENT_FILL)
        self.assertGreaterEqual(design_system.contrast(design_system.ON_ACCENT, nav), 4.5)
        asyncio.run(tasks.pop()())
        self.assertIn("Мои пилоты и их результаты", texts(app.TABS[4](AppState(page))))   # экраны собираются

    def test_mini_widget(self):
        page, tasks = self._main_with_loop()
        page.window.width, page.window.height = 500, 900
        page.navigation_bar.on_change(Ctl(control=Ctl(selected_index=4)))
        asyncio.run(tasks.pop()())
        nav = page.navigation_bar
        clickable(page.added[0], "Мини-виджет")[0].on_click(Ctl())
        asyncio.run(tasks.pop()())
        self.assertEqual((page.window.width, page.window.height, page.window.always_on_top), (340, 300, True))
        self.assertIsNone(page.navigation_bar)                    # без нижнего меню
        t = texts(page.added[0])
        for expected in ("Italian Grand Prix", "3 д 5 ч", "ANT", "LEC", "LAW"):
            self.assertIn(expected, t)

        def button(tip):
            return next(n for n in walk(page.added[0]) if str(getattr(n, "tooltip", "")).startswith(tip))
        button("Свернуть").on_click(Ctl())
        self.assertTrue(page.window.minimized)                    # окно уходит в панель задач
        page.window.minimized = False
        button("Развернуть").on_click(Ctl())
        asyncio.run(tasks.pop()())
        self.assertEqual((page.window.width, page.window.height, page.window.always_on_top), (500, 900, False))
        self.assertIs(page.navigation_bar, nav)
        state = AppState(FakePage())
        state.on_key("M", ctrl=True)
        self.assertTrue(state.mini)                               # Ctrl+M
        state.on_minimize = mock.Mock()
        state.on_key("H", ctrl=True)
        state.on_minimize.assert_called_once()                    # Ctrl+H — свернуть
        state.on_key("L", ctrl=True)
        self.assertEqual((state.mini, state.sub), (False, "live"))   # Ctrl+L — Live Timing

    def test_background_pauses_live_polling(self):
        page, _ = self._main_with_loop()
        self.state.load()
        race = self.state.schedule[3]
        self.state.sub = "live"
        with mock.patch.object(self.state, "live_now", return_value=(race, "Race")):
            self.assertTrue(self.state.live_watched())
            self.state.set_background(True)
            self.assertFalse(self.state.live_watched())               # в фоне — не опрашиваем
            renders = len(self.renders)
            with mock.patch.object(self.state, "watch_live") as watch:
                self.state.set_background(False)
            watch.assert_called_once()                                # вернулись — сразу свежие данные
            self.assertEqual(len(self.renders), renders + 1)
        page.on_app_lifecycle_state_change(Ctl(state="pause"))          # обработчик окна подключён и не падает

    def test_mini_widget_during_session(self):
        from services import live
        from ui.screens import mini
        fill_db()
        self.state.load()
        race = self.state.schedule[3]
        live._state["data"] = {"session": {"name": "Race", "start": 0}, "live": True, "racing": True, "lap": 31,
                               "total_laps": 56, "track": "Сейфти-кар", "messages": [], "updated": time.time(),
                               "rows": [{"position": i, "code": c, "colour": None, "gap": g, "interval": g,
                                         "tyre": "M"} for i, (c, g) in
                                        enumerate([("LEC", ""), ("NOR", "+1.2"), ("VER", "+0.8"), ("ANT", "+3.1"),
                                                   ("RUS", "+0.4"), ("HAM", "+2.0")], start=1)]}
        self.state.mini = True
        with mock.patch.object(self.state, "live_now", return_value=(race, "Race")):
            t = texts(mini.build(self.state))
        for expected in ("LIVE", "Гонка", "круг 31/56", "Сейфти-кар", "LEC", "лидер", "RUS", "+0.4"):
            self.assertIn(expected, t)
        self.assertNotIn("HAM", t)                                # только пятёрка

    def test_saved_theme_applied_on_start(self):
        from ui import theming
        self.addCleanup(theming.apply, "dark")
        fill_db()
        api.set_setting("theme", "light")
        page = FakePage()
        with mock.patch.object(api, "start_background_refresh", return_value=mock.Mock()):
            app.main(page)
        self.assertEqual((design_system.THEME, page.bgcolor), ("light", "#F3F3F6"))

    def test_screen_change_animates_only_on_navigation(self):
        page, tasks = self._main_with_loop()
        page.navigation_bar.on_change(Ctl(control=Ctl(selected_index=1)))
        asyncio.run(tasks.pop()())
        fades = [n for n in walk(page.added[0]) if type(n).__name__ == "FadeIn"]
        self.assertTrue(fades and all(f.opacity == 0 for f in fades))   # новый экран — появляется плавно
        page.navigation_bar.on_change(Ctl(control=Ctl(selected_index=1)))   # тот же экран (обновление)
        asyncio.run(tasks.pop()())
        fades = [n for n in walk(page.added[0]) if type(n).__name__ == "FadeIn"]
        self.assertTrue(fades and all(f.opacity == 1 for f in fades))   # перерисовка без анимации

    # --- сообщения об ошибках сети (FR-14)
    def test_banner_states(self):
        self.state.load()
        # данных нет, ошибки нет -> спокойное «Загружаем данные…»
        self.assertIn("Загружаем данные…", texts(self.build("tab1")))
        # данных нет, сеть недоступна
        self.state.status = {"state": "empty", "updated_at": None, "error": "boom"}
        t = texts(self.build("tab1"))
        self.assertIn("Не удалось загрузить данные", t)
        self.assertIn("Проверь подключение к интернету и нажми «Повторить»", " ".join(t))
        self.assertNotIn("boom", " ".join(t))                      # техническая ошибка пользователю не показывается
        # данные есть, но сеть пропала
        fill_db()
        self.state.load()
        self.state.status = {"state": "cached", "updated_at": time.time() - 7200, "error": "x"}
        for name in ("tab0", "tab1", "tab2", "tab3", "favorites"):  # баннер на всех экранах
            self.assertIn("Нет соединения с сервером данных", texts(self.build(name)), name)
        # всё хорошо / идёт обновление — баннера нет
        self.state.status = {"state": "live", "updated_at": time.time(), "error": None}
        self.assertNotIn("Нет соединения с сервером данных", texts(self.build("tab1")))
        self.state.status = {"state": "cached", "updated_at": time.time() - 7200, "error": "x"}
        self.state.refreshing = True
        self.assertNotIn("Нет соединения с сервером данных", texts(self.build("tab1")))

    def test_banner_retry_button_triggers_refresh(self):
        fill_db()
        self.state.load()
        self.state.status = {"state": "cached", "updated_at": time.time() - 7200, "error": "x"}
        calls = []
        self.state.refresh_now = lambda: calls.append(1)
        retry = [n for n in walk(self.build("tab1")) if type(n).__name__ == "Container"
                 and "Повторить" in texts(n) and callable(getattr(n, "on_click", None))]
        self.assertTrue(retry)
        retry[0].on_click(Ctl())
        self.assertEqual(calls, [1])

    def test_settings_shows_log_and_db_paths(self):
        fill_db()
        self.state.load()
        t = " ".join(texts(app.SUBS["settings"](self.state)))
        self.assertIn("База:", t)
        self.assertIn("Журнал: отключён", t)                       # в тестах файловый журнал выключен

    # --- первый запуск без сети: данные из снимка (FR-15)
    def test_first_launch_offline_uses_seed(self):
        from services import seed
        fill_db()
        snap = os.path.join(self.tmp.name, "seed.json")
        seed.export_snapshot(snap)
        with open(snap, encoding="utf-8") as f:
            data = json.load(f)
        data["exported_at"] = time.time() - 3 * 86400                       # снимок трёхдневной давности
        with open(snap, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.environ["F1_HUB_DB"] = os.path.join(self.tmp.name, "fresh.db")   # «первый запуск»
        page = FakePage()
        with mock.patch.dict(os.environ, {"F1_HUB_SEED": snap}), \
             mock.patch.object(api, "start_background_refresh", return_value=mock.Mock()):
            app.main(page)
        shown = texts(page.added[0])
        self.assertIn("Добро пожаловать", shown)                  # сначала знакомство — команды уже из снимка
        self.assertIn("Mercedes", shown)
        self.assertIsNone(page.navigation_bar)
        db.set_setting("onboarded", "1")
        page = FakePage()
        with mock.patch.dict(os.environ, {"F1_HUB_SEED": snap}), \
             mock.patch.object(api, "start_background_refresh", return_value=mock.Mock()):
            app.main(page)
        shown = texts(page.added[0])
        self.assertIn("Antonelli", shown)                         # таблица видна сразу
        self.assertIn("Из кэша", shown)                            # и честно помечена как сохранённая

    def test_screen_error_is_contained(self):
        self.state.load()
        original = app.TABS[0]
        app.TABS[0] = mock.Mock(side_effect=RuntimeError("boom"))
        try:
            tree = app.build_screen(self.state)
        finally:
            app.TABS[0] = original
        t = texts(tree)
        self.assertIn("Не удалось показать экран", t)
        self.assertNotIn("boom", " ".join(t))                  # технический текст — в журнал, а не на экран
        self.assertTrue(clickable(tree, "На главную") and clickable(tree, "Повторить"))


class FmtTest(unittest.TestCase):
    def test_plural(self):
        self.assertEqual([plural(n, "очко", "очка", "очков") for n in (1, 2, 5, 11, 12, 21, 25, 0)],
                         ["очко", "очка", "очков", "очков", "очков", "очко", "очков", "очков"])

    def test_countdown(self):
        self.assertEqual(fmt_countdown(3 * 86400 + 5 * 3600 + 60), "3 д 5 ч")
        self.assertEqual(fmt_countdown(3 * 3600 + 20 * 60), "3 ч 20 мин")
        self.assertEqual(fmt_countdown(5 * 60 + 1), "5 мин")
        self.assertEqual(fmt_countdown(10), "1 мин")
        self.assertEqual(fmt_countdown(0), "идёт сейчас")


if __name__ == "__main__":
    unittest.main()
