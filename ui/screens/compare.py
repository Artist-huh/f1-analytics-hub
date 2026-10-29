"""Сравнение 2–4 пилотов: показатели сезона, график очков, личные встречи"""
import flet as ft

from design_system import *
from services import stats as st
from ui.components import *
from ui.fmt import plural, short_name, to_int
from ui.state import MAX_COMPARE
from ui.widgets import empty_state, screen, touch

# (подпись, ключ, меньше-лучше, формат)
METRICS = [
    ("Позиция в зачёте", "position", True, lambda v: f"P{v}"),
    ("Очки", "points", False, lambda v: f"{v:g}"),
    ("Победы", "wins", False, str),
    ("Подиумы", "podiums", False, str),
    ("Поулы", "poles", False, str),
    ("Быстрые круги", "fastest_laps", False, str),
    ("Финиши в топ-10", "top10", False, str),
    ("Сходы", "dnf", True, str),
    ("Лучший финиш", "best", True, lambda v: f"P{v}"),
    ("Средний финиш", "avg_finish", True, lambda v: f"{v:.1f}"),
    ("Средняя квалификация", "avg_quali", True, lambda v: f"{v:.1f}"),
    ("Очков за гонку", "points_per_race", False, lambda v: f"{v:.1f}"),
    ("Отыгрыш со старта", "avg_gain", False, lambda v: f"{v:+.1f}"),
]

head_to_head = st.head_to_head   # совместимость: тесты и другие экраны


def metric_values(state, drivers, key):
    """Значения показателя для каждого пилота (None — нет данных)."""
    out = []
    for d in drivers:
        if key == "position":
            out.append(to_int(d["position"]))
        elif key == "points":
            out.append(float(d["points"]))
        else:
            out.append(state.driver_stats(d["driver_id"]).get(key))
    return out


def leaders(values, lower_is_better):
    """Индексы лучших значений (несколько при равенстве; пусто, если все равны или нет данных)."""
    known = [v for v in values if v is not None]
    if len(known) < 2 or len(set(known)) == 1:
        return set()
    best = min(known) if lower_is_better else max(known)
    return {i for i, v in enumerate(values) if v == best}


def build(state):
    """Построить экран сравнения"""
    if len(state.standings) < 2:
        return screen(state, "Сравнение", [empty_state(state, "Не с кем сравнивать",
                                                        "Нужна таблица чемпионата — нажми «Обновить».")], back=True)
    drivers = [state.driver(i) for i in state.compare_ids()]
    sections = [
        _build_selector(state, drivers),
        _build_metrics(state, drivers),
        _build_chart(state, drivers),
        _build_head_to_head(state, drivers),
    ]
    n = len(drivers)
    return screen(state, "Сравнение", sections,
                  subtitle=f"{n} {plural(n, 'пилот', 'пилота', 'пилотов')} · сезон {state.season}", back=True)


