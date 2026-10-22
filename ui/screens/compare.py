"""Экран сравнения двух пилотов head-to-head"""
import flet as ft
from design_system import *
from ui.components import *
from ui.fmt import to_int
from ui.widgets import empty_state, field_border, screen


def build(state):
    """Построить экран сравнения"""
    drivers = state.standings
    if len(drivers) < 2:
        return screen(state, "Сравнение", [empty_state(state, "Не с кем сравнивать",
                                                        "Нужна таблица чемпионата — нажми «Обновить».")], back=True)

    is_mobile = ResponsiveContainer.is_mobile(page_width(state))
    d1 = state.driver(state.ui.get("cmp1")) or drivers[0]
    d2 = state.driver(state.ui.get("cmp2"))
    if d2 is None or d2["driver_id"] == d1["driver_id"]:
        d2 = next(d for d in drivers if d["driver_id"] != d1["driver_id"])

    sections = [
        _build_driver_selector(state, drivers, d1, d2, is_mobile),
        _build_comparison_header(d1, d2, is_mobile),
        _build_stats_comparison(d1, d2),
        _build_head_to_head(state, d1, d2),
    ]
    return screen(state, "Сравнение", sections, subtitle="Два пилота лицом к лицу", back=True)


def _build_driver_selector(state, drivers, d1, d2, is_mobile):
    """Селекторы для выбора пилотов"""

    current = {"cmp1": d1["driver_id"], "cmp2": d2["driver_id"]}

    def on_select(slot, other):
        def handler(e):
            chosen = e.control.value
            if not chosen:
                return
            state.ui[other] = current[slot] if chosen == current[other] else current[other]  # один пилот дважды — меняем местами
            state.ui[slot] = chosen
            state.render()
        return handler

    def dropdown(label, value, handler):
        return ft.Dropdown(
            label=label,
            value=value,
            options=[ft.DropdownOption(key=d["driver_id"], text=f"{d['position']}. {d['name']}") for d in drivers],
            on_select=handler,
            border=field_border(LINE_STRONG, ACCENT_PRIMARY),
            bgcolor=SURFACE,
            color=TEXT_PRIMARY,
            text_size=FONT_BODY,
            dense=True,
            expand=True,
        )

    def swap(e):
        state.ui["cmp1"], state.ui["cmp2"] = current["cmp2"], current["cmp1"]
        state.render()

    first = dropdown("Пилот 1", d1["driver_id"], on_select("cmp1", "cmp2"))
    second = dropdown("Пилот 2", d2["driver_id"], on_select("cmp2", "cmp1"))
    swap_btn = ft.IconButton(icon=ft.Icons.SWAP_HORIZ_ROUNDED if not is_mobile else ft.Icons.SWAP_VERT_ROUNDED,
                             icon_color=ACCENT_PRIMARY, tooltip="Поменять местами", on_click=swap)
    if is_mobile:
        content = ft.Column([ft.Row([first]), ft.Row([ft.Container(expand=True), swap_btn, ft.Container(expand=True)]),
                             ft.Row([second])], spacing=0)
    else:
        content = ft.Row([first, swap_btn, second], vertical_alignment=ft.CrossAxisAlignment.CENTER)
    return ft.Container(content=content, bgcolor=SURFACE, border_radius=RADIUS_MD, padding=SPACE_SM,
                        border=ft.Border.all(1, LINE))


