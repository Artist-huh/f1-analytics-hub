"""Главный экран: ближайшая гонка, подиум последней гонки, лидеры чемпионата, быстрый доступ"""
import contextlib
import math
import time

import flet as ft

from design_system import *
from services import f1_api as api
from services import live
from ui.components import *
from ui.fmt import SESSION_NAMES, fmt_clock, fmt_countdown, fmt_day, plural, short_name
from ui.rows import driver_row, team_row, tower
from ui.screens import home_blocks as hb
from ui.widgets import empty_state, screen


def render(state):
    """Отрисовка главного экрана"""
    is_mobile = ResponsiveContainer.is_mobile(page_width(state))
    standings = state.standings

    # Live Timing и быстрый доступ — первыми и закреплены: самые частые действия всегда под рукой.
    # Остальное — блоки в порядке пользователя (home_blocks, экран «Настроить главную»).
    sections = [_build_live_card(state), _build_quick_actions(state)]
    if not standings:
        race = state.next_race()
        if race:
            sections.append(_build_next_race_hero(race, state, is_mobile))
        sections.append(empty_state(state, "Данных пока нет",
                                    "Подключись к интернету и нажми «Обновить» — таблицы сохранятся "
                                    "и будут доступны без сети."))
    else:
        for key, on in hb.layout():
            if on:
                block = _block(state, key, is_mobile)
                if block is not None:
                    sections.append(block)
        sections.append(ft.Row([ft.TextButton("Настроить главную", icon=ft.Icons.TUNE_ROUNDED,
                                              on_click=lambda e: state.open_sub("home_edit"))],
                               alignment=ft.MainAxisAlignment.CENTER))

    subtitle = f"Сезон {state.season}" if state.season else None
    return screen(state, "F1 Hub", sections, subtitle=subtitle)


def _block(state, key, is_mobile):
    """Один блок главной по ключу (None — показывать нечего)."""
    if key == "next_race":
        race = state.next_race()
        return _build_next_race_hero(race, state, is_mobile) if race else None
    if key == "podium":
        last, podium = state.last_race()
        return _build_last_podium(state, last, podium, is_narrow(state)) if podium else None
    if key == "season":
        return _build_season_stats(state, is_narrow(state))
    if key == "title":
        return _build_title_fight(state)
    if key == "drivers":
        return _build_top_drivers(state, state.standings[:5])
    if key == "teams":
        return _build_top_constructors(state, state.constructors[:5]) if state.constructors else None
    if key == "favorites":
        favs = [d for d in state.standings if d["driver_id"] in state.favorites]
        return _build_favorites_strip(state, favs) if favs else None
    if key == "predict":
        return hb.predict_block(state)
    if key == "radio":
        return hb.radio_block(state)
    if key == "weather":
        return hb.weather_block(state)
    return None


# ========================================
# СЕКЦИИ
# ========================================

LIGHTS = 5                 # стартовые огни: загораются по одному за каждый день до гонки


def lights_lit(seconds_left, live):
    """Сколько огней горит: 5 — гонка в ближайшие сутки, 0 — больше пяти дней или гонка уже идёт (огни погасли)."""
    if live:
        return 0
    return max(0, min(LIGHTS, LIGHTS + 1 - math.ceil(max(seconds_left, 0) / 86400)))


def start_lights(state, lit):
    """Пять стартовых огней F1: корпус и по два стекла. При первом показе экрана загораются по очереди."""
    lamps = []
    units = []
    for _unit in range(LIGHTS):
        pair = [ft.Container(width=14, height=14, border_radius=7, bgcolor=LIGHT_OFF, animate=anim(ANIM_FAST))
                for _ in range(2)]
        lamps.append(pair)
        units.append(ft.Container(ft.Column(pair, spacing=4, tight=True), bgcolor=LIGHT_HOUSING,
                                  border_radius=RADIUS_SM, padding=ft.Padding.symmetric(horizontal=5, vertical=6)))

    def light(i):
        for lamp in lamps[i]:
            lamp.bgcolor = LIGHT_ON
            lamp.shadow = glow(LIGHT_ON, 0.7)

    run_task = getattr(state.page, "run_task", None)
    if lit and state.fresh and motion_on() and run_task:
        async def sequence():
            import asyncio
            for i in range(lit):
                await asyncio.sleep(0.35)
                light(i)
                with contextlib.suppress(RuntimeError, AssertionError, AttributeError):   # экран уже сменился
                    row.update()
        run_task(sequence)
    else:
        for i in range(lit):
            light(i)
    tip = (f"Огни загораются по одному за каждый день до гонки: горит {lit} из {LIGHTS}" if lit else
           "Огни загорятся за пять дней до гонки, по одному в день")
    row = ft.Row(units, spacing=6, tight=True, tooltip=tip)
    return row


