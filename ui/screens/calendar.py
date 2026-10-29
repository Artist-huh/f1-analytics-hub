"""Календарь сезона: ближайшая гонка с отсчётом, предстоящие и прошедшие этапы"""
import time

import flet as ft

from design_system import *
from services import f1_api as api
from ui.components import *
from ui.fmt import SESSION_NAMES, fmt_clock, fmt_countdown, fmt_date, fmt_date_full, fmt_day, short_name
from ui.widgets import empty_state, pill, screen

# Характеристики трасс: (часть названия автодрома или города, длина круга, кругов в гонке)
TRACK_INFO = [
    ("bahrain", "5,412 км", 57), ("jeddah", "6,174 км", 50), ("albert park", "5,278 км", 58),
    ("suzuka", "5,807 км", 53), ("shanghai", "5,451 км", 56), ("miami", "5,412 км", 57),
    ("enzo e dino", "4,909 км", 63), ("monaco", "3,337 км", 78), ("villeneuve", "4,361 км", 70),
    ("catalunya", "4,657 км", 66), ("red bull ring", "4,318 км", 71), ("silverstone", "5,891 км", 52),
    ("hungaroring", "4,381 км", 70), ("spa-francorchamps", "7,004 км", 44), ("zandvoort", "4,259 км", 72),
    ("monza", "5,793 км", 53), ("baku", "6,003 км", 51), ("marina bay", "4,940 км", 62),
    ("americas", "5,513 км", 56), ("hermanos", "4,304 км", 71), ("carlos pace", "4,309 км", 71),
    ("las vegas", "6,201 км", 50), ("losail", "5,419 км", 57), ("yas marina", "5,281 км", 58),
]


def track_info(race):
    """(длина, круги) по названию автодрома/города; None для незнакомой трассы."""
    text = f"{race.get('circuit', '')} {race.get('locality', '')}".lower()
    return next(((length, laps) for needle, length, laps in TRACK_INFO if needle in text), None)


def build_calendar(state):
    """Построить календарь гонок"""
    races = state.schedule
    if not races:
        return screen(state, "Календарь", [empty_state(state, "Календарь ещё не загружен",
                                                        "Нажми «Обновить», когда появится интернет.")])

    view = state.ui.get("cal", "upcoming")

    def choose(key):
        state.ui["cal"] = key
        state.render()

    states = {r["round"]: api.race_state(r) for r in races}
    podiums = state.podiums()
    done = sum(1 for s in states.values() if s == "past")

    body = [ft.Row([pill("Предстоящие", view == "upcoming", lambda e: choose("upcoming")),
                    pill(f"Прошедшие · {done}" if done else "Прошедшие", view == "past",
                         lambda e: choose("past"))], spacing=SPACE_XS)]

    shown = [r for r in races if (states[r["round"]] == "past") == (view == "past")]
    if view == "past":
        shown.reverse()  # свежие сверху
    if not shown:
        body.append(empty_block(ft.Icons.HISTORY_EDU_ROUNDED,
                                "Сезон завершён" if view == "upcoming" else "Здесь пока пусто",
                                "Итоги сезона — в «Истории сезонов»." if view == "upcoming" else None,
                                ("История сезонов", lambda e: state.open_sub("history")) if view == "upcoming"
                                else None, art="track"))

    for i, race in enumerate(shown):
        if view == "upcoming" and i == 0:
            body.append(_build_next_race_card(state, race, states[race["round"]]))
            if len(shown) > 1:
                body.append(SectionHeader("Дальше в сезоне", subtitle=f"{len(shown) - 1} этапов"))
        else:
            body.append(_build_race_card(state, race, podiums.get(race["round"]), past=view == "past"))

    sub = f"Сезон {state.season or races[0]['season']} · пройдено {done} из {len(races)}"
    return screen(state, "Календарь", body, subtitle=sub)


