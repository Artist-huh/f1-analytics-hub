"""Раздел «Ещё»: меню, дуэль пилотов, стратегия, настройки."""
import flet as ft

from services import db, f1_api as api, log
from theme import ACCENT, ROSSO, GIALLO, RAISED, SURFACE, TEXT, MUTED, DIM, OK, WARN, team_color
from ui.fmt import fmt_updated
from ui.widgets import button, card, dropdown, empty_state, screen, team_bar, tyre_chip, txt


# ---------------------------------------------------------------- меню
def _tile(icon, title, hint, on_click):
    return card(ft.Row(
        [ft.Container(ft.Icon(icon, color=ACCENT, size=22), bgcolor=RAISED, border_radius=20, width=40, height=40,
                      alignment=ft.Alignment.CENTER),
         ft.Column([txt(title, 16, bold=True), txt(hint, 12, MUTED)], expand=True, spacing=1),
         ft.Icon(ft.Icons.CHEVRON_RIGHT, color=DIM)],
        vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
        on_click=on_click, padding=12, ink=True)


def build_menu(state):
    body = [
        _tile(ft.Icons.STAR_ROUNDED, "Избранное", "Мои пилоты и их результаты",
              lambda e: state.open_sub("favorites")),
        _tile(ft.Icons.COMPARE_ARROWS, "Сравнение", "Любые два пилота: очки, победы, личные встречи",
              lambda e: state.open_sub("compare")),
        _tile(ft.Icons.SPORTS_MOTORSPORTS, "Дуэль с Леклером", "Леклер против любого пилота",
              lambda e: state.open_sub("duel")),
        _tile(ft.Icons.TIMELINE, "Стратегия", "Какие шины и сколько остановок на трассе",
              lambda e: state.open_sub("strategy")),
        _tile(ft.Icons.SETTINGS, "Настройки", "Обновление данных и локальная база",
              lambda e: state.open_sub("settings")),
    ]
    return screen(state, "Ещё", body)


# ---------------------------------------------------------------- дуэль
def _metric(title, left, right, left_color, right_color, lower_better=False, bar=False):
    try:
        lv, rv = float(left), float(right)
        better_left = lv < rv if lower_better else lv > rv
        better_right = rv < lv if lower_better else rv > lv
    except (TypeError, ValueError):
        lv = rv = 0.0
        better_left = better_right = False
    items = [
        txt(title, 12, MUTED, text_align=ft.TextAlign.CENTER),
        ft.Row([txt(left, 34, GIALLO if better_left else TEXT, bold=True, head=True, expand=True,
                    text_align=ft.TextAlign.CENTER),
                txt(right, 34, GIALLO if better_right else TEXT, bold=True, head=True, expand=True,
                    text_align=ft.TextAlign.CENTER)]),
    ]
    if bar and lv + rv > 0:
        items.append(ft.Row([
            ft.Container(expand=int(lv * 10) or None, height=5, bgcolor=left_color, border_radius=3),
            ft.Container(expand=int(rv * 10) or None, height=5, bgcolor=right_color, border_radius=3),
        ], spacing=2))
    return card(ft.Column(items, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2))


def build_duel(state):
    lec = state.leclerc
    opponents = [d for d in state.standings if d["driver_id"] != api.LECLERC_ID]
    if not lec or not opponents:
        return screen(state, "Дуэль", [empty_state(state, "Не с кем сравнивать",
                                                   "Нужна таблица чемпионата — нажми «Обновить».")], back=True)
    # избранные — первыми, напарник по умолчанию
    opponents.sort(key=lambda d: d["driver_id"] not in state.favorites)
    mate = next((d for d in opponents if d["team"] == lec["team"]), opponents[0])
    chosen = state.ui.get("duel_opp", mate["driver_id"])
    opp = next((d for d in opponents if d["driver_id"] == chosen), mate)

    def on_select(e):
        state.ui["duel_opp"] = next((d["driver_id"] for d in opponents if d["name"] == e.control.value), mate["driver_id"])
        state.render()

    lc, oc = team_color(lec["team"]), team_color(opp["team"])
    head = ft.Row([
        ft.Row([team_bar(lc, 44), ft.Column([txt(lec["name"].split()[-1], 26, bold=True, head=True),
                                             txt(lec["team"], 11, MUTED)], spacing=0)], expand=True, spacing=8),
        ft.Row([ft.Column([txt(opp["name"].split()[-1], 26, bold=True, head=True),
                           txt(opp["team"], 11, MUTED)], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
                team_bar(oc, 44)], expand=True, spacing=8, alignment=ft.MainAxisAlignment.END),
    ])
    gap = float(opp["points"]) - float(lec["points"])
    verdict = ("Очки равны" if gap == 0 else
               f"Леклер впереди на {abs(gap):g}" if gap < 0 else f"{opp['name'].split()[-1]} впереди на {gap:g}")
    body = [
        dropdown(label="Соперник", value=opp["name"],
                    options=[ft.DropdownOption(key=d["name"], text=("★ " if d["driver_id"] in state.favorites else "") + d["name"])
                             for d in opponents],
                    on_select=on_select),
        head,
        txt(verdict, 13, MUTED, text_align=ft.TextAlign.CENTER),
        _metric("Позиция в зачёте", lec["position"], opp["position"], lc, oc, lower_better=True),
        _metric("Очки", lec["points"], opp["points"], lc, oc, bar=True),
        _metric("Победы", lec["wins"], opp["wins"], lc, oc),
    ]
    return screen(state, "Дуэль", body, subtitle=f"Сезон {state.season}", back=True)


# ---------------------------------------------------------------- стратегия
# Базовые прикидки приложения (не официальные планы команды): круги, износ, обгоны, шины по порядку.
TRACKS = {
    "Monaco":      {"laps": 78, "wear": "низкий",  "overtake": "очень сложно", "stints": ["S", "H"],
                    "note": "На узкой трассе позиция важнее скорости. Один стоп — меньше риска потерять место."},
    "Monza":       {"laps": 53, "wear": "средний", "overtake": "легко",        "stints": ["M", "H"],
                    "note": "Храм скорости. Классический один стоп."},
    "Silverstone": {"laps": 52, "wear": "высокий", "overtake": "средне",       "stints": ["S", "M", "H"],
                    "note": "Быстрые повороты изнашивают резину. Два стопа дают свежие шины."},
    "Spa":         {"laps": 44, "wear": "средний", "overtake": "легко",        "stints": ["M", "H"],
                    "note": "Длинный круг, один стоп. Погода может изменить всё."},
    "Hungaroring": {"laps": 70, "wear": "средний", "overtake": "сложно",       "stints": ["S", "M", "S"],
                    "note": "Узко, как в Монако. Свежие мягкие в конце — для атаки."},
    "Suzuka":      {"laps": 53, "wear": "высокий", "overtake": "средне",       "stints": ["M", "H", "S"],
                    "note": "Техничная трасса: баланс скорости и износа."},
    "Baku":        {"laps": 51, "wear": "низкий",  "overtake": "с DRS",        "stints": ["S", "H"],
                    "note": "Длинная прямая и Safety Car часто решают гонку."},
    "Singapore":   {"laps": 62, "wear": "высокий", "overtake": "сложно",       "stints": ["S", "M", "S"],
                    "note": "Ночная уличная трасса: сильный износ, два стопа."},
}
_NEEDLES = {"monaco": "Monaco", "monza": "Monza", "silverstone": "Silverstone", "spa": "Spa",
            "hungaro": "Hungaroring", "suzuka": "Suzuka", "baku": "Baku", "marina bay": "Singapore",
            "singapore": "Singapore"}


def _guess_track(race):
    if race:
        text = f"{race['circuit']} {race['race_name']} {race['locality']}".lower()
        for needle, name in _NEEDLES.items():
            if needle in text:
                return name
    return None


def build_strategy(state):
    chosen = state.ui.get("track") or _guess_track(state.next_race()) or "Monaco"

    def on_select(e):
        if e.control.value:
            state.ui["track"] = e.control.value
            state.render()

    t = TRACKS[chosen]
    stops = len(t["stints"]) - 1
    chips = []
    for i, letter in enumerate(t["stints"]):
        if i:
            chips.append(ft.Icon(ft.Icons.CHEVRON_RIGHT, color=DIM, size=18))
        chips.append(tyre_chip(letter))
    body = [
        dropdown(label="Трасса", value=chosen, options=[ft.DropdownOption(key=n, text=n) for n in TRACKS],
                 on_select=on_select),
        card(ft.Column([
            txt(chosen, 26, bold=True, head=True),
            txt(f"{t['laps']} кругов · износ {t['wear']} · обгоны: {t['overtake']}", 12, MUTED),
            ft.Container(height=6),
            ft.Row(chips, spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            txt(f"{stops} {'пит-стоп' if stops == 1 else 'пит-стопа'}", 16, bold=True),
            txt(t["note"], 13, MUTED),
            ft.Container(height=4),
            ft.Row([tyre_chip("S"), txt("мягкие", 12, MUTED), tyre_chip("M"), txt("средние", 12, MUTED),
                    tyre_chip("H"), txt("жёсткие", 12, MUTED)], spacing=6, wrap=True),
        ], spacing=3), radius=16, padding=16),
        txt("Это базовые прикидки приложения, а не официальные планы Ferrari.", 11, DIM),
    ]
    return screen(state, "Стратегия", body, subtitle="План пит-стопов по трассам", back=True)


# ---------------------------------------------------------------- настройки
INTERVALS = {"5": "каждые 5 минут", "10": "каждые 10 минут", "30": "каждые 30 минут"}
STATE_TEXT = {"live": "данные свежие", "cached": "показаны сохранённые данные", "empty": "данных нет"}


def _line(label, value, color=TEXT):
    return ft.Row([txt(label, 13, MUTED, expand=True), txt(value, 13, color, text_align=ft.TextAlign.RIGHT)],
                  vertical_alignment=ft.CrossAxisAlignment.START)


def build_settings(state):
    minutes = str(state.refresh_minutes())
    if minutes not in INTERVALS:
        minutes = "5"

    def on_interval(e):
        api.set_setting("refresh_minutes", e.control.value)
        state.start_refresher()
        state.render()

    st = state.status
    color = {"live": OK, "cached": WARN}.get(st["state"], ROSSO)
    info = [_line("Состояние", STATE_TEXT.get(st["state"], "—"), color),
            _line("Обновлено", fmt_updated(st["updated_at"])),
            _line("Источник", "Jolpica F1 API"),
            _line("Размер базы", f"{db.db_size_kb()} КБ")]
    if st["error"]:
        info.append(_line("Последняя ошибка", str(st["error"])[:90], WARN))

    body = [
        card(ft.Column([
            txt("Обновление данных", 16, bold=True, head=True),
            dropdown(label="Автообновление", value=minutes,
                     options=[ft.DropdownOption(key=k, text=v) for k, v in INTERVALS.items()],
                     on_select=on_interval),
            button("Обновить сейчас", lambda e: state.refresh_now(), icon=ft.Icons.REFRESH),
            txt("Лимит Jolpica — около 200 запросов в час; при таких интервалах приложение укладывается с запасом.", 11, DIM),
        ], spacing=10)),
        card(ft.Column([txt("Состояние данных", 16, bold=True, head=True)] + info, spacing=8)),
        card(ft.Column([
            txt("Локальная база", 16, bold=True, head=True),
            txt(f"База: {db.db_path()}", 11, DIM),
            txt(f"Журнал: {log.log_path() or 'отключён'}", 11, DIM),
            button("Очистить сохранённые данные", lambda e: _confirm_clear(state), primary=False,
                   icon=ft.Icons.DELETE_OUTLINE),
            txt("Избранные пилоты и настройки останутся. Данные загрузятся заново.", 11, DIM),
        ], spacing=10)),
    ]
    return screen(state, "Настройки", body, back=True)


def _confirm_clear(state):
    """Очистка необратима — сначала спрашиваем."""
    page = state.page

    def confirm(e):
        page.pop_dialog()
        state.clear_cache()

    page.show_dialog(ft.AlertDialog(
        modal=True,
        title=txt("Очистить сохранённые данные?", 18, bold=True),
        content=txt("Таблицы, календарь и результаты будут удалены и загрузятся заново из сети. "
                    "Без интернета приложение останется без данных. Избранное и настройки сохранятся.", 13, MUTED),
        actions=[ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog()),
                 ft.TextButton("Очистить", on_click=confirm, style=ft.ButtonStyle(color=ROSSO))],
        bgcolor=SURFACE,
    ))
