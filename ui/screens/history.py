"""История сезонов с 1950 года: чемпионы, зачёты, победители гонок, рекорды по титулам"""
import flet as ft

from design_system import *
from services import archive
from ui.components import *
from ui.fmt import nation_ru, plural
from ui.widgets import dropdown, pill, retry_block, screen


def build(state):
    view = state.ui.get("hist_view", "season")

    def switch(key):
        state.ui["hist_view"] = key
        state.render()

    tabs = ft.Row([pill("Сезон", view == "season", lambda e: switch("season")),
                   pill("Чемпионы", view == "champions", lambda e: switch("champions"))], spacing=SPACE_XS)
    body = [tabs] + (_season_view(state) if view == "season" else _champions_view(state))
    return screen(state, "История", body, subtitle=f"Формула-1 с {archive.FIRST_SEASON} года", back=True)


# ---------------------------------------------------------------- общие элементы
def _person_avatar(state, row, size=40):
    """Фото, если пилот выступает сейчас (портрет текущего сезона), иначе инициалы в цвете команды."""
    current = state.driver(row.get("driver_id"))
    if current:
        return DriverAvatar(current["code"], current["team"], size=size, src=state.photo(current))
    code = row.get("code") or "".join(p[0] for p in row.get("name", "?").split()[:2])
    return DriverAvatar(code, row.get("team"), size=size)


def _years(state):
    last = int(state.season) if state.season else archive.FIRST_SEASON
    return list(range(last, archive.FIRST_SEASON - 1, -1))


def _selected_year(state):
    years = _years(state)
    default = years[1] if len(years) > 1 else years[0]       # прошлый сезон — он уже завершён
    year = state.ui.get("hist_year", default)
    return year if year in years else default


