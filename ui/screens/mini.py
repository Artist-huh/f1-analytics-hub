"""Мини-виджет (компьютер): маленькое окно поверх остальных.
Во время сессии — живая пятёрка с отрывами и статусом трассы, в остальное время — таймер до гонки и топ-3."""
import flet as ft

from design_system import *
from services import live
from ui.components import *
from ui.fmt import SESSION_NAMES, fmt_clock, fmt_countdown, fmt_day
from ui.screens.live_table import leader_text as _leader_text


def build(state):
    live_now = state.live_now()
    items = _live(state, live_now) if live_now else _countdown(state)
    if not items:
        items = [ft.Text("Данных пока нет", size=FONT_BODY_SMALL, color=TEXT_MUTED)]
    items.append(ft.Row([
        ft.IconButton(ft.Icons.SENSORS_ROUNDED, icon_color=DANGER if live_now else TEXT_SECONDARY, icon_size=20,
                      tooltip="Live Timing (Ctrl+L)", on_click=lambda e: _expand_to(state, "live")),
        ft.Container(expand=True),
        ft.IconButton(ft.Icons.MINIMIZE_ROUNDED, icon_color=TEXT_SECONDARY, icon_size=20,
                      tooltip="Свернуть (Ctrl+H)", on_click=lambda e: state.minimize()),
        ft.IconButton(ft.Icons.OPEN_IN_FULL_ROUNDED, icon_color=TEXT_SECONDARY, icon_size=20,
                      tooltip="Развернуть (Ctrl+M)", on_click=lambda e: state.toggle_mini()),
    ], spacing=0))
    return ft.Column(items, spacing=SPACE_XS, tight=True)


def _live(state, live_now):
    """Сессия идёт: шапка LIVE и пятёрка лидеров из потока F1 (обновляется раз в 5 с)."""
    state.watch_live()
    race, key = live_now
    data, _, _ = live.snapshot()
    extra = ""
    if data:
        if data["racing"] and data.get("lap"):
            extra = f"круг {data['lap']}" + (f"/{data['total_laps']}" if data.get("total_laps") else "")
        elif data.get("remaining"):
            extra = f"осталось {data['remaining']}"
    head = ft.Container(ft.Row([
        ft.Container(width=8, height=8, border_radius=4, bgcolor=ON_COLOR),
        ft.Text("LIVE", size=FONT_CAPTION, color=ON_COLOR, font_family=FONT_ITALIC),
        ft.Text(SESSION_NAMES.get(key, key), size=FONT_CAPTION, color=ON_COLOR, expand=True),
        ft.Text(extra, size=FONT_CAPTION, color=ON_COLOR),
    ], spacing=6), bgcolor=LIVE_RED, border_radius=RADIUS_FULL, padding=ft.Padding.symmetric(horizontal=10, vertical=3),
        on_click=lambda e: _expand_to(state, "live"), ink=True, tooltip="Открыть Live Timing")
    items = [head]
    if data and data.get("track"):
        flag_bg = DANGER if "Красный" in data["track"] else WARNING
        items.append(ft.Container(ft.Text(data["track"], size=FONT_CAPTION, color=readable_on(flag_bg),
                                          weight=ft.FontWeight.BOLD),
                                  bgcolor=flag_bg, border_radius=RADIUS_SM,
                                  padding=ft.Padding.symmetric(horizontal=8, vertical=2)))
    if not data:
        items.append(skeleton("Загружаем live timing…", "rows", 3))
        return items
    for r in data["rows"][:5]:
        gap = r["interval"] if data["racing"] else r["gap"]
        items.append(ft.Row([
            ft.Text(str(r["position"]), size=FONT_BODY_SMALL, color=TEXT_SECONDARY, font_family=FONT_ITALIC,
                    width=scaled(18)),
            ft.Container(width=3, height=16, bgcolor=r["colour"] or TEXT_DIM, border_radius=2),
            ft.Text(r["code"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, font_family=FONT_ITALIC, expand=True),
            ft.Text(gap or _leader_text(r, data), size=FONT_CAPTION, font_family=FONT_MONO,
                    color=ACCENT_TEXT if r["position"] == 1 else TEXT_SECONDARY),
            ft.Text(r["tyre"] or "", size=FONT_CAPTION, color=TEXT_MUTED, width=scaled(12)),
        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER))
    return items


def _countdown(state):
    race = state.next_race()
    items = []
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
                                                  colors=HERO_CARBON),   # как герой главной: красный — только LIVE
            border_radius=RADIUS_MD, padding=ft.Padding.symmetric(horizontal=SPACE_SM, vertical=SPACE_XS)))
    for d in state.standings[:3]:
        items.append(ft.Row([
            PositionBadge(d["position"], size=24),
            DriverAvatar(d["code"], d["team"], size=26, src=state.photo(d)),
            ft.Text(d["code"] or d["name"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, font_family=FONT_ITALIC,
                    expand=True),
            ft.Text(d["points"], size=FONT_BODY, color=TEXT_PRIMARY, font_family=FONT_DISPLAY_ITALIC),
        ], spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER))
    return items


def _expand_to(state, sub):
    state.toggle_mini()
    state.open_sub(sub)
