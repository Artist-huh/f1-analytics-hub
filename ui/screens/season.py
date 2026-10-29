"""Экран чемпионата — турнирные таблицы пилотов и команд"""
import flet as ft

from design_system import *
from ui.components import *
from ui.rows import driver_row, team_row, tower
from ui.screens import heatmap
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
        pill("Карта сезона", view == "heat", lambda e: switch_view("heat")),
    ], spacing=SPACE_XS, scroll=ft.ScrollMode.AUTO)

    body = [tabs]
    if not state.standings:
        body.append(empty_state(state, "Таблицы пока нет",
                                "Подключись к интернету и нажми «Обновить» — данные сохранятся "
                                "и дальше будут доступны без сети."))
    elif view == "teams":
        body += _build_constructor_standings(state, is_mobile)
    elif view == "heat":
        body += heatmap.build_section(state)
    else:
        rows = state.standings
        if view == "favs":
            rows = [d for d in rows if d["driver_id"] in state.favorites]
        body += _build_driver_standings(state, rows, float(state.standings[0]["points"]), favs_view=view == "favs")

    return screen(state, "Чемпионат", body, subtitle=f"Сезон {state.season}" if state.season else None)


def _build_driver_standings(state, standings, leader_points, favs_view=False):
    """Таблица пилотов: строки появляются по очереди"""
    if not standings:
        if favs_view:
            return [empty_block(ft.Icons.STAR_ROUNDED, "Нет избранных пилотов",
                                "Нажми на звёздочку рядом с пилотом — он появится здесь.",
                                ("Выбрать пилотов", lambda e: state.open_tab(3)))]
        return [empty_block(ft.Icons.REFRESH_ROUNDED, "Нет данных", "Таблица появится после обновления.",
                            ("Обновить", lambda e: state.refresh_now()), art="flag")]

    rows = []
    for d in standings:
        points = float(d["points"])
        gap = leader_points - points
        fav = d["driver_id"] in state.favorites
        trailing = ft.Row([
            star_button(fav, lambda e, i=d["driver_id"]: state.toggle_favorite(i)),
            ft.Column([
                ft.Text(d["points"], size=FONT_H4, color=TEXT_PRIMARY, font_family=FONT_DISPLAY_ITALIC),
                ft.Text("лидер" if gap <= 0 else f"−{gap:g}", size=FONT_CAPTION,
                        color=ACCENT_TEXT if gap <= 0 else TEXT_DIM),
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END, width=52),
        ], spacing=0, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        rows.append(driver_row(state, d, trailing=trailing, flat=True))
    return [tower(rows)]


def _build_constructor_standings(state, is_mobile):
    """Таблица команд: логотипы, пилоты, болид"""
    standings = state.constructors
    if not standings:
        return [empty_block(ft.Icons.REFRESH_ROUNDED, "Кубок конструкторов ещё не загружен", None,
                            ("Обновить", lambda e: state.refresh_now()), art="flag")]
    leader_points = float(standings[0]["points"]) or 1
    cards = [ft.Container(team_row(state, c, leader_points, show_car=not is_mobile or i == 0),
                          col={"xs": 12, "lg": 6})
             for i, c in enumerate(standings)]
    return [ft.ResponsiveRow(cards, spacing=SPACE_XS, run_spacing=SPACE_XS)]   # на широком экране — 2 колонки
