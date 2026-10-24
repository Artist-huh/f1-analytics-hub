"""Игра в прогнозы: поул и подиум ближайшего этапа, очки за прошедшие, итог сезона"""
import time

import flet as ft

from design_system import *
from services import predictions as pr
from ui.components import *
from ui.fmt import fmt_clock, fmt_date_full, plural
from ui.widgets import button, screen

SLOTS = [("pole", "Поул"), ("p1", "1-е место"), ("p2", "2-е место"), ("p3", "3-е место")]


def actual_podiums(state):
    """round -> [P1, P2, P3] по результатам гонок."""
    out = {}
    for r in state.season_results:
        if r["position"] in ("1", "2", "3"):
            out.setdefault(r["round"], [None] * 3)[int(r["position"]) - 1] = r["driver_id"]
    return {k: v for k, v in out.items() if all(v)}


def actual_poles(state):
    return {r["round"]: r["driver_id"] for r in state.qualifying if r["position"] == "1"}


def next_open_race(state, now=None):
    now = time.time() if now is None else now
    return next((r for r in state.schedule if pr.is_open(r, now)), None)


def build(state):
    season = state.schedule[0].get("season", "") if state.schedule else ""
    if not state.schedule or not state.standings:
        return screen(state, "Прогнозы", [empty_block(ft.Icons.SPORTS_SCORE, "Нет данных сезона",
                                                      "Обнови данные, когда будет интернет.",
                                                      ("Обновить", lambda e: state.refresh_now()))], back=True)
    picks = pr.load_season(season)
    podiums, poles = actual_podiums(state), actual_poles(state)
    body = [_summary(pr.season_stats(picks, podiums, poles))]
    race = next_open_race(state)
    if race:
        body.append(_picker(state, season, race, picks.get(race["round"], {})))
    else:
        body.append(AnimatedCard(ft.Text("Сезон завершён: новых этапов для прогноза нет.", size=FONT_BODY_SMALL,
                                         color=TEXT_SECONDARY)))
    past = [r for r in reversed(state.schedule) if r["round"] in picks and (not race or r["round"] != race["round"])]
    if past:
        body.append(ft.Text("Мои прогнозы", size=FONT_H3, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600))
        body += [_past(state, r, picks[r["round"]], poles.get(r["round"]), podiums.get(r["round"])) for r in past]
    body.append(ft.Text(f"Очки: поул — {pr.POLE_POINTS}, пилот на своём месте подиума — {pr.EXACT_POINTS}, "
                        f"на подиуме, но на другом месте — {pr.PODIUM_POINTS}, весь подиум по порядку — ещё "
                        f"{pr.PERFECT_BONUS}. Прогноз принимается до старта квалификации.",
                        size=FONT_CAPTION, color=TEXT_DIM))
    return screen(state, "Прогнозы", body, subtitle=f"Сезон {season}", back=True)


