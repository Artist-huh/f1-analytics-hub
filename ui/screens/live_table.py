"""Таблица Live Timing, которая обновляется на месте.

Обычно экран строится заново при каждом обновлении — тогда Flutter не может анимировать перестановку.
Здесь строки — постоянные элементы в Stack с анимированной позицией: при обгоне строка плавно едет на
новое место, а изменившийся отрыв на секунду подсвечивается (меньше — зелёным, больше — красным), как на
табло F1. Новые данные применяет apply(); если изменился состав или режим — экран перерисовывается целиком.
"""
import contextlib
import re
import threading

import flet as ft

from design_system import *
from ui.components import *
from ui.fmt import plural

MOVE_MS = 450          # перестановка строк
FLASH_SECONDS = 1.2    # подсветка изменившегося отрыва
ROW_GAP = 4


def row_height():
    return scaled(46)


def gap_seconds(text):
    """'+1.234' -> 1.234; '' (лидер) -> 0.0; '+1 кр.' и прочее -> None (не сравниваем)."""
    if not text:
        return 0.0
    m = re.fullmatch(r"\+?(\d+(?:\.\d+)?)", text.strip())
    return float(m.group(1)) if m else None


def flash_color(old, new, threshold=0.05):
    """Отрыв сократился — зелёный, вырос — красный, иначе None."""
    if old is None or new is None or abs(new - old) < threshold:
        return None
    return SUCCESS if new < old else DANGER


def leader_text(r, data):
    """У лидера отрыва нет: в гонке — «лидер», в практике и квалификации — его лучший круг (как на табло F1)."""
    if r["position"] != 1:
        return ""
    return "лидер" if data["racing"] else (r.get("best") or "")


def _badge_colors(pos):
    podium = pos in POSITION_COLORS
    return (POSITION_COLORS[pos] if podium else SURFACE_RAISED), (INK if podium else TEXT_PRIMARY)


class LiveTable:
    def __init__(self, state, data, mode, avatars, tyre_badge):
        self.state, self.mode, self.avatars = state, mode, avatars
        self.codes = [r["code"] for r in data["rows"]]
        self.rows = {}
        self.prev = {}
        by_code = {d["code"]: d for d in state.standings}
        boxes = []
        for i, r in enumerate(data["rows"]):
            d = by_code.get(r["code"])
            color = r["colour"] or (get_team_color(d["team"]) if d else TEXT_DIM)
            bg, fg = _badge_colors(r["position"])
            pos_text = ft.Text(str(r["position"]), size=14, color=fg, font_family=FONT_DISPLAY_ITALIC)
            badge = ft.Container(pos_text, width=28, height=28, bgcolor=bg, border_radius=RADIUS_SM,
                                 alignment=ft.Alignment.CENTER)
            gap_text = ft.Text("", size=FONT_BODY_SMALL, font_family=FONT_MONO, text_align=ft.TextAlign.RIGHT)
            gap_box = ft.Container(gap_text, width=scaled(78), alignment=ft.Alignment.CENTER_RIGHT,
                                   border_radius=6, padding=ft.Padding.symmetric(horizontal=4),
                                   animate=ft.Animation(400, ft.AnimationCurve.EASE_OUT))
            tyre_slot = ft.Container(tyre_badge(r["tyre"], r["tyre_age"]))
            pits_text = ft.Text("", size=FONT_CAPTION, color=TEXT_SECONDARY, font_family=FONT_MONO)
            pits_box = ft.Container(pits_text, width=scaled(22), alignment=ft.Alignment.CENTER)
            box = ft.Container(ft.Row([
                badge,
                ft.Container(width=3, height=30, bgcolor=color, border_radius=2),
                *([DriverAvatar(r["code"], d["team"] if d else r["team"], size=32, src=state.photo(d) if d else None)]
                  if avatars else []),
                ft.Column([ft.Text(r["code"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, font_family=FONT_ITALIC,
                                   no_wrap=True),
                           ft.Text(r["team"], size=FONT_TINY, color=TEXT_MUTED, max_lines=1,
                                   overflow=ft.TextOverflow.ELLIPSIS)], spacing=0, expand=True),
                gap_box, tyre_slot, pits_box,
            ], spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                left=0, right=0, top=i * (row_height() + ROW_GAP), height=row_height(),
                animate_position=ft.Animation(MOVE_MS, ft.AnimationCurve.EASE_IN_OUT),
                bgcolor=SURFACE, border_radius=CARD_SIZES["s"][1], border=ft.Border.all(1, LINE_SUBTLE),
                padding=ft.Padding.symmetric(horizontal=SPACE_XS, vertical=4),
                on_click=(lambda e, i=d["driver_id"]: state.open_driver(i)) if d else None, ink=bool(d))
            self.rows[r["code"]] = {"box": box, "badge": badge, "pos": pos_text, "gap": gap_text, "gap_box": gap_box,
                                    "tyre": tyre_slot, "pits": pits_text, "pits_box": pits_box}
            boxes.append(box)
        self.stack = ft.Stack(boxes, height=len(boxes) * (row_height() + ROW_GAP))
        self.tyre_badge = tyre_badge
        self.apply(data, flash=False)

    def matches(self, data, mode):
        return mode == self.mode and sorted(r["code"] for r in data["rows"]) == sorted(self.codes)

    def apply(self, data, flash=True):
        """Новые позиции и цифры; -> коды пилотов, чей отрыв подсвечен."""
        flashed = []
        for i, r in enumerate(data["rows"]):
            row = self.rows.get(r["code"])
            if row is None:
                continue
            row["box"].top = i * (row_height() + ROW_GAP)
            bg, fg = _badge_colors(r["position"])
            row["badge"].bgcolor, row["pos"].color, row["pos"].value = bg, fg, str(r["position"])
            gap = r["gap"] if self.mode == "leader" else r["interval"]
            row["gap"].value = gap or leader_text(r, data)
            row["gap"].color = TEXT_PRIMARY if gap else ACCENT_TEXT
            seconds = gap_seconds(gap) if gap or r["position"] == 1 else None
            color = flash_color(self.prev.get(r["code"]), seconds) if flash else None
            row["gap_box"].bgcolor = ft.Colors.with_opacity(0.28, color) if color else None
            if color:
                flashed.append(r["code"])
            self.prev[r["code"]] = seconds
            row["tyre"].content = self.tyre_badge(r["tyre"], r["tyre_age"])
            row["pits"].value = str(r["pits"])
            row["pits_box"].tooltip = f"{r['pits']} {plural(r['pits'], 'пит-стоп', 'пит-стопа', 'пит-стопов')}"
        if flashed:
            threading.Timer(FLASH_SECONDS, lambda: self.state.run_on_ui(self._fade)).start()
        return flashed

    def _fade(self):
        for row in self.rows.values():
            row["gap_box"].bgcolor = None
        self.update()

    def update(self):
        with contextlib.suppress(RuntimeError, AssertionError, AttributeError):   # экран уже перестроен
            self.stack.update()