def _hero_outline(state, race):
    """Контур трассы ближайшей гонки (кэш навсегда) или None, пока не загружен."""
    from services import archive, track_map
    year = int(state.season or time.strftime("%Y"))
    meetings = archive.get(track_map.meetings_key(year), lambda: track_map.fetch_meetings(year), 7 * 86400,
                           state.render)
    key = track_map.circuit_for(meetings, race["start_ts"])
    if not key:
        return None
    return archive.get(track_map.outline_key(key), lambda: track_map.fetch_outline(key, year), None, state.render)


def _build_next_race_hero(race, state, is_mobile):
    """Hero «стартовая решётка»: карбон, контур трассы, обратный отсчёт и пять стартовых огней."""
    from ui.screens.live_track import outline_canvas
    live = race["state"] == "live"
    countdown = ft.Text(
        "LIVE" if live else fmt_countdown(race["seconds_left"]),
        size=FONT_H1 if is_mobile else FONT_DISPLAY,
        color=LIGHT_ON if live else ON_COLOR,
        font_family=FONT_DISPLAY_ITALIC,
    )
    if not live:
        state.countdown = (countdown, race["round"])  # main.ticker обновляет этот текст на месте
    flag_src, iso = state.flag(country=race["country"])
    soft = ft.Colors.with_opacity(0.72, ON_COLOR)
    total = len(state.schedule)
    stage = "Гонка идёт" if live else f"Этап {race['round']} из {total}" if total else f"Этап {race['round']}"
    if any(s["key"] == "Sprint" for s in race["sessions"]):
        stage += ", спринт"

    timer = ft.Column([
        countdown,
        ft.Text("Огни погасли — гонка в эфире" if live else
                f"Старт {fmt_day(race['start_ts'])} в {fmt_clock(race['start_ts'])}",
                size=FONT_BODY_SMALL, color=soft),
    ], spacing=0)
    lights = start_lights(state, lights_lit(race["seconds_left"], live))

    button = ft.Container(
        ft.Row([ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, color=F1_RED, size=18),
                ft.Text("Расписание", color=INK, weight=ft.FontWeight.W_700)], spacing=SPACE_XS, tight=True),
        bgcolor=ON_COLOR, border_radius=RADIUS_FULL, height=TOUCH, alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(horizontal=SPACE_LG), ink=True,
        on_click=lambda e: state.open_tab(2),
    )
    head = [
        ft.Row([flag(flag_src, 18, iso), ft.Text(stage, size=FONT_BODY_SMALL, color=soft)],
               spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ft.Column([
            ft.Text(race["race_name"], size=FONT_H3, color=ON_COLOR, font_family=FONT_HEADING),
            ft.Text(race["circuit"], size=FONT_BODY_SMALL, color=soft, max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS),
        ], spacing=2),
    ]
    outline = _hero_outline(state, race)
    inner = content_width(state) - 2 * SPACE_LG

    def track_view(width, max_ratio):
        from services import track_map
        h = track_map.fitted_height(outline, width, pad=6, max_ratio=max_ratio)
        return ft.Container(outline_canvas(outline, width, h, ft.Colors.with_opacity(0.55, ON_COLOR), 3, LIGHT_ON),
                            alignment=ft.Alignment.CENTER, tooltip=f"Трасса: {race['circuit']}",
                            padding=ft.Padding.symmetric(vertical=SPACE_XS))

    if is_mobile:
        # телефон: трасса — своей строкой между названием и отсчётом
        bottom = ft.Column([ft.Row([timer, lights], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                   vertical_alignment=ft.CrossAxisAlignment.END, wrap=True, run_spacing=SPACE_SM),
                            button], spacing=SPACE_MD, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        track = [track_view(min(inner, 520), 0.4)] if outline else []
        body = ft.Column([*head, *track, bottom], spacing=SPACE_SM)
    else:
        # компьютер: трасса справа от текста — иначе на всю ширину она выталкивает отсчёт и кнопку за край окна
        left = ft.Column([*head, ft.Container(height=SPACE_MD), timer,
                          ft.Row([lights, button], spacing=SPACE_LG,
                                 vertical_alignment=ft.CrossAxisAlignment.CENTER)],
                         spacing=SPACE_SM, expand=True)
        body = ft.Row([left, track_view(round(inner * 0.45), 0.6)] if outline else [left],
                      spacing=SPACE_LG, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    return ft.Container(
        content=body,
        padding=SPACE_LG,
        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT, colors=HERO_CARBON),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ON_COLOR)),
        border_radius=RADIUS_LG,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        on_click=lambda e: state.open_tab(2),
        ink=True,
    )