def _build_next_race_card(state, race, race_state):
    """Большая карточка ближайшей гонки"""
    live = race_state == "live"
    sprint = any(s["key"] == "Sprint" for s in race["sessions"])
    info = track_info(race)
    flag_src, iso = state.flag(country=race["country"])

    # красный — только когда этап идёт; ближайший выделен рамкой и порядком, а не красным
    chips = [_chip("Идёт сейчас", LIVE_RED, ON_COLOR) if live else _chip("Ближайшая", SURFACE_ELEVATED, TEXT_PRIMARY)]
    if sprint:
        chips.append(_chip("Спринт", SURFACE_ELEVATED, WARNING))

    countdown = ft.Text(
        "Гонка идёт" if live else fmt_countdown(race["start_ts"] - time.time()),
        size=FONT_H2, color=TEXT_PRIMARY, font_family=FONT_DISPLAY_ITALIC, no_wrap=True,
    )
    specs = []
    if info:
        specs = [_spec("Длина круга", info[0], ft.Icons.STRAIGHTEN_ROUNDED),
                 _spec("Кругов", str(info[1]), ft.Icons.REPLAY_ROUNDED)]

    items = [
        ft.Row(chips + [ft.Container(expand=True), flag(flag_src, 20, iso)], spacing=SPACE_XS),
        ft.Text(race["race_name"], size=FONT_H3, color=TEXT_PRIMARY, font_family=FONT_HEADING),
        ft.Text(f"Этап {race['round']} · {race['circuit']}", size=FONT_BODY_SMALL, color=TEXT_SECONDARY),
        ft.Text(f"{race['locality']}, {race['country']}", size=FONT_BODY_SMALL, color=TEXT_MUTED),
        ft.Container(
            content=ft.Row([
                ft.Column([ft.Text("До старта", size=FONT_CAPTION, color=TEXT_MUTED), countdown],
                          spacing=0, expand=True),
                *([] if large_text() else specs),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=SPACE_SM),
            gradient=ft.LinearGradient(begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT,
                                       colors=[ACCENT_SOFT if live else SURFACE_ELEVATED, SURFACE_RAISED]),
            border_radius=RADIUS_MD, padding=SPACE_SM,
        ),
        *([ft.Row(specs, spacing=SPACE_LG)] if large_text() and specs else []),   # крупный текст: под отсчётом
        session_list(race),
        _circuit_button(state, race),
    ]
    return ft.Container(
        content=ft.Column(items, spacing=SPACE_XS),
        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                   colors=[SURFACE_RAISED, SURFACE]),
        border_radius=RADIUS_LG,
        padding=SPACE_MD,
        border=ft.Border.all(1, LIVE_RED if live else LINE_STRONG),
        shadow=glow(LIVE_RED, strength=0.25) if live else shadow(1),
    )


def _mini_podium(state, podium):
    """Три фото призёров внахлёст: P1 впереди."""
    size = 34
    avatars = []
    for i, row in enumerate(podium):
        d = state.driver(row["driver_id"])
        avatars.append(ft.Container(
            DriverAvatar(d["code"] if d else row["driver_id"][:3], row.get("team"), size=size,
                         src=state.photo(d) if d else None),
            left=i * (size - 12)))
    return ft.Stack(list(reversed(avatars)), width=size + 2 * (size - 12), height=size)


