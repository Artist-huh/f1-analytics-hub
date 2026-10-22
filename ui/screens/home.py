"""Главный экран: ближайшая гонка, сводка сезона, топ-5 пилотов и команд, быстрый доступ"""
import flet as ft
from design_system import *
from ui.components import *
from ui.fmt import fmt_countdown, fmt_day, fmt_clock, plural
from ui.widgets import empty_state, screen
from services import f1_api as api


def render(state):
    """Отрисовка главного экрана"""
    is_mobile = ResponsiveContainer.is_mobile(page_width(state))
    standings, constructors = state.standings, state.constructors

    sections = []
    race = state.next_race()
    if race:
        sections.append(_build_next_race_hero(race, state, is_mobile))

    if not standings:
        sections.append(empty_state(state, "Данных пока нет",
                                    "Подключись к интернету и нажми «Обновить» — таблицы сохранятся и будут доступны без сети."))
    else:
        sections.append(_build_season_stats(state, is_narrow(state)))
        sections.append(_build_top_drivers(state, standings[:5]))
        if constructors:
            sections.append(_build_top_constructors(state, constructors[:5]))
        favs = [d for d in standings if d["driver_id"] in state.favorites]
        if favs:
            sections.append(_build_favorites_strip(state, favs))

    sections.append(_build_quick_actions(state))

    subtitle = f"Сезон {state.season}" if state.season else None
    return screen(state, "F1 Hub", sections, subtitle=subtitle)


# ========================================
# СЕКЦИИ
# ========================================

def _build_next_race_hero(race, state, is_mobile):
    """Hero-секция с таймером до следующей гонки"""
    live = race["state"] == "live"
    countdown = ft.Text(
        "Идёт сейчас" if live else fmt_countdown(race["seconds_left"]),
        size=FONT_H1 if is_mobile else FONT_DISPLAY,
        weight=ft.FontWeight.BOLD,
        color=ACCENT_PRIMARY,
        font_family=FONT_HEADING,
    )
    if not live:
        state.countdown = (countdown, race["round"])  # main.ticker обновляет этот текст на месте

    timer = ft.Container(
        content=ft.Column([
            countdown,
            ft.Text("гонка уже идёт" if live else f"до старта · {fmt_day(race['start_ts'])}, {fmt_clock(race['start_ts'])}",
                    size=FONT_CAPTION, color=TEXT_MUTED),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
        padding=ft.Padding.symmetric(horizontal=SPACE_MD, vertical=SPACE_SM),
        bgcolor=SURFACE_ELEVATED,
        border_radius=RADIUS_LG,
    )
    button = ft.Button(
        content=ft.Row([
            ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, color=BG_DEEP, size=18),
            ft.Text("Календарь", color=BG_DEEP, weight=ft.FontWeight.W_600),
        ], spacing=SPACE_XS, tight=True),
        bgcolor=ACCENT_PRIMARY,
        on_click=lambda e: state.open_tab(2),
    )
    bottom = (ft.Column([timer, button], spacing=SPACE_SM, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
              if is_mobile else
              ft.Row([timer, button], spacing=SPACE_MD, vertical_alignment=ft.CrossAxisAlignment.CENTER))

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.SPORTS_SCORE_ROUNDED, color=ACCENT_PRIMARY, size=32),
                ft.Column([
                    ft.Text("Гонка идёт сейчас" if live else "Следующая гонка", size=FONT_CAPTION, color=TEXT_MUTED),
                    ft.Text(race["race_name"], size=FONT_H3, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                    ft.Text(f"Этап {race['round']} · {race['circuit']}, {race['country']}",
                            size=FONT_BODY_SMALL, color=TEXT_MUTED),
                ], spacing=2, expand=True),
            ], spacing=SPACE_SM),
            bottom,
        ], spacing=SPACE_MD),
        padding=SPACE_LG,
        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                   colors=[SURFACE_RAISED, SURFACE]),
        border=ft.Border.all(1, LINE),
        border_radius=RADIUS_LG,
        on_click=lambda e: state.open_tab(2),
    )


def _build_season_stats(state, compact):
    """Статистика сезона"""
    schedule = state.schedule
    done = sum(1 for r in schedule if api.race_state(r) == "past")
    leader = state.standings[0]
    team_leader = state.constructors[0] if state.constructors else None

    cards = [
        StatCard("Гонок пройдено", f"{done}/{len(schedule)}" if schedule else "—", ft.Icons.FLAG_ROUNDED,
                 compact=compact),
        StatCard("Лидер пилотов", leader["name"].split()[-1], ft.Icons.PERSON_ROUNDED,
                 subtitle=_points(leader["points"]), compact=compact),
    ]
    if team_leader:
        cards.append(StatCard("Лидер команд", team_leader["name"], ft.Icons.GROUPS_ROUNDED,
                              subtitle=_points(team_leader["points"]), compact=compact))
    return ft.Column([
        SectionHeader(f"Сезон {state.season}"),
        ft.Row(cards, spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.START),
    ], spacing=SPACE_SM)


