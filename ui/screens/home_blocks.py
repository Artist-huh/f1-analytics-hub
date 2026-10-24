"""Главная из блоков: пользователь сам выбирает и переставляет их (экран «Настроить главную»).

Live Timing и быстрый доступ закреплены наверху — они всегда под рукой. Остальное — блоки из BLOCKS;
порядок и видимость хранятся в настройке home_blocks (JSON). Новые блоки из обновлений добавляются в конец.
"""
import json
import time

import flet as ft

from design_system import *
from services import archive, f1live, live
from services import f1_api as api
from services import predictions as pr
from ui.components import *

# ключ -> (название, иконка, цвет раздела)
BLOCKS = {
    "next_race": ("Ближайшая гонка", ft.Icons.FLAG_ROUNDED, "race"),
    "podium": ("Подиум последней гонки", ft.Icons.EMOJI_EVENTS_ROUNDED, "title"),
    "season": ("Сезон в цифрах", ft.Icons.INSIGHTS_ROUNDED, "strategy"),
    "title": ("Борьба за титул", ft.Icons.MILITARY_TECH_ROUNDED, "title"),
    "drivers": ("Лидеры: пилоты", ft.Icons.PERSON_ROUNDED, "compare"),
    "teams": ("Лидеры: команды", ft.Icons.GROUPS_ROUNDED, "history"),
    "favorites": ("Избранные пилоты", ft.Icons.STAR_ROUNDED, "favorites"),
    "predict": ("Прогнозы", ft.Icons.SPORTS_SCORE, "predict"),
    "radio": ("Радио команд", ft.Icons.RADIO_ROUNDED, "live"),
    "weather": ("Погода на трассе", ft.Icons.WB_SUNNY_ROUNDED, "mini"),
}
WEATHER_KEY = "weather_now"
WEATHER_TTL = 15 * 60


def layout():
    """[(ключ, включён)] в порядке пользователя; неизвестные ключи отбрасываются, новые — в конец."""
    try:
        saved = json.loads(api.get_setting("home_blocks", "[]"))
    except (TypeError, ValueError):
        saved = []
    out, seen = [], set()
    for item in saved if isinstance(saved, list) else []:
        key = item.get("key") if isinstance(item, dict) else None
        if key in BLOCKS and key not in seen:
            out.append((key, bool(item.get("on", True))))
            seen.add(key)
    out += [(k, True) for k in BLOCKS if k not in seen]
    return out


def save_layout(items):
    api.set_setting("home_blocks", json.dumps([{"key": k, "on": on} for k, on in items]))


# ---------------------------------------------------------------- новые блоки
def predict_block(state):
    """Прогноз на ближайший этап: сделан или нет, и очки сезона."""
    from ui.screens.predict import actual_podiums, actual_poles, next_open_race
    season = state.schedule[0].get("season", "") if state.schedule else ""
    if not season or not state.standings:
        return None
    picks = pr.load_season(season)
    stats = pr.season_stats(picks, actual_podiums(state), actual_poles(state))
    race = next_open_race(state)
    pick = picks.get(race["round"], {}) if race else {}
    if race and all(pick.get(k) for k in pr.PICKS):
        codes = [(state.driver(pick[k]) or {}).get("code", "?") for k in ("p1", "p2", "p3")]
        line = f"{race['race_name']}: подиум {' · '.join(codes)}"
    elif race:
        line = f"{race['race_name']}: прогноз ещё не сделан — угадай поул и подиум"
    else:
        line = "Сезон завершён"
    return _block_card("predict", ft.Column([
        ft.Text(line, size=FONT_BODY_SMALL, color=TEXT_PRIMARY),
        ft.Text(f"Сезон: {stats['points']} очк. за {stats['rounds']} этап(ов)", size=FONT_CAPTION, color=TEXT_MUTED),
    ], spacing=2), lambda e: state.open_sub("predict"))