def _build_race_card(state, race, podium, past=False):
    """Компактная карточка этапа: номер, флаг, название; у прошедших — подиум"""
    sprint = any(s["key"] == "Sprint" for s in race["sessions"])
    where = f"{race['locality']}, {race['country']}" + (" · спринт" if sprint else "")
    flag_src, iso = state.flag(country=race["country"])
    if podium:
        winner = state.driver(podium[0]["driver_id"])
        right = _mini_podium(state, podium)
        where = f"Победа: {short_name(winner['name']) if winner else podium[0]['driver_id']}"
    elif past:
        right = ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=SUCCESS, size=22)
    else:
        right = ft.Text(fmt_date(race["start_ts"]), size=FONT_BODY_SMALL, color=TEXT_SECONDARY,
                        weight=ft.FontWeight.W_600)

    return AnimatedCard(
        content=ft.Row([
            ft.Container(
                content=ft.Text(race["round"], size=FONT_BODY, color=TEXT_MUTED if past else TEXT_PRIMARY,
                                font_family=FONT_DISPLAY_ITALIC),
                width=34, height=34, bgcolor=SURFACE_RAISED, border_radius=RADIUS_SM,
                alignment=ft.Alignment.CENTER,
            ),
            flag(flag_src, 18, iso),
            ft.Column([
                ft.Text(race["race_name"], size=FONT_BODY, weight=ft.FontWeight.W_600,
                        color=TEXT_SECONDARY if past else TEXT_PRIMARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(where, size=FONT_CAPTION, color=TEXT_DIM, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=2, expand=True),
            right,
        ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        on_click=lambda e, r=race, p=podium: _show_race_details(state, r, p),
        padding=ft.Padding.symmetric(horizontal=SPACE_SM, vertical=SPACE_SM),
    )


def session_list(race, highlight="Race"):
    """Расписание уик-энда в местном времени пользователя."""
    rows = []
    for s in race["sessions"]:
        main = s["key"] == highlight
        rows.append(ft.Row([
            ft.Text(SESSION_NAMES.get(s["key"], s["key"]), size=FONT_BODY_SMALL,
                    color=TEXT_PRIMARY if main else TEXT_MUTED,
                    weight=ft.FontWeight.BOLD if main else None, expand=True),
            ft.Text(fmt_day(s["ts"]), size=FONT_BODY_SMALL, color=TEXT_MUTED),
            ft.Container(
                ft.Text(fmt_clock(s["ts"]), size=FONT_BODY, color=ACCENT_TEXT if main else TEXT_PRIMARY,
                        font_family=FONT_HEADING),
                width=scaled(48), alignment=ft.Alignment.CENTER_RIGHT,
            ),
        ], spacing=SPACE_XS))
    return ft.Column(rows, spacing=6)


def _open_driver_from_dialog(state, driver_id):
    state.page.pop_dialog()
    state.open_driver(driver_id)


def _show_race_details(state, race, podium):
    """Окно этапа: трасса, подиум с фото, расписание"""
    info = track_info(race)
    flag_src, iso = state.flag(country=race["country"])
    lines = [
        ft.Row([flag(flag_src, 16, iso),
                ft.Text(f"{race['circuit']} · {race['locality']}, {race['country']}", size=FONT_BODY_SMALL,
                        color=TEXT_SECONDARY, expand=True)], spacing=SPACE_XS),
        ft.Text(fmt_date_full(race["start_ts"]), size=FONT_BODY_SMALL, color=TEXT_MUTED),
    ]
    if info:
        lines.append(ft.Text(f"Круг {info[0]} · {info[1]} кругов", size=FONT_BODY_SMALL, color=TEXT_MUTED))
    if podium:
        lines += [ft.Container(height=SPACE_XS),
                  ft.Text("Подиум", size=FONT_CAPTION, color=TEXT_MUTED, font_family=FONT_ITALIC)]
        for i, row in enumerate(podium, start=1):
            d = state.driver(row["driver_id"])
            lines.append(ft.Container(
                ft.Row([
                    PositionBadge(i, size=28),
                    DriverAvatar(d["code"] if d else "", row.get("team"), size=36, src=state.photo(d) if d else None),
                    ft.Column([ft.Text(d["name"] if d else row["driver_id"], size=FONT_BODY_SMALL,
                                       color=TEXT_PRIMARY, weight=ft.FontWeight.W_600),
                               ft.Text(row.get("team", ""), size=FONT_CAPTION, color=TEXT_MUTED)],
                              spacing=0, expand=True),
                    ft.Text(f"+{row['points']}", size=FONT_BODY, color=TEXT_PRIMARY, font_family=FONT_DISPLAY_ITALIC),
                ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ink=True, border_radius=RADIUS_SM, padding=ft.Padding.symmetric(horizontal=4, vertical=6),   # 48 dp
                on_click=(lambda e, i=row["driver_id"]: _open_driver_from_dialog(state, i)) if d else None,
            ))
    lines += [ft.Container(height=SPACE_XS), session_list(race), ft.Container(height=SPACE_XS)]
    if podium:
        lines.append(_strategy_button(state, race))
    lines.append(_circuit_button(state, race, close_dialog=True))

    dialog = ft.AlertDialog(
        title=ft.Text(f"{race['round']}. {race['race_name']}", size=FONT_H4, color=TEXT_PRIMARY,
                      font_family=FONT_HEADING),
        content=ft.Column(lines, spacing=SPACE_XXS, tight=True, width=380, scroll=ft.ScrollMode.AUTO),
        actions=[ft.TextButton("Закрыть", on_click=lambda e: state.page.pop_dialog())],
        bgcolor=SURFACE,
    )
    state.page.show_dialog(dialog)


def _strategy_button(state, race):
    def go(e):
        state.page.pop_dialog()
        state.open_race_strategy(race)

    return ft.Container(
        ft.Row([ft.Icon(ft.Icons.TIRE_REPAIR_ROUNDED, color=ACCENT_TEXT, size=18),
                ft.Text("Разбор гонки: шины, позиции, темп", size=FONT_BODY_SMALL, color=TEXT_PRIMARY,
                        weight=ft.FontWeight.W_600),
                ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=TEXT_DIM, size=18)], spacing=SPACE_XS, tight=True),
        height=TOUCH, padding=ft.Padding.symmetric(horizontal=SPACE_SM), border_radius=RADIUS_MD,
        bgcolor=SURFACE_RAISED, ink=True, on_click=go, alignment=ft.Alignment.CENTER_LEFT,
    )


def _circuit_button(state, race, close_dialog=False):
    def go(e):
        if close_dialog:
            state.page.pop_dialog()
        state.open_circuit(race)

    return ft.Container(
        ft.Row([ft.Icon(ft.Icons.ROUTE_ROUNDED, color=ACCENT_TEXT, size=18),
                ft.Text("Трасса и история", size=FONT_BODY_SMALL, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600),
                ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=TEXT_DIM, size=18)], spacing=SPACE_XS, tight=True),
        height=TOUCH, padding=ft.Padding.symmetric(horizontal=SPACE_SM), border_radius=RADIUS_MD,
        bgcolor=SURFACE_RAISED, ink=True, on_click=go, alignment=ft.Alignment.CENTER_LEFT,
    )


def _chip(label, bg, fg):
    return ft.Container(
        content=ft.Text(label, size=FONT_CAPTION, weight=ft.FontWeight.BOLD, color=fg),
        bgcolor=bg, border_radius=RADIUS_SM,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def _spec(label, value, icon):
    return ft.Column([
        ft.Icon(icon, color=ACCENT_TEXT, size=18),
        ft.Text(value, size=FONT_BODY, color=TEXT_PRIMARY, font_family=FONT_HEADING),
        ft.Text(label, size=FONT_CAPTION, color=TEXT_MUTED),
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)