def _build_top_drivers(state, drivers):
    """Топ-5 пилотов"""
    rows = []
    for d in drivers:
        rows.append(ft.Container(
            content=ft.Row([
                PositionBadge(d["position"]),
                DriverAvatar(d["code"], d["team"], size=40),
                ft.Column([
                    ft.Text(d["name"], size=FONT_BODY, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(d["team"], size=FONT_CAPTION, color=TEXT_MUTED, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=2, expand=True),
                _points_block(d["points"]),
            ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=SPACE_SM,
            bgcolor=SURFACE,
            border_radius=RADIUS_MD,
            border=ft.Border.all(1, SURFACE_ELEVATED),
            ink=True,
            on_click=lambda e, i=d["driver_id"]: state.open_driver(i),
        ))

    return ft.Column([
        SectionHeader("Чемпионат пилотов", subtitle="Топ-5", action_text="Все →",
                      on_action=lambda e: _open_championship(state, "drivers")),
        ft.Column(rows, spacing=SPACE_XS),
    ], spacing=SPACE_SM)


def _build_top_constructors(state, constructors):
    """Топ-5 команд"""
    leader = float(constructors[0]["points"]) or 1
    rows = []
    for c in constructors:
        color = get_team_color(c["name"])
        rows.append(ft.Container(
            content=ft.Column([
                ft.Row([
                    PositionBadge(c["position"]),
                    ft.Container(width=6, height=28, bgcolor=color, border_radius=RADIUS_SM),
                    ft.Text(c["name"], size=FONT_BODY, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY,
                            expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    _points_block(c["points"]),
                ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                progress_bar(float(c["points"]) / leader, color),
            ], spacing=SPACE_XS),
            padding=SPACE_SM,
            bgcolor=SURFACE,
            border_radius=RADIUS_MD,
            border=ft.Border.all(1, SURFACE_ELEVATED),
        ))

    return ft.Column([
        SectionHeader("Кубок конструкторов", subtitle="Топ-5", action_text="Все →",
                      on_action=lambda e: _open_championship(state, "teams")),
        ft.Column(rows, spacing=SPACE_XS),
    ], spacing=SPACE_SM)


def _build_favorites_strip(state, favs):
    """Избранные пилоты — чипы с очками"""
    chips = [
        ft.Container(
            content=ft.Row([
                ft.Container(width=4, height=20, bgcolor=get_team_color(d["team"]), border_radius=2),
                ft.Text(d["code"] or d["name"].split()[-1][:3].upper(), size=FONT_BODY,
                        weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY, font_family=FONT_HEADING),
                ft.Text(d["points"], size=FONT_BODY, weight=ft.FontWeight.BOLD, color=ACCENT_PRIMARY,
                        font_family=FONT_HEADING),
            ], spacing=6, tight=True),
            bgcolor=SURFACE, border_radius=RADIUS_SM,
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            ink=True,
            on_click=lambda e, i=d["driver_id"]: state.open_driver(i),
        )
        for d in favs
    ]
    return ft.Column([
        SectionHeader("Избранные", action_text="Все →", on_action=lambda e: state.open_sub("favorites")),
        ft.Row(chips, wrap=True, spacing=SPACE_XS, run_spacing=SPACE_XS),
    ], spacing=SPACE_SM)


def _build_quick_actions(state):
    """Быстрые действия"""
    actions = [
        (ft.Icons.PERSON_ROUNDED, "Пилоты", TEAMS["red_bull"]["primary"], lambda e: state.open_tab(3)),
        (ft.Icons.CALENDAR_MONTH_ROUNDED, "Календарь", TEAMS["ferrari"]["primary"], lambda e: state.open_tab(2)),
        (ft.Icons.STAR_ROUNDED, "Избранное", TEAMS["mclaren"]["primary"], lambda e: state.open_sub("favorites")),
        (ft.Icons.COMPARE_ARROWS_ROUNDED, "Сравнение", TEAMS["mercedes"]["primary"], lambda e: state.open_sub("compare")),
    ]
    cards = [
        ft.Container(
            content=ft.Column([
                ft.Icon(icon, size=28, color=color),
                ft.Text(label, size=FONT_CAPTION, color=TEXT_PRIMARY, max_lines=1),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=SPACE_XXS),
            padding=ft.Padding.symmetric(horizontal=SPACE_XXS, vertical=SPACE_SM),
            bgcolor=SURFACE,
            border_radius=RADIUS_MD,
            ink=True,
            on_click=handler,
            expand=True,
        )
        for icon, label, color, handler in actions
    ]
    return ft.Column([
        SectionHeader("Быстрый доступ"),
        ft.Row(cards, spacing=SPACE_XS),
    ], spacing=SPACE_SM)


# ========================================
# HELPERS
# ========================================

def _points(points):
    value = float(points)
    return f"{value:g} {plural(value, 'очко', 'очка', 'очков')}"


def _points_block(points):
    value = float(points)
    return ft.Column([
        ft.Text(f"{value:g}", size=FONT_H4, weight=ft.FontWeight.BOLD, color=ACCENT_PRIMARY, font_family=FONT_HEADING),
        ft.Text(plural(value, "очко", "очка", "очков"), size=FONT_CAPTION, color=TEXT_DIM),
    ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END)


def _open_championship(state, view):
    state.ui["champ"] = view
    state.open_tab(1)
