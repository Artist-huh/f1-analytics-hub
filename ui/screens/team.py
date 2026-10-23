"""Страница команды: логотип и болид, показатели сезона, пилоты, дуэль напарников, график очков"""
import flet as ft
from design_system import *
from services import stats as st
from ui.components import *
from ui.fmt import plural, short_name, to_int
from ui.widgets import screen


def team_stats(state, team_name):
    """Показатели команды по результатам гонок её машин (учитывает смену пилотов по ходу сезона)."""
    key = team_key(team_name)
    races = [r for r in state.season_results if team_key(r.get("team")) == key] if key else []
    ids = {d["driver_id"] for d in state.team_drivers(team_name)}
    quali = [q for q in state.qualifying if q["driver_id"] in ids]
    positions = [to_int(r["position"]) for r in races]
    return {
        "wins": sum(1 for p in positions if p == 1),
        "podiums": sum(1 for p in positions if p and p <= 3),
        "poles": sum(1 for q in quali if q["position"] == "1"),
        "fastest_laps": sum(1 for r in races if str(r.get("fastest_rank")) == "1"),
        "dnf": sum(1 for r, p in zip(races, positions) if p is None and r["position"] != "W"),
        "one_two": sum(1 for rnd in {r["round"] for r in races}
                       if sorted(to_int(r["position"]) or 99 for r in races if r["round"] == rnd)[:2] == [1, 2]),
        "races": races,
    }


def team_points_by_round(state, team_name, rounds):
    """Набор очков команды по этапам: гонки её машин + спринты её нынешних пилотов."""
    key = team_key(team_name)
    races = [r for r in state.season_results if team_key(r.get("team")) == key] if key else []
    ids = {d["driver_id"] for d in state.team_drivers(team_name)}
    sprints = [s for s in state.sprints if s["driver_id"] in ids]
    return st.cumulative_points(races, sprints, rounds)


def build(state):
    name = state.ui.get("team")
    team = next((c for c in state.constructors if c["name"] == name), None)
    if not team:
        return screen(state, "Команда", [empty_block(ft.Icons.GROUPS_ROUNDED, "Команда не выбрана",
                                                     "Выбери команду в разделе «Чемпионат».")], back=True)
    drivers = sorted(state.team_drivers(name), key=lambda d: int(d["position"]))
    s = team_stats(state, name)
    sections = [_hero(state, team, drivers), _stats(team, s), _drivers(state, drivers)]
    if len(drivers) >= 2:
        sections.append(_duel(state, drivers[0], drivers[1]))
    sections.append(_chart(state, team))
    return screen(state, name, sections, subtitle=f"Кубок конструкторов {team['season']}", back=True)


def _hero(state, team, drivers):
    top, bottom = get_team_gradient(team["name"])
    flag_src, iso = state.flag(nationality=team.get("nationality"))
    return ft.Container(
        ft.Column([
            ft.Row([TeamLogo(team["name"], state.team_logo(team["name"]), size=56),
                    ft.Column([ft.Text(team["name"].upper(), size=FONT_H3, color=ON_COLOR, font_family=FONT_DISPLAY_ITALIC),
                               ft.Row([flag(flag_src, 12, iso),
                                       ft.Text(" · ".join(short_name(d["name"]) for d in drivers),
                                               size=FONT_BODY_SMALL, color=ON_COLOR)], spacing=6)],
                              spacing=2, expand=True)], spacing=SPACE_SM),
            ft.Container(image(state.team_car(team["name"]), height=90, fit=ft.BoxFit.CONTAIN, label=f"Болид {team['name']}"),
                         alignment=ft.Alignment.CENTER, height=90),
            ft.Row([_hero_value(f"P{team['position']}", "в Кубке"),
                    _hero_value(team["points"], plural(float(team["points"]), "очко", "очка", "очков")),
                    _hero_value(team["wins"], plural(int(team["wins"]), "победа", "победы", "побед"))],
                   spacing=SPACE_LG),
        ], spacing=SPACE_SM),
        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                   colors=[top, bottom, BG_DEEP], stops=[0.0, 0.6, 1.0]),
        border_radius=RADIUS_LG, padding=SPACE_MD, clip_behavior=ft.ClipBehavior.ANTI_ALIAS, shadow=glow(top, 0.3),
    )


def _hero_value(value, label):
    return ft.Column([ft.Text(str(value), size=FONT_H2, color=ON_COLOR, font_family=FONT_DISPLAY_ITALIC),
                      ft.Text(label, size=FONT_CAPTION, color=ON_COLOR)], spacing=0)


