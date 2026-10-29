"""Страница пилота: портрет, статистика сезона, график очков, результаты гонок"""
import flet as ft

from design_system import *
from services import stats as st
from ui.components import *
from ui.fmt import MONTHS, plural, short_name, to_int
from ui.widgets import screen


def season_summary(results):
    """Краткая сводка по результатам (используется и в тестах)."""
    s = st.driver_stats(results)
    return {"podiums": s["podiums"], "best": s["best"], "dnf": s["dnf"], "avg_gain": s["avg_gain"],
            "race_points": s["race_points"]}


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
                                                   "Выбери пилота в разделе «Пилоты» или «Чемпионат».",
                                                   ("К списку пилотов", lambda e: state.open_tab(3)))], back=True)

    is_mobile = ResponsiveContainer.is_mobile(page_width(state))
    results = state.driver_results(driver["driver_id"])
    s = state.driver_stats(driver["driver_id"])

    sections = [
        _build_hero(state, driver, is_mobile),
        _build_actions(state, driver),
        _build_stats(driver, s, bool(results)),
    ]
    if results:
        sections += [_build_points_chart(state, driver), _build_points_by_race(results),
                     _build_race_results(state, driver, results)]
    elif state.results_loading(driver["driver_id"]):
        sections.append(skeleton("Загружаем результаты гонок…", "rows", 5))
    else:
        sections.append(empty_block(ft.Icons.FLAG_ROUNDED, "Результатов пока нет",
                                    "Появятся после первой гонки пилота или после обновления данных.", art="flag"))

    return screen(state, short_name(driver["name"]), sections, subtitle=f"Сезон {driver['season']}", back=True)


def _build_hero(state, driver, is_mobile):
    """Портрет на градиенте команды, номер, флаг, логотип команды, позиция и очки."""
    team = driver["team"]
    top, bottom = get_team_gradient(team)
    height = 230 if is_mobile else 280
    flag_src, iso = state.flag(nationality=driver.get("nationality"))
    parts = driver["name"].split()
    first, last = " ".join(parts[:-1]), parts[-1]

    info = ft.Column([
        ft.Row([flag(flag_src, 16, iso), ft.Text(driver.get("nationality", ""), size=FONT_CAPTION,
                                                  color=ON_COLOR)],
               spacing=6),
        ft.Column([
            ft.Text(first, size=FONT_BODY_LARGE, color=ON_COLOR),
            ft.Text(last.upper(), size=FONT_H1 if not is_mobile else FONT_H2, color=ON_COLOR,
                    font_family=FONT_DISPLAY_ITALIC),
        ], spacing=0),
        ft.Container(ft.Row([TeamLogo(team, state.team_logo(team), size=30),
                             ft.Text(team, size=FONT_BODY_SMALL, color=ON_COLOR, weight=ft.FontWeight.W_600,
                                     expand=True,
                                     max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)], spacing=SPACE_XS),
                     on_click=lambda e: _open_team_of(state, team), ink=True, border_radius=RADIUS_SM,
                     height=TOUCH, tooltip="Страница команды"),                    # зона нажатия 48 dp
        ft.Container(expand=True),
        ft.Row([
            _hero_value(f"P{driver['position']}", "в зачёте"),
            _hero_value(driver["points"], plural(float(driver["points"]), "очко", "очка", "очков")),
        ], spacing=SPACE_LG),
    ], spacing=SPACE_XS, width=200 if is_mobile else 260)

    return ft.Container(
        content=ft.Stack([
            ft.Container(ft.Text(driver.get("number") or "", size=180, font_family=FONT_DISPLAY_ITALIC,
                                 color=ft.Colors.with_opacity(0.15, ON_COLOR)), right=10, top=-40),
            ft.Container(driver_hero(driver["driver_id"],
                                     image(state.photo(driver, "hero"), width=round(height * 0.8), height=height,
                                           fit=ft.BoxFit.COVER, label=f"Фото: {driver['name']}",
                                           fallback=ft.Container(width=round(height * 0.8), height=height))),
                         right=SPACE_LG, top=PHOTO_DROP + 4),   # голова не у края
            ft.Container(info, left=SPACE_MD, top=SPACE_MD, bottom=SPACE_MD),
        ], height=height, clip_behavior=ft.ClipBehavior.HARD_EDGE),
        height=height,
        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                   colors=[top, bottom, BG_DEEP], stops=[0.0, 0.6, 1.0]),
        border_radius=RADIUS_LG,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        shadow=glow(top, 0.3),
    )


