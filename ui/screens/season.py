"""Экран чемпионата — турнирные таблицы пилотов и команд"""
import flet as ft
from design_system import *
from ui.components import *
from ui.fmt import plural
from ui.widgets import empty_state, pill, screen


def render(state):
    """Отрисовка экрана чемпионата"""
    is_mobile = ResponsiveContainer.is_mobile(page_width(state))
    view = state.ui.get("champ", "drivers")

    def switch_view(key):
        state.ui["champ"] = key
        state.render()

    favs = len(state.favorites)
    tabs = ft.Row([
        pill("Пилоты", view == "drivers", lambda e: switch_view("drivers")),
        pill("Команды", view == "teams", lambda e: switch_view("teams")),
        pill(f"Избранные · {favs}" if favs else "Избранные", view == "favs", lambda e: switch_view("favs")),
    ], spacing=SPACE_XS, scroll=ft.ScrollMode.AUTO)

    body = [tabs]
    if not state.standings:
        body.append(empty_state(state, "Таблицы пока нет",
                                "Подключись к интернету и нажми «Обновить» — данные сохранятся и дальше будут доступны без сети."))
    elif view == "teams":
        body.append(_build_constructor_standings(state.constructors, is_mobile))
    else:
        rows = state.standings
        if view == "favs":
            rows = [d for d in rows if d["driver_id"] in state.favorites]
        body.append(_build_driver_standings(state, rows, float(state.standings[0]["points"]), is_mobile,
                                            favs_view=view == "favs"))

    return screen(state, "Чемпионат", body, subtitle=f"Сезон {state.season}" if state.season else None)


def _build_driver_standings(state, standings, leader_points, is_mobile, favs_view=False):
    """Таблица пилотов"""
    if not standings:
        if favs_view:
            return empty_block(ft.Icons.STAR_BORDER_ROUNDED, "Нет избранных пилотов",
                               "Нажми на звёздочку рядом с пилотом — он появится здесь.")
        return empty_block(ft.Icons.TABLE_CHART_OUTLINED, "Нет данных")

    rows = []
    for d in standings:
        points = float(d["points"])
        gap = leader_points - points
        color = get_team_color(d["team"])
        fav = d["driver_id"] in state.favorites
        star = ft.IconButton(
            icon=ft.Icons.STAR_ROUNDED if fav else ft.Icons.STAR_BORDER_ROUNDED,
            icon_color=TEAMS["ferrari"]["accent"] if fav else TEXT_DIM,
            icon_size=22,
            tooltip="Убрать из избранного" if fav else "В избранное",
            on_click=lambda e, i=d["driver_id"]: state.toggle_favorite(i),
        )
        rows.append(ft.Container(
            content=ft.Column([
                ft.Row([
                    PositionBadge(d["position"]),
                    DriverAvatar(d["code"], d["team"], size=36 if is_mobile else 40),
                    ft.Column([
                        ft.Text(d["name"], size=FONT_BODY, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(d["team"], size=FONT_CAPTION, color=TEXT_MUTED, max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=2, expand=True),
                    star,
                    ft.Column([
                        ft.Text(d["points"], size=FONT_H4, weight=ft.FontWeight.BOLD, color=ACCENT_PRIMARY,
                                font_family=FONT_HEADING),
                        ft.Text("лидер" if gap <= 0 else f"−{gap:g}", size=FONT_CAPTION, color=TEXT_DIM),
                    ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
                ], spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                progress_bar(points / leader_points if leader_points else 0, color),
            ], spacing=SPACE_XS),
            padding=ft.Padding.only(left=SPACE_SM, right=SPACE_SM, top=SPACE_XS, bottom=SPACE_SM),
            bgcolor=SURFACE,
            border_radius=RADIUS_MD,
            border=ft.Border.all(1, ACCENT_DEEP if fav else SURFACE_ELEVATED),
            ink=True,
            on_click=lambda e, i=d["driver_id"]: state.open_driver(i),
        ))
    return ft.Column(rows, spacing=SPACE_XS)


def _build_constructor_standings(standings, is_mobile):
    """Таблица команд"""
    if not standings:
        return empty_block(ft.Icons.TABLE_CHART_OUTLINED, "Кубок конструкторов ещё не загружен")

    leader_points = float(standings[0]["points"])
    rows = []
    for c in standings:
        points = float(c["points"])
        wins = int(c["wins"])
        color = get_team_color(c["name"])
        rows.append(ft.Container(
            content=ft.Column([
                ft.Row([
                    PositionBadge(c["position"]),
                    ft.Container(width=6, height=32, bgcolor=color, border_radius=RADIUS_SM),
                    ft.Column([
                        ft.Text(c["name"], size=FONT_BODY, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"{wins} {plural(wins, 'победа', 'победы', 'побед')}",
                                size=FONT_CAPTION, color=TEXT_MUTED),
                    ], spacing=2, expand=True),
                    ft.Text(c["points"], size=FONT_H4, weight=ft.FontWeight.BOLD, color=ACCENT_PRIMARY,
                            font_family=FONT_HEADING),
                ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                progress_bar(points / leader_points if leader_points else 0, color),
            ], spacing=SPACE_XS),
            padding=SPACE_SM,
            bgcolor=SURFACE,
            border_radius=RADIUS_MD,
            border=ft.Border.all(1, SURFACE_ELEVATED),
        ))
    return ft.Column(rows, spacing=SPACE_XS)
