"""Строки таблиц, общие для экранов: пилот (позиция, фото, флаг, команда, очки) и команда."""
import flet as ft

from design_system import *
from ui.components import *
from ui.fmt import plural, short_name


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
            driver_hero(d["driver_id"], DriverAvatar(d["code"], d["team"], size=40 if compact else 44,
                                                     src=state.photo(d))),
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
        items.append(ft.Container(image(state.team_car(c["name"]), height=64, fit=ft.BoxFit.CONTAIN,
                                        label=f"Болид {c['name']}"),
                                  alignment=ft.Alignment.CENTER, height=64))
    items.append(progress_bar(float(c["points"]) / leader_points if leader_points else 0, color))
    return AnimatedCard(
        content=ft.Column(items, spacing=SPACE_XS),
        accent=color,
        on_click=lambda e, n=c["name"]: state.open_team(n),
    )


def points_block(points, caption=None):
    value = float(points)
    return ft.Column([
        ft.Text(f"{value:g}", size=FONT_H4, color=TEXT_PRIMARY, font_family=FONT_DISPLAY_ITALIC),
        ft.Text(caption or plural(value, "очко", "очка", "очков"), size=FONT_CAPTION, color=TEXT_DIM),
    ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END)