def _open_team_of(state, team_name):
    """Название команды у пилота и в Кубке конструкторов может отличаться — ищем по ключу команды."""
    key = team_key(team_name)
    match = next((c["name"] for c in state.constructors if team_key(c["name"]) == key and key), team_name)
    state.open_team(match)


def _hero_value(value, label):
    return ft.Column([
        ft.Text(str(value), size=FONT_H2, color=ON_COLOR, font_family=FONT_DISPLAY_ITALIC),
        ft.Text(label, size=FONT_CAPTION, color=ON_COLOR),
    ], spacing=0)


def _build_actions(state, driver):
    fav = driver["driver_id"] in state.favorites

    def action(icon, label, on_click, color=TEXT_PRIMARY):
        return ft.Container(
            ft.Row([ft.Icon(icon, color=color, size=20),
                    ft.Text(label, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600)],
                   spacing=SPACE_XS, tight=True, alignment=ft.MainAxisAlignment.CENTER),
            height=TOUCH, expand=True, border_radius=RADIUS_MD, bgcolor=SURFACE_RAISED,
            border=ft.Border.all(1, LINE), ink=True, on_click=on_click, alignment=ft.Alignment.CENTER,
        )

    return ft.Row([
        action(ft.Icons.STAR_ROUNDED if fav else ft.Icons.STAR_BORDER_ROUNDED,
               "В избранном" if fav else "В избранное",
               lambda e: state.toggle_favorite(driver["driver_id"]), GOLD if fav else TEXT_PRIMARY),
        action(ft.Icons.COMPARE_ARROWS_ROUNDED, "Сравнить", lambda e: state.compare_with(driver["driver_id"]),
               ACCENT_TEXT),
    ], spacing=SPACE_XS)


def _build_stats(driver, s, has_results):
    """8 показателей сезона сеткой 4×2 (на телефоне тоже 4 в ряд — компактно)."""
    dash = "…" if not has_results else "—"
    best = f"P{s['best']}" if s["best"] else dash
    items = [
        ("Очки", driver["points"], ft.Icons.EMOJI_EVENTS_ROUNDED, TEXT_PRIMARY),
        ("Победы", s["wins"], ft.Icons.MILITARY_TECH_ROUNDED, GOLD),
        ("Подиумы", s["podiums"], ft.Icons.WORKSPACE_PREMIUM_ROUNDED, POSITION_COLORS[3]),
        ("Поулы", s["poles"], ft.Icons.TIMER_ROUNDED, ACCENT_TEXT),
        ("Быстрые круги", s["fastest_laps"], ft.Icons.SPEED_ROUNDED, SECTOR_OVERALL),   # фиолетовый F1
        ("Сходы", s["dnf"], ft.Icons.CANCEL_ROUNDED, TEXT_MUTED),
        ("Лучший финиш", best, ft.Icons.TRENDING_UP_ROUNDED, SUCCESS),
        ("Средний финиш", st.fmt_avg(s["avg_finish"]), ft.Icons.TIMELINE_ROUNDED, INFO),
    ]
    cards = [ft.Container(StatCard(label, value, icon, color, compact=True, expand=False),
                          col={"xs": 6 if large_text() else 3, "md": 3}) for label, value, icon, color in items]
    return ft.Column([SectionHeader("Статистика сезона"),
                      ft.ResponsiveRow(cards, spacing=SPACE_XS, run_spacing=SPACE_XS)], spacing=SPACE_SM)


def _build_points_chart(state, driver):
    """Набор очков по ходу сезона: пилот и напарник(и)."""
    rounds = st.rounds(state.season_results, state.sprints)
    people = [driver] + state.teammates(driver)
    series = []
    for i, d in enumerate(people):
        values = st.cumulative_points(state.driver_results(d["driver_id"]), state.driver_sprints(d["driver_id"]),
                                      rounds)
        color = get_team_color(d["team"]) if i == 0 else TEXT_MUTED
        series.append((short_name(d["name"]), color, values))
    chart = line_chart(series, rounds, content_width(state) - 2 * SPACE_SM, height=200)
    return ft.Column([
        SectionHeader("Набор очков",
                      subtitle="Гонки и спринты, по этапам" + (" · против напарника" if len(people) > 1 else "")),
        AnimatedCard(ft.Column([chart, legend(series)], spacing=SPACE_XS)),
    ], spacing=SPACE_SM)


