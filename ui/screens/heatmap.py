"""Тепловая карта сезона: пилоты × этапы, клетка окрашена по месту (гонки или квалификации)"""
import flet as ft
from design_system import *
from ui.components import *
from ui.fmt import short_name, to_int
from ui.widgets import pill

CELL = 24
LABEL_W = 46
POINTS_GREENS = ["#22C55E", "#1FB257", "#1C9F4F", "#198C47", "#16793F", "#136637", "#10532F"]   # P4 … P10


def cell_color(position_text):
    """Цвет клетки по месту: подиум — медали, 4–10 — зелёная шкала, ниже — серый, сход — красный."""
    p = to_int(position_text)
    if p is None:
        return (DANGER, ON_COLOR) if position_text and position_text != "W" else (None, TEXT_DIM)
    if p in POSITION_COLORS:
        return POSITION_COLORS[p], INK
    if p <= 10:
        return POINTS_GREENS[p - 4], ON_COLOR
    return SURFACE_ELEVATED, TEXT_MUTED


def season_grid(state, mode="race"):
    """Строки карты: [(пилот, {этап: позиция-строка})] по местам в зачёте и список этапов."""
    source = state.season_results if mode == "race" else state.qualifying
    by_driver = {}
    for r in source:
        by_driver.setdefault(r["driver_id"], {})[r["round"]] = r["position"]
    rounds = sorted({r["round"] for r in source}, key=int)
    return [(d, by_driver.get(d["driver_id"], {})) for d in state.standings], rounds


def build_section(state):
    mode = state.ui.get("heat_mode", "race")

    def switch(key):
        state.ui["heat_mode"] = key
        state.render()

    rows, rounds = season_grid(state, mode)
    if not rounds:
        return [empty_block(ft.Icons.GRID_ON_ROUNDED, "Результатов пока нет",
                            "Карта появится после первой гонки сезона.")]
    names = {r["round"]: r for r in state.schedule}

    header = [ft.Container(width=LABEL_W)]
    for rnd in rounds:
        race = names.get(rnd, {})
        flag_src, iso = state.flag(country=race.get("country")) if race else (None, "")
        header.append(ft.Container(
            ft.Column([flag(flag_src, 10, iso), ft.Text(rnd, size=FONT_MICRO, color=TEXT_DIM)],
                      spacing=1, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=CELL, tooltip=race.get("race_name", f"Этап {rnd}")))
    lines = [ft.Row(header, spacing=2)]
    for d, places in rows:
        cells = [ft.Container(
            ft.Row([ft.Container(width=3, height=16, bgcolor=get_team_color(d["team"]), border_radius=2),
                    ft.Text(d["code"] or short_name(d["name"])[:3].upper(), size=FONT_CAPTION, color=TEXT_PRIMARY,
                            font_family=FONT_ITALIC)], spacing=4),
            width=LABEL_W, on_click=lambda e, i=d["driver_id"]: state.open_driver(i), ink=True)]
        for rnd in rounds:
            pos = places.get(rnd, "")
            bg, fg = cell_color(pos)
            race = names.get(rnd, {})
            cells.append(ft.Container(
                ft.Text(pos if pos != "W" else "", size=FONT_TINY, color=fg, weight=ft.FontWeight.BOLD),
                width=CELL, height=CELL, bgcolor=bg, border_radius=4, alignment=ft.Alignment.CENTER,
                border=None if bg else ft.Border.all(1, LINE_SUBTLE),
                tooltip=f"{d['name']} · {race.get('race_name', 'этап ' + rnd)}: "
                        + (f"P{pos}" if to_int(pos) else "сход" if pos and pos != "W" else "не участвовал")))
        lines.append(ft.Row(cells, spacing=2))
    grid = ft.Row([ft.Column(lines, spacing=2)], scroll=ft.ScrollMode.AUTO)   # на телефоне — прокрутка вбок

    legend_items = [(POSITION_COLORS[1], "P1"), (POSITION_COLORS[2], "P2"), (POSITION_COLORS[3], "P3"),
                    (POINTS_GREENS[0], "очки"), (SURFACE_ELEVATED, "11+"), (DANGER, "сход")]
    legend_row = ft.Row([ft.Row([ft.Container(width=12, height=12, border_radius=3, bgcolor=c),
                                 ft.Text(t, size=FONT_CAPTION, color=TEXT_SECONDARY)], spacing=4, tight=True)
                         for c, t in legend_items], wrap=True, spacing=SPACE_SM)
    return [
        ft.Row([pill("Гонки", mode == "race", lambda e: switch("race")),
                pill("Квалификации", mode == "quali", lambda e: switch("quali"))], spacing=SPACE_XS),
        legend_row,
        AnimatedCard(grid, padding=SPACE_SM),
        ft.Text("Нажми на пилота — откроется его страница. Строки — по местам в чемпионате.",
                size=FONT_CAPTION, color=TEXT_DIM),
    ]
