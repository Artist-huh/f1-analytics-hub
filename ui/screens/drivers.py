"""Экран выбора и просмотра пилотов"""
import flet as ft
from design_system import *
from ui.components import *
from ui.widgets import empty_state, screen


def build(state):
    """Построить экран пилотов"""
    all_drivers = state.standings
    if not all_drivers:
        return screen(state, "Пилоты", [empty_state(state, "Список пилотов пуст",
                                                     "Данные появятся после первого обновления.")])

    state.ui.setdefault("drv_q", "")
    state.ui.setdefault("drv_team", None)

    # Сетка обновляется на месте: поле поиска не пересоздаётся и не теряет фокус
    grid = ft.ResponsiveRow(spacing=SPACE_SM, run_spacing=SPACE_SM)
    counter = ft.Text(size=FONT_BODY_SMALL, color=TEXT_MUTED)

    def fill_grid():
        found = filter_drivers(all_drivers, state.ui["drv_q"], state.ui["drv_team"])
        counter.value = f"Найдено: {len(found)} из {len(all_drivers)}"
        grid.controls = [_build_driver_card(state, d) for d in found] or [
            ft.Container(empty_block(ft.Icons.SEARCH_OFF_ROUNDED, "Пилоты не найдены",
                                     "Измени запрос или сбрось фильтр команды."), col=12)
        ]

    def on_search(e):
        state.ui["drv_q"] = e.control.value or ""
        fill_grid()
        try:
            grid.update()
            counter.update()
        except RuntimeError:   # экран уже перестроен (например, фоновым обновлением) — запрос сохранён в state.ui
            state.render()

    fill_grid()
    return screen(state, "Пилоты", [
        _build_search_and_filters(state, all_drivers, on_search),
        counter,
        grid,
    ], subtitle=f"{len(all_drivers)} пилотов в сезоне {state.season}")


def _build_search_and_filters(state, drivers, on_search):
    """Поиск и фильтры"""
    search_field = ft.TextField(
        value=state.ui["drv_q"],
        hint_text="Имя, код или команда",
        prefix_icon=ft.Icons.SEARCH,
        border_color=LINE_STRONG,
        focused_border_color=ACCENT_PRIMARY,
        bgcolor=SURFACE,
        color=TEXT_PRIMARY,
        hint_style=ft.TextStyle(color=TEXT_MUTED),
        text_size=FONT_BODY,
        dense=True,
        expand=True,
        on_change=on_search,
    )

    def choose(team):
        state.ui["drv_team"] = team
        state.render()

    teams = sorted({d["team"] for d in drivers if d["team"] and d["team"] != "—"})
    selected = state.ui["drv_team"]
    chips = [ft.Chip(
        label=ft.Text("Все", size=FONT_BODY_SMALL),
        selected=selected is None,
        selected_color=SURFACE_ELEVATED,
        bgcolor=SURFACE_RAISED,
        show_checkmark=False,
        on_select=lambda e: choose(None),
    )]
    for team in teams:
        chips.append(ft.Chip(
            label=ft.Text(team, size=FONT_BODY_SMALL),
            leading=ft.Container(width=10, height=10, bgcolor=get_team_color(team), border_radius=RADIUS_FULL),
            selected=selected == team,
            selected_color=SURFACE_ELEVATED,
            bgcolor=SURFACE_RAISED,
            show_checkmark=False,
            on_select=lambda e, t=team: choose(None if state.ui["drv_team"] == t else t),
        ))

    return ft.Column([
        ft.Row([search_field]),
        ft.Row(chips, spacing=SPACE_XS, scroll=ft.ScrollMode.AUTO),
    ], spacing=SPACE_SM)


def _build_driver_card(state, d):
    """Карточка пилота"""
    color = get_team_color(d["team"])
    fav = d["driver_id"] in state.favorites
    header = ft.Row([
        DriverAvatar(d["code"], d["team"], size=48),
        ft.Column([
            ft.Text(d["name"], size=FONT_BODY_LARGE, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(d["team"], size=FONT_BODY_SMALL, color=TEXT_SECONDARY, max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS),
        ], spacing=2, expand=True),
        ft.IconButton(
            icon=ft.Icons.STAR_ROUNDED if fav else ft.Icons.STAR_BORDER_ROUNDED,
            icon_color=TEAMS["ferrari"]["accent"] if fav else TEXT_DIM,
            tooltip="Убрать из избранного" if fav else "В избранное",
            on_click=lambda e, i=d["driver_id"]: state.toggle_favorite(i),
        ),
        PositionBadge(d["position"], size=36),
    ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    stats = ft.Row([
        _mini_stat("Очки", d["points"], ACCENT_PRIMARY),
        create_divider(vertical=True),
        _mini_stat("Победы", d["wins"], SUCCESS),
        create_divider(vertical=True),
        _mini_stat("Код", d["code"] or "—", TEXT_PRIMARY),
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    return AnimatedCard(
        content=ft.Column([header, stats, ft.Container(height=3, bgcolor=color, border_radius=RADIUS_SM)],
                          spacing=SPACE_SM),
        on_click=lambda e, i=d["driver_id"]: state.open_driver(i),
        padding=SPACE_MD,
        col={"xs": 12, "md": 6, "xl": 4},
    )


def _mini_stat(label, value, color):
    """Мини-статистика"""
    return ft.Column([
        ft.Text(str(value), size=FONT_H3, weight=ft.FontWeight.BOLD, color=color, font_family=FONT_HEADING),
        ft.Text(label, size=FONT_CAPTION, color=TEXT_MUTED),
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0, expand=True)


def filter_drivers(drivers, query, team):
    """Фильтр по команде и поиск по имени, коду и команде (без учёта регистра)."""
    found = [d for d in drivers if not team or d["team"] == team]
    q = (query or "").strip().lower()
    if q:
        found = [d for d in found if q in d["name"].lower() or q in d["code"].lower() or q in d["team"].lower()]
    return found
