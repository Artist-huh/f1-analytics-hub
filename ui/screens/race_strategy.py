"""Разбор гонки, вкладка «Шины»: полосы по кругам для каждого пилота, цвет — состав, отметки пит-стопов"""
import flet as ft

from design_system import *
from services import archive, live
from ui.components import *
from ui.fmt import plural
from ui.widgets import retry_block

TYRE_NAMES = {"S": "мягкие", "M": "средние", "H": "жёсткие", "I": "промежуточные", "W": "дождевые"}
TYRE_COLOR = {"S": TYRE_COLORS["SOFT"], "M": TYRE_COLORS["MEDIUM"], "H": TYRE_COLORS["HARD"],
              "I": TYRE_COLORS["INTERMEDIATE"], "W": TYRE_COLORS["WET"]}


def strategy_key(race):
    return f"strategy:{race.get('season')}:{race['round']}"


def finishing_order(state, race):
    """Коды пилотов по местам финиша этой гонки (из результатов Jolpica)."""
    codes = {d["driver_id"]: d["code"] for d in state.standings}
    rows = [r for r in state.season_results if r["round"] == race["round"]]
    rows.sort(key=lambda r: int(r["position"]) if r["position"].isdigit() else 99)
    return [codes.get(r["driver_id"], "") for r in rows]


def tyres_section(state, race):
    """Вкладка «Шины» разбора гонки: полосы стинтов по кругам (OpenF1)."""
    key = strategy_key(race)
    fetch = lambda: live.fetch_strategy(int(race["season"]), race["date"])
    data = archive.get(key, fetch, None, state.render)
    if not data:
        if archive.loading(key):
            return [skeleton("Загружаем стинты и пит-стопы…", "bars", 10)]
        err = archive.error(key)
        hint = (live.LOCKED_TEXT if err == live.LOCKED_TEXT else
                "OpenF1 не отдал данные этой гонки — возможно, они ещё не опубликованы." if err else
                "Нужен интернет: данные загружаются один раз и дальше доступны без сети.")
        return [retry_block("Стратегия не загружена", hint,
                            lambda e: (archive.get(key, fetch, None, state.render, force=True), state.render()))]

    rows = live.strategy_rows(data, finishing_order(state, race))
    used = sorted({s["tyre"] for r in rows for s in r["stints"]},
                  key=lambda t: "SMHIW?".index(t) if t in "SMHIW" else 9)
    legend_row = ft.Row([ft.Row([ft.Container(width=14, height=14, border_radius=7,
                                              bgcolor=TYRE_COLOR.get(t, TEXT_DIM), border=_edge(t)),
                                 ft.Text(TYRE_NAMES.get(t, t), size=FONT_CAPTION, color=TEXT_SECONDARY)],
                                spacing=4, tight=True) for t in used], wrap=True, spacing=SPACE_SM)
    stops = [len(r["pits"]) for r in rows]
    common = max(set(stops), key=stops.count) if stops else 0
    summary = (f"{data['laps']} {plural(data['laps'], 'круг', 'круга', 'кругов')} · чаще всего — "
               f"{common} {plural(common, 'пит-стоп', 'пит-стопа', 'пит-стопов')}")
    return [
        AnimatedCard(ft.Column([ft.Text(summary, size=FONT_BODY_SMALL, color=TEXT_SECONDARY), legend_row],
                               spacing=SPACE_XS)),
        _axis(data["laps"]),
        ft.Column([_row(state, r, data["laps"]) for r in rows], spacing=6),
        ft.Text("Источник — OpenF1. Порядок — по местам финиша; цифры на полосах — номер круга пит-стопа.",
                size=FONT_CAPTION, color=TEXT_DIM),
    ]


def _edge(tyre):
    edge = tyre_edge(TYRE_COLOR.get(tyre, TEXT_DIM))
    return ft.Border.all(1, edge) if edge else None


LABEL_W = 46
STOPS_W = 26


def _axis(laps):
    marks = [1] + [k for k in range(10, laps, 10) if laps - k >= 5] + [laps]
    cells = []
    prev = 0
    for m in marks:
        cells.append(ft.Container(ft.Text(str(m), size=FONT_TINY, color=TEXT_DIM, max_lines=1, no_wrap=True),
                                  expand=max(1, m - prev),
                                  alignment=ft.Alignment.CENTER_RIGHT))
        prev = m
    return ft.Row([ft.Container(width=LABEL_W), ft.Row(cells, spacing=0, expand=True), ft.Container(width=STOPS_W)],
                  spacing=SPACE_XS)


def _row(state, r, total):
    segments = []
    last = 0
    for s in r["stints"]:
        if s["start"] > last + 1:                       # пропуск (нет данных) — прозрачный отрезок
            segments.append(ft.Container(expand=s["start"] - last - 1))
        color = TYRE_COLOR.get(s["tyre"], TEXT_DIM)
        segments.append(ft.Container(
            ft.Text(s["tyre"] if s["laps"] >= 5 else "", size=FONT_TINY, color=readable_on(color),
                    weight=ft.FontWeight.BOLD),
            expand=s["laps"], height=18, bgcolor=color, border_radius=4, alignment=ft.Alignment.CENTER,
            border=_edge(s["tyre"]),
            tooltip=f"{TYRE_NAMES.get(s['tyre'], s['tyre'])}: круги {s['start']}–{s['end']}"
                    + (f", б/у ({s['age']} кр.)" if s["age"] else ", новые"),
        ))
        last = s["end"]
    if last < total:
        segments.append(ft.Container(expand=total - last))       # сход — полоса обрывается
    pit_laps = ", ".join(str(p["lap"]) for p in r["pits"])
    color = r["colour"] or TEXT_DIM
    return ft.Column([
        ft.Row([
            ft.Row([ft.Container(width=3, height=18, bgcolor=color, border_radius=2),
                    ft.Text(r["code"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, font_family=FONT_ITALIC)],
                   spacing=4, width=LABEL_W),
            ft.Row(segments, spacing=2, expand=True),
            ft.Text(str(len(r["pits"])), size=FONT_BODY_SMALL, color=TEXT_SECONDARY, width=STOPS_W,
                    text_align=ft.TextAlign.CENTER, tooltip="пит-стопов"),
        ], spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ft.Row([ft.Container(width=LABEL_W), ft.Text(f"пит: {pit_laps}" if pit_laps else "без пит-стопов",
                                                    size=FONT_TINY, color=TEXT_DIM)], spacing=SPACE_XS),
    ], spacing=0)
