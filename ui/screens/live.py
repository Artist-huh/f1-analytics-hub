"""Live-тайминг: позиции, отрывы, шины, пит-стопы и радио текущей сессии (поток F1, запасной — OpenF1)"""
import flet as ft

from design_system import *
from services import live
from ui.components import *
from ui.fmt import fmt_clock, plural
from ui.screens.calendar import track_info
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
            body = [ft.Row([ft.ProgressRing(width=20, height=20, stroke_width=2, color=F1_RED),
                            ft.Text("Загружаем данные сессии…", size=FONT_BODY_SMALL, color=TEXT_MUTED)],
                           spacing=SPACE_SM)]
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
    if data.get("track"):
        body.append(_track_status(data["track"]))
    tabs = [pill("Таблица", view == "table", lambda e: show("table"))]
    if radio_items:
        tabs.append(pill(f"Радио · {len(radio_items)}", view == "radio", lambda e: show("radio")))
    if data["racing"] and view == "table":
        tabs += [pill("До лидера", mode == "leader", lambda e: switch("leader")),
                 pill("Интервал", mode == "interval", lambda e: switch("interval"))]
    body.append(ft.Row(tabs, spacing=SPACE_XS, scroll=ft.ScrollMode.AUTO))
    if view == "radio" and radio_items:
        body += _radio(state, data)
    else:
        body.append(_table(state, data, mode))
        if data["messages"]:
            body.append(_messages(data["messages"]))
    source = ("Источник — официальный live timing F1: данные идут и во время сессии."
              if data.get("source") == "F1" else
              "Источник — OpenF1. Во время сессии бесплатный доступ закрыт; после сессии показан её итог.")
    body.append(ft.Text(source, size=FONT_CAPTION, color=TEXT_DIM))
    s = data["session"]
    return screen(state, "Live-тайминг", body, subtitle=f"{s['country']} · {s['location']}", back=True)


def _header(state, data):
    s = data["session"]
    name = SESSION_RU.get(s["name"], s["name"])
    total = None
    place = (s["location"] or "").lower()
    nxt = next((r for r in state.schedule if r["locality"] and place and
                (place in r["locality"].lower() or r["locality"].lower() in place)), None)
    if nxt:
        info = track_info(nxt)
        total = info[1] if info else None
    total = data.get("total_laps") or total
    lap = f"Круг {data['lap']}" + (f" из {total}" if total else "") if data["lap"] and data["racing"] else ""
    if not lap and data.get("remaining") and data["live"]:
        lap = f"осталось {data['remaining']}"
    if data["live"]:
        badge = ft.Container(ft.Row([ft.Container(width=8, height=8, border_radius=4, bgcolor=ON_COLOR),
                                     ft.Text("LIVE", size=FONT_CAPTION, color=ON_COLOR, font_family=FONT_ITALIC)],
                                    spacing=6, tight=True),
                             bgcolor=DANGER, border_radius=RADIUS_FULL,
                             padding=ft.Padding.symmetric(horizontal=10, vertical=4))
        status = "Сессия идёт"
    else:
        badge = ft.Container(ft.Text("ФИНИШ", size=FONT_CAPTION, color=ON_COLOR, font_family=FONT_ITALIC),
                             bgcolor=ft.Colors.with_opacity(0.25, BG_DEEPEST), border_radius=RADIUS_FULL,
                             padding=ft.Padding.symmetric(horizontal=10, vertical=4))
        status = "Итог последней сессии"
    return ft.Container(ft.Column([
        ft.Row([badge, ft.Container(expand=True),
                ft.Text(f"обновлено в {fmt_clock(data['updated'])}", size=FONT_CAPTION, color=ON_COLOR)]),
        ft.Text(f"{name} · {s['circuit']} {s['year'] or ''}", size=FONT_H3, color=ON_COLOR, font_family=FONT_HEADING),
        ft.Text(" · ".join(x for x in (status, lap) if x), size=FONT_BODY_SMALL, color=ON_COLOR),
    ], spacing=SPACE_XS), gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                                     colors=GRADIENT_RED),
        border_radius=RADIUS_LG, padding=SPACE_MD, shadow=glow(strength=0.3))


def _leader_text(r, data):
    """У лидера отрыва нет: в гонке — «лидер», в практике и квалификации — его лучший круг (как на табло F1)."""
    if r["position"] != 1:
        return ""
    return "лидер" if data["racing"] else (r.get("best") or "")