def _build_comparison_header(d1, d2, is_mobile):
    """Header с двумя пилотами"""

    def column(d):
        return ft.Column([
            DriverAvatar(d["code"], d["team"], size=48 if is_mobile else 64),
            ft.Text(d["name"].split()[-1], size=FONT_H4, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY,
                    text_align=ft.TextAlign.CENTER, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(d["team"], size=FONT_BODY_SMALL, color=TEXT_SECONDARY, text_align=ft.TextAlign.CENTER,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=SPACE_XXS, expand=True)

    return ft.Row([
        column(d1),
        ft.Text("VS", size=FONT_H2, weight=ft.FontWeight.BOLD, color=ACCENT_PRIMARY, font_family=FONT_HEADING),
        column(d2),
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER)


def _build_stats_comparison(d1, d2):
    """Сравнение статистики (числа сравниваются как числа, а не как строки)"""
    stats = [
        ("Позиция", d1["position"], d2["position"], True),   # True = меньше лучше
        ("Очки", d1["points"], d2["points"], False),
        ("Победы", d1["wins"], d2["wins"], False),
    ]
    c1, c2 = get_team_color(d1["team"]), get_team_color(d2["team"])
    rows = []
    for label, v1, v2, lower_is_better in stats:
        a, b = float(v1), float(v2)
        if a == b:
            leader = 0
        elif lower_is_better:
            leader = 1 if a < b else 2
        else:
            leader = 1 if a > b else 2

        def value(text, slot):
            return ft.Text(text, size=FONT_H3, weight=ft.FontWeight.BOLD, font_family=FONT_HEADING,
                           color=SUCCESS if leader == slot else TEXT_PRIMARY if leader == 0 else TEXT_MUTED,
                           text_align=ft.TextAlign.CENTER, expand=True)

        items = [ft.Row([value(v1, 1), ft.Text(label, size=FONT_BODY_SMALL, color=TEXT_SECONDARY, expand=True,
                                               text_align=ft.TextAlign.CENTER), value(v2, 2)])]
        if not lower_is_better and a + b > 0:
            items.append(ft.Row([
                ft.Container(expand=round(a * 10) or None, height=4, bgcolor=c1, border_radius=2),
                ft.Container(expand=round(b * 10) or None, height=4, bgcolor=c2, border_radius=2),
            ], spacing=2))
        rows.append(ft.Container(content=ft.Column(items, spacing=SPACE_XS), bgcolor=SURFACE,
                                 border_radius=RADIUS_SM, padding=SPACE_SM))

    return ft.Column([SectionHeader("Статистика"), ft.Column(rows, spacing=SPACE_XS)], spacing=SPACE_SM)


def head_to_head(results1, results2):
    """Кто финишировал выше на общих этапах. Сход проигрывает финишу; два схода — не в счёт.
    -> (побед первого, побед второго, [(этап, название, поз1, поз2), ...])"""
    by_round = {r["round"]: r for r in results2}
    w1 = w2 = 0
    races = []
    for r1 in results1:
        r2 = by_round.get(r1["round"])
        if not r2:
            continue
        p1, p2 = to_int(r1["position"]), to_int(r2["position"])
        if p1 is None and p2 is None:
            continue
        if p2 is None or (p1 is not None and p1 < p2):
            w1 += 1
        else:
            w2 += 1
        races.append((r1["round"], r1["race_name"], r1["position"], r2["position"]))
    return w1, w2, races


def _build_head_to_head(state, d1, d2):
    """История личных встреч"""
    header = SectionHeader("Head-to-Head", subtitle="Кто финишировал выше в гонках")
    res1, res2 = state.driver_results(d1["driver_id"]), state.driver_results(d2["driver_id"])
    if not res1 or not res2:
        loading = state.results_loading(d1["driver_id"]) or state.results_loading(d2["driver_id"])
        return ft.Column([header, ft.Row([
            ft.ProgressRing(width=18, height=18, stroke_width=2, color=ACCENT_PRIMARY) if loading
            else ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=TEXT_DIM, size=18),
            ft.Text("Загружаем результаты гонок…" if loading else "Нет общих гонок для сравнения",
                    size=FONT_BODY_SMALL, color=TEXT_MUTED),
        ], spacing=SPACE_SM)], spacing=SPACE_SM)

    w1, w2, races = head_to_head(res1, res2)
    c1, c2 = get_team_color(d1["team"]), get_team_color(d2["team"])
    score = ft.Container(
        content=ft.Row([
            ft.Text(str(w1), size=FONT_H1, weight=ft.FontWeight.BOLD, color=c1, font_family=FONT_HEADING,
                    expand=True, text_align=ft.TextAlign.CENTER),
            ft.Text(":", size=FONT_H2, color=TEXT_DIM),
            ft.Text(str(w2), size=FONT_H1, weight=ft.FontWeight.BOLD, color=c2, font_family=FONT_HEADING,
                    expand=True, text_align=ft.TextAlign.CENTER),
        ]),
        bgcolor=SURFACE, border_radius=RADIUS_MD, padding=SPACE_SM,
    )
    lines = []
    for rnd, name, p1, p2 in reversed(races):
        a, b = to_int(p1), to_int(p2)
        first_won = b is None or (a is not None and a < b)
        lines.append(ft.Row([
            ft.Text(f"P{p1}" if a else p1, size=FONT_BODY_SMALL, weight=ft.FontWeight.BOLD, width=40,
                    color=SUCCESS if first_won else TEXT_MUTED, text_align=ft.TextAlign.CENTER),
            ft.Text(f"{rnd}. {name}", size=FONT_BODY_SMALL, color=TEXT_SECONDARY, expand=True,
                    text_align=ft.TextAlign.CENTER, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(f"P{p2}" if b else p2, size=FONT_BODY_SMALL, weight=ft.FontWeight.BOLD, width=40,
                    color=SUCCESS if not first_won else TEXT_MUTED, text_align=ft.TextAlign.CENTER),
        ]))
    return ft.Column([header, score, ft.Column(lines, spacing=SPACE_XXS)], spacing=SPACE_SM)
