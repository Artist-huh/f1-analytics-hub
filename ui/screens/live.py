"""Live-тайминг: позиции, отрывы, шины, пит-стопы и радио текущей сессии (поток F1, запасной — OpenF1)"""
import contextlib

import flet as ft

from design_system import *
from services import live
from ui.components import *
from ui.fmt import fmt_clock
from ui.screens.calendar import track_info
from ui.screens.live_table import LiveTable
from ui.screens.live_track import track_section
from ui.widgets import pill, retry_block, screen

SESSION_RU = {"Race": "Гонка", "Qualifying": "Квалификация", "Sprint": "Спринт",
              "Sprint Qualifying": "Спринт-квалификация", "Sprint Shootout": "Спринт-квалификация",
              "Practice 1": "Практика 1", "Practice 2": "Практика 2", "Practice 3": "Практика 3"}
TYRE_COLORS_SHORT = {"S": TYRE_COLORS["SOFT"], "M": TYRE_COLORS["MEDIUM"], "H": TYRE_COLORS["HARD"],
                     "I": TYRE_COLORS["INTERMEDIATE"], "W": TYRE_COLORS["WET"]}


def build(state):
    state.watch_live()
    data, error, loading = live.snapshot()
    if not data:
        if loading or not error:
            body = [skeleton("Загружаем данные сессии…", "rows", 10)]
        else:
            locked = error == live.LOCKED_TEXT
            body = [retry_block("Доступ к данным закрыт до конца сессии" if locked else "Нет данных о сессии",
                                live.LOCKED_TEXT if locked else "OpenF1 не ответил. Проверь интернет и повтори.",
                                lambda e: live.refresh(on_done=state.render))]
        return screen(state, "Live-тайминг", body, back=True)

    mode = state.ui.get("live_gap", "leader")

    def switch(key):
        state.ui["live_gap"] = key
        state.render()

    view = state.ui.get("live_view", "table")
    radio_items = data.get("radio") or []

    def show(key):
        state.ui["live_view"] = key
        state.render()

    body = [_header(state, data)]
    if data.get("weather"):
        body.append(weather_strip(data["weather"]))
    if data.get("track"):
        body.append(_track_status(data["track"]))
    tabs = [pill("Таблица", view == "table", lambda e: show("table"))]
    if data.get("circuit_key"):
        tabs.append(pill("Трасса", view == "track", lambda e: show("track")))
    if radio_items:
        tabs.append(pill(f"Радио ({len(radio_items)})", view == "radio", lambda e: show("radio")))
    if data["racing"] and view == "table":
        tabs += [pill("До лидера", mode == "leader", lambda e: switch("leader")),
                 pill("Интервал", mode == "interval", lambda e: switch("interval"))]
    body.append(ft.Row(tabs, spacing=SPACE_XS, scroll=ft.ScrollMode.AUTO))
    state.ui["live_shown"] = _structure(data)
    if view == "radio" and radio_items:
        state.ui.pop("live_table", None)
        body += _radio(state, data)
    elif view == "track" and data.get("circuit_key"):
        state.ui.pop("live_table", None)
        body += track_section(state, data)
    else:
        body.append(_table(state, data, mode))
        if data["messages"]:
            body.append(_messages(data["messages"]))
    source = ("Источник — официальный live timing F1: данные идут и во время сессии."
              if data.get("source") == "F1" else
              "Источник — OpenF1. Во время сессии бесплатный доступ закрыт; после сессии показан её итог.")
    body.append(ft.Text(source, size=FONT_CAPTION, color=TEXT_DIM))
    s = data["session"]
    return screen(state, "Live-тайминг", body, subtitle=f"{s['country']}, {s['location']}", back=True)


def _status_line(state, data):
    """«Сессия идёт, круг 31 из 56» / «Сессия идёт, осталось 00:41:12» / «Итог последней сессии»."""
    s = data["session"]
    total = None
    place = (s["location"] or "").lower()
    nxt = next((r for r in state.schedule if r["locality"] and place and
                (place in r["locality"].lower() or r["locality"].lower() in place)), None)
    if nxt:
        info = track_info(nxt)
        total = info[1] if info else None
    total = data.get("total_laps") or total
    lap = f"круг {data['lap']}" + (f" из {total}" if total else "") if data["lap"] and data["racing"] else ""
    if not lap and data.get("remaining") and data["live"]:
        lap = f"осталось {data['remaining']}"
    status = "Сессия идёт" if data["live"] else "Итог последней сессии"
    return ", ".join(x for x in (status, lap) if x)


