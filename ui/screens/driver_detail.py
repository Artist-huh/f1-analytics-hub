"""Детальная страница пилота: сводка сезона, очки по гонкам, результаты"""
import flet as ft
from design_system import *
from ui.components import *
from ui.fmt import MONTHS, plural, to_int
from ui.widgets import bar_chart, screen


def season_summary(results):
    """Простые показатели по списку результатов (без сети, чистая функция)."""
    positions = [to_int(r["position"]) for r in results]
    finished = [p for p in positions if p is not None]
    gains = []
    for r in results:
        pos, grid = to_int(r["position"]), to_int(r["grid"])
        if pos is not None and grid:           # grid 0 = старт из боксов, не считаем
            gains.append(grid - pos)
    return {
        "podiums": sum(1 for p in finished if p <= 3),
        "best": min(finished) if finished else None,
        "dnf": sum(1 for p in positions if p is None),
        "avg_gain": sum(gains) / len(gains) if gains else None,
        "race_points": sum(float(r["points"]) for r in results),
    }


def fmt_date_str(iso):
    """'2026-03-08' -> '8 мар' (дата гонки без часового пояса)."""
    try:
        _, m, d = iso.split("-")
        return f"{int(d)} {MONTHS[int(m) - 1]}"
    except (ValueError, IndexError, AttributeError):
        return iso or ""


def build(state):
    """Построить детальную страницу пилота"""
    driver = state.driver(state.ui.get("driver_id"))
    if not driver:
        return screen(state, "Пилот", [empty_block(ft.Icons.PERSON_OFF_ROUNDED, "Пилот не выбран",
                                                   "Выбери пилота в разделе «Пилоты» или «Чемпионат».")], back=True)

    is_mobile = ResponsiveContainer.is_mobile(page_width(state))
    results = state.driver_results(driver["driver_id"])
    summary = season_summary(results)

    sections = [
        _build_driver_header(state, driver, is_mobile),
        _build_season_stats(driver, summary, bool(results), is_narrow(state)),
    ]
    if results:
        sections += [_build_points_chart(results, summary), _build_race_results(results)]
    elif state.results_loading(driver["driver_id"]):
        sections.append(ft.Row([ft.ProgressRing(width=18, height=18, stroke_width=2, color=ACCENT_PRIMARY),
                                ft.Text("Загружаем результаты гонок…", size=FONT_BODY_SMALL, color=TEXT_MUTED)],
                               spacing=SPACE_SM))
    else:
        sections.append(empty_block(ft.Icons.FLAG_OUTLINED, "Результатов пока нет",
                                    "Появятся после первой гонки пилота или после обновления данных."))

    return screen(state, driver["name"].split()[-1], sections, subtitle=f"Сезон {driver['season']}", back=True)


def _build_driver_header(state, driver, is_mobile):
    """Header с информацией о пилоте"""
    team = driver["team"]
    color = get_team_color(team)
    fav = driver["driver_id"] in state.favorites

    def compare(e):
        state.ui["cmp1"] = driver["driver_id"]
        state.open_sub("compare")

    actions = ft.Row([
        ft.OutlinedButton(
            content=ft.Row([ft.Icon(ft.Icons.STAR_ROUNDED if fav else ft.Icons.STAR_BORDER_ROUNDED,
                                    color=TEAMS["ferrari"]["accent"] if fav else TEXT_PRIMARY, size=18),
                            ft.Text("В избранном" if fav else "В избранное", color=TEXT_PRIMARY)],
                           spacing=SPACE_XS, tight=True),
            on_click=lambda e: state.toggle_favorite(driver["driver_id"]),
        ),
        ft.OutlinedButton(
            content=ft.Row([ft.Icon(ft.Icons.COMPARE_ARROWS_ROUNDED, color=TEXT_PRIMARY, size=18),
                            ft.Text("Сравнить", color=TEXT_PRIMARY)], spacing=SPACE_XS, tight=True),
            on_click=compare,
        ),
    ], spacing=SPACE_XS, wrap=True)

    return ft.Container(
        content=ft.Column([
            ft.Row([
                DriverAvatar(driver["code"], team, size=64 if is_mobile else 80),
                ft.Column([
                    ft.Text(driver["name"], size=FONT_H3 if is_mobile else FONT_H2, weight=ft.FontWeight.BOLD,
                            color=TEXT_PRIMARY),
                    ft.Text(team, size=FONT_BODY, color=TEXT_SECONDARY),
                ], spacing=SPACE_XXS, expand=True),
                PositionBadge(driver["position"], size=44),
            ], spacing=SPACE_MD, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            actions,
        ], spacing=SPACE_SM),
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[ft.Colors.with_opacity(0.25, color), SURFACE],
        ),
        border_radius=RADIUS_LG,
        padding=SPACE_MD,
        border=ft.Border.all(1, color),
    )


