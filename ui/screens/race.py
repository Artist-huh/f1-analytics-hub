"""Разбор прошедшей гонки: шины, позиции по кругам, темп, отставание в квалификации, радио"""
import flet as ft

from design_system import *
from services import archive, jolpica
from services import stats as st
from ui.components import *
from ui.fmt import plural, short_name
from ui.screens.race_radio import radio_section
from ui.screens.race_strategy import finishing_order, tyres_section
from ui.widgets import pill, retry_block, screen, touch

TABS = [("tyres", "Шины"), ("positions", "Позиции"), ("pace", "Темп"), ("quali", "Квалификация"),
        ("radio", "Радио")]


def laps_key(race):
    return f"laps:{race.get('season')}:{race['round']}"


def quali_key(race):
    return f"quali:{race.get('season')}:{race['round']}"


def build(state):
    race = state.ui.get("strat_race")
    if not race:
        return screen(state, "Разбор гонки", [empty_block(ft.Icons.FLAG_ROUNDED, "Гонка не выбрана",
                                                          "Открой прошедший этап в календаре.",
                                                          ("Открыть календарь", lambda e: state.open_tab(2)),
                                                          art="track")], back=True)
    view = state.ui.get("race_view", "tyres")

    def switch(key):
        state.ui["race_view"] = key
        state.render()

    tabs = ft.Row([pill(label, view == key, lambda e, k=key: switch(k)) for key, label in TABS],
                  spacing=SPACE_XS, scroll=ft.ScrollMode.AUTO)
    section = {"tyres": tyres_section, "positions": positions_section, "pace": pace_section,
               "quali": quali_section, "radio": radio_section}.get(view, tyres_section)(state, race)
    return screen(state, "Разбор гонки", [tabs] + section, subtitle=f"{race['round']}. {race['race_name']}",
                  back=True)


# ---------------------------------------------------------------- общие элементы
def _load(state, key, fetch, what):
    """Данные из архива или [индикатор/повтор] — второе значение."""
    data = archive.get(key, fetch, None, state.render)
    if data:
        return data, None
    if archive.loading(key):
        return None, [skeleton(f"Загружаем {what}…", "chart")]
    return None, [retry_block(f"Не удалось загрузить {what}",
                              "Нужен интернет: данные загружаются один раз и дальше доступны без сети.",
                              lambda e: (archive.get(key, fetch, None, state.render, force=True), state.render()))]


def _laps(state, race):
    return _load(state, laps_key(race), lambda: jolpica.fetch_race_laps(race["season"], race["round"]),
                 "круги гонки")


def _driver(state, driver_id):
    d = state.driver(driver_id)
    return d or {"driver_id": driver_id, "code": driver_id[:3].upper(), "team": "", "name": driver_id}


def _picked(state, race, laps):
    """Пилоты для графика темпа: выбранные или первые три финишёра."""
    order = [i for i in state.ui.get("pace_ids", []) if i in laps]
    if not order:
        rows = sorted((r for r in state.season_results if r["round"] == race["round"]),
                      key=lambda r: int(r["position"]) if r["position"].isdigit() else 99)
        order = [r["driver_id"] for r in rows if r["driver_id"] in laps][:3]
    return order[:4]


# ---------------------------------------------------------------- позиции по кругам
def positions_section(state, race):
    laps, fallback = _laps(state, race)
    if fallback:
        return fallback
    order = [r["driver_id"] for r in sorted((r for r in state.season_results if r["round"] == race["round"]),
                                             key=lambda r: int(r["position"]) if r["position"].isdigit() else 99)]
    order += [d for d in laps if d not in order]
    highlight = set(order[:10]) | set(state.favorites)
    series = []
    for driver_id in reversed(order):                       # первые — поверх остальных
        pts = [(n, pos) for n, pos, _ in laps.get(driver_id, [])]
        d = _driver(state, driver_id)
        bright = driver_id in highlight
        series.append((d["code"], get_team_color(d["team"]) if bright else LINE_STRONG, pts, 2.2 if bright else 1))
    total = max((len(v) for v in laps.values()), default=0)
    chart = series_chart(series, content_width(state) - 2 * SPACE_SM, height=380, y_min=1,
                         y_max=max(len(laps), 2), invert=True, y_format=lambda v: f"P{round(v)}", ticks=5)
    gains = []
    grid = {r["driver_id"]: r for r in state.season_results if r["round"] == race["round"]}
    for driver_id in order:
        r = grid.get(driver_id)
        if r and r["grid"].isdigit() and int(r["grid"]) and r["position"].isdigit():
            gains.append((int(r["grid"]) - int(r["position"]), driver_id))
    best = max(gains, default=None)
    note = (f"Больше всех отыграл {short_name(_driver(state, best[1])['name'])}: +{best[0]} "
            f"{plural(best[0], 'позиция', 'позиции', 'позиций')}" if best and best[0] > 0 else None)
    return [
        AnimatedCard(chart),
        ft.Text(note, size=FONT_BODY_SMALL, color=TEXT_SECONDARY) if note else ft.Container(),
        ft.Text(f"{total} {plural(total, 'круг', 'круга', 'кругов')}. Цветом — первая десятка и избранные, "
                "серым — остальные. Источник — Jolpica.", size=FONT_CAPTION, color=TEXT_DIM),
    ]


