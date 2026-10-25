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

FLASH_SECONDS = 1.2    # подсветка изменившегося отрыва
ROW_GAP = 4


def row_height():
    return scaled(48)                 # зона нажатия строки — не меньше 48 dp


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


# Сектор передаётся не только цветом: ещё высотой полоски и текстом (подсказка, экранный диктор)
SECTOR_STYLE = {"overall": ("SECTOR_OVERALL", 7, "лучший в сессии"),
                "personal": ("SECTOR_PERSONAL", 5, "личный лучший"),
                "normal": ("SECTOR_NORMAL", 3, "пройден"), "none": ("LINE_STRONG", 3, "ещё не пройден")}


def sector_bars():
    """Три полоски секторов в общей рамке (вид и подпись ставит paint_sectors)."""
    bars = [ft.Container(width=scaled(12), height=3, border_radius=2, bgcolor=LINE_STRONG) for _ in range(3)]
    return ft.Container(ft.Row(bars, spacing=2, tight=True, vertical_alignment=ft.CrossAxisAlignment.END),
                        height=8, data=bars, tooltip="Секторы")


def paint_sectors(group, states):
    """Цвет, высота и подпись каждой полоски; -> текст подписи («Секторы: 1 — лучший в сессии, …»)."""
    import design_system as ds
    parts = []
    for i, (bar, st) in enumerate(zip(group.data, (list(states or []) + ["none"] * 3)[:3], strict=False), start=1):
        token, height, label = SECTOR_STYLE.get(st, SECTOR_STYLE["none"])
        bar.bgcolor, bar.height = getattr(ds, token), height
        parts.append(f"{i} — {label}")
    group.tooltip = "Секторы: " + ", ".join(parts)
    return group.tooltip


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
        favorites = set(state.favorites)
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
                                   animate=anim(ANIM_SLOW))
            tyre_slot = ft.Container(tyre_badge(r["tyre"], r["tyre_age"]))
            pits_text = ft.Text("", size=FONT_CAPTION, color=TEXT_SECONDARY, font_family=FONT_MONO)
            pits_box = ft.Container(pits_text, width=scaled(22), alignment=ft.Alignment.CENTER)
            bars = sector_bars()
            favorite = bool(d and d["driver_id"] in favorites)
            # любимый пилот — тонкая рамка цвета его команды и лёгкий фон: строку легко найти взглядом
            border = ft.Border.all(1.5, color) if favorite else ft.Border.all(1, LINE_SUBTLE)
            bg = ft.Colors.with_opacity(0.10, color) if favorite else SURFACE
            row_content = ft.Row([
                badge,
                ft.Container(width=3, height=30, bgcolor=color, border_radius=2),
                *([DriverAvatar(r["code"], d["team"] if d else r["team"], size=32, src=state.photo(d) if d else None)]
                  if avatars else []),
                ft.Column([ft.Row([ft.Text(r["code"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY,
                                           font_family=FONT_ITALIC, no_wrap=True),
                                   bars], spacing=6, tight=True),
                           ft.Text(r["team"], size=FONT_TINY, color=TEXT_MUTED, max_lines=1,
                                   overflow=ft.TextOverflow.ELLIPSIS)], spacing=2, expand=True),
                gap_box, tyre_slot, pits_box,
            ], spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            code = r["code"]
            # свайп по строке (телефон) или долгое нажатие — мини-карточка пилота, не уходя с экрана
            gesture = ft.GestureDetector(content=row_content,
                                         on_horizontal_drag_end=lambda e, c=code: self._swiped(e, c))
            box = ft.Container(gesture, on_long_press=lambda e, c=code: show_driver_card(state, c),
                               tooltip=f"{code}: нажми — страница пилота, свайп или долгое нажатие — карточка",
                left=0, right=0, top=i * (row_height() + ROW_GAP), height=row_height(),
                animate_position=anim(ANIM_MOVE, ft.AnimationCurve.EASE_IN_OUT),
                bgcolor=bg, border_radius=CARD_SIZES["s"][1], border=border,
                padding=ft.Padding.symmetric(horizontal=SPACE_XS, vertical=4),
                on_click=(lambda e, i=d["driver_id"]: state.open_driver(i)) if d else None, ink=bool(d))
            self.rows[r["code"]] = {"box": box, "badge": badge, "pos": pos_text, "gap": gap_text, "gap_box": gap_box,
                                    "tyre": tyre_slot, "pits": pits_text, "pits_box": pits_box, "sectors": bars,
                                    "favorite": favorite}
            boxes.append(box)
        self.stack = ft.Stack(boxes, height=len(boxes) * (row_height() + ROW_GAP))
        self.tyre_badge = tyre_badge
        self.apply(data, flash=False)

    def _swiped(self, e, code):
        velocity = getattr(e, "primary_velocity", None) or 0
        if abs(velocity) >= 150:                           # короткое случайное смещение — не свайп
            show_driver_card(self.state, code)

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
            paint_sectors(row["sectors"], r.get("sectors"))
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


# ---------------------------------------------------------------- мини-карточка пилота
TYRE_RU = {"S": "мягкие", "M": "средние", "H": "жёсткие", "I": "промежуточные", "W": "дождевые"}


def driver_card(state, row, data):
    """Содержимое мини-карточки: позиция, шины, круги, последний и лучший круг, отрыв, секторы."""
    d = next((x for x in state.standings if x["code"] == row["code"]), None)
    color = row.get("colour") or (get_team_color(d["team"]) if d else TEXT_DIM)

    def stat(label, value):
        return ft.Column([ft.Text(value or "—", size=FONT_BODY, color=TEXT_PRIMARY, font_family=FONT_MONO),
                          ft.Text(label, size=FONT_CAPTION, color=TEXT_MUTED)], spacing=0, expand=True)
    bars = sector_bars()
    paint_sectors(bars, row.get("sectors"))
    states = (list(row.get("sectors") or []) + ["none"] * 3)[:3]
    legend = ", ".join(f"С{i}: {SECTOR_STYLE.get(s, SECTOR_STYLE['none'])[2]}" for i, s in enumerate(states, start=1))
    gap = row["gap"]
    tyre = f"{TYRE_RU.get(row['tyre'], row['tyre'] or '—')}" + (f", {row['tyre_age']} кр." if row.get("tyre_age")
                                                                  is not None else "")
    items = [
        ft.Row([ft.Container(width=4, height=40, bgcolor=color, border_radius=2),
                DriverAvatar(row["code"], d["team"] if d else row.get("team", ""), size=44,
                             src=state.photo(d) if d else None),
                ft.Column([ft.Text(f"P{row['position']} · {row['code']}", size=FONT_H3, color=TEXT_PRIMARY,
                                   font_family=FONT_DISPLAY_ITALIC),
                           ft.Text(d["name"] if d else row.get("name", ""), size=FONT_BODY_SMALL, color=TEXT_MUTED)],
                          spacing=0, expand=True),
                ft.Column([ft.Text("Секторы", size=FONT_CAPTION, color=TEXT_MUTED), bars,
                           ft.Text(legend, size=FONT_TINY, color=TEXT_MUTED)],
                          spacing=4, horizontal_alignment=ft.CrossAxisAlignment.END)],
               spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ft.Row([stat("отрыв", gap or leader_text(row, data)), stat("последний круг", row.get("last")),
                stat("лучший круг", row.get("best"))], spacing=SPACE_SM),
        ft.Row([stat("шины", tyre), stat("кругов", str(row.get("laps") or "")), stat("пит-стопов", str(row["pits"]))],
               spacing=SPACE_SM),
    ]
    if row.get("in_pit"):
        items.append(ft.Text("Сейчас в боксах", size=FONT_BODY_SMALL, color=WARNING))
    if d:
        def open_page(e):
            state.page.pop_dialog()
            state.open_driver(d["driver_id"])
        items.append(ft.FilledTonalButton("Страница пилота", icon=ft.Icons.PERSON_ROUNDED, tooltip="Страница пилота",
                                          on_click=open_page))
    return ft.Container(ft.Column(items, spacing=SPACE_MD, tight=True), padding=SPACE_LG, bgcolor=SURFACE)


def show_driver_card(state, code):
    from services import live
    data = live.snapshot()[0]
    row = next((r for r in (data or {}).get("rows", []) if r["code"] == code), None)
    if not row:
        return
    state.page.show_dialog(ft.BottomSheet(driver_card(state, row, data), bgcolor=SURFACE, show_drag_handle=True))