def _stats(team, s):
    items = [("Подиумы", s["podiums"], ft.Icons.WORKSPACE_PREMIUM_ROUNDED, POSITION_COLORS[3]),
             ("Дубли 1–2", s["one_two"], ft.Icons.FILTER_2_ROUNDED, GOLD),
             ("Поулы", s["poles"], ft.Icons.TIMER_ROUNDED, ACCENT_TEXT),
             ("Быстрые круги", s["fastest_laps"], ft.Icons.SPEED_ROUNDED, "#B36BFF"),
             ("Сходы", s["dnf"], ft.Icons.CANCEL_ROUNDED, TEXT_MUTED),
             ("Гонок", len({r["round"] for r in s["races"]}), ft.Icons.FLAG_ROUNDED, INFO)]
    cards = [ft.Container(StatCard(label, value, icon, color, compact=True, expand=False),
                          col={"xs": 6 if large_text() else 4, "md": 2}) for label, value, icon, color in items]
    return ft.Column([SectionHeader("Сезон команды"), ft.ResponsiveRow(cards, spacing=SPACE_XS, run_spacing=SPACE_XS)],
                     spacing=SPACE_SM)


def _drivers(state, drivers):
    from ui.screens.home import driver_row
    rows = [driver_row(state, d) for d in drivers]
    actions = []
    if len(drivers) >= 2:
        actions.append(GradientButton("Сравнить пилотов команды", icon=ft.Icons.COMPARE_ARROWS_ROUNDED,
                                      on_click=lambda e: state.set_compare_and_open([d["driver_id"] for d in drivers])))
    return ft.Column([SectionHeader("Пилоты")] + rows + actions, spacing=SPACE_XS)


def _duel(state, a, b):
    ra, rb = state.driver_results(a["driver_id"]), state.driver_results(b["driver_id"])
    w1, w2, _ = st.head_to_head(ra, rb)
    q1, q2 = st.quali_head_to_head(state.driver_quali(a["driver_id"]), state.driver_quali(b["driver_id"]))
    color = get_team_color(a["team"])
    digits = readable_text(color, 3.0)

    def score(title, x, y):
        total = x + y
        return AnimatedCard(ft.Column([
            ft.Text(title, size=FONT_CAPTION, color=TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
            ft.Row([ft.Text(str(x), size=FONT_H1, color=digits, font_family=FONT_DISPLAY_ITALIC, expand=True,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(":", size=FONT_H2, color=TEXT_DIM),
                    ft.Text(str(y), size=FONT_H1, color=TEXT_SECONDARY, font_family=FONT_DISPLAY_ITALIC, expand=True,
                            text_align=ft.TextAlign.CENTER)]),
            ft.Row([ft.Container(expand=x or None, height=5, bgcolor=color, border_radius=3),
                    ft.Container(expand=y or None, height=5, bgcolor=TEXT_SECONDARY, border_radius=3)],
                   spacing=2) if total else ft.Container(),
        ], spacing=SPACE_XXS, horizontal_alignment=ft.CrossAxisAlignment.CENTER), padding=SPACE_SM, expand=True)

    return ft.Column([
        SectionHeader("Дуэль напарников", subtitle=f"{short_name(a['name'])} против {short_name(b['name'])}"),
        ft.Row([ft.Column([DriverAvatar(a["code"], a["team"], size=48, src=state.photo(a)),
                           ft.Text(a["code"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, font_family=FONT_ITALIC)],
                          horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                score("Гонки", w1, w2), score("Квалификации", q1, q2),
                ft.Column([DriverAvatar(b["code"], b["team"], size=48, src=state.photo(b)),
                           ft.Text(b["code"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, font_family=FONT_ITALIC)],
                          horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)],
               spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    ], spacing=SPACE_SM)


def _chart(state, team):
    rounds = st.rounds(state.season_results, state.sprints)
    if not rounds:
        return ft.Container()
    series = [(team["name"], get_team_color(team["name"]), team_points_by_round(state, team["name"], rounds))]
    leader = state.constructors[0] if team["position"] != "1" else (state.constructors[1] if len(state.constructors) > 1 else None)
    if leader:
        series.append((leader["name"], TEXT_MUTED, team_points_by_round(state, leader["name"], rounds)))
    return ft.Column([
        SectionHeader("Набор очков", subtitle="По этапам, " + ("против ближайшего соперника" if team["position"] == "1"
                                                                else "против лидера Кубка")),
        AnimatedCard(ft.Column([line_chart(series, rounds, content_width(state) - 2 * SPACE_SM, height=200),
                                legend(series)], spacing=SPACE_XS), padding=SPACE_SM),
    ], spacing=SPACE_SM)
