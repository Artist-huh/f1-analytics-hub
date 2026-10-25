"""Прогноз чемпионата: кто ещё может стать чемпионом и что нужно лидеру"""
import flet as ft

from design_system import *
from ui.components import *
from ui.fmt import plural, short_name
from ui.widgets import empty_state, pill, screen


def build(state):
    view = state.ui.get("title_kind", "drivers")
    rows = state.standings if view == "drivers" else state.constructors
    if not rows:
        return screen(state, "Борьба за титул", [empty_state(state, "Нет таблицы чемпионата",
                                                              "Нажми «Обновить», когда появится интернет.")],
                      back=True)

    def switch(kind):
        state.ui["title_kind"] = kind
        state.render()

    race = state.title_race(view)
    body = [
        ft.Row([pill("Пилоты", view == "drivers", lambda e: switch("drivers")),
                pill("Команды", view == "teams", lambda e: switch("teams"))], spacing=SPACE_XS),
        _summary(race),
    ]
    if race["clinched"]:
        body.append(_champion(state, rows[0], view))
    elif race["next_clinch"] is not None:
        body.append(_next_clinch(state, rows, race, view))
    body.append(_contenders(state, race, view, len(rows)))
    body.append(ft.Text("Расчёт: победа в гонке — 25 очков, в спринте — 8 (у команды 43 и 15 — первые два места). "
                        "При равенстве очков чемпиона определяет число побед — здесь это не учитывается.",
                        size=FONT_CAPTION, color=TEXT_DIM))
    return screen(state, "Борьба за титул", body, subtitle=f"Сезон {state.season}", back=True)


def _summary(race):
    races, sprints = race["races_left"], race["sprints_left"]
    left = f"{races} {plural(races, 'гонка', 'гонки', 'гонок')}"
    if sprints:
        left += f" и {sprints} {plural(sprints, 'спринт', 'спринта', 'спринтов')}"

    def cell(value, label):
        return ft.Column([ft.Text(str(value), size=FONT_H2, color=ON_COLOR, font_family=FONT_DISPLAY_ITALIC),
                          ft.Text(label, size=FONT_CAPTION, color=ON_COLOR)],
                         spacing=0, expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    n = len(race["contenders"])
    return ft.Container(
        ft.Column([
            ft.Text(f"Осталось: {left}" if races or sprints else "Сезон завершён", size=FONT_BODY,
                    color=ON_COLOR, weight=ft.FontWeight.W_600),
            ft.Row([cell(race["available"], "очков разыгрывается"),
                    cell(n, plural(n, "претендент", "претендента", "претендентов"))]),
        ], spacing=SPACE_SM),
        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT, colors=GRADIENT_RED),
        border_radius=RADIUS_LG, padding=SPACE_MD, shadow=glow(strength=0.3),
    )


def _who(state, row, view):
    """(имя, команда, цвет, источник фото)"""
    if view == "drivers":
        return row["name"], row["team"], get_team_color(row["team"]), state.photo(row)
    return row["name"], "", get_team_color(row["name"]), None


def _avatar(state, row, view, size):
    if view == "drivers":
        return DriverAvatar(row["code"], row["team"], size=size, src=state.photo(row))
    return TeamLogo(row["name"], state.team_logo(row["name"]), size=size)


def _champion(state, row, view):
    name, _, color, _ = _who(state, row, view)
    return AnimatedCard(ft.Row([
        _avatar(state, row, view, 64),
        ft.Column([ft.Text("Чемпион мира" if view == "drivers" else "Обладатель Кубка конструкторов",
                           size=FONT_CAPTION, color=GOLD, font_family=FONT_ITALIC),
                   ft.Text(name, size=FONT_H3, color=TEXT_PRIMARY, font_family=FONT_HEADING),
                   ft.Text(f"Титул оформлен досрочно · {row['points']} очков", size=FONT_BODY_SMALL,
                           color=TEXT_MUTED)], spacing=2, expand=True),
        ft.Icon(ft.Icons.EMOJI_EVENTS_ROUNDED, color=GOLD, size=40),
    ], spacing=SPACE_MD, vertical_alignment=ft.CrossAxisAlignment.CENTER), accent=GOLD, size="l")


def _next_clinch(state, rows, race, view):
    leader, second = rows[0], rows[1]
    nxt = state.next_race()
    where = nxt["race_name"] if nxt else "ближайшей гонке"
    need = race["next_clinch"]
    rival = short_name(second["name"]) if view == "drivers" else second["name"]
    cond = (f"достаточно не уступить {rival}" if need == 0 else
            f"нужно опередить {rival} минимум на {need:g} {plural(int(need), 'очко', 'очка', 'очков')}")
    name = short_name(leader["name"]) if view == "drivers" else leader["name"]
    return AnimatedCard(ft.Row([
        _avatar(state, leader, view, 52),
        ft.Column([ft.Text("Может оформить титул", size=FONT_CAPTION, color=ACCENT_TEXT, font_family=FONT_ITALIC),
                   ft.Text(f"{name} — уже на этапе «{where}»", size=FONT_BODY, color=TEXT_PRIMARY,
                           weight=ft.FontWeight.W_600),
                   ft.Text(f"Для этого {cond}.", size=FONT_BODY_SMALL, color=TEXT_SECONDARY)],
                  spacing=2, expand=True),
    ], spacing=SPACE_MD, vertical_alignment=ft.CrossAxisAlignment.CENTER), accent=F1_RED, size="l")


def _contenders(state, race, view, total):
    rows = []
    leader_pts = race["contenders"][0][1] if race["contenders"] else 0
    top = max((c[2] for c in race["contenders"]), default=1) or 1
    for row, pts, best, gap in race["contenders"]:
        name, team, color, _ = _who(state, row, view)
        hint = "лидер" if gap <= 0 else f"отставание {gap:g} · нужно отыграть {gap:g} из {race['available']}"
        rows.append(AnimatedCard(ft.Column([
            ft.Row([
                PositionBadge(row["position"]),
                _avatar(state, row, view, 40),
                ft.Column([ft.Text(name, size=FONT_BODY, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600, max_lines=1,
                                   overflow=ft.TextOverflow.ELLIPSIS),
                           ft.Text(hint, size=FONT_CAPTION, color=TEXT_MUTED)], spacing=1, expand=True),
                ft.Column([ft.Text(f"{pts:g}", size=FONT_H4, color=TEXT_PRIMARY, font_family=FONT_DISPLAY_ITALIC),
                           ft.Text(f"макс. {best:g}", size=FONT_CAPTION, color=TEXT_DIM)],
                          spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
            ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            # полоса: набрано / максимум возможного; отметка — очки лидера
            ft.Stack([
                progress_bar(best / top, ft.Colors.with_opacity(0.35, color), height=6),
                progress_bar(pts / top, color, height=6),
            ]),
        ], spacing=SPACE_XS), accent=color,
            on_click=(lambda e, i=row["driver_id"]: state.open_driver(i)) if view == "drivers" else None))
    out = [SectionHeader("Ещё могут стать чемпионом" if view == "drivers" else "Ещё могут выиграть Кубок",
                         subtitle="Тёмная часть полосы — набрано, светлая — максимум при победах "
                                  "во всех оставшихся гонках")]
    out += rows
    gone = total - len(race["contenders"])
    if gone:
        out.append(ft.Text(f"Остальные {gone} уже не могут догнать лидера ({leader_pts:g} очков).",
                           size=FONT_BODY_SMALL, color=TEXT_MUTED))
    return ft.Column(out, spacing=SPACE_XS)