# ---------------------------------------------------------------- сезон
def _season_view(state):
    year = _selected_year(state)
    years = _years(state)

    def choose(y):
        state.ui["hist_year"] = int(y)
        state.ui["hist_all"] = False
        state.render()

    def arrow(icon, target, tip):
        enabled = target in years
        return ft.IconButton(icon=icon, icon_color=TEXT_PRIMARY if enabled else TEXT_DIM, tooltip=tip,
                             width=TOUCH, height=TOUCH, on_click=(lambda e: choose(target)) if enabled else None)

    picker = ft.Row([
        arrow(ft.Icons.CHEVRON_LEFT_ROUNDED, year - 1, "Предыдущий сезон"),
        ft.Container(dropdown(label="Сезон", value=str(year),
                              options=[ft.DropdownOption(key=str(y), text=str(y)) for y in years],
                              on_select=lambda e: choose(e.control.value)), expand=True),
        arrow(ft.Icons.CHEVRON_RIGHT_ROUNDED, year + 1, "Следующий сезон"),
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=SPACE_XXS)

    data = archive.season(year, state.season, on_done=state.render)
    key = archive.season_key(year)
    if not data:
        if archive.loading(key):
            return [picker, skeleton(f"Загружаем сезон {year}…", "rows", 6)]
        return [picker, retry_block(f"Сезон {year} не загружен",
                                    "Нужен интернет: архив загружается один раз и дальше доступен без сети.",
                                    lambda e: (archive.season(year, state.season, on_done=state.render, force=True),
                                               state.render()))]
    sections = [picker]
    if data["standings"]:
        sections.append(_champion_hero(state, data, year))
    sections += _standings(state, data)
    if data["constructors"]:
        sections.append(_constructors(state, data))
    if data["winners"]:
        sections.append(_winners(state, data))
    return sections


def _champion_hero(state, data, year):
    lead = data["standings"][0]
    finished = str(year) != str(state.season)
    # исторические команды (Brabham, Lotus…) — на карбоне, а не красным: красный в приложении значит «в эфире»
    top, bottom = get_team_gradient(lead["team"]) if team_key(lead["team"]) else tuple(HERO_CARBON)
    flag_src, iso = state.flag(nationality=lead.get("nationality"))
    team_champ = data["constructors"][0]["name"] if data["constructors"] else None
    lines = [ft.Text("Чемпион мира" if finished else "Лидер чемпионата", size=FONT_CAPTION, color=ON_COLOR,
                     font_family=FONT_ITALIC),
             ft.Text(lead["name"], size=FONT_H3, color=ON_COLOR, font_family=FONT_HEADING),
             ft.Row([flag(flag_src, 14, iso), ft.Text(lead["team"], size=FONT_BODY_SMALL, color=ON_COLOR)], spacing=6),
             ft.Text(f"{lead['points']} очков, {lead['wins']} "
                     f"{plural(int(lead['wins']), 'победа', 'победы', 'побед')}",
                     size=FONT_BODY_SMALL, color=ON_COLOR)]
    if team_champ:
        lines.append(ft.Text(f"Кубок конструкторов: {team_champ}", size=FONT_CAPTION, color=ON_COLOR))
    return ft.Container(
        ft.Row([_person_avatar(state, lead, 72), ft.Column(lines, spacing=2, expand=True),
                ft.Icon(ft.Icons.EMOJI_EVENTS_ROUNDED, color=GOLD, size=44)],
               spacing=SPACE_MD, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                   colors=[top, bottom, BG_DEEP], stops=[0.0, 0.65, 1.0]),
        border_radius=RADIUS_LG, padding=SPACE_MD, shadow=glow(top, 0.3),
    )


def _standings(state, data):
    rows = data["standings"]
    show_all = state.ui.get("hist_all", False)
    shown = rows if show_all else rows[:10]
    items = []
    for r in shown:
        flag_src, iso = state.flag(nationality=r.get("nationality"))
        items.append(ft.Container(ft.Row([
            PositionBadge(r["position"], size=28),
            _person_avatar(state, r, 36),
            ft.Column([ft.Row([flag(flag_src, 11, iso),
                               ft.Text(r["name"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600,
                                       max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True)], spacing=6),
                       ft.Text(r["team"], size=FONT_CAPTION, color=TEXT_MUTED, max_lines=1)], spacing=0, expand=True),
            ft.Column([ft.Text(r["points"], size=FONT_BODY, color=TEXT_PRIMARY, font_family=FONT_DISPLAY_ITALIC),
                       ft.Text(f"{r['wins']} поб.", size=FONT_CAPTION, color=TEXT_DIM)],
                      spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
        ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=SURFACE, border_radius=RADIUS_SM, border=ft.Border.all(1, LINE_SUBTLE),
            padding=ft.Padding.symmetric(horizontal=SPACE_SM, vertical=6)))
    out = [SectionHeader("Личный зачёт", subtitle=f"{len(rows)} {plural(len(rows), 'пилот', 'пилота', 'пилотов')}"
                         f", {data['rounds']} {plural(int(data['rounds'] or 0), 'этап', 'этапа', 'этапов')}")]
    out.append(ft.Column(items, spacing=SPACE_XXS))
    if len(rows) > 10:
        def toggle(e):
            state.ui["hist_all"] = not show_all
            state.render()
        out.append(ft.Container(ft.Text("Свернуть" if show_all else f"Показать всех ({len(rows)})",
                                        size=FONT_BODY_SMALL, color=ACCENT_TEXT, weight=ft.FontWeight.W_600),
                                on_click=toggle, ink=True, border_radius=RADIUS_SM, height=TOUCH,
                                alignment=ft.Alignment.CENTER_LEFT, padding=ft.Padding.symmetric(horizontal=SPACE_XS)))
    return out


def _constructors(state, data):
    rows = data["constructors"]
    lead = float(rows[0]["points"]) or 1
    items = []
    for c in rows[:10]:
        color = get_team_color(c["name"]) if team_key(c["name"]) else TEXT_MUTED
        items.append(ft.Container(ft.Column([
            ft.Row([PositionBadge(c["position"], size=28),
                    ft.Text(c["name"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600,
                            expand=True),
                    ft.Text(c["points"], size=FONT_BODY, color=TEXT_PRIMARY, font_family=FONT_DISPLAY_ITALIC)],
                   spacing=SPACE_SM),
            progress_bar(float(c["points"]) / lead, color, height=3),
        ], spacing=4), bgcolor=SURFACE, border_radius=RADIUS_SM, border=ft.Border.all(1, LINE_SUBTLE),
            padding=ft.Padding.symmetric(horizontal=SPACE_SM, vertical=6)))
    return ft.Column([SectionHeader("Кубок конструкторов"), ft.Column(items, spacing=SPACE_XXS)], spacing=SPACE_SM)


def _winners(state, data):
    items = []
    for w in data["winners"]:
        flag_src, iso = state.flag(country=w.get("country"))
        items.append(ft.Row([
            ft.Container(ft.Text(w["round"], size=FONT_BODY_SMALL, color=TEXT_MUTED, font_family=FONT_DISPLAY_ITALIC),
                         width=26, alignment=ft.Alignment.CENTER),
            flag(flag_src, 14, iso),
            ft.Column([ft.Text(w["race_name"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, max_lines=1,
                               overflow=ft.TextOverflow.ELLIPSIS),
                       ft.Text(f"{w['name']}, {w['team']}", size=FONT_CAPTION, color=TEXT_MUTED, max_lines=1,
                               overflow=ft.TextOverflow.ELLIPSIS)], spacing=0, expand=True),
        ], spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER))
    wins = {}
    for w in data["winners"]:
        wins[w["name"]] = wins.get(w["name"], 0) + 1
    most = max(wins.items(), key=lambda kv: kv[1]) if wins else None
    sub = f"Больше всего побед: {most[0]} — {most[1]}" if most else None
    return ft.Column([SectionHeader("Победители гонок", subtitle=sub),
                      AnimatedCard(ft.Column(items, spacing=SPACE_XS))], spacing=SPACE_SM)


# ---------------------------------------------------------------- чемпионы всех лет
def _champions_view(state):
    rows = archive.champions()
    if not rows:
        def to_seasons(e):
            state.ui["hist_view"] = "season"
            state.render()
        return [empty_block(ft.Icons.HISTORY_ROUNDED, "Список чемпионов недоступен",
                            "Он не вошёл в эту сборку приложения. Итоги любого года с 1950-го — во вкладке «Сезон».",
                            ("К сезонам", to_seasons), art="flag")]
    rec = archive.records(rows)
    out = []
    if state.standings and str(int(rows[0]["season"]) + 1) == str(state.season):
        lead = state.standings[0]
        race = state.title_race("drivers")
        status = "чемпион мира" if race["clinched"] else "лидирует, сезон продолжается"
        out.append(AnimatedCard(ft.Row([
            DriverAvatar(lead["code"], lead["team"], size=40, src=state.photo(lead)),
            ft.Column([ft.Text(f"{state.season}: {lead['name']}", size=FONT_BODY, color=TEXT_PRIMARY,
                               weight=ft.FontWeight.W_600),
                       ft.Text(status, size=FONT_CAPTION, color=TEXT_MUTED)], spacing=0, expand=True),
        ], spacing=SPACE_SM), accent=F1_RED, on_click=lambda e: state.open_sub("title")))

    def leaderboard(title, pairs, unit=("титул", "титула", "титулов")):
        top = pairs[0][1] if pairs else 1
        items = []
        for name, n in pairs[:5]:
            items.append(ft.Row([
                ft.Text(name, size=FONT_BODY_SMALL, color=TEXT_PRIMARY, width=150, max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS),
                ft.Container(progress_bar(n / top, GOLD, height=8), expand=True),
                ft.Text(f"{n}", size=FONT_BODY, color=TEXT_PRIMARY, font_family=FONT_DISPLAY_ITALIC, width=28,
                        text_align=ft.TextAlign.RIGHT),
            ], spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER))
        return AnimatedCard(ft.Column([ft.Text(title, size=FONT_BODY_SMALL, color=TEXT_SECONDARY,
                                               weight=ft.FontWeight.W_600)] + items, spacing=SPACE_XS))

    out.append(SectionHeader("Рекорды", subtitle=f"По {len(rows)} сезонам: {rows[-1]['season']}–{rows[0]['season']}"))
    out.append(ft.ResponsiveRow([
        ft.Container(leaderboard("Больше всего титулов — пилоты", rec["drivers"]), col={"xs": 12, "md": 4}),
        ft.Container(leaderboard("Кубков конструкторов — команды", rec["teams"]), col={"xs": 12, "md": 4}),
        ft.Container(leaderboard("Титулов по странам", [(nation_ru(n), k) for n, k in rec["nations"]]),
                     col={"xs": 12, "md": 4}),
    ], spacing=SPACE_XS, run_spacing=SPACE_XS))
    best = rec["best_wins"]
    if best:
        out.append(ft.Text(f"Больше всего побед за чемпионский сезон: {best['name']} — {best['wins']} "
                           f"({best['season']})",
                           size=FONT_BODY_SMALL, color=TEXT_MUTED))

    out.append(SectionHeader("Чемпионы по годам", subtitle="Нажми на год — откроется сезон"))
    items = []
    for r in rows:
        flag_src, iso = state.flag(nationality=r.get("nationality"))
        items.append(ft.Container(ft.Row([
            ft.Text(r["season"], size=FONT_BODY, color=TEXT_PRIMARY, font_family=FONT_DISPLAY_ITALIC, width=48),
            _person_avatar(state, r, 32),
            ft.Column([ft.Row([flag(flag_src, 11, iso),
                               ft.Text(r["name"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600,
                                       max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True)], spacing=6),
                       ft.Text(r["team"] + (f", Кубок: {r['constructor']}" if r.get("constructor") else ""),
                               size=FONT_CAPTION, color=TEXT_MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)],
                      spacing=0, expand=True),
        ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=SURFACE, border_radius=RADIUS_SM, border=ft.Border.all(1, LINE_SUBTLE), ink=True,
            padding=ft.Padding.symmetric(horizontal=SPACE_SM, vertical=6),
            on_click=lambda e, y=int(r["season"]): _open_year(state, y)))
    out.append(ft.Column(items, spacing=SPACE_XXS))
    return out


def _open_year(state, year):
    state.ui.update(hist_view="season", hist_year=year, hist_all=False)
    state.render()