def tyre_badge(letter, age):
    color = TYRE_COLORS_SHORT.get(letter, TEXT_DIM)
    return ft.Row([
        ft.Container(ft.Text(letter or "—", size=FONT_CAPTION, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                     width=scaled(24), height=scaled(24), border_radius=12, border=ft.Border.all(3, color),
                     alignment=ft.Alignment.CENTER),
        ft.Text(f"{age}" if age is not None else "", size=FONT_CAPTION, color=TEXT_MUTED, width=scaled(20),
                font_family=FONT_MONO),
    ], spacing=4, tight=True)


def _table(state, data, mode):
    by_code = {d["code"]: d for d in state.standings}
    rows = []
    avatars = not (large_text() and is_narrow(state))     # крупный текст на телефоне: место — под код пилота
    for r in data["rows"]:
        d = by_code.get(r["code"])
        color = r["colour"] or (get_team_color(d["team"]) if d else TEXT_DIM)
        gap = r["gap"] if mode == "leader" else r["interval"]
        rows.append(ft.Container(ft.Row([
            PositionBadge(r["position"], size=28),
            ft.Container(width=3, height=30, bgcolor=color, border_radius=2),
            *([DriverAvatar(r["code"], d["team"] if d else r["team"], size=32, src=state.photo(d) if d else None)]
              if avatars else []),
            ft.Column([ft.Text(r["code"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, font_family=FONT_ITALIC,
                               no_wrap=True),
                       ft.Text(r["team"], size=FONT_TINY, color=TEXT_MUTED, max_lines=1,
                               overflow=ft.TextOverflow.ELLIPSIS)],
                      spacing=0, expand=True),
            ft.Text(gap or _leader_text(r, data), size=FONT_BODY_SMALL, font_family=FONT_MONO,
                    color=TEXT_PRIMARY if gap else ACCENT_TEXT, width=scaled(78), text_align=ft.TextAlign.RIGHT),
            tyre_badge(r["tyre"], r["tyre_age"]),
            ft.Container(ft.Text(f"{r['pits']}", size=FONT_CAPTION, color=TEXT_SECONDARY, font_family=FONT_MONO),
                         width=scaled(22),
                         alignment=ft.Alignment.CENTER,
                         tooltip=f"{r['pits']} {plural(r['pits'], 'пит-стоп', 'пит-стопа', 'пит-стопов')}"),
        ], spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=SURFACE, border_radius=RADIUS_SM, border=ft.Border.all(1, LINE_SUBTLE),
            padding=ft.Padding.symmetric(horizontal=SPACE_XS, vertical=4),
            on_click=(lambda e, i=d["driver_id"]: state.open_driver(i)) if d else None, ink=bool(d)))
    head = ft.Row([ft.Text("Поз.", size=FONT_TINY, color=TEXT_DIM, width=70 if avatars else 30),
                   ft.Text("Пилот", size=FONT_TINY, color=TEXT_DIM, expand=True),
                   ft.Text("Отрыв" if mode == "leader" else "Интервал", size=FONT_TINY, color=TEXT_DIM,
                           width=scaled(78),
                           text_align=ft.TextAlign.RIGHT),
                   ft.Text("Шины", size=FONT_TINY, color=TEXT_DIM, width=scaled(48), no_wrap=True),
                   ft.Text("Пит", size=FONT_TINY, color=TEXT_DIM, width=scaled(22), no_wrap=True)], spacing=SPACE_XS)
    return ft.Column([ft.Container(head, padding=ft.Padding.symmetric(horizontal=SPACE_XS))] + rows, spacing=SPACE_XXS)


def _track_status(text):
    """Сейфти-кар, жёлтый или красный флаг — крупной плашкой над таблицей."""
    color = DANGER if "Красный" in text else WARNING
    return ft.Container(ft.Row([ft.Icon(ft.Icons.FLAG_ROUNDED, color=INK, size=20),
                                ft.Text(text, size=FONT_BODY, color=INK, weight=ft.FontWeight.BOLD)],
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
                       ft.Text(" · ".join(x for x in (fmt_clock(m["time"]) if m["time"] else "",
                                                      f"круг {m['lap']}" if m["lap"] else "") if x),
                               size=FONT_CAPTION, color=TEXT_MUTED)], spacing=0, expand=True),
        ], spacing=SPACE_SM))
    return ft.Column([SectionHeader("Дирекция гонки", subtitle="Последние сообщения"),
                      AnimatedCard(ft.Column(items, spacing=SPACE_XS), padding=SPACE_SM)], spacing=SPACE_SM)