def radio_block(state):
    """Три свежие записи: из текущей сессии, иначе — из последней гонки (если уже загружены)."""
    from services import radio
    data = live.snapshot()[0]
    items, drivers, open_ = [], {}, None
    if data and data.get("live") and data.get("radio"):
        items, drivers = list(reversed(data["radio"]))[:3], data.get("drivers") or {}
        open_ = lambda e: (state.ui.__setitem__("live_view", "radio"), state.open_sub("live"))
    else:
        last, _ = state.last_race()
        cached = archive.get(radio.radio_key(last), lambda: None) if last else None
        if cached:
            items, drivers = list(reversed(cached["messages"]))[:3], cached.get("drivers") or {}
            open_ = lambda e: (state.ui.__setitem__("race_view", "radio"), state.open_race_strategy(last))
    if not items:
        return _block_card("radio", ft.Text("Записи появятся во время сессии или после открытия разбора гонки.",
                                            size=FONT_BODY_SMALL, color=TEXT_MUTED),
                           lambda e: state.open_sub("live"))
    lines = []
    for m in items:
        info = drivers.get(m["driver"], {})
        text = radio.cached(m["url"]) if radio.supported() else None
        lines.append(ft.Row([
            ft.Container(width=3, height=18, bgcolor=f"#{info['colour']}" if info.get("colour") else TEXT_DIM,
                         border_radius=2),
            ft.Text(info.get("code") or m["driver"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY,
                    font_family=FONT_ITALIC, width=40),
            ft.Text((text or {}).get("ru") or "запись без перевода — открой, чтобы послушать", size=FONT_CAPTION,
                    color=TEXT_SECONDARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
        ], spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER))
    return _block_card("radio", ft.Column(lines, spacing=6), open_)


def fetch_weather():
    state = f1live.fetch_state(["WeatherData", "SessionInfo"])
    info = state.get("SessionInfo") or {}
    return {"weather": f1live.weather(state.get("WeatherData")), "place": (info.get("Meeting") or {}).get("Location"),
            "session": info.get("Name"), "at": time.time()}


def weather_block(state):
    """Погода на трассе текущего уик-энда (поток F1, кэш 15 минут)."""
    from ui.screens.live import weather_strip
    data = archive.get(WEATHER_KEY, fetch_weather, WEATHER_TTL, state.render)
    if not data or not data.get("weather"):
        if archive.loading(WEATHER_KEY):
            return skeleton("Погода на трассе…", "rows", 1)
        return None
    return _block_card("weather", ft.Column([
        ft.Text(f"{data.get('place') or 'Трасса'} · {data.get('session') or ''}".strip(" ·"), size=FONT_CAPTION,
                color=TEXT_MUTED),
        weather_strip(data["weather"]),
    ], spacing=SPACE_XS), lambda e: state.open_sub("live"))


def _block_card(key, body, on_click):
    title, icon, section = BLOCKS[key]
    return AnimatedCard(ft.Column([
        ft.Row([icon_badge(icon, SECTION_COLORS[section], size=28),
                ft.Text(title, size=FONT_BODY, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600, expand=True),
                ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=TEXT_DIM, size=18)],
               spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        body,
    ], spacing=SPACE_XS), on_click=on_click, size="m")


# ---------------------------------------------------------------- экран «Настроить главную»
def build_editor(state):
    from ui.widgets import screen
    items = layout()

    def store(new_items):
        save_layout(new_items)
        state.render()

    def toggle(key, on):
        store([(k, on if k == key else v) for k, v in items])

    def move(i, delta):
        j = i + delta
        if 0 <= j < len(items):
            new = list(items)
            new[i], new[j] = new[j], new[i]
            store(new)

    def reorder(e):
        new = list(items)
        new.insert(e.new_index, new.pop(e.old_index))
        store(new)

    rows = []
    for i, (key, on) in enumerate(items):
        title, icon, section = BLOCKS[key]
        rows.append(ft.Container(ft.Row([
            ft.Icon(ft.Icons.DRAG_INDICATOR_ROUNDED, color=TEXT_DIM, size=20),
            icon_badge(icon, SECTION_COLORS[section], size=32),
            ft.Text(title, size=FONT_BODY, color=TEXT_PRIMARY if on else TEXT_MUTED, expand=True),
            ft.IconButton(ft.Icons.ARROW_UPWARD_ROUNDED, icon_size=18, tooltip=f"{title}: выше",
                          on_click=lambda e, i=i: move(i, -1), disabled=i == 0),
            ft.IconButton(ft.Icons.ARROW_DOWNWARD_ROUNDED, icon_size=18, tooltip=f"{title}: ниже",
                          on_click=lambda e, i=i: move(i, 1), disabled=i == len(items) - 1),
            ft.Switch(value=on, active_color=F1_RED, tooltip=f"{title}: показывать",
                      on_change=lambda e, k=key: toggle(k, bool(e.control.value))),
        ], spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            key=key, bgcolor=SURFACE, border_radius=CARD_SIZES["s"][1], border=ft.Border.all(1, LINE_SUBTLE),
            padding=ft.Padding.symmetric(horizontal=SPACE_XS, vertical=2)))
    body = [
        ft.Text("Перетащи блок за ручку или стрелками; переключатель — показывать ли его. Live Timing и быстрый "
                "доступ всегда наверху.", size=FONT_BODY_SMALL, color=TEXT_SECONDARY),
        ft.ReorderableListView(rows, on_reorder=reorder, spacing=SPACE_XS, show_default_drag_handles=True),
        ft.TextButton("Вернуть как было", icon=ft.Icons.RESTART_ALT_ROUNDED,
                      on_click=lambda e: store([(k, True) for k in BLOCKS])),
    ]
    return screen(state, "Главная под себя", body, back=True)