# ---------------------------------------------------------------- выбор пилотов
def _build_selector(state, drivers):
    ids = [d["driver_id"] for d in drivers]
    narrow = is_narrow(state)

    def remove(driver_id):
        state.set_compare([i for i in ids if i != driver_id])

    cells = []
    for d in drivers:
        color = get_team_color(d["team"])
        cells.append(ft.Container(
            ft.Column([
                ft.Stack([
                    ft.Container(DriverAvatar(d["code"], d["team"], size=52 if narrow else 64, src=state.photo(d),
                                              on_click=lambda e, i=d["driver_id"]: state.open_driver(i)),
                                 left=0, top=12),
                    # крестик 24 px, зона нажатия 48 dp — над правым верхним углом фото
                    ft.Container(
                        ft.Container(ft.Icon(ft.Icons.CLOSE_ROUNDED, size=14, color=TEXT_PRIMARY),
                                     width=24, height=24, border_radius=12, bgcolor=SURFACE_ELEVATED,
                                     alignment=ft.Alignment.CENTER),
                        width=TOUCH, height=TOUCH, right=0, top=0, alignment=ft.Alignment.CENTER,
                        border_radius=TOUCH / 2, ink=True,
                        on_click=lambda e, i=d["driver_id"]: remove(i), tooltip="Убрать из сравнения",
                    ) if len(drivers) > 2 else ft.Container(),
                ], width=(52 if narrow else 64) + 24, height=(52 if narrow else 64) + 12),
                ft.Text(d["code"] or short_name(d["name"]), size=FONT_BODY, color=TEXT_PRIMARY,
                        font_family=FONT_ITALIC),
                ft.Container(height=3, width=36, bgcolor=color, border_radius=2),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=SPACE_XXS),
            expand=True,
        ))
    if len(drivers) < MAX_COMPARE:
        cells.append(ft.Container(
            ft.Column([
                ft.Container(ft.Icon(ft.Icons.ADD_ROUNDED, color=TEXT_PRIMARY, size=26),
                             width=52 if narrow else 64, height=52 if narrow else 64, border_radius=32,
                             border=ft.Border.all(2, F1_RED), alignment=ft.Alignment.CENTER,
                             bgcolor=ACCENT_SOFT),
                ft.Text("Добавить", size=FONT_CAPTION, color=TEXT_MUTED),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=SPACE_XXS),
            expand=True, ink=True, border_radius=RADIUS_MD, on_click=lambda e: _show_picker(state, ids),
        ))

    presets = _presets(state)
    chips = [touch(ft.Container(ft.Text(label, size=FONT_CAPTION, color=TEXT_SECONDARY, weight=ft.FontWeight.W_600),
                                bgcolor=SURFACE_RAISED, border_radius=RADIUS_FULL, ink=True,
                                padding=ft.Padding.symmetric(horizontal=12),
                                on_click=lambda e, p=preset: state.set_compare(p)), 32)
             for label, preset in presets]
    return AnimatedCard(ft.Column([
        ft.Row(cells, vertical_alignment=ft.CrossAxisAlignment.START, spacing=SPACE_XXS),
        ft.Row(chips, spacing=SPACE_XS, scroll=ft.ScrollMode.AUTO),
    ], spacing=SPACE_SM))


def _presets(state):
    s = state.standings
    out = [("Топ-2", [d["driver_id"] for d in s[:2]]), ("Топ-3", [d["driver_id"] for d in s[:3]]),
           ("Топ-4", [d["driver_id"] for d in s[:4]])]
    leader = s[0]
    mates = [leader] + state.teammates(leader)
    if len(mates) > 1:
        out.append((f"Напарники {leader['team']}", [d["driver_id"] for d in mates]))
    favs = [i for i in state.favorites if state.driver(i)]
    if len(favs) >= 2:
        out.append(("Избранные", favs[:MAX_COMPARE]))
    return out


def _show_picker(state, ids):
    """Диалог выбора пилота для сравнения (с фото)."""
    page = state.page

    def add(driver_id):
        page.pop_dialog()
        state.set_compare(ids + [driver_id])

    items = [
        ft.Container(
            content=ft.Row([
                PositionBadge(d["position"], size=28),
                DriverAvatar(d["code"], d["team"], size=40, src=state.photo(d)),
                ft.Column([
                    ft.Text(d["name"], size=FONT_BODY, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                    ft.Text(d["team"], size=FONT_CAPTION, color=TEXT_SECONDARY),
                ], spacing=2, expand=True),
                ft.Icon(ft.Icons.ADD_CIRCLE_ROUNDED, color=ACCENT_TEXT),
            ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=SURFACE_RAISED, border_radius=RADIUS_SM, padding=SPACE_XS, ink=True,
            on_click=lambda e, i=d["driver_id"]: add(i),
        )
        for d in state.standings if d["driver_id"] not in ids
    ]
    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Добавить в сравнение", size=FONT_H4, color=TEXT_PRIMARY, font_family=FONT_HEADING),
        content=ft.Column(items, spacing=SPACE_XS, scroll=ft.ScrollMode.AUTO, width=380, height=420),
        actions=[ft.TextButton("Закрыть", on_click=lambda e: page.pop_dialog())],
        bgcolor=SURFACE,
    ))


# ---------------------------------------------------------------- показатели
def _build_metrics(state, drivers):
    colors = [get_team_color(d["team"]) for d in drivers]
    rows = []
    for label, key, lower, fmt in METRICS:
        values = metric_values(state, drivers, key)
        best = leaders(values, lower)
        known = [v for v in values if v is not None]
        span = (max(known) - min(min(known), 0)) if known else 0
        cells = []
        for i, v in enumerate(values):
            win = i in best
            text = "—" if v is None else fmt(v)
            bar = None
            if v is not None and not lower and span > 0 and key != "avg_gain":
                bar = progress_bar(max(v, 0) / span, colors[i], height=3)
            cells.append(ft.Container(
                ft.Column([ft.Text(text, size=FONT_H4, font_family=FONT_DISPLAY_ITALIC,
                                   color=TEXT_PRIMARY if win else TEXT_MUTED, text_align=ft.TextAlign.CENTER)]
                          + ([bar] if bar else []),
                          spacing=4, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                expand=True, padding=ft.Padding.symmetric(horizontal=6, vertical=6), border_radius=RADIUS_SM,
                bgcolor=ft.Colors.with_opacity(0.18, colors[i]) if win else None,
                border=ft.Border.all(1, colors[i]) if win else None,
            ))
        rows.append(ft.Container(
            ft.Column([ft.Text(label, size=FONT_CAPTION, color=TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
                       ft.Row(cells, spacing=SPACE_XXS)],
                      spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=SURFACE, border_radius=RADIUS_SM, padding=ft.Padding.symmetric(horizontal=6, vertical=SPACE_XS),
            border=ft.Border.all(1, LINE_SUBTLE),
        ))
    header = ft.Row([ft.Container(ft.Text(d["code"] or short_name(d["name"]), size=FONT_BODY_SMALL,
                                          color=readable_text(colors[i]), font_family=FONT_ITALIC,
                                          text_align=ft.TextAlign.CENTER),
                                  expand=True)
                     for i, d in enumerate(drivers)], spacing=SPACE_XXS)
    return ft.Column([SectionHeader("Показатели сезона", subtitle="Лучшее значение выделено цветом команды"),
                      ft.Container(header, padding=ft.Padding.symmetric(horizontal=6)),
                      ft.Column(rows, spacing=SPACE_XXS)], spacing=SPACE_SM)


# ---------------------------------------------------------------- график
def _build_chart(state, drivers):
    rounds = st.rounds(state.season_results, state.sprints)
    series = [(short_name(d["name"]), get_team_color(d["team"]),
               st.cumulative_points(state.driver_results(d["driver_id"]), state.driver_sprints(d["driver_id"]), rounds))
              for d in drivers]
    if not rounds:
        return ft.Container()
    return ft.Column([
        SectionHeader("Набор очков", subtitle="Гонки и спринты по этапам (напарники — пунктиром)"),
        AnimatedCard(ft.Column([line_chart(series, rounds, content_width(state) - 2 * SPACE_SM, height=220),
                                legend(series)], spacing=SPACE_XS)),
    ], spacing=SPACE_SM)


# ---------------------------------------------------------------- личные встречи
def _build_head_to_head(state, drivers):
    results = {d["driver_id"]: state.driver_results(d["driver_id"]) for d in drivers}
    if not all(results.values()):
        loading = any(state.results_loading(d["driver_id"]) for d in drivers)
        return ft.Column([SectionHeader("Личные встречи"), ft.Row([
            ft.ProgressRing(width=18, height=18, stroke_width=2, color=F1_RED) if loading
            else ft.Icon(ft.Icons.INFO_ROUNDED, color=TEXT_DIM, size=18),
            ft.Text("Загружаем результаты гонок…" if loading else "Нет общих гонок для сравнения",
                    size=FONT_BODY_SMALL, color=TEXT_MUTED),
        ], spacing=SPACE_SM)], spacing=SPACE_SM)
    if len(drivers) == 2:
        return _build_duel(state, *drivers, results)
    return _build_group(state, drivers, results)


def _score_card(title, a, b, c1, c2):
    total = a + b
    return AnimatedCard(ft.Column([
        ft.Text(title, size=FONT_CAPTION, color=TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
        ft.Row([
            ft.Text(str(a), size=FONT_H1, color=readable_text(c1, 3.0), font_family=FONT_DISPLAY_ITALIC, expand=True,
                    text_align=ft.TextAlign.CENTER),
            ft.Text(":", size=FONT_H2, color=TEXT_DIM),
            ft.Text(str(b), size=FONT_H1, color=readable_text(c2, 3.0), font_family=FONT_DISPLAY_ITALIC, expand=True,
                    text_align=ft.TextAlign.CENTER),
        ]),
        ft.Row([ft.Container(expand=a or None, height=5, bgcolor=c1, border_radius=3),
                ft.Container(expand=b or None, height=5, bgcolor=c2, border_radius=3)],
               spacing=2) if total else ft.Container(),
    ], spacing=SPACE_XXS, horizontal_alignment=ft.CrossAxisAlignment.CENTER), expand=True)


def _build_duel(state, d1, d2, results):
    w1, w2, races = st.head_to_head(results[d1["driver_id"]], results[d2["driver_id"]])
    q1, q2 = st.quali_head_to_head(state.driver_quali(d1["driver_id"]), state.driver_quali(d2["driver_id"]))
    c1, c2 = get_team_color(d1["team"]), get_team_color(d2["team"])
    if c1 == c2:
        c2 = TEXT_SECONDARY      # напарники: второй — светлым, чтобы различать
    lines = []
    for rnd, name, p1, p2 in reversed(races):
        a, b = to_int(p1), to_int(p2)
        first_won = b is None or (a is not None and a < b)
        lines.append(ft.Row([
            ft.Text(f"P{p1}" if a else p1, size=FONT_BODY_SMALL, weight=ft.FontWeight.BOLD, width=40,
                    color=readable_text(c1) if first_won else TEXT_DIM, text_align=ft.TextAlign.CENTER),
            ft.Text(f"{rnd}. {name}", size=FONT_BODY_SMALL, color=TEXT_SECONDARY, expand=True,
                    text_align=ft.TextAlign.CENTER, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(f"P{p2}" if b else p2, size=FONT_BODY_SMALL, weight=ft.FontWeight.BOLD, width=40,
                    color=readable_text(c2) if not first_won else TEXT_DIM, text_align=ft.TextAlign.CENTER),
        ]))
    return ft.Column([
        SectionHeader("Личные встречи", subtitle=f"{d1['code']} против {d2['code']}"),
        ft.Row([_score_card("Гонки: кто финишировал выше", w1, w2, c1, c2),
                _score_card("Квалификации", q1, q2, c1, c2)], spacing=SPACE_XS),
        ft.Column(lines, spacing=SPACE_XXS),
    ], spacing=SPACE_SM)


def _build_group(state, drivers, results):
    counts = st.finishing_ahead(results)
    top = max(counts.values()) or 1
    rows = []
    for d in sorted(drivers, key=lambda x: -counts[x["driver_id"]]):
        n = counts[d["driver_id"]]
        color = get_team_color(d["team"])
        rows.append(ft.Row([
            DriverAvatar(d["code"], d["team"], size=36, src=state.photo(d)),
            ft.Column([ft.Text(d["name"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600),
                       progress_bar(n / top, color, height=6)], spacing=4, expand=True),
            ft.Text(str(n), size=FONT_H3, color=TEXT_PRIMARY, font_family=FONT_DISPLAY_ITALIC, width=40,
                    text_align=ft.TextAlign.RIGHT),
        ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER))
    return ft.Column([
        SectionHeader("Кто чаще был впереди", subtitle="Гонки, где пилот финишировал выше всех выбранных"),
        AnimatedCard(ft.Column(rows, spacing=SPACE_SM)),
    ], spacing=SPACE_SM)
