"""Оболочка приложения: навигация, клавиши, обработчики, баннер, настройки, уведомления.

Flet подменён заглушкой (tests/ui_support.py): ошибки в именах параметров ловит только test_real_flet.
"""
from tests.ui_support import *  # заглушка Flet, FakePage, fill_db и прочие помощники


class UiAppTest(UiTestCase):
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

    def test_settings_content(self):
        fill_db()
        self.state.load()
        t = texts(app.SUBS["settings"](self.state))
        self.assertIn("данные свежие", t)
        self.assertIn("Jolpica F1 API", t)
        self.assertIn("О приложении", t)
        self.assertIn("Фото и логотипы", t)

    def test_problem_report(self):
        """Отчёт о проблеме: без имени пользователя и путей к его папкам, ссылка не длиннее, чем примет GitHub,
        кнопка в «Настройках» показывает подсказку, что делать дальше."""
        from services import report
        home = os.path.expanduser("~")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "f1_hub.log")
            with open(path, "w", encoding="utf-8") as f:
                f.write("".join(f"2026-10-30 12:00:{i:02d} INFO f1hub.db: база {home}\\.f1_analytics_hub\\f1_hub.db "
                                f"{'длинная строка ' * 20}\n" for i in range(200)))
            full, url = report.prepare(path)
        self.assertNotIn(home, full)
        self.assertIn("~", full)
        self.assertIn("Версия:", full)
        self.assertLessEqual(len(url), report.MAX_URL)
        self.assertTrue(url.startswith(report.ISSUES))
        self.assertIn("(журнал отключён)", report.build(None))
        self.assertIn("(журнал не прочитан", report.log_tail(os.path.join(home, "нет-такого.log")))
        self.state.load()
        tree = app.SUBS["settings"](self.state)
        with mock.patch.object(report, "prepare", return_value=("отчёт", report.ISSUES)) as prepare:
            clickable(tree, "Сообщить о проблеме")[0].on_click(Ctl())
        prepare.assert_called_once()
        self.assertTrue(self.page.dialogs)                                  # подсказка «Отчёт скопирован…»

    def test_version_has_one_source(self):
        """Номер версии записан только в pyproject.toml: раньше он был в шести местах, и при выпуске
        «Настройки» показывали старый номер."""
        import re

        from services import version
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "pyproject.toml"), encoding="utf-8") as f:
            self.assertIn(f'version = "{version.VERSION}"', f.read())
        self.assertRegex(version.VERSION, r"^\d+\.\d+\.\d+$")
        self.state.load()
        self.assertTrue(any(s.startswith(f"F1 Analytics Hub {version.VERSION} —")
                            for s in texts(app.SUBS["settings"](self.state))))
        for name in ("build.bat", "BUILD.md", os.path.join(".github", "workflows", "build.yml")):
            with self.subTest(file=name), open(os.path.join(root, name), encoding="utf-8") as f:
                self.assertIsNone(re.search(r'product-version "\d', f.read()))   # номер не вписан руками
        self.assertEqual(version.read_version(os.path.join(root, "нет-такого.toml")), "")

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

    def test_handler_error_does_not_crash_session(self):
        """Ошибка в обработчике (диск полон, база занята) раньше вызывала Session.error -> красный экран
        «сессия упала». После запуска она только пишется в журнал, а пользователь видит плашку."""
        fill_db()
        page = FakePage()
        crashed = []
        page.session = Ctl(error=crashed.append)
        with mock.patch.object(api, "start_background_refresh", return_value=mock.Mock()):
            app.main(page)
        with self.assertLogs("f1hub.main", "ERROR"):
            page.session.error("sqlite3.OperationalError: disk I/O error\nTraceback …")
        self.assertEqual(crashed, [])                                       # сессия не уронена
        self.assertIn("Не получилось выполнить действие", " ".join(texts(page.dialogs[-1])))

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

    def test_error_screen_follows_theme(self):
        """main.py брал цвета через «import *» и не перезагружается при смене темы: в светлой теме сообщение
        об ошибке рисовалось белым по светлому фону — его не было видно."""
        from ui import theming
        self.addCleanup(theming.apply, "dark")
        theming.apply("light")
        self.state.load()
        original = app.TABS[0]
        app.TABS[0] = mock.Mock(side_effect=RuntimeError("boom"))
        try:
            tree = app.build_screen(self.state)
        finally:
            app.TABS[0] = original
        title = next(n for n in walk(tree) if getattr(n, "value", None) == "Не удалось показать экран")
        self.assertEqual(title.color, design_system.TEXT_PRIMARY)
        self.assertEqual(design_system.TEXT_PRIMARY, "#15151E")                # тёмный текст светлой темы

    def test_star_imports_of_tokens_are_reloaded_on_theme_change(self):
        """Кто берёт токены через «from design_system import *», получает копии значений — после смены темы
        их обновит только перезагрузка модуля. Поэтому каждый такой модуль обязан быть в списке ui.theming."""
        import re

        from ui import theming
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        star = set()
        for folder in (".", "ui", os.path.join("ui", "screens"), "services"):
            for path in glob.glob(os.path.join(root, folder, "*.py")):
                with open(path, encoding="utf-8") as f:
                    if re.search(r"^from design_system import \*", f.read(), re.MULTILINE):
                        rel = os.path.relpath(path, root)[:-3].replace(os.sep, ".")
                        star.add(rel)
        self.assertTrue(star)
        self.assertEqual(star - set(theming._screen_modules()), set())


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