# ---------------------------------------------------------------- темп по кругам
def pace_section(state, race):
    laps, fallback = _laps(state, race)
    if fallback:
        return fallback
    picked = _picked(state, race, laps)

    def toggle(driver_id):
        ids = list(picked)
        ids = [i for i in ids if i != driver_id] if driver_id in ids else (ids + [driver_id])[-4:]
        state.ui["pace_ids"] = ids or picked
        state.render()

    chips = []
    finish = finishing_order(state, race)
    by_code = {d["code"]: d["driver_id"] for d in state.standings}
    for code in finish[:12]:
        driver_id = by_code.get(code)
        if not driver_id or driver_id not in laps:
            continue
        d = _driver(state, driver_id)
        active = driver_id in picked
        color = get_team_color(d["team"])
        chips.append(touch(ft.Container(
            ft.Text(code, size=FONT_CAPTION, color=readable_on(color) if active else TEXT_SECONDARY,
                    font_family=FONT_ITALIC),
            bgcolor=color if active else SURFACE_RAISED, border_radius=RADIUS_FULL, ink=True,
            padding=ft.Padding.symmetric(horizontal=12), on_click=lambda e, i=driver_id: toggle(i),
            tooltip=f"{d['name']}: показать на графике"), 32))
    series, rows = [], []
    colors_used = []
    for driver_id in picked:
        d = _driver(state, driver_id)
        color = get_team_color(d["team"])
        if color in colors_used:
            color = TEXT_SECONDARY                       # напарник — светлым, чтобы различать
        colors_used.append(color)
        clean = st.clean_laps(laps[driver_id])
        series.append((d["code"], color, clean, 2))
        p = st.pace_summary(laps[driver_id])
        rows.append((d, color, p))
    ys = [t for _, _, pts, _ in series for _, t in pts]
    chart = series_chart(series, content_width(state) - 2 * SPACE_SM, height=260, end_labels=False,
                         y_min=min(ys) if ys else None, y_max=max(ys) if ys else None, y_format=fmt_lap, ticks=5)
    fastest = min((p["median"] for _, _, p in rows if p["median"]), default=None)
    table = []
    for d, color, p in rows:
        gap = (p["median"] - fastest) if p["median"] and fastest else None
        table.append(ft.Row([
            ft.Container(width=4, height=28, bgcolor=color, border_radius=2),
            ft.Text(d["code"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, font_family=FONT_ITALIC, width=40),
            ft.Column([ft.Text(f"средний {fmt_lap(p['median'])}", size=FONT_BODY_SMALL, color=TEXT_PRIMARY),
                       ft.Text(f"лучший {fmt_lap(p['best'])} · {p['laps']} чистых кругов", size=FONT_CAPTION,
                               color=TEXT_MUTED)], spacing=0, expand=True),
            ft.Text("быстрее всех" if gap == 0 else (f"+{gap:.3f}" if gap is not None else "—"),
                    size=FONT_BODY_SMALL, font_family=FONT_MONO,
                    color=ACCENT_TEXT if gap == 0 else TEXT_SECONDARY),
        ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER))
    return [
        ft.Row(chips, spacing=SPACE_XS, scroll=ft.ScrollMode.AUTO),
        AnimatedCard(ft.Column([chart, legend([(n, c, None) for n, c, _, _ in series])], spacing=SPACE_XS)),
        AnimatedCard(ft.Column(table, spacing=SPACE_XS)),
        ft.Text("Чистые круги: без первого круга, заездов в боксы и сейфти-кара (медленнее медианы > 4 %). "
                "Выбери до четырёх пилотов.", size=FONT_CAPTION, color=TEXT_DIM),
    ]


# ---------------------------------------------------------------- квалификация
def quali_section(state, race):
    data, fallback = _load(state, quali_key(race),
                           lambda: jolpica.fetch_race_qualifying(race["season"], race["round"]), "квалификацию")
    if fallback:
        return fallback
    gaps = st.quali_gaps(data)
    worst = max((g for _, _, g in gaps if g is not None), default=1) or 1
    rows = []
    for r, _best, gap in gaps:
        color = get_team_color(r["team"])
        stage = "Q3" if r.get("q3") else "Q2" if r.get("q2") else "Q1"
        bar = (ft.Row([ft.Container(width=10, height=10, bgcolor=GOLD, border_radius=5)]) if gap == 0 else
               progress_bar(gap / worst, color, height=10) if gap is not None else ft.Container())
        rows.append(ft.Row([
            PositionBadge(r["position"], size=26),
            ft.Text(r["code"] or r["driver_id"][:3].upper(), size=FONT_BODY_SMALL, color=TEXT_PRIMARY,
                    font_family=FONT_ITALIC, width=40),
            ft.Container(bar, expand=True),
            ft.Text("поул" if gap == 0 else (f"+{gap:.3f}" if gap is not None else "без времени"),
                    size=FONT_BODY_SMALL, font_family=FONT_MONO,
                    color=GOLD if gap == 0 else TEXT_SECONDARY, width=78, text_align=ft.TextAlign.RIGHT),
            ft.Text(stage, size=FONT_CAPTION, color=TEXT_DIM, width=24),
        ], spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER))
    pole = gaps[0] if gaps else None
    head = (f"Поул: {pole[0]['name']} — {fmt_lap(pole[1])}" if pole and pole[1] else "Квалификация")
    return [
        AnimatedCard(ft.Text(head, size=FONT_BODY, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600)),
        AnimatedCard(ft.Column(rows, spacing=6)),
        ft.Text("Лучшее время в той части квалификации, до которой дошёл пилот. Источник — Jolpica.",
                size=FONT_CAPTION, color=TEXT_DIM),
    ]
