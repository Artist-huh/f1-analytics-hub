"""Разделы сезона: главная, чемпионат, календарь, пилоты, сравнение, история, прогнозы.

Flet подменён заглушкой (tests/ui_support.py): ошибки в именах параметров ловит только test_real_flet.
"""
from tests.ui_support import *  # заглушка Flet, FakePage, fill_db и прочие помощники


class UiSeasonTest(UiTestCase):
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
        field.on_change(Ctl(control=Ctl(value="Леклер")))                  # по-русски — подсказка про латиницу
        self.assertTrue(any("латиницей" in t for t in texts(grid)))
        accented = [dict(rows[0], name="Sergio Pérez"), dict(rows[0], name="Nico Hülkenberg", driver_id="hul")]
        self.assertEqual([d["name"] for d in drivers.filter_drivers(accented, "perez", None)], ["Sergio Pérez"])
        self.assertEqual([d["driver_id"] for d in drivers.filter_drivers(accented, "HULKENBERG", None)], ["hul"])
        for odd in ("a" * 100000, "%_\\[(.*", "\x00", "😀" * 500, None):          # странный ввод — не падает
            drivers.filter_drivers(rows, odd, None)

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
        save = [n for n in walk(self.build("predict")) if "Сохранить" in texts(n) and getattr(n, "disabled", None)]
        self.assertTrue(save)                                                    # прогноз уже сохранён — выключена
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
        editor = self.build("home_edit")
        lst = next(n for n in walk(editor) if type(n).__name__ == "ReorderableListView")
        handles = [n for n in walk(editor) if type(n).__name__ == "ReorderableDragHandle"]
        self.assertFalse(lst.show_default_drag_handles)               # одна ручка на строку, и она слева
        self.assertEqual(len(handles), len(hb.layout()))
        lst.on_reorder(Ctl(old_index=0, new_index=2))
        self.assertEqual([k for k, _ in hb.layout()][:3], ["weather", "next_race", "drivers"])
        sw = [n for n in walk(self.build("home_edit")) if getattr(n, "tooltip", "") == "Лидеры: пилоты: показывать"]
        sw[0].on_change(Ctl(control=Ctl(value=True)))
        self.assertIn(("drivers", True), hb.layout())
        clickable(self.build("home_edit"), "Вернуть как было")[0].on_click(Ctl())
        self.assertEqual(hb.layout(), [(k, True) for k in hb.BLOCKS])

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

    def test_strategy_defaults_to_next_race_track(self):
        fill_db()
        self.state.load()
        t = texts(app.SUBS["strategy"](self.state))
        self.assertIn("Monza", t)                         # ближайшая гонка — Монца
        self.assertIn("1 пит-стоп", t)

    def test_nationality_in_russian(self):
        from ui.fmt import NATIONS_RU, nation_ru
        self.assertEqual(nation_ru("Italian"), "Италия")
        self.assertEqual(nation_ru("Monegasque"), "Монако")
        self.assertEqual(nation_ru("Martian"), "Martian")                  # неизвестное — как пришло
        self.assertEqual(nation_ru(None), "")
        missing = set(design_system.NATIONALITY_ISO) - set(NATIONS_RU)
        self.assertEqual(missing, set())                                   # у кого есть флаг — есть и название
        fill_db()
        self.state.load()
        self.state.open_driver("leclerc")
        t = texts(self.build("driver_detail"))
        self.assertIn("Монако", t)
        self.assertNotIn("Monegasque", t)