# ---------------------------------------------------------------- итог сезона
def _summary(s):
    def cell(value, label):
        return ft.Column([ft.Text(str(value), size=FONT_H2, color=TEXT_PRIMARY, font_family=FONT_ITALIC),
                          ft.Text(label, size=FONT_CAPTION, color=TEXT_MUTED)], spacing=0, expand=True,
                         horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    best = f"лучший этап — {s['best'][0]}-й, {s['best'][1]} очк." if s["best"] else "пока нет оценённых этапов"
    share = f"{round(100 * s['points'] / s['max'])} % от максимума" if s["max"] else ""
    return AnimatedCard(ft.Column([
        ft.Row([cell(s["points"], plural(s["points"], "очко", "очка", "очков")),
                cell(s["rounds"], plural(s["rounds"], "этап", "этапа", "этапов")),
                cell(s["exact"], "точных")], spacing=SPACE_SM),
        ft.Text(" · ".join(x for x in (best, share) if x), size=FONT_CAPTION, color=TEXT_SECONDARY,
                text_align=ft.TextAlign.CENTER),
    ], spacing=SPACE_XS, horizontal_alignment=ft.CrossAxisAlignment.CENTER))


# ---------------------------------------------------------------- прогноз на ближайший этап
def _picker(state, season, race, saved):
    draft = state.ui.setdefault("predict_draft", {})
    if draft.get("_round") != race["round"]:
        draft.clear()
        draft.update(saved, _round=race["round"])
    slot = state.ui.get("predict_slot", "pole")

    def choose_slot(key):
        state.ui["predict_slot"] = key
        state.render()

    def choose_driver(driver_id):
        if slot != "pole":                                   # на подиуме пилот один раз
            for k in ("p1", "p2", "p3"):
                if k != slot and draft.get(k) == driver_id:
                    draft[k] = None
        draft[slot] = driver_id
        order = [k for k, _ in SLOTS]
        empty = [k for k in order[order.index(slot) + 1:] + order if not draft.get(k)]
        state.ui["predict_slot"] = empty[0] if empty else slot
        state.render()

    def submit(e):
        pr.save(season, race["round"], {k: draft.get(k) for k, _ in SLOTS})
        show_snack(state.page, "Прогноз сохранён — изменить можно до старта квалификации")
        state.render()

    slots = []
    for key, label in SLOTS:
        d = state.driver(draft.get(key)) if draft.get(key) else None
        active = key == slot
        slots.append(ft.Container(
            ft.Column([ft.Text(label, size=FONT_CAPTION, color=TEXT_MUTED),
                       ft.Text(d["code"] if d else "—", size=FONT_H3, font_family=FONT_ITALIC,
                               color=readable_text(get_team_color(d["team"]), 3.0) if d else TEXT_DIM)],
                      spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            expand=True, padding=SPACE_XS, border_radius=RADIUS_MD, ink=True,
            bgcolor=SURFACE_RAISED if active else None,
            border=ft.Border.all(2, F1_RED if active else LINE_STRONG),
            on_click=lambda e, k=key: choose_slot(k),
            tooltip=f"{label}: {d['name'] if d else 'не выбран'}"))
    chips = []
    for d in state.standings:
        chosen = draft.get(slot) == d["driver_id"]
        color = get_team_color(d["team"])
        chips.append(ft.Container(
            ft.Text(d["code"], size=FONT_CAPTION, color=readable_on(color) if chosen else TEXT_SECONDARY,
                    font_family=FONT_ITALIC),
            bgcolor=color if chosen else SURFACE_RAISED, border_radius=RADIUS_FULL, ink=True,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            on_click=lambda e, i=d["driver_id"]: choose_driver(i), tooltip=d["name"]))
    ready = all(draft.get(k) for k, _ in SLOTS)
    changed = any(draft.get(k) != saved.get(k) for k, _ in SLOTS)
    can_save = ready and changed
    status = ("Прогноз сохранён" if saved and not changed else
              "Есть несохранённые изменения" if saved else "Выбери поул и подиум")
    return AnimatedCard(ft.Column([
        ft.Text(f"{race['round']}. {race['race_name']}", size=FONT_BODY, color=TEXT_PRIMARY,
                weight=ft.FontWeight.W_600),
        ft.Text(f"Приём до {fmt_date_full(pr.lock_time(race))}, {fmt_clock(pr.lock_time(race))}", size=FONT_CAPTION,
                color=TEXT_MUTED),
        ft.Row(slots, spacing=SPACE_XS),
        ft.Text(f"Кто возьмёт «{dict(SLOTS)[slot].lower()}»?", size=FONT_BODY_SMALL, color=TEXT_SECONDARY),
        ft.Row(chips, spacing=SPACE_XS, run_spacing=SPACE_XS, wrap=True),
        ft.Row([ft.Text(status, size=FONT_CAPTION, color=TEXT_MUTED, expand=True),
                button("Сохранить", submit if can_save else None, primary=can_save, icon=ft.Icons.CHECK_ROUNDED)],
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
    ], spacing=SPACE_SM))


# ---------------------------------------------------------------- прошедшие этапы
def _past(state, race, pick, pole, podium):
    result = pr.score(pick, pole, podium)

    def name(driver_id):
        d = state.driver(driver_id) if driver_id else None
        return d["code"] if d else "—"

    lines = []
    for key, label in SLOTS:
        points, why = result["items"].get(key, (None, "ждём результатов"))
        actual = pole if key == "pole" else (podium[int(key[1]) - 1] if podium else None)
        lines.append(ft.Row([
            ft.Text(label, size=FONT_CAPTION, color=TEXT_MUTED, width=72),
            ft.Text(name(pick.get(key)), size=FONT_BODY_SMALL, color=TEXT_PRIMARY, font_family=FONT_ITALIC,
                    width=44),
            ft.Text(f"факт: {name(actual)}" if actual else why, size=FONT_CAPTION, color=TEXT_SECONDARY,
                    expand=True),
            ft.Text(f"+{points}" if points else ("0" if points == 0 else ""), size=FONT_BODY_SMALL,
                    color=SUCCESS if points else TEXT_DIM, width=32, text_align=ft.TextAlign.RIGHT,
                    tooltip=why),
        ], spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER))
    if "bonus" in result["items"]:
        lines.append(ft.Text(f"Бонус +{pr.PERFECT_BONUS}: весь подиум в точном порядке", size=FONT_CAPTION,
                             color=GOLD))
    total = (f"{result['total']} из {pr.MAX_POINTS}" if result["complete"] else "ждём результатов")
    return AnimatedCard(ft.Column([
        ft.Row([ft.Text(f"{race['round']}. {race['race_name']}", size=FONT_BODY_SMALL, color=TEXT_PRIMARY,
                        weight=ft.FontWeight.W_600, expand=True),
                ft.Text(total, size=FONT_BODY_SMALL, color=ACCENT_TEXT if result["complete"] else TEXT_DIM)]),
        *lines,
    ], spacing=4))
