"""Экран «Пилоты»: карточки с портретами, поиск и фильтр по команде"""
import flet as ft
from design_system import *
from ui.components import *
from ui.widgets import empty_state, field_border, screen


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
        border=field_border(LINE_STRONG, F1_RED),
        bgcolor=SURFACE,
        color=TEXT_PRIMARY,
        cursor_color=F1_RED,
        hint_style=ft.TextStyle(color=TEXT_MUTED),
        text_size=FONT_BODY,
        expand=True,
        autofocus=state.ui.pop("drv_focus", False),   # Ctrl+F
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
        selected_color=ACCENT_SOFT,
        bgcolor=SURFACE_RAISED,
        show_checkmark=False,
        on_select=lambda e: choose(None),
    )]
    for team in teams:
        chips.append(ft.Chip(
            label=ft.Text(team, size=FONT_BODY_SMALL),
            leading=ft.Container(width=10, height=10, bgcolor=get_team_color(team), border_radius=RADIUS_FULL),
            selected=selected == team,
            selected_color=ACCENT_SOFT,
            bgcolor=SURFACE_RAISED,
            show_checkmark=False,
            on_select=lambda e, t=team: choose(None if state.ui["drv_team"] == t else t),
        ))

    return ft.Column([
        ft.Row([search_field]),
        ft.Row(chips, spacing=SPACE_XS, scroll=ft.ScrollMode.AUTO),
    ], spacing=SPACE_SM)


def _build_driver_card(state, d):
    """Карточка пилота: градиент команды, портрет справа, номер-водяной знак."""
    top, bottom = get_team_gradient(d["team"])
    fav = d["driver_id"] in state.favorites
    s = state.driver_stats(d["driver_id"])
    flag_src, iso = state.flag(nationality=d.get("nationality"))
    parts = d["name"].split()
    first, last = " ".join(parts[:-1]), parts[-1] if parts else d["name"]
    height = scaled(184)

    portrait = ft.Container(
        image(state.photo(d, "portrait"), height=height, fit=ft.BoxFit.FIT_HEIGHT, label=f"Фото: {d['name']}",
              fallback=ft.Container()),
        right=0, bottom=0, height=height,
    )
    number = ft.Text(d.get("number") or "", size=120, font_family=FONT_DISPLAY_ITALIC,
                     color=ft.Colors.with_opacity(0.16, ON_COLOR))
    info = ft.Column([
        ft.Row([PositionBadge(d["position"], size=30), flag(flag_src, 14, iso)], spacing=SPACE_XS,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ft.Column([
            ft.Text(first, size=FONT_BODY_SMALL, color=ft.Colors.with_opacity(0.85, ON_COLOR), max_lines=1),
            ft.Text(last.upper(), size=FONT_H3, color=ON_COLOR, font_family=FONT_DISPLAY_ITALIC, max_lines=1),
            ft.Text(d["team"], size=FONT_CAPTION, color=ft.Colors.with_opacity(0.75, ON_COLOR), max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS),
        ], spacing=0),
        ft.Container(expand=True),
        ft.Row([_mini_stat(d["points"], "очки"), _mini_stat(s["wins"], "победы"), _mini_stat(s["podiums"], "подиумы")],
               spacing=SPACE_MD),
    ], spacing=SPACE_XS, width=scaled(180))

    return AnimatedCard(
        content=ft.Stack([
            ft.Container(number, right=8, top=-18),
            portrait,
            ft.Container(info, left=0, top=0, bottom=0),
            ft.Container(star_button(fav, lambda e, i=d["driver_id"]: state.toggle_favorite(i)), right=-6, top=-6),
        ], height=height - 2 * SPACE_SM, clip_behavior=ft.ClipBehavior.HARD_EDGE),
        on_click=lambda e, i=d["driver_id"]: state.open_driver(i),
        padding=ft.Padding.only(left=SPACE_MD, top=SPACE_SM, bottom=SPACE_SM),
        height=height,
        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                   colors=[top, bottom, BG_DEEP], stops=[0.0, 0.55, 1.0]),
        bgcolor=None,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.25, top)),
        accent=top,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        col={"xs": 12, "md": 6, "xl": 4},
    )


def _mini_stat(value, label):
    return ft.Column([
        ft.Text(str(value), size=FONT_H4, color=ON_COLOR, font_family=FONT_DISPLAY_ITALIC),
        ft.Text(label, size=FONT_TINY, color=ft.Colors.with_opacity(0.75, ON_COLOR)),
    ], spacing=0)


def filter_drivers(drivers, query, team):
    """Фильтр по команде и поиск по имени, коду и команде (без учёта регистра)."""
    found = [d for d in drivers if not team or d["team"] == team]
    q = (query or "").strip().lower()
    if q:
        found = [d for d in found if q in d["name"].lower() or q in d["code"].lower() or q in d["team"].lower()]
    return found
