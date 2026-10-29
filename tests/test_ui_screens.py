"""Все экраны целиком: пустая и полная база, ширины, доступность, темы, анимации.

Flet подменён заглушкой (tests/ui_support.py): ошибки в именах параметров ловит только test_real_flet.
"""
from tests.ui_support import *  # заглушка Flet, FakePage, fill_db и прочие помощники


class UiScreensTest(UiTestCase):
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
        self.assertEqual(app.nav_bar(None).animation_duration.kw.get("milliseconds"), 0)   # и нижняя навигация
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

    def test_narrow_screen_with_large_text(self):
        """360 px при «Очень крупном» тексте: в Live колонка пилота схлопывалась в ноль (не было ни кода,
        ни имени), подписи плиток главной резались посередине слова («Сравне»)."""
        from services import live
        self.addCleanup(design_system.apply_font_scale, 1.0)
        design_system.apply_font_scale(1.3)
        fill_db()
        self.state.load()
        self.page.width = 360
        live._state["data"] = {"session": {"name": "Race", "type": "Race", "country": "", "location": "", "circuit": "",
                                           "start": 0, "end": 0, "year": 2026},
                               "live": True, "racing": True, "lap": 3, "messages": [], "radio": [], "track": None,
                               "updated": time.time(),
                               "rows": [{"position": 1, "code": "LEC", "number": 16, "name": "", "team": "Ferrari",
                                         "colour": None, "gap": "", "interval": "", "tyre": "M", "tyre_age": 4,
                                         "pits": 1}]}
        self.state.sub = "live"
        t = texts(self.build("live"))
        self.assertIn("LEC", t)
        self.assertNotIn("Пит", t)                                  # плотная таблица: без колонки пит-стопов
        self.assertTrue(self.state.ui["live_table"].tight)
        self.state.sub = None
        home = self.build("tab0")
        self.assertTrue(any(type(n).__name__ == "ResponsiveRow" and "Сравнение" in texts(n) for n in walk(home)))
        self.page.width = 900                                        # широко — как раньше
        self.state.sub = "live"
        self.build("live")
        self.assertFalse(self.state.ui["live_table"].tight)

    def test_driver_hero_photo_does_not_cover_text(self):
        """360 px при «Очень крупном» тексте: фото пилота шириной 0.8 высоты карточки заезжало на имя,
        команду и очки (видно на снимке /shots). Теперь фото и колонка текста делят ширину карточки."""
        for width in (360, 440, 1100):
            for scale in (1.0, 1.3):
                card_w = width - 2 * design_system.SPACE_MD
                height = round((230 if width < 800 else 280) * scale)
                for last in ("NORRIS", "ANTONELLI", "HULKENBERG"):
                    with self.subTest(width=width, scale=scale, last=last):
                        photo_w, info_w, size, _ = driver_detail.hero_layout(card_w, height, width < 800, last)
                        self.assertLessEqual(photo_w + info_w + driver_detail.HERO_GAP, card_w)   # не внахлёст
                        self.assertGreaterEqual(photo_w, 120)                                     # лицо видно
                        self.assertLessEqual(size * len(last) * 0.7, info_w)                      # фамилия целиком

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
