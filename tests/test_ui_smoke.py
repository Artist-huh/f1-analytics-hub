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
    return [str(n.value) for n in walk(node) if type(n).__name__ == "Text" and getattr(n, "value", None) not in (None, "")]


def make_fake_flet():
    mod = types.ModuleType("flet")

    def __getattr__(name):
        if name.startswith("__"):
            raise AttributeError(name)
        return type(name, (Ctl,), {})
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
for _m in [m for m in sys.modules if m == "ui" or m.startswith("ui.") or m == "main"]:
    del sys.modules[_m]

from services import db, f1_api as api, jolpica  # noqa: E402
from tests.test_data_layer import results_json, router, standings_json  # noqa: E402
import design_system  # noqa: E402
import main as app  # noqa: E402
from ui.fmt import fmt_countdown, plural  # noqa: E402
from ui.screens import calendar, compare, driver_detail, drivers  # noqa: E402
from ui.state import AppState  # noqa: E402


def fill_db():
    """Реальные парсеры + подставной API, затем календарь с будущими датами."""
    with mock.patch.object(jolpica._session, "get", router(standings=standings_json(), results=results_json())):
        with mock.patch.object(jolpica, "MIN_INTERVAL", 0):
            assert api.refresh_all(force=True)
    now = time.time()

    def race(rnd, name, circuit, locality, start):
        return {"round": str(rnd), "race_name": name, "circuit": circuit, "locality": locality, "country": "X",
                "date": "2026-01-01", "start_ts": start,
                "sessions": [{"key": "Qualifying", "ts": start - 86400}, {"key": "Race", "ts": start}]}
    rows = [
        race(1, "Australian Grand Prix", "Albert Park", "Melbourne", now - 90 * 86400),
        race(2, "Chinese Grand Prix", "Shanghai", "Shanghai", now - 80 * 86400),
        race(3, "Japanese Grand Prix", "Suzuka", "Suzuka", now - 70 * 86400),
        race(4, "Italian Grand Prix", "Autodromo Nazionale di Monza", "Monza", now + 3 * 86400 + 5 * 3600 + 600),
        race(5, "Singapore Grand Prix", "Marina Bay", "Marina Bay", now + 10 * 86400),
    ]
    db.save_schedule("2026", rows)


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
        api._state.update(error=None, fail_until=0.0)
        self.page = FakePage()
        self.state = AppState(self.page)
        self.renders = []
        self.state.render = lambda: self.renders.append(1)
        net = mock.patch.object(AppState, "_fetch_results", return_value=True)   # экраны не ходят в сеть
        self.fetch = net.start()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.environ.pop, "F1_HUB_DB", None)
        self.addCleanup(api.shutdown)
        self.addCleanup(net.stop)
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

    # --- с данными и на разной ширине окна: экраны собираются без ошибок
    def test_every_screen_renders_with_data_on_all_widths(self):
        fill_db()
        self.state.load()
        self.state.ui["driver_id"] = "leclerc"
        for width in (360, 430, 900, 1400):
            self.page.width = width
            for name, build in self.all_screens():
                with self.subTest(screen=name, width=width):
                    t = texts(build(self.state))
                    self.assertTrue(t)
                    self.assertFalse(any("Не удалось" in x for x in t))

    def test_home_content(self):
        fill_db()
        self.state.load()
        t = texts(self.build("tab0"))
        for expected in ("F1 Hub", "Сезон 2026", "Следующая гонка", "Italian Grand Prix", "3 д 5 ч",
                         "Antonelli", "Mercedes", "3/5", "Andrea Kimi Antonelli", "Charles Leclerc"):
            self.assertIn(expected, t)
        self.assertIsNotNone(self.state.countdown)        # отсчёт зарегистрирован для ticker
        self.assertEqual(self.state.countdown[1], "4")

    def test_home_buttons_navigate(self):
        fill_db()
        self.state.load()
        clickable(self.build("tab0"), "Избранное")[-1].on_click(Ctl())
        self.assertEqual(self.state.sub, "favorites")
        self.state.open_tab(0)
        clickable(self.build("tab0"), "Сравнение")[-1].on_click(Ctl())
        self.assertEqual(self.state.sub, "compare")
        self.state.open_tab(0)
        clickable(self.build("tab0"), "Andrea Kimi Antonelli")[-1].on_click(Ctl())
        self.assertEqual((self.state.sub, self.state.ui["driver_id"]), ("driver_detail", "antonelli"))

    def test_championship_tabs(self):
        fill_db()
        self.state.load()
        t = texts(self.build("tab1"))
        self.assertIn("Andrea Kimi Antonelli", t)
        self.assertIn("лидер", t)
        self.assertIn("−78", t)                           # отставание Леклера от лидера
        self.state.ui["champ"] = "teams"
        t = texts(self.build("tab1"))
        self.assertIn("Mercedes", t)
        self.assertIn("6 побед", t)
        self.assertIn("0 побед", t)
        self.state.ui["champ"] = "favs"
        self.assertIn("Нет избранных пилотов", texts(self.build("tab1")))
        api.toggle_favorite("leclerc")
        self.state.load()
        favs = texts(self.build("tab1"))
        self.assertIn("Charles Leclerc", favs)
        self.assertNotIn("Andrea Kimi Antonelli", favs)

    def test_calendar_upcoming_past_and_dialog(self):
        fill_db()
        self.state.load()
        t = texts(self.build("tab2"))
        self.assertIn("Ближайшая", t)
        self.assertIn("Квалификация", t)
        self.assertIn("Сезон 2026 · пройдено 3 из 5", t)
        self.assertIn("Singapore Grand Prix", t)
        self.assertIn("5,793 км", t)                      # Монца опознана по названию автодрома
        self.state.ui["cal"] = "past"
        tree = self.build("tab2")
        t = texts(tree)
        self.assertIn("P3 · +15", t)                      # результат Леклера на прошедшем этапе
        self.assertIn("R · +0", t)                        # сход
        self.assertIn("P2 · +17.5", t)
        clickable(tree, "Japanese Grand Prix")[0].on_click(Ctl())
        self.assertEqual(len(self.page.dialogs), 1)       # модальное окно с расписанием
        dialog = self.page.dialogs[0]
        self.assertIn("3. Japanese Grand Prix", texts(dialog))
        clickable(dialog, "Закрыть")[0].on_click(Ctl())
        self.assertEqual(self.page.dialogs, [])

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
        self.assertIn("Liam Lawson", texts(grid))
        self.assertNotIn("Charles Leclerc", texts(grid))
        field.on_change(Ctl(control=Ctl(value="nobody")))
        self.assertIn("Пилоты не найдены", texts(grid))

    def test_driver_detail_and_summary(self):
        fill_db()
        self.state.load()
        s = driver_detail.season_summary(self.state.results)
        self.assertEqual((s["podiums"], s["best"], s["dnf"]), (2, 2, 1))
        self.assertAlmostEqual(s["avg_gain"], 1.0)
        self.assertAlmostEqual(s["race_points"], 32.5)
        self.state.open_driver("leclerc")
        t = texts(self.build("driver_detail"))
        for expected in ("Charles Leclerc", "+1.0", "P2", "Результаты гонок", "Japanese GP"):
            self.assertIn(expected, t)

    def test_driver_detail_loads_other_driver_results_on_demand(self):
        fill_db()
        self.state.load()
        self.state.open_driver("antonelli")
        self.build("driver_detail")
        for _ in range(100):
            if self.fetch.called and not self.state.results_loading("antonelli"):
                break
            time.sleep(0.02)
        self.fetch.assert_called_once_with("antonelli")
        self.assertIn("Результатов пока нет", texts(self.build("driver_detail")))
        self.fetch.assert_called_once()                   # повторно в сеть не идём

    def test_compare_numbers_and_head_to_head(self):
        fill_db()
        self.state.load()
        self.state.ui.update(cmp1="lawson", cmp2="leclerc")
        tree = self.build("compare")
        pos_row = next(n for n in walk(tree) if type(n).__name__ == "Row" and "Позиция" in texts(n))
        colors = {n.value: n.color for n in walk(pos_row) if type(n).__name__ == "Text" and n.value in ("10", "4")}
        self.assertEqual(colors["4"], design_system.SUCCESS)   # P4 лучше P10 (раньше сравнивались строки)
        self.assertNotEqual(colors["10"], design_system.SUCCESS)
        r1 = [{"round": "1", "race_name": "A", "position": "3"}, {"round": "2", "race_name": "B", "position": "R"},
              {"round": "3", "race_name": "C", "position": "5"}, {"round": "4", "race_name": "D", "position": "R"}]
        r2 = [{"round": "1", "race_name": "A", "position": "1"}, {"round": "2", "race_name": "B", "position": "9"},
              {"round": "3", "race_name": "C", "position": "R"}, {"round": "4", "race_name": "D", "position": "R"}]
        w1, w2, races = compare.head_to_head(r1, r2)
        self.assertEqual((w1, w2, len(races)), (1, 2, 3))      # двойной сход не считается

    def test_compare_select_and_swap(self):
        fill_db()
        self.state.load()
        first, second = [n for n in walk(self.build("compare")) if type(n).__name__ == "Dropdown"]
        self.assertEqual((first.value, second.value), ("antonelli", "leclerc"))
        first.on_select(Ctl(control=Ctl(value="leclerc")))     # тот же пилот, что во втором слоте
        self.assertEqual((self.state.ui["cmp1"], self.state.ui["cmp2"]), ("leclerc", "antonelli"))
        swap = next(n for n in walk(self.build("compare")) if getattr(n, "tooltip", None) == "Поменять местами")
        swap.on_click(Ctl())
        self.assertEqual((self.state.ui["cmp1"], self.state.ui["cmp2"]), ("antonelli", "leclerc"))

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
        t = texts(self.build("favorites"))
        self.assertIn("165", t)                                  # 39 + 126 — числа, а не строки
        self.assertIn("P4", t)
        api.toggle_favorite("antonelli")
        self.state.load()
        clickable(self.build("favorites"), "Добавить пилота")[0].on_click(Ctl())
        self.assertIn("Все пилоты уже в избранном!", texts(self.page.dialogs[-1]))   # уведомление

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

    def test_duel_and_settings(self):
        fill_db()
        self.state.load()
        t = texts(app.SUBS["duel"](self.state))
        self.assertIn("Позиция в зачёте", t)
        self.assertIn("Antonelli впереди на 78", t)
        t = texts(app.SUBS["settings"](self.state))
        self.assertIn("данные свежие", t)
        self.assertIn("Jolpica F1 API", t)

    # --- обработчики нажатий не падают
    def test_handlers(self):
        fill_db()
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
        self.assertEqual(design_system.get_team_color(""), design_system.TEXT_DIM)      # раньше — цвет Red Bull
        self.assertEqual(design_system.get_team_color("Racing Bulls"), design_system.TEAMS["rb"]["primary"])
        self.assertEqual(design_system.get_team_color("Red Bull"), design_system.TEAMS["red_bull"]["primary"])
        self.assertNotEqual(design_system.get_team_color("Audi"), design_system.TEXT_DIM)
        self.assertNotEqual(design_system.get_team_color("Cadillac F1 Team"), design_system.TEXT_DIM)

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

    def test_render_from_threads_goes_through_event_loop(self):
        """page.update() из фонового потока во Flet 0.80+ не доходит до окна — нужен run_task."""
        fill_db()
        page = FakePage()
        tasks = []
        page.run_task = tasks.append
        with mock.patch.object(api, "start_background_refresh", return_value=mock.Mock()), \
             mock.patch("threading.Thread.start"):
            app.main(page)
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
        self.assertIn("Andrea Kimi Antonelli", shown)              # таблица видна сразу
        self.assertIn("Из кэша", shown)                            # и честно помечена как сохранённая

    def test_screen_error_is_contained(self):
        self.state.load()
        original = app.TABS[0]
        app.TABS[0] = mock.Mock(side_effect=RuntimeError("boom"))
        try:
            tree = app.build_screen(self.state)
        finally:
            app.TABS[0] = original
        self.assertIn("Не удалось показать экран", texts(tree))


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