def next_session(schedule, now=None):
    """Ближайшая будущая сессия: (этап, ключ, время) или None."""
    now = time.time() if now is None else now
    upcoming = [(s["ts"], race, s["key"]) for race in schedule for s in race["sessions"] if s["ts"] > now]
    if not upcoming:
        return None
    ts, race, key = min(upcoming, key=lambda x: x[0])
    return race, key, ts


def _build_live_card(state):
    """Live Timing — всегда наверху главной: во время сессии — красная карточка LIVE,
    в остальное время — что дальше и когда, плюс вход в итог последней сессии."""
    now_live = state.live_now()
    if now_live:
        race, key = now_live
        badge = ft.Container(ft.Row([ft.Container(width=8, height=8, border_radius=4, bgcolor=ON_COLOR),
                                     ft.Text("LIVE", size=FONT_CAPTION, color=ON_COLOR, font_family=FONT_ITALIC)],
                                    spacing=6, tight=True),
                             bgcolor=LIVE_RED, border_radius=RADIUS_FULL,      # белый — 4.97:1 в любой теме
                             padding=ft.Padding.symmetric(horizontal=10, vertical=4))
        title = f"Сейчас: {SESSION_NAMES.get(key, key)}"
        hint = f"{race['race_name']} · позиции, отрывы, шины, радио"
        state.watch_live()                                  # во время сессии — живая тройка прямо на главной
        data = live.snapshot()[0]
        if data and data["live"] and data["rows"]:
            top = " · ".join(f"{r['position']}. {r['code']}" for r in data["rows"][:3])
            when = (f"круг {data['lap']}" if data["racing"] and data.get("lap") else
                    f"осталось {data['remaining']}" if data.get("remaining") else "")
            hint = " · ".join(x for x in (top, when, data.get("track") or "") if x)
    else:
        # вне сессии — нейтральный значок: красный только когда идёт эфир
        badge = icon_badge(ft.Icons.SENSORS_ROUNDED, SECTION_COLORS["live"])
        upcoming = next_session(state.schedule)
        title = "Live Timing"
        hint = (f"{SESSION_NAMES.get(upcoming[1], upcoming[1])} через {fmt_countdown(upcoming[2] - time.time())}. "
                "Пока здесь итог прошлой сессии" if upcoming else "Итог прошлой сессии")
    return AnimatedCard(ft.Row([
        badge,
        ft.Column([ft.Text(title, size=FONT_BODY_LARGE, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600,
                           font_family=FONT_HEADING),
                   ft.Text(hint, size=FONT_CAPTION, color=TEXT_MUTED, max_lines=2,
                           overflow=ft.TextOverflow.ELLIPSIS)],
                  spacing=0, expand=True),
        ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=TEXT_DIM),
    ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        accent=DANGER if now_live else F1_RED, on_click=lambda e: state.open_sub("live"),
        tooltip="Live Timing: открыть", **({"border": ft.Border.all(1, DANGER)} if now_live else {}))


def _build_last_podium(state, race, podium, compact):
    """Подиум последней гонки: P2 — P1 — P3 с фото, как на церемонии."""
    heights = {1: 64, 2: 44, 3: 30}
    size = 56 if compact else 68

    def place(row, pos):
        driver = state.driver(row["driver_id"]) or {"code": row["driver_id"][:3].upper(), "team": row.get("team"),
                                                    "name": row["driver_id"], "season": state.season}
        color = POSITION_COLORS[pos]
        return ft.Column([
            DriverAvatar(driver.get("code"), driver.get("team"), size=size + (10 if pos == 1 else 0),
                         src=state.photo(driver), on_click=lambda e, i=row["driver_id"]: state.open_driver(i)),
            ft.Text(short_name(driver.get("name", "")), size=FONT_BODY_SMALL, color=TEXT_PRIMARY,
                    weight=ft.FontWeight.W_600, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Container(
                ft.Text(str(pos), size=FONT_H3, color=INK, font_family=FONT_DISPLAY_ITALIC),
                height=heights[pos], bgcolor=color, alignment=ft.Alignment.CENTER,
                border_radius=ft.BorderRadius.only(top_left=RADIUS_SM, top_right=RADIUS_SM),
                gradient=ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER,
                                           colors=[color, ft.Colors.with_opacity(0.55, color)]),
            ),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=SPACE_XXS, expand=True,
            alignment=ft.MainAxisAlignment.END)

    name = race.get("race_name", "") if race else ""
    flag_src, iso = state.flag(country=race.get("country")) if race else (None, "")
    return ft.Column([
        SectionHeader("Последняя гонка", subtitle=f"Этап {race['round']} · {name}" if race else None,
                      action_text="Разбор" if race and race.get("date") else "Календарь",
                      on_action=(lambda e: state.open_race_strategy(race)) if race and race.get("date")
                      else (lambda e: _open_calendar_past(state))),
        AnimatedCard(
            ft.Column([
                ft.Row([flag(flag_src, 16, iso), ft.Text(name, size=FONT_BODY_SMALL, color=TEXT_MUTED, expand=True,
                                                          max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)],
                       spacing=SPACE_XS),
                ft.Row([place(podium[1], 2), place(podium[0], 1), place(podium[2], 3)],
                       vertical_alignment=ft.CrossAxisAlignment.END, spacing=SPACE_XS),
            ], spacing=SPACE_SM),
            padding=ft.Padding.only(left=SPACE_MD, right=SPACE_MD, top=SPACE_SM),
        ),
    ], spacing=SPACE_SM)


def _build_season_stats(state, compact):
    """Статистика сезона"""
    schedule = state.schedule
    done = sum(1 for r in schedule if api.race_state(r) == "past")
    leader = state.standings[0]
    team_leader = state.constructors[0] if state.constructors else None

    cards = [
        StatCard("Гонок пройдено", f"{done}/{len(schedule)}" if schedule else "—", ft.Icons.FLAG_ROUNDED,
                 F1_RED, compact=compact),
        StatCard("Лидер пилотов", leader["name"].split()[-1], ft.Icons.PERSON_ROUNDED,
                 get_team_color(leader["team"]), subtitle=_points(leader["points"]), compact=compact),
    ]
    if team_leader:
        cards.append(StatCard("Лидер команд", team_leader["name"], ft.Icons.GROUPS_ROUNDED,
                              get_team_color(team_leader["name"]), subtitle=_points(team_leader["points"]),
                              compact=compact))
    return ft.Column([
        SectionHeader(f"Сезон {state.season}"),
        ft.Row(cards, spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.START),
    ], spacing=SPACE_SM)


def _build_title_fight(state):
    """Короткая сводка борьбы за титул -> экран прогноза."""
    race = state.title_race("drivers")
    contenders = race["contenders"]
    if race["clinched"]:
        title, hint = f"{short_name(state.standings[0]['name'])} — чемпион мира", "Титул оформлен досрочно"
    else:
        n = len(contenders)
        title = f"В борьбе {n} {plural(n, 'пилот', 'пилота', 'пилотов')}"
        hint = f"Разыгрывается ещё {race['available']} очков"
        if race["next_clinch"] is not None:
            hint += f" · {short_name(state.standings[0]['name'])} может стать чемпионом в ближайшей гонке"
    faces = [DriverAvatar(r["code"], r["team"], size=32, src=state.photo(r)) for r, *_ in contenders[:5]]
    return AnimatedCard(ft.Row([
        ft.Icon(ft.Icons.EMOJI_EVENTS_ROUNDED, color=GOLD, size=28),
        ft.Column([ft.Text(title, size=FONT_BODY, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600),
                   ft.Text(hint, size=FONT_CAPTION, color=TEXT_MUTED, max_lines=2)], spacing=1, expand=True),
        ft.Row(faces, spacing=-8, tight=True),
        ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=TEXT_DIM),
    ], spacing=SPACE_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        accent=GOLD, on_click=lambda e: state.open_sub("title"))


def _build_top_drivers(state, drivers):
    return ft.Column([
        SectionHeader("Чемпионат пилотов", subtitle="Топ-5", action_text="Все",
                      on_action=lambda e: _open_championship(state, "drivers")),
        tower([driver_row(state, d, flat=True) for d in drivers]),
    ], spacing=SPACE_SM)


def _build_top_constructors(state, constructors):
    leader = float(constructors[0]["points"]) or 1
    return ft.Column([
        SectionHeader("Кубок конструкторов", subtitle="Топ-5", action_text="Все",
                      on_action=lambda e: _open_championship(state, "teams")),
        ft.Column([team_row(state, c, leader) for c in constructors], spacing=SPACE_XS),
    ], spacing=SPACE_SM)


def _build_favorites_strip(state, favs):
    """Избранные пилоты — фото, код и очки"""
    chips = [
        ft.Container(
            content=ft.Column([
                DriverAvatar(d["code"], d["team"], size=52, src=state.photo(d)),
                ft.Text(d["code"] or short_name(d["name"]), size=FONT_BODY_SMALL, color=TEXT_PRIMARY,
                        font_family=FONT_ITALIC),
                ft.Text(f"{d['points']} очк.", size=FONT_CAPTION, color=TEXT_MUTED),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            padding=SPACE_XS, border_radius=RADIUS_MD, ink=True, width=84,
            on_click=lambda e, i=d["driver_id"]: state.open_driver(i),
        )
        for d in favs
    ]
    return ft.Column([
        SectionHeader("Избранные", action_text="Все", on_action=lambda e: state.open_sub("favorites")),
        ft.Row(chips, spacing=SPACE_XS, scroll=ft.ScrollMode.AUTO),
    ], spacing=SPACE_SM)


def _build_quick_actions(state):
    actions = [
        (ft.Icons.FLAG_ROUNDED, "Разбор", "race", lambda e: _open_last_race(state)),
        (ft.Icons.COMPARE_ARROWS_ROUNDED, "Сравнение", "compare", lambda e: state.open_sub("compare")),
        (ft.Icons.SPORTS_SCORE_ROUNDED, "Прогнозы", "predict", lambda e: state.open_sub("predict")),
        (ft.Icons.STAR_ROUNDED, "Избранное", "favorites", lambda e: state.open_sub("favorites")),
    ]
    cards = [
        AnimatedCard(
            content=ft.Column([
                icon_badge(icon, SECTION_COLORS[section]),
                ft.Text(label, size=FONT_CAPTION, color=TEXT_PRIMARY, max_lines=1),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=SPACE_XS),
            padding=ft.Padding.symmetric(horizontal=SPACE_XXS, vertical=SPACE_SM),
            on_click=handler,
            expand=True,
            accent=SECTION_COLORS[section],
        )
        for icon, label, section, handler in actions
    ]
    return ft.Row(cards, spacing=SPACE_XS)


# ========================================
# HELPERS
# ========================================

def _points(points):
    value = float(points)
    return f"{value:g} {plural(value, 'очко', 'очка', 'очков')}"


def _open_championship(state, view):
    state.ui["champ"] = view
    state.open_tab(1)


def _open_last_race(state):
    """«Разбор» — последняя прошедшая гонка (шины, позиции, темп, радио)."""
    last, _ = state.last_race()
    if last:
        state.open_race_strategy(last)
    else:
        _open_calendar_past(state)


def _open_calendar_past(state):
    state.ui["cal"] = "past"
    state.open_tab(2)
