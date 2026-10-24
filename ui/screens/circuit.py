"""Трасса: схема, характеристики, история — победители, поулы, лучший круг в гонке"""
import time
from collections import Counter

import flet as ft

from design_system import *
from services import archive, media
from ui.components import *
from ui.fmt import fmt_date_full, plural
from ui.screens.calendar import session_list, track_info
from ui.widgets import retry_block, screen


def lap_seconds(text):
    """'1:21.046' -> 81.046; пустая строка -> None."""
    try:
        minutes, rest = text.split(":") if ":" in text else ("0", text)
        return int(minutes) * 60 + float(rest)
    except (AttributeError, ValueError):
        return None


def circuit_summary(data):
    """Итоги трассы за все годы из ответа archive.circuit()."""
    winners, poles, fastest = data.get("winners", []), data.get("poles", []), data.get("fastest", [])
    by_driver = Counter(w["name"] for w in winners)
    by_team = Counter(w["team"] for w in winners if w.get("team"))
    by_pole = Counter(p["name"] for p in poles)
    laps = [(lap_seconds(f["time"]), f) for f in fastest if lap_seconds(f["time"])]
    record = min(laps, key=lambda x: x[0])[1] if laps else None
    return {
        "races": len(winners),
        "first": min((int(w["season"]) for w in winners), default=None),
        "top_driver": by_driver.most_common(1)[0] if by_driver else None,
        "top_team": by_team.most_common(1)[0] if by_team else None,
        "top_pole": by_pole.most_common(1)[0] if by_pole else None,
        "record": record,
    }


def build(state):
    race = state.ui.get("circuit")
    if race:   # актуальная версия этапа (в старом снимке данных могло не быть идентификатора трассы)
        race = next((r for r in state.schedule if r["round"] == race.get("round")
                     and r.get("season") == race.get("season")), race)
    if not race:
        return screen(state, "Трасса", [empty_block(ft.Icons.ROUTE_ROUNDED, "Трасса не выбрана",
                                                    "Открой этап в календаре и нажми «Трасса и история».",
                                                    ("Открыть календарь", lambda e: state.open_tab(2)),
                                                    art="track")], back=True)
    sections = [_hero(state, race)]
    if race.get("start_ts") and race["start_ts"] > time.time():
        sections.append(ft.Column([SectionHeader("Расписание уик-энда"),
                                   AnimatedCard(session_list(race))], spacing=SPACE_SM))
    cid = race.get("circuit_id")
    data = archive.circuit(cid, on_done=state.render) if cid else None
    if data:
        sections += _history(state, data)
    elif cid and archive.loading(archive.circuit_key(cid)):
        sections.append(skeleton("Загружаем историю трассы…", "rows", 4))
    else:
        sections.append(retry_block("История трассы не загружена",
                                    "Нужен интернет: данные загружаются один раз и дальше доступны без сети.",
                                    lambda e: (archive.circuit(cid, on_done=state.render, force=True),
                                               state.render()) if cid else None))
    return screen(state, race.get("locality") or "Трасса", sections, subtitle=race.get("circuit"), back=True)


def _hero(state, race):
    info = track_info(race)
    flag_src, iso = state.flag(country=race.get("country"))
    track = media.track(race.get("season") or state.season, race.get("circuit_id"), dark_lines=IS_LIGHT)
    specs = []
    if info:
        specs = [("Длина круга", info[0]), ("Кругов", str(info[1]))]
    specs.append(("Этап", race.get("round", "—")))
    return AnimatedCard(ft.Column([
        ft.Row([flag(flag_src, 18, iso),
                ft.Column([ft.Text(race.get("race_name", ""), size=FONT_H4, color=TEXT_PRIMARY,
                                   font_family=FONT_HEADING),
                           ft.Text(f"{race.get('locality', '')}, {race.get('country', '')}", size=FONT_BODY_SMALL,
                                   color=TEXT_MUTED)], spacing=0, expand=True)], spacing=SPACE_SM),
        ft.Container(image(track, height=200, fit=ft.BoxFit.CONTAIN, label=f"Схема трассы {race['circuit']}",
                           fallback=ft.Icon(ft.Icons.ROUTE_ROUNDED, size=80, color=TEXT_DIM)),
                     alignment=ft.Alignment.CENTER, height=200, padding=SPACE_XS),
        ft.Row([ft.Column([ft.Text(v, size=FONT_H4, color=TEXT_PRIMARY, font_family=FONT_DISPLAY_ITALIC),
                           ft.Text(k, size=FONT_CAPTION, color=TEXT_MUTED)],
                          horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0, expand=True)
                for k, v in specs]),
        ft.Text(fmt_date_full(race["start_ts"]), size=FONT_CAPTION,
                color=TEXT_DIM) if race.get("start_ts") else ft.Container(),
    ], spacing=SPACE_SM), size="l", accent=F1_RED)


def _history(state, data):
    s = circuit_summary(data)
    if not s["races"]:
        return [ft.Text("Гонок Формулы-1 на этой трассе ещё не было — это новый этап календаря.",
                        size=FONT_BODY_SMALL, color=TEXT_MUTED)]
    facts = [("Первый Гран-при", str(s["first"])),
             ("Гонок проведено", str(s["races"]))]
    if s["top_driver"]:
        facts.append(("Больше всего побед", f"{s['top_driver'][0]} — {s['top_driver'][1]}"))
    if s["top_team"]:
        facts.append(("Лучшая команда", f"{s['top_team'][0]} — {s['top_team'][1]} "
                                        f"{plural(s['top_team'][1], 'победа', 'победы', 'побед')}"))
    if s["top_pole"]:
        facts.append(("Больше всего поулов", f"{s['top_pole'][0]} — {s['top_pole'][1]}"))
    if s["record"]:
        r = s["record"]
        facts.append(("Лучший круг в гонке", f"{r['time']} — {r['name']}, {r['season']}"))
    fact_rows = [ft.Row([ft.Text(k, size=FONT_BODY_SMALL, color=TEXT_MUTED, expand=True),
                         ft.Text(v, size=FONT_BODY_SMALL, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600,
                                 text_align=ft.TextAlign.RIGHT)], spacing=SPACE_SM) for k, v in facts]
    out = [SectionHeader("Трасса в цифрах",
                         subtitle="Данные о кругах — с 2004 года; конфигурация трассы могла меняться"),
           AnimatedCard(ft.Column(fact_rows, spacing=SPACE_XS))]
    out.append(_people(state, "Последние победители", list(reversed(data["winners"]))[:10]))
    if data.get("poles"):
        out.append(_people(state, "Последние поулы", list(reversed(data["poles"]))[:10], show_time=True))
    return out


def _people(state, title, rows, show_time=False):
    from ui.screens.history import _person_avatar
    items = []
    for r in rows:
        right = r.get("time") if show_time else ""
        items.append(ft.Row([
            ft.Text(r["season"], size=FONT_BODY_SMALL, color=TEXT_MUTED, font_family=FONT_DISPLAY_ITALIC, width=44),
            _person_avatar(state, r, 30),
            ft.Column([ft.Text(r["name"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600,
                               max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                       ft.Text(r.get("team", ""), size=FONT_CAPTION, color=TEXT_MUTED, max_lines=1)],
                      spacing=0, expand=True),
            ft.Text(right, size=FONT_CAPTION, color=TEXT_SECONDARY),
        ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER))
    return ft.Column([SectionHeader(title), AnimatedCard(ft.Column(items, spacing=SPACE_XS))],
                     spacing=SPACE_SM)
