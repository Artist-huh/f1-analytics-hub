"""Экран избранных пилотов"""
import flet as ft

from design_system import *
from ui.components import *
from ui.fmt import plural
from ui.screens.home import driver_row
from ui.widgets import screen


def build(state):
    """Построить экран избранного"""
    by_id = {d["driver_id"]: d for d in state.standings}
    favorite_drivers = [by_id[i] for i in state.favorites if i in by_id]
    missing = [i for i in state.favorites if i not in by_id]   # пилоты, которых нет в текущем зачёте

    sections = []
    if not state.favorites:
        sections.append(empty_block(ft.Icons.STAR_OUTLINE_ROUNDED, "Нет избранных пилотов",
                                    "Добавьте гонщиков, чтобы быстро отслеживать их результаты"))
    else:
        if favorite_drivers:
            sections.append(_build_quick_stats(state, favorite_drivers))
        sections.append(_build_favorites_list(state, favorite_drivers, missing))
        if len(favorite_drivers) >= 2:
            sections.append(GradientButton("Сравнить избранных", icon=ft.Icons.COMPARE_ARROWS_ROUNDED,
                                           on_click=lambda e: _compare(state, favorite_drivers)))

    if state.standings:
        sections.append(ft.Container(
            ft.Row([ft.Icon(ft.Icons.ADD_ROUNDED, color=TEXT_PRIMARY),
                    ft.Text("Добавить пилота", color=TEXT_PRIMARY, weight=ft.FontWeight.W_600)],
                   spacing=SPACE_XS, tight=True),
            height=TOUCH, alignment=ft.Alignment.CENTER, border_radius=RADIUS_FULL, bgcolor=SURFACE_RAISED,
            border=ft.Border.all(1, LINE_STRONG), ink=True, on_click=lambda e: _show_add_dialog(state)))

    n = len(state.favorites)
    return screen(state, "Избранное", sections, subtitle=f"{n} {plural(n, 'пилот', 'пилота', 'пилотов')}", back=True)


def _compare(state, drivers):
    state.ui["cmp"] = [d["driver_id"] for d in drivers][:4]
    state.open_sub("compare")


def _build_quick_stats(state, drivers):
    """Сводка по избранным"""
    total_points = sum(float(d["points"]) for d in drivers)
    total_wins = sum(state.driver_stats(d["driver_id"])["wins"] for d in drivers)
    total_podiums = sum(state.driver_stats(d["driver_id"])["podiums"] for d in drivers)
    best_position = min(int(d["position"]) for d in drivers)
    compact = is_narrow(state)
    return ft.Row([
        StatCard("Очков", f"{total_points:g}", ft.Icons.EMOJI_EVENTS_ROUNDED, TEXT_PRIMARY, compact=compact),
        StatCard("Побед", str(total_wins), ft.Icons.MILITARY_TECH_ROUNDED, GOLD, compact=compact),
        StatCard("Подиумов", str(total_podiums), ft.Icons.WORKSPACE_PREMIUM_ROUNDED, POSITION_COLORS[3],
                 compact=compact),
        StatCard("Лучшее место", f"P{best_position}", ft.Icons.TRENDING_UP_ROUNDED, ACCENT_TEXT, compact=compact),
    ], spacing=SPACE_XS)


def _build_favorites_list(state, drivers, missing):
    """Список избранных пилотов"""
    cards = []
    for d in drivers:
        trailing = star_button(True, lambda e, i=d["driver_id"]: state.toggle_favorite(i))
        points = float(d["points"])
        cards.append(driver_row(state, d, trailing=trailing,
                                subtitle=f"{points:g} {plural(points, 'очко', 'очка', 'очков')} · {d['team']}"))
    for driver_id in missing:
        cards.append(ft.Container(
            content=ft.Row([
                ft.Text(f"{driver_id} — нет в текущем зачёте", size=FONT_BODY_SMALL, color=TEXT_MUTED, expand=True),
                ft.IconButton(icon=ft.Icons.DELETE_OUTLINE_ROUNDED, icon_color=TEXT_DIM, tooltip="Убрать",
                              on_click=lambda e, i=driver_id: state.toggle_favorite(i)),
            ]),
            bgcolor=SURFACE, border_radius=RADIUS_MD, padding=ft.Padding.only(left=SPACE_MD),
        ))
    return ft.Column([SectionHeader("Мои пилоты"), ft.Column(cards, spacing=SPACE_XS)], spacing=SPACE_SM)


def _show_add_dialog(state):
    """Модальное окно выбора пилота"""
    page = state.page
    available = [d for d in state.standings if d["driver_id"] not in state.favorites]
    if not available:
        show_snack(page, "Все пилоты уже в избранном!", SURFACE_ELEVATED)
        return

    def add(driver_id):
        page.pop_dialog()
        state.toggle_favorite(driver_id)

    items = [
        ft.Container(
            content=ft.Row([
                DriverAvatar(d["code"], d["team"], size=40, src=state.photo(d)),
                ft.Column([
                    ft.Text(d["name"], size=FONT_BODY, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                    ft.Text(d["team"], size=FONT_CAPTION, color=TEXT_SECONDARY),
                ], spacing=2, expand=True),
                ft.Icon(ft.Icons.STAR_BORDER_ROUNDED, color=GOLD),
            ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=SURFACE_RAISED,
            border_radius=RADIUS_SM,
            padding=SPACE_XS,
            ink=True,
            on_click=lambda e, i=d["driver_id"]: add(i),
        )
        for d in available
    ]
    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Добавить в избранное", size=FONT_H4, color=TEXT_PRIMARY, font_family=FONT_HEADING),
        content=ft.Column(items, spacing=SPACE_XS, scroll=ft.ScrollMode.AUTO, width=380, height=420),
        actions=[ft.TextButton("Закрыть", on_click=lambda e: page.pop_dialog())],
        bgcolor=SURFACE,
    ))
