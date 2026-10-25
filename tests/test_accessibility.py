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
                self.assertGreaterEqual(ds.contrast(ds.ON_COLOR, top), 3.0)          # крупный текст
                self.assertGreaterEqual(ds.contrast(ds.ON_COLOR, bottom), AA)

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

    def test_contrast_formula(self):
        self.assertAlmostEqual(ds.contrast("#000000", "#FFFFFF"), 21.0)
        self.assertAlmostEqual(ds.contrast("#777777", "#777777"), 1.0)


if __name__ == "__main__":
    unittest.main()
