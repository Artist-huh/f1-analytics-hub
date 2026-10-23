"""Мини-виджет (компьютер): маленькое окно поверх остальных — таймер до гонки и топ-3 зачёта"""
import flet as ft
from design_system import *
from ui.components import *
from ui.fmt import fmt_clock, fmt_countdown, fmt_day


def build(state):
    race = state.next_race()
    items = []
    live_now = state.live_now()
    if live_now:
        from ui.fmt import SESSION_NAMES
        items.append(ft.Container(
            ft.Text(f"LIVE · {SESSION_NAMES.get(live_now[1], live_now[1])}", size=FONT_CAPTION, color=ON_COLOR,
                    font_family=FONT_ITALIC),
            bgcolor=DANGER, border_radius=RADIUS_FULL, padding=ft.Padding.symmetric(horizontal=10, vertical=3),
            on_click=lambda e: _expand_to(state, "live"), ink=True))
    if race:
        flag_src, iso = state.flag(country=race["country"])
        countdown = ft.Text("Идёт сейчас" if race["state"] == "live" else fmt_countdown(race["seconds_left"]),
                            size=FONT_H2, color=ON_COLOR, font_family=FONT_DISPLAY_ITALIC)
        if race["state"] != "live":
            state.countdown = (countdown, race["round"])     # main.ticker обновляет текст на месте
        items.append(ft.Container(ft.Column([
            ft.Row([flag(flag_src, 14, iso),
                    ft.Text(race["race_name"], size=FONT_BODY_SMALL, color=ON_COLOR, weight=ft.FontWeight.W_600,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True)], spacing=6),
            countdown,
            ft.Text(f"{fmt_day(race['start_ts'])}, {fmt_clock(race['start_ts'])}", size=FONT_CAPTION, color=ON_COLOR),
        ], spacing=0), gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                                  colors=GRADIENT_RED),
            border_radius=RADIUS_MD, padding=ft.Padding.symmetric(horizontal=SPACE_SM, vertical=SPACE_XS)))
    for d in state.standings[:3]:
        items.append(ft.Row([
            PositionBadge(d["position"], size=24),
            DriverAvatar(d["code"], d["team"], size=26, src=state.photo(d)),
            ft.Text(d["code"] or d["name"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, font_family=FONT_ITALIC,
                    expand=True),
            ft.Text(d["points"], size=FONT_BODY, color=TEXT_PRIMARY, font_family=FONT_DISPLAY_ITALIC),
        ], spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER))
    if not items:
        items.append(ft.Text("Данных пока нет", size=FONT_BODY_SMALL, color=TEXT_MUTED))
    items.append(ft.Row([
        ft.TextButton("Развернуть", icon=ft.Icons.OPEN_IN_FULL_ROUNDED, on_click=lambda e: state.toggle_mini()),
    ], alignment=ft.MainAxisAlignment.END))
    return ft.Column(items, spacing=SPACE_XS, tight=True)


def _expand_to(state, sub):
    state.toggle_mini()
    state.open_sub(sub)
