"""Доступность: контраст текста во всех темах (WCAG AA) и подписи для экранного диктора."""
import unittest

import design_system as ds

TEXT_TOKENS = ("TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_MUTED", "TEXT_DIM", "ACCENT_TEXT",
               "SUCCESS", "WARNING", "DANGER", "GOLD")
BACKGROUNDS = ("BG", "SURFACE", "SURFACE_RAISED")
AA = 4.5


class ContrastTest(unittest.TestCase):
    def tearDown(self):
        ds.apply_theme("dark")

    def check_theme(self, name, team=None, tokens=TEXT_TOKENS):
        ds.apply_theme(name, team)
        for fg in tokens:
            for bg in BACKGROUNDS:
                ratio = ds.contrast(getattr(ds, fg), getattr(ds, bg))
                with self.subTest(theme=name, team=team, fg=fg, bg=bg):
                    self.assertGreaterEqual(ratio, AA, f"{fg} {getattr(ds, fg)} на {bg} {getattr(ds, bg)}: {ratio:.2f}")

    def test_dark_and_light_text(self):
        self.check_theme("dark")
        self.check_theme("oled")
        self.check_theme("light")
        ds.apply_theme("oled")
        self.assertEqual((ds.BG, ds.THEME), ("#000000", "oled"))

    def test_team_accent_text(self):
        for team in ds.TEAMS:
            self.check_theme("team", team, tokens=("ACCENT_TEXT",))

    def test_text_on_team_colors(self):
        """Подписи на плашках цвета команды (чипы пилотов): белые или тёмные — что читается лучше."""
        for key, team in ds.TEAMS.items():
            fg = ds.readable_on(team["color"])
            with self.subTest(team=key):
                self.assertGreaterEqual(ds.contrast(fg, team["color"]), 4.0)

    def test_white_text_on_team_gradients(self):
        for key in ds.TEAMS:
            top, bottom = ds.get_team_gradient(key.replace("_", " "))
            with self.subTest(team=key):
                self.assertGreaterEqual(ds.contrast(ds.ON_COLOR, top), AA)           # на карточках и мелкие подписи
                self.assertGreaterEqual(ds.contrast(ds.ON_COLOR, bottom), AA)

    def test_text_on_accent_fill_in_every_theme(self):
        """Кнопки, вкладки, индикатор навигации: белый на ACCENT_FILL и обоих концах GRADIENT_ACCENT — 4.5:1,
        в том числе в теме любой команды (яркий цвет Mercedes или Sauber под белым был 1.7–1.8:1)."""
        cases = [("dark", None), ("oled", None), ("light", None)] + [("team", k.replace("_", " ")) for k in ds.TEAMS]
        for name, team in cases:
            ds.apply_theme(name, team)
            for bg in [ds.ACCENT_FILL, *ds.GRADIENT_ACCENT]:
                with self.subTest(theme=name, team=team, bg=bg):
                    self.assertGreaterEqual(ds.contrast(ds.ON_ACCENT, bg), AA)

    def test_live_and_flag_badges(self):
        """LIVE — белый на LIVE_RED; плашки флагов — readable_on(цвет флага) во всех темах."""
        for name in ("dark", "oled", "light"):
            ds.apply_theme(name)
            with self.subTest(theme=name):
                for bg in (ds.LIVE_RED, *ds.GRADIENT_LIVE):
                    self.assertGreaterEqual(ds.contrast(ds.ON_COLOR, bg), AA)
                for flag_bg in (ds.WARNING, ds.DANGER):
                    self.assertGreaterEqual(ds.contrast(ds.readable_on(flag_bg), flag_bg), AA)

    def test_tyres_visible_on_cards(self):
        """Шина видна на карточке: её цвет или обводка (tyre_edge) — не меньше 3:1 к SURFACE в обеих темах."""
        for name in ("dark", "light"):
            ds.apply_theme(name)
            for tyre, color in ds.TYRE_COLORS.items():
                edge = ds.tyre_edge(color) or color
                with self.subTest(theme=name, tyre=tyre):
                    self.assertGreaterEqual(ds.contrast(edge, ds.SURFACE), 3.0)
                    self.assertGreaterEqual(ds.contrast(ds.readable_on(color), color), AA)   # буква на полосе

    def test_team_colored_text_on_cards(self):
        for name in ("dark", "light"):
            ds.apply_theme(name)
            for key, team in ds.TEAMS.items():
                with self.subTest(theme=name, team=key):
                    self.assertGreaterEqual(ds.contrast(ds.readable_text(team["color"]), ds.SURFACE), AA)
                    self.assertGreaterEqual(ds.contrast(ds.readable_text(team["color"], 3.0), ds.SURFACE), 3.0)

    def test_all_fonts_bundled(self):
        """Каждый шрифт из FONTS лежит в assets — иначе Flutter молча рисует запасным шрифтом."""
        import os
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
        for family, path in ds.FONTS.items():
            with self.subTest(font=family):
                self.assertTrue(os.path.isfile(os.path.join(root, path)), path)

    def test_sector_colors_visible_in_both_themes(self):
        """Полоски секторов — не текст, но несут смысл: не меньше 3:1 к карточке (WCAG 1.4.11) в обеих темах."""
        for name in ("dark", "oled", "light"):
            ds.apply_theme(name)
            for token in ("SECTOR_OVERALL", "SECTOR_PERSONAL", "SECTOR_NORMAL"):
                with self.subTest(theme=name, token=token):
                    self.assertGreaterEqual(ds.contrast(getattr(ds, token), ds.SURFACE), 3.0)

    def test_heatmap_cells_readable(self):
        """Цифры места в клетках карты сезона читаются на любом фоне клетки (4.5:1) во всех темах."""
        for name in ("dark", "light"):
            ds.apply_theme(name)
            for p in range(1, 11):
                bg = ds.POSITION_COLORS.get(p) or ds.POINTS_GREENS[p - 4]
                fg = ds.INK if p in ds.POSITION_COLORS else ds.readable_on(bg)
                with self.subTest(theme=name, position=p):
                    self.assertGreaterEqual(ds.contrast(fg, bg), 4.5)

    def test_no_hardcoded_hex_in_screens(self):
        """Цвета живут в дизайн-системе: в экранах нет «зашитых» #RRGGBB (их не видит тест контраста)."""
        import os
        import re
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")
        found = []
        for folder, _, files in os.walk(root):
            for f in files:
                if f.endswith(".py"):
                    with open(os.path.join(folder, f), encoding="utf-8") as fh:
                        text = fh.read()
                    found += [f"{f}: {m}" for m in re.findall(r"[\"']#[0-9A-Fa-f]{6}[\"']", text)]
        self.assertEqual(found, [])

    def test_icons_one_style(self):
        """Один стиль иконок — сплошные _ROUNDED. Контурные (…_OUTLINED, а также …_OUTLINE_ROUNDED и …_BORDER_ROUNDED,
        у которых имя тоже кончается на _ROUNDED) — только там, где значат «не выбрано»: навигация, радиокнопка,
        звезда «ещё не в избранном»."""
        import os
        import re
        allowed = {("main.py", "HOME_OUTLINED"), ("main.py", "EMOJI_EVENTS_OUTLINED"),
                   ("main.py", "CALENDAR_TODAY_OUTLINED"), ("main.py", "PERSON_OUTLINE_ROUNDED"),
                   ("welcome.py", "CIRCLE_OUTLINED"), ("components.py", "STAR_BORDER_ROUNDED"),
                   ("driver_detail.py", "STAR_BORDER_ROUNDED"), ("favorites.py", "STAR_BORDER_ROUNDED")}
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        paths = [os.path.join(root, "main.py")] + [os.path.join(folder, f)
                                                   for folder, _, files in os.walk(os.path.join(root, "ui"))
                                                   for f in files if f.endswith(".py")]
        found = []
        for path in paths:
            with open(path, encoding="utf-8") as fh:
                names = re.findall(r"ft\.Icons\.([A-Z0-9_]+)", fh.read())
            name = os.path.basename(path)
            found += [f"{name}: {n}" for n in names
                      if (not n.endswith("_ROUNDED") or re.search(r"_(OUTLINE|BORDER)_", n))
                      and (name, n) not in allowed]
        self.assertEqual(found, [])

    def test_no_bright_red_under_text(self):
        """Яркий градиент GRADIENT_RED (белый на ACCENT_GLOW — 3.75:1) и DANGER как фон не используются в интерфейсе:
        под текстом — GRADIENT_ACCENT / ACCENT_FILL, «в эфире» — LIVE_RED."""
        import os
        import re
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        found = []
        for folder, _, files in os.walk(os.path.join(root, "ui")):
            for f in files:
                if f.endswith(".py"):
                    with open(os.path.join(folder, f), encoding="utf-8") as fh:
                        text = fh.read()
                    found += [f"{f}: {m}" for m in re.findall(r"GRADIENT_RED|ACCENT_GLOW|bgcolor=DANGER", text)]
        self.assertEqual(found, [])

    def test_no_middle_dot_joins(self):
        """Подписи без склеек «A · B · C» (шаблонный приём): перечисления — через запятую, счётчики — в скобках."""
        import os
        import re
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")
        found = []
        for folder, _, files in os.walk(root):
            for f in files:
                if f.endswith(".py"):
                    with open(os.path.join(folder, f), encoding="utf-8") as fh:
                        for i, line in enumerate(fh, 1):
                            code = line.split("#")[0]
                            if re.search(r"[\"'][^\"']*·[^\"']*[\"']", code):
                                found.append(f"{f}:{i}")
        self.assertEqual(found, [])

    def test_contrast_formula(self):
        self.assertAlmostEqual(ds.contrast("#000000", "#FFFFFF"), 21.0)
        self.assertAlmostEqual(ds.contrast("#777777", "#777777"), 1.0)


if __name__ == "__main__":
    unittest.main()
