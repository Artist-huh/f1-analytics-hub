"""Главный экран: ближайшая гонка, подиум последней гонки, лидеры чемпионата, быстрый доступ"""
import flet as ft
from design_system import *
from ui.components import *
from ui.fmt import fmt_countdown, fmt_day, fmt_clock, plural, short_name
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
        last, podium = state.last_race()
        if podium:
            sections.append(_build_last_podium(state, last, podium, is_narrow(state)))
        sections.append(_build_season_stats(state, is_narrow(state)))
        sections.append(_build_title_fight(state))
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
    """Hero: красный градиент, флаг страны, обратный отсчёт курсивом."""
    live = race["state"] == "live"
    countdown = ft.Text(
        "LIVE" if live else fmt_countdown(race["seconds_left"]),
        size=FONT_H1 if is_mobile else FONT_DISPLAY,
        color=TEXT_PRIMARY,
        font_family=FONT_DISPLAY_ITALIC,
    )
    if not live:
        state.countdown = (countdown, race["round"])  # main.ticker обновляет этот текст на месте
    flag_src, iso = state.flag(country=race["country"])
    sprint = any(s["key"] == "Sprint" for s in race["sessions"])

    badge_items = [ft.Text("ГОНКА ИДЁТ" if live else f"ЭТАП {race['round']}", size=FONT_CAPTION,
                           color=ON_ACCENT, font_family=FONT_ITALIC)]
    if sprint:
        badge_items.append(ft.Text("· СПРИНТ", size=FONT_CAPTION, color=ON_ACCENT, font_family=FONT_ITALIC))
    badge = ft.Container(ft.Row(badge_items, spacing=4, tight=True),
                         bgcolor=ft.Colors.with_opacity(0.22, BG_DEEPEST), border_radius=RADIUS_FULL,
                         padding=ft.Padding.symmetric(horizontal=10, vertical=4))

    timer = ft.Column([
        countdown,
        ft.Text("в эфире" if live else f"до старта · {fmt_day(race['start_ts'])}, {fmt_clock(race['start_ts'])}",
                size=FONT_BODY_SMALL, color=ft.Colors.with_opacity(0.85, TEXT_PRIMARY)),
    ], spacing=0)

    button = ft.Container(
        ft.Row([ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, color=F1_RED, size=18),
                ft.Text("Расписание", color=BG, weight=ft.FontWeight.W_700)], spacing=SPACE_XS, tight=True),
        bgcolor=TEXT_PRIMARY, border_radius=RADIUS_FULL, height=TOUCH, alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(horizontal=SPACE_LG), ink=True,
        on_click=lambda e: state.open_tab(2),
    )
    bottom = (ft.Column([timer, button], spacing=SPACE_MD, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
              if is_mobile else
              ft.Row([ft.Container(timer, expand=True), button], spacing=SPACE_MD,
                     vertical_alignment=ft.CrossAxisAlignment.END))

    return ft.Container(
        content=ft.Stack([
            # «шахматный флаг» — декоративные полосы справа
            ft.Container(ft.Icon(ft.Icons.SPORTS_SCORE_ROUNDED, size=150,
                                 color=ft.Colors.with_opacity(0.10, TEXT_PRIMARY)),
                         right=-20, top=-20),
            ft.Column([
                ft.Row([badge, ft.Container(expand=True), flag(flag_src, 22, iso)],
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Column([
                    ft.Text(race["race_name"], size=FONT_H3, color=TEXT_PRIMARY, font_family=FONT_HEADING),
                    ft.Text(f"{race['circuit']} · {race['locality']}", size=FONT_BODY_SMALL,
                            color=ft.Colors.with_opacity(0.85, TEXT_PRIMARY), max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=2),
                bottom,
            ], spacing=SPACE_MD),
        ]),
        padding=SPACE_LG,
        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                   colors=[ACCENT_GLOW, F1_RED, ACCENT_DEEP]),
        border_radius=RADIUS_LG,
        shadow=glow(strength=0.35),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        on_click=lambda e: state.open_tab(2),
        ink=True,
    )


def _build_last_podium(state, race, podium, compact):
    """Подиум последней гонки: P2 — P1 — P3 с фото, как на церемонии."""
    heights = {1: 64, 2: 44, 3: 30}
    size = 56 if compact else 68

    def place(row, pos):
        driver = state.driver(row["driver_id"]) or {"code": row["driver_id"][:3].upper(), "team": row.get("team"),
                                                    "name": row["driver_id"], "season": state.season}
        color = POSITION_COLORS[pos]
        return ft.Column([
            DriverAvatar(driver.get("code"), driver.get("team"), size=size + (10 if pos == 1 else 0),
                         src=state.photo(driver), on_click=lambda e, i=row["driver_id"]: state.open_driver(i)),
            ft.Text(short_name(driver.get("name", "")), size=FONT_BODY_SMALL, color=TEXT_PRIMARY,
                    weight=ft.FontWeight.W_600, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Container(
                ft.Text(str(pos), size=FONT_H3, color=BG, font_family=FONT_DISPLAY_ITALIC),
                height=heights[pos], bgcolor=color, alignment=ft.Alignment.CENTER,
                border_radius=ft.BorderRadius.only(top_left=RADIUS_SM, top_right=RADIUS_SM),
                gradient=ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER,
                                           colors=[color, ft.Colors.with_opacity(0.55, color)]),
            ),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=SPACE_XXS, expand=True,
            alignment=ft.MainAxisAlignment.END)

    name = race.get("race_name", "") if race else ""
    flag_src, iso = state.flag(country=race.get("country")) if race else (None, "")
    return ft.Column([
        SectionHeader("Последняя гонка", subtitle=f"Этап {race['round']} · {name}" if race else None,
                      action_text="Календарь", on_action=lambda e: _open_calendar_past(state)),
        AnimatedCard(
            ft.Column([
                ft.Row([flag(flag_src, 16, iso), ft.Text(name, size=FONT_BODY_SMALL, color=TEXT_MUTED, expand=True,
                                                          max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)],
                       spacing=SPACE_XS),
                ft.Row([place(podium[1], 2), place(podium[0], 1), place(podium[2], 3)],
                       vertical_alignment=ft.CrossAxisAlignment.END, spacing=SPACE_XS),
            ], spacing=SPACE_SM),
            padding=ft.Padding.only(left=SPACE_MD, right=SPACE_MD, top=SPACE_SM),
        ),
    ], spacing=SPACE_SM)


def _build_season_stats(state, compact):
    """Статистика сезона"""
    schedule = state.schedule
    done = sum(1 for r in schedule if api.race_state(r) == "past")
    leader = state.standings[0]
    team_leader = state.constructors[0] if state.constructors else None

    cards = [
        StatCard("Гонок пройдено", f"{done}/{len(schedule)}" if schedule else "—", ft.Icons.FLAG_ROUNDED,
                 F1_RED, compact=compact),
        StatCard("Лидер пилотов", leader["name"].split()[-1], ft.Icons.PERSON_ROUNDED,
                 get_team_color(leader["team"]), subtitle=_points(leader["points"]), compact=compact),
    ]
    if team_leader:
        cards.append(StatCard("Лидер команд", team_leader["name"], ft.Icons.GROUPS_ROUNDED,
                              get_team_color(team_leader["name"]), subtitle=_points(team_leader["points"]),
                              compact=compact))
    return ft.Column([
        SectionHeader(f"Сезон {state.season}"),
        ft.Row(cards, spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.START),
    ], spacing=SPACE_SM)


def _build_title_fight(state):
    """Короткая сводка борьбы за титул -> экран прогноза."""
    race = state.title_race("drivers")
    contenders = race["contenders"]
    if race["clinched"]:
        title, hint = f"{short_name(state.standings[0]['name'])} — чемпион мира", "Титул оформлен досрочно"
    else:
        n = len(contenders)
        title = f"В борьбе {n} {plural(n, 'пилот', 'пилота', 'пилотов')}"
        hint = f"Разыгрывается ещё {race['available']} очков"
        if race["next_clinch"] is not None:
            hint += f" · {short_name(state.standings[0]['name'])} может стать чемпионом в ближайшей гонке"
    faces = [DriverAvatar(r["code"], r["team"], size=32, src=state.photo(r)) for r, *_ in contenders[:5]]
    return AnimatedCard(ft.Row([
        ft.Icon(ft.Icons.EMOJI_EVENTS_ROUNDED, color=GOLD, size=28),
        ft.Column([ft.Text(title, size=FONT_BODY, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600),
                   ft.Text(hint, size=FONT_CAPTION, color=TEXT_MUTED, max_lines=2)], spacing=1, expand=True),
        ft.Row(faces, spacing=-8, tight=True),
        ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=TEXT_DIM),
    ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=SPACE_SM, accent=GOLD, on_click=lambda e: state.open_sub("title"))


def driver_row(state, d, trailing=None, subtitle=None):
    """Строка пилота: позиция, фото, флаг и имя, команда, очки.
    На узком экране (телефон) — фамилия вместо полного имени и без отдельной полосы команды."""
    color = get_team_color(d["team"])
    flag_src, iso = state.flag(nationality=d.get("nationality"))
    compact = page_width(state) < 480
    name = short_name(d["name"]) if compact else d["name"]
    lead = [PositionBadge(d["position"])]
    if not compact:
        lead.append(ft.Container(width=3, height=36, bgcolor=color, border_radius=2))
    return AnimatedCard(
        content=ft.Row(lead + [
            DriverAvatar(d["code"], d["team"], size=40 if compact else 44, src=state.photo(d)),
            ft.Column([
                ft.Row([flag(flag_src, 12, iso),
                        ft.Text(name, size=FONT_BODY, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True)],
                       spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(subtitle or d["team"], size=FONT_CAPTION, color=TEXT_MUTED, max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=2, expand=True),
            trailing or points_block(d["points"]),
        ], spacing=SPACE_XS if compact else SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=SPACE_SM, vertical=SPACE_XS),
        on_click=lambda e, i=d["driver_id"]: state.open_driver(i),
        accent=color,
    )


def _build_top_drivers(state, drivers):
    return ft.Column([
        SectionHeader("Чемпионат пилотов", subtitle="Топ-5", action_text="Все",
                      on_action=lambda e: _open_championship(state, "drivers")),
        ft.Column([driver_row(state, d) for d in drivers], spacing=SPACE_XS),
    ], spacing=SPACE_SM)


def team_row(state, c, leader_points, show_car=False):
    """Строка команды: позиция, логотип, название, пилоты, очки, полоса отставания; болид на широком экране."""
    color = get_team_color(c["name"])
    drivers = state.team_drivers(c["name"])
    names = " · ".join(d["name"].split()[-1] for d in drivers[:3])
    wins = int(c["wins"])
    top = ft.Row([
        PositionBadge(c["position"]),
        TeamLogo(c["name"], state.team_logo(c["name"]), size=44),
        ft.Column([
            ft.Text(c["name"], size=FONT_BODY, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(names or f"{wins} {plural(wins, 'победа', 'победы', 'побед')}", size=FONT_CAPTION,
                    color=TEXT_MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
        ], spacing=2, expand=True),
        points_block(c["points"]),
    ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER)
    items = [top]
    if show_car:
        items.append(ft.Container(image(state.team_car(c["name"]), height=64, fit=ft.BoxFit.CONTAIN),
                                  alignment=ft.Alignment.CENTER, height=64))
    items.append(progress_bar(float(c["points"]) / leader_points if leader_points else 0, color))
    return AnimatedCard(
        content=ft.Column(items, spacing=SPACE_XS),
        padding=SPACE_SM,
        accent=color,
        on_click=lambda e, n=c["name"]: open_team(state, n),
    )


def _build_top_constructors(state, constructors):
    leader = float(constructors[0]["points"]) or 1
    return ft.Column([
        SectionHeader("Кубок конструкторов", subtitle="Топ-5", action_text="Все",
                      on_action=lambda e: _open_championship(state, "teams")),
        ft.Column([team_row(state, c, leader) for c in constructors], spacing=SPACE_XS),
    ], spacing=SPACE_SM)


def _build_favorites_strip(state, favs):
    """Избранные пилоты — фото, код и очки"""
    chips = [
        ft.Container(
            content=ft.Column([
                DriverAvatar(d["code"], d["team"], size=52, src=state.photo(d)),
                ft.Text(d["code"] or short_name(d["name"]), size=FONT_BODY_SMALL, color=TEXT_PRIMARY,
                        font_family=FONT_ITALIC),
                ft.Text(f"{d['points']} очк.", size=FONT_CAPTION, color=TEXT_MUTED),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            padding=SPACE_XS, border_radius=RADIUS_MD, ink=True, width=84,
            on_click=lambda e, i=d["driver_id"]: state.open_driver(i),
        )
        for d in favs
    ]
    return ft.Column([
        SectionHeader("Избранные", action_text="Все", on_action=lambda e: state.open_sub("favorites")),
        ft.Row(chips, spacing=SPACE_XS, scroll=ft.ScrollMode.AUTO),
    ], spacing=SPACE_SM)


def _build_quick_actions(state):
    actions = [
        (ft.Icons.PERSON_ROUNDED, "Пилоты", lambda e: state.open_tab(3)),
        (ft.Icons.COMPARE_ARROWS_ROUNDED, "Сравнение", lambda e: state.open_sub("compare")),
        (ft.Icons.STAR_ROUNDED, "Избранное", lambda e: state.open_sub("favorites")),
        (ft.Icons.CALENDAR_MONTH_ROUNDED, "Календарь", lambda e: state.open_tab(2)),
    ]
    cards = [
        AnimatedCard(
            content=ft.Column([
                ft.Container(ft.Icon(icon, size=22, color=TEXT_PRIMARY), width=40, height=40,
                             border_radius=20, alignment=ft.Alignment.CENTER,
                             gradient=ft.LinearGradient(colors=[ACCENT_GLOW, ACCENT_DEEP],
                                                        begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT)),
                ft.Text(label, size=FONT_CAPTION, color=TEXT_PRIMARY, max_lines=1),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=SPACE_XS),
            padding=ft.Padding.symmetric(horizontal=SPACE_XXS, vertical=SPACE_SM),
            on_click=handler,
            expand=True,
            accent=F1_RED,
        )
        for icon, label, handler in actions
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


def points_block(points, caption=None):
    value = float(points)
    return ft.Column([
        ft.Text(f"{value:g}", size=FONT_H4, color=TEXT_PRIMARY, font_family=FONT_DISPLAY_ITALIC),
        ft.Text(caption or plural(value, "очко", "очка", "очков"), size=FONT_CAPTION, color=TEXT_DIM),
    ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END)


def _open_championship(state, view):
    state.ui["champ"] = view
    state.open_tab(1)


def _open_calendar_past(state):
    state.ui["cal"] = "past"
    state.open_tab(2)


def open_team(state, team_name):
    """Команда -> список её пилотов на экране «Пилоты»."""
    drivers = state.team_drivers(team_name)
    state.ui["drv_team"] = drivers[0]["team"] if drivers else None
    state.ui["drv_q"] = ""
    state.open_tab(3)
