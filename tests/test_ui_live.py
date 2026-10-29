"""Live Timing, мини-виджет, вибрация и фоновый опрос.

Flet подменён заглушкой (tests/ui_support.py): ошибки в именах параметров ловит только test_real_flet.
"""
from tests.ui_support import *  # заглушка Flet, FakePage, fill_db и прочие помощники


class UiLiveTest(UiTestCase):
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

    def test_live_sources_down_message(self):
        """Оба источника Live Timing молчат: экран говорит, что дело в источнике, а не в интернете."""
        from services import live
        saved = dict(live._state)
        self.addCleanup(live._state.update, saved)
        live._state.update(data=None, error=live.SOURCES_DOWN_TEXT, loading=False, error_at=time.time())
        self.state.sub = "live"
        t = texts(self.build("live"))
        self.assertIn("Источники данных недоступны", t)
        self.assertIn(live.SOURCES_DOWN_TEXT, t)
        self.assertNotIn("OpenF1 не ответил. Проверь интернет и повтори.", t)

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
            for name in ("model/model.bin", "model/config.json", "sentencepiece.model", "stanza/en/x.pt", "README.md",
                         "model/../../../escaped.txt"):               # «zip slip» — за пределы папки модели
                z.writestr(f"translate-en_ru-1_9/{name}", b"x")
        with mock.patch.dict(os.environ, {"FLET_APP_STORAGE_DATA": self.tmp.name}):
            radio.extract_argos(pkg)
            got = sorted(str(p.relative_to(radio.argos_dir())).replace("\\", "/")
                         for p in radio.argos_dir().rglob("*") if p.is_file())
        self.assertEqual(got, ["model/config.json", "model/model.bin", "sentencepiece.model"])   # без stanza
        self.assertFalse(glob.glob(os.path.join(self.tmp.name, "**", "escaped.txt"), recursive=True))   # не наружу
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