def _header(state, data):
    s = data["session"]
    name = SESSION_RU.get(s["name"], s["name"])
    if data["live"]:
        badge = ft.Container(ft.Row([ft.Container(width=8, height=8, border_radius=4, bgcolor=ON_COLOR),
                                     ft.Text("LIVE", size=FONT_CAPTION, color=ON_COLOR, font_family=FONT_ITALIC)],
                                    spacing=6, tight=True),
                             bgcolor=LIVE_RED, border_radius=RADIUS_FULL,      # белый — 4.97:1 в любой теме
                             padding=ft.Padding.symmetric(horizontal=10, vertical=4))
    else:
        badge = ft.Container(ft.Row([ft.Icon(ft.Icons.SPORTS_SCORE_ROUNDED, color=ON_COLOR, size=14),
                                     ft.Text("Финиш", size=FONT_CAPTION, color=ON_COLOR, font_family=FONT_ITALIC)],
                                    spacing=4, tight=True),
                             bgcolor=ft.Colors.with_opacity(0.12, ON_COLOR), border_radius=RADIUS_FULL,
                             padding=ft.Padding.symmetric(horizontal=10, vertical=4))
    soft = ON_COLOR if data["live"] else ft.Colors.with_opacity(0.78, ON_COLOR)   # на красном — только сплошной белый
    updated = ft.Text(f"обновлено в {fmt_clock(data['updated'])}", size=FONT_CAPTION, color=soft)
    status = ft.Text(_status_line(state, data), size=FONT_BODY_SMALL, color=ON_COLOR)
    state.ui["live_head"] = {"updated": updated, "status": status}     # обновляются на месте (update_in_place)
    return ft.Container(ft.Column([
        ft.Row([badge, ft.Container(expand=True), updated]),
        ft.Column([ft.Text(name, size=FONT_H3, color=ON_COLOR, font_family=FONT_HEADING),
                   ft.Text(f"{s['circuit']} {s['year'] or ''}".strip(), size=FONT_BODY_SMALL, color=soft)], spacing=0),
        status,
    ], spacing=SPACE_XS),
        # красный — только пока сессия идёт; итог прошлой — на карбоне, как герой главной
        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                   colors=GRADIENT_LIVE if data["live"] else HERO_CARBON),
        border=None if data["live"] else ft.Border.all(1, ft.Colors.with_opacity(0.08, ON_COLOR)),
        border_radius=RADIUS_LG, padding=SPACE_MD, shadow=glow(strength=0.3) if data["live"] else None)