def _build_season_stats(driver, s, has_results, compact):
    """Статистика за сезон"""
    dash = "…" if not has_results else "—"
    gain = s["avg_gain"]
    gain_text = dash if gain is None else f"{'+' if gain > 0 else '−' if gain < 0 else ''}{abs(gain):.1f}"
    first = [
        StatCard("Очки", driver["points"], ft.Icons.EMOJI_EVENTS_ROUNDED, ACCENT_PRIMARY, compact=compact),
        StatCard("Победы", driver["wins"], ft.Icons.MILITARY_TECH_ROUNDED, SUCCESS, compact=compact),
        StatCard("Подиумы", s["podiums"] if has_results else dash, ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
                 TEAMS["mclaren"]["primary"], compact=compact),
    ]
    second = [
        StatCard("Лучший финиш", f"P{s['best']}" if s["best"] else dash, ft.Icons.TRENDING_UP_ROUNDED, WARNING, compact=compact),
        StatCard("Сходы", s["dnf"] if has_results else dash, ft.Icons.CANCEL_ROUNDED, DANGER, compact=compact),
        StatCard("Мест со старта", gain_text, ft.Icons.SWAP_VERT_ROUNDED, INFO, compact=compact),
    ]
    return ft.Column([
        SectionHeader("Статистика сезона"),
        ft.Row(first, spacing=SPACE_XS),
        ft.Row(second, spacing=SPACE_XS),
    ], spacing=SPACE_XS)


def _build_points_chart(results, s):
    """Столбики очков по этапам"""
    items = []
    for r in results:
        pos = to_int(r["position"])
        color = POSITION_COLORS.get(pos, ACCENT_DEEP if pos else TEXT_DIM)
        items.append((r["round"], float(r["points"]), color, r["points"]))
    total = s["race_points"]
    return ft.Column([
        SectionHeader("Очки по гонкам",
                      subtitle=f"{total:g} {plural(total, 'очко', 'очка', 'очков')} за гонки (без спринтов). "
                               "Золото, серебро, бронза — подиумы."),
        ft.Container(bar_chart(items), bgcolor=SURFACE, border_radius=RADIUS_MD, padding=SPACE_SM,
                     border=ft.Border.all(1, LINE)),
    ], spacing=SPACE_SM)


def _build_race_results(results):
    """Результаты гонок, свежие сверху"""
    rows = []
    for r in reversed(results):
        pos, grid = to_int(r["position"]), to_int(r["grid"])
        delta = None if pos is None or not grid else grid - pos
        if delta is None:
            change = ft.Text("—", size=FONT_BODY_SMALL, color=TEXT_DIM)
        elif delta == 0:
            change = ft.Text("=", size=FONT_BODY_SMALL, color=TEXT_MUTED, weight=ft.FontWeight.BOLD)
        else:
            change = ft.Text(f"{'+' if delta > 0 else '−'}{abs(delta)}", size=FONT_BODY_SMALL,
                             color=SUCCESS if delta > 0 else WARNING, weight=ft.FontWeight.BOLD)
        rows.append(ft.Container(
            content=ft.Row([
                PositionBadge(pos or 0, size=34) if pos else ft.Container(
                    ft.Text(r["position"], size=FONT_BODY_SMALL, color=DANGER, weight=ft.FontWeight.BOLD),
                    width=34, height=34, alignment=ft.Alignment.CENTER, bgcolor=SURFACE_ELEVATED,
                    border_radius=RADIUS_SM, tooltip=r["status"]),
                ft.Column([
                    ft.Text(r["race_name"], size=FONT_BODY, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"Этап {r['round']} · старт {r['grid']} · {fmt_date_str(r['date'])}",
                            size=FONT_CAPTION, color=TEXT_MUTED),
                ], spacing=1, expand=True),
                ft.Column([
                    ft.Text(f"+{r['points']}", size=FONT_BODY, weight=ft.FontWeight.BOLD, color=ACCENT_PRIMARY,
                            font_family=FONT_HEADING),
                    change,
                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
            ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=SURFACE,
            border_radius=RADIUS_SM,
            padding=ft.Padding.symmetric(horizontal=SPACE_SM, vertical=SPACE_XS),
        ))
    return ft.Column([SectionHeader("Результаты гонок", subtitle="Свежие сверху"),
                      ft.Column(rows, spacing=SPACE_XXS)], spacing=SPACE_SM)