def _build_points_by_race(results):
    """Столбики очков за каждую гонку: подиумы — цветом медали, остальные очки — зелёным, как на карте сезона."""
    top = max((float(r["points"]) for r in results), default=0) or 1
    cols = []
    for r in results:
        pts = float(r["points"])
        pos = to_int(r["position"])
        color = readable_text(POSITION_COLORS.get(pos, SUCCESS), 3.0) if pts else SURFACE_ELEVATED
        cols.append(ft.Column([
            ft.Text(f"{pts:g}" if pts else "", size=FONT_TINY, color=TEXT_MUTED),
            ft.Container(width=18, height=max(3, int(100 * pts / top)), bgcolor=color, border_radius=4,
                         tooltip=f"{r['race_name']}: {r['position']} место, {pts:g} очк."),
            ft.Text(r["round"], size=FONT_TINY, color=TEXT_DIM),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=3))
    total = sum(float(r["points"]) for r in results)
    return ft.Column([
        SectionHeader("Очки по гонкам", subtitle=f"{total:g} {plural(total, 'очко', 'очка', 'очков')} за гонки "
                                                 "(без спринтов). Золото, серебро, бронза — подиумы."),
        AnimatedCard(ft.Row(cols, spacing=8, vertical_alignment=ft.CrossAxisAlignment.END, scroll=ft.ScrollMode.AUTO)),
    ], spacing=SPACE_SM)


def _build_race_results(state, driver, results):
    """Результаты гонок, свежие сверху: место, старт, отыгрыш, быстрый круг, флаг страны."""
    quali = {q["round"]: q["position"] for q in state.driver_quali(driver["driver_id"])}
    rows = []
    for r in reversed(results):
        pos, grid = to_int(r["position"]), to_int(r["grid"])
        delta = None if pos is None or not grid else grid - pos
        if delta is None:
            change = ft.Text("—", size=FONT_BODY_SMALL, color=TEXT_DIM)
        elif delta == 0:
            change = ft.Text("=", size=FONT_BODY_SMALL, color=TEXT_MUTED, weight=ft.FontWeight.BOLD)
        else:
            change = ft.Text(f"{'▲' if delta > 0 else '▼'}{abs(delta)}", size=FONT_BODY_SMALL,
                             color=SUCCESS if delta > 0 else WARNING, weight=ft.FontWeight.BOLD)
        flag_src, iso = state.flag(country=r["country"])
        extras = []
        if str(r.get("fastest_rank")) == "1":
            extras.append(ft.Icon(ft.Icons.SPEED_ROUNDED, color=SECTOR_OVERALL, size=16, tooltip="Быстрый круг"))
        if quali.get(r["round"]) == "1":
            extras.append(ft.Icon(ft.Icons.TIMER_ROUNDED, color=ACCENT_TEXT, size=16, tooltip="Поул"))
        badge = PositionBadge(pos, size=34) if pos else ft.Container(
            ft.Text(r["position"], size=FONT_BODY_SMALL, color=DANGER, weight=ft.FontWeight.BOLD),
            width=34, height=34, alignment=ft.Alignment.CENTER, bgcolor=SURFACE_ELEVATED,
            border_radius=RADIUS_SM, tooltip=r["status"])
        start = f"квал. P{quali[r['round']]} · старт {r['grid']}" if r["round"] in quali else f"старт {r['grid']}"
        rows.append(ft.Container(
            content=ft.Row([
                badge,
                ft.Column([
                    ft.Row([flag(flag_src, 12, iso),
                            ft.Text(r["race_name"], size=FONT_BODY, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True)] + extras,
                           spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Text(f"Этап {r['round']} · {start} · {fmt_date_str(r['date'])}",
                            size=FONT_CAPTION, color=TEXT_MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=1, expand=True),
                ft.Column([
                    ft.Text(f"+{r['points']}", size=FONT_BODY, color=TEXT_PRIMARY, font_family=FONT_DISPLAY_ITALIC),
                    change,
                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
            ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=SURFACE,
            border_radius=RADIUS_SM,
            border=ft.Border.all(1, LINE_SUBTLE),
            padding=ft.Padding.symmetric(horizontal=SPACE_SM, vertical=SPACE_XS),
        ))
    return ft.Column([SectionHeader("Результаты гонок", subtitle="Свежие сверху"),
                      ft.Column(rows, spacing=SPACE_XXS)], spacing=SPACE_SM)