def tyre_badge(letter, age):
    color = TYRE_COLORS_SHORT.get(letter, TEXT_DIM)
    return ft.Row([
        ft.Container(ft.Text(letter or "—", size=FONT_CAPTION, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                     width=scaled(24), height=scaled(24), border_radius=12,
                     border=ft.Border.all(3, readable_text(color, 3.0)),   # жёсткая в светлой теме — серым кольцом
                     alignment=ft.Alignment.CENTER),
        ft.Text(f"{age}" if age is not None else "", size=FONT_CAPTION, color=TEXT_MUTED, width=scaled(20),
                font_family=FONT_MONO),
    ], spacing=4, tight=True)


def _table(state, data, mode):
    """Таблица на месте обновляемых строк (live_table.LiveTable): обгоны анимируются, отрывы подсвечиваются."""
    avatars = not (large_text() and is_narrow(state))     # крупный текст на телефоне: место — под код пилота
    table = LiveTable(state, data, mode, avatars, tyre_badge)
    state.ui["live_table"] = table
    head = ft.Row([ft.Text("Поз.", size=FONT_TINY, color=TEXT_DIM, width=70 if avatars else 30),
                   ft.Text("Пилот", size=FONT_TINY, color=TEXT_DIM, expand=True),
                   ft.Text("Отрыв" if mode == "leader" else "Интервал", size=FONT_TINY, color=TEXT_DIM,
                           width=scaled(78),
                           text_align=ft.TextAlign.RIGHT),
                   ft.Text("Шины", size=FONT_TINY, color=TEXT_DIM, width=scaled(48), no_wrap=True),
                   ft.Text("Пит", size=FONT_TINY, color=TEXT_DIM, width=scaled(22), no_wrap=True)], spacing=SPACE_XS)
    return ft.Column([ft.Container(head, padding=ft.Padding.symmetric(horizontal=SPACE_XS)), table.stack],
                     spacing=SPACE_XXS)


def update_in_place(state, data):
    """Свежий снимок, а экран Live уже открыт: обновить таблицу и шапку без перестройки экрана.
    -> False, если изменилось что-то структурное (тогда нужна обычная перерисовка)."""
    view = state.ui.get("live_view", "table")
    table = state.ui.get("live_track") if view == "track" else state.ui.get("live_table")
    head = state.ui.get("live_head")
    shown = state.ui.get("live_shown") or {}
    if not table or not head or state.sub != "live" or view not in ("table", "track") or shown != _structure(data):
        return False
    if not (table.matches(data) if view == "track" else table.matches(data, state.ui.get("live_gap", "leader"))):
        return False
    table.apply(data)
    head["updated"].value = f"обновлено в {fmt_clock(data['updated'])}"
    head["status"].value = _status_line(state, data)
    table.update()
    for text in head.values():
        with contextlib.suppress(RuntimeError, AssertionError, AttributeError):   # экран уже перестроен
            text.update()
    return True


def _weather_key(w):
    """Погода для сравнения «изменилось ли»: целые градусы и дождь — десятые доли не перестраивают экран."""
    if not w:
        return None
    return tuple(round(w[k]) if w.get(k) is not None else None for k in ("air", "track", "humidity")) + (w.get("rain"),)


def _structure(data):
    """Что требует полной перерисовки: сессия, сейфти-кар и флаги, число записей радио, последнее сообщение."""
    s = data["session"]
    return {"session": (s.get("name"), s.get("location")), "live": data["live"], "track": data.get("track"),
            "weather": _weather_key(data.get("weather")),
            "radio": len(data.get("radio") or []), "message": (data["messages"][0]["text"] if data["messages"] else "")}


def weather_strip(w):
    """Погода на трассе: воздух, асфальт, влажность, ветер, дождь — строкой чипов."""
    def chip(icon, text, color=TEXT_SECONDARY):
        # значок — 3:1 и в светлой теме (сырые цвета разделов там 1.5–2.6:1)
        return ft.Row([ft.Icon(icon, size=16, color=readable_text(color, 3.0)),
                       ft.Text(text, size=FONT_CAPTION, color=TEXT_SECONDARY)],
                      spacing=4, tight=True)
    items = []
    if w.get("air") is not None:
        items.append(chip(ft.Icons.THERMOSTAT_ROUNDED, f"воздух {w['air']:.0f}°", SECTION_COLORS["history"]))
    if w.get("track") is not None:
        items.append(chip(ft.Icons.ROUTE_ROUNDED, f"трасса {w['track']:.0f}°", DANGER))
    if w.get("humidity") is not None:
        items.append(chip(ft.Icons.WATER_DROP_ROUNDED, f"{w['humidity']:.0f} %", SECTION_COLORS["race"]))
    if w.get("wind") is not None:
        items.append(chip(ft.Icons.AIR_ROUNDED, f"{w['wind']:.1f} м/с"))
    items.append(chip(ft.Icons.UMBRELLA_ROUNDED, "дождь", SECTION_COLORS["race"]) if w.get("rain") else
                 chip(ft.Icons.WB_SUNNY_ROUNDED, "сухо", SECTION_COLORS["favorites"]))
    return AnimatedCard(ft.Row(items, spacing=SPACE_MD, wrap=True, run_spacing=SPACE_XS), size="s")


def _track_status(text):
    """Сейфти-кар, жёлтый или красный флаг — крупной плашкой над таблицей."""
    color = DANGER if "Красный" in text else WARNING
    fg = readable_on(color)                  # в светлой теме фон темнее — текст белый (тёмный там 2.9:1)
    return ft.Container(ft.Row([ft.Icon(ft.Icons.FLAG_ROUNDED, color=fg, size=20),
                                ft.Text(text, size=FONT_BODY, color=fg, weight=ft.FontWeight.BOLD)],
                               spacing=SPACE_XS),
                        bgcolor=color, border_radius=RADIUS_MD, padding=ft.Padding.symmetric(horizontal=SPACE_SM,
                                                                                               vertical=SPACE_XS))


def _radio(state, data):
    """Радио текущей сессии: свежие записи сверху; проигрывание и перевод — как в разборе гонки."""
    from services import radio
    from ui.screens.race_radio import _message, _translate_card
    items = list(reversed(data["radio"]))[:20]
    start = data["session"].get("start")
    feed = [_message(state, m, data["drivers"].get(m["driver"], {}), start) for m in items]
    if radio.supported() and radio.models_ready():
        waiting = [m["url"] for m in items if not radio.status(m["url"]) and not radio.cached(m["url"])]
        if waiting:
            feed.insert(0, ft.TextButton(f"Перевести новые ({len(waiting)})", icon=ft.Icons.TRANSLATE_ROUNDED,
                                         on_click=lambda e: ([radio.request(u, state.render) for u in waiting],
                                                             state.render())))
    return [_translate_card(state), ft.Column(feed, spacing=SPACE_XS)]


FLAG_COLORS = {"GREEN": SUCCESS, "YELLOW": WARNING, "DOUBLE YELLOW": WARNING, "RED": DANGER, "CHEQUERED": TEXT_PRIMARY,
               "BLUE": INFO, "CLEAR": SUCCESS}


def _messages(messages):
    items = []
    for m in messages:
        color = FLAG_COLORS.get(m["flag"] or "", TEXT_DIM)
        items.append(ft.Row([
            ft.Container(width=6, height=28, bgcolor=color, border_radius=3),
            ft.Column([ft.Text(m["text"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY),
                       ft.Text(", ".join(x for x in (fmt_clock(m["time"]) if m["time"] else "",
                                                      f"круг {m['lap']}" if m["lap"] else "") if x),
                               size=FONT_CAPTION, color=TEXT_MUTED)], spacing=0, expand=True),
        ], spacing=SPACE_SM))
    return ft.Column([SectionHeader("Дирекция гонки", subtitle="Последние сообщения"),
                      AnimatedCard(ft.Column(items, spacing=SPACE_XS))], spacing=SPACE_SM)
