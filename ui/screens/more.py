"""Раздел «Ещё»: меню, стратегия, настройки."""
import flet as ft

from design_system import (ACCENT, ACCENT_DEEP, ACCENT_GLOW, ACCENT_TEXT, DANGER, DIM, F1_RED, MUTED, OK, ON_ACCENT,
                           RAISED, SURFACE, TEXT, WARN)
from services import db, f1_api as api, log, media, notify
from ui.fmt import fmt_updated
from ui.widgets import button, card, dropdown, screen, tyre_chip, txt


# ---------------------------------------------------------------- меню
def _tile(icon, title, hint, on_click):
    return card(ft.Row(
        [ft.Container(ft.Icon(icon, color=ON_ACCENT, size=22), border_radius=20, width=42, height=42,
                      alignment=ft.Alignment.CENTER,
                      gradient=ft.LinearGradient(colors=[ACCENT_GLOW, ACCENT_DEEP], begin=ft.Alignment.TOP_LEFT,
                                                 end=ft.Alignment.BOTTOM_RIGHT)),
         ft.Column([txt(title, 16, bold=True), txt(hint, 12, MUTED)], expand=True, spacing=1),
         ft.Icon(ft.Icons.CHEVRON_RIGHT, color=DIM)],
        vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
        on_click=on_click, padding=12, ink=True)


def build_menu(state):
    body = [
        _tile(ft.Icons.COMPARE_ARROWS, "Сравнение пилотов", "2–4 пилота: очки, победы, поулы, личные встречи",
              lambda e: state.open_sub("compare")),
        _tile(ft.Icons.SENSORS, "Live-тайминг", "Позиции, отрывы, шины и пит-стопы — сейчас или итог сессии",
              lambda e: state.open_sub("live")),
        _tile(ft.Icons.EMOJI_EVENTS, "Борьба за титул", "Кто ещё может стать чемпионом и что нужно лидеру",
              lambda e: state.open_sub("title")),
        _tile(ft.Icons.HISTORY_EDU, "История сезонов", "Чемпионы, зачёты и победители с 1950 года",
              lambda e: state.open_sub("history")),
        _tile(ft.Icons.STAR_ROUNDED, "Избранное", "Мои пилоты и их результаты",
              lambda e: state.open_sub("favorites")),
        _tile(ft.Icons.TIMELINE, "Стратегия", "Какие шины и сколько остановок на трассе",
              lambda e: state.open_sub("strategy")),
        _tile(ft.Icons.SETTINGS, "Настройки", "Оформление, уведомления, обновление данных",
              lambda e: state.open_sub("settings")),
    ]
    if not notify.is_android():
        body.insert(-1, _tile(ft.Icons.PICTURE_IN_PICTURE_ALT, "Мини-виджет", "Окно поверх остальных: таймер и топ-3 (Ctrl+M)",
                              lambda e: state.toggle_mini()))
    return screen(state, "Ещё", body)


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
        txt("Это базовые прикидки приложения, а не официальные планы команд.", 11, DIM),
    ]
    return screen(state, "Стратегия", body, subtitle="План пит-стопов по трассам", back=True)


# ---------------------------------------------------------------- настройки
INTERVALS = {"5": "каждые 5 минут", "10": "каждые 10 минут", "30": "каждые 30 минут"}
STATE_TEXT = {"live": "данные свежие", "cached": "показаны сохранённые данные", "empty": "данных нет"}


def _line(label, value, color=TEXT):
    return ft.Row([txt(label, 13, MUTED, expand=True), txt(value, 13, color, text_align=ft.TextAlign.RIGHT)],
                  vertical_alignment=ft.CrossAxisAlignment.START)


def _theme_card(state):
    """Оформление: тёмная / светлая / в цветах команды (+ выбор команды)."""
    import design_system as ds
    current, chosen_team = ds.THEME, ds.THEME_TEAM

    def option(key, icon, hint):
        active = current == key
        return ft.Container(
            ft.Column([ft.Icon(icon, color=ON_ACCENT if active else TEXT, size=22),
                       txt(ds.THEME_NAMES[key], 12, ON_ACCENT if active else TEXT, bold=True),
                       txt(hint, 10, ON_ACCENT if active else MUTED, text_align=ft.TextAlign.CENTER)],
                      horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            expand=True, padding=10, border_radius=12, ink=True,
            bgcolor=ACCENT if active else RAISED,
            on_click=lambda e, k=key: state.set_theme(k, chosen_team or (state.constructors[0]["name"]
                                                                         if k == "team" and state.constructors else None)),
        )

    items = [txt("Оформление", 16, bold=True, head=True),
             ft.Row([option("dark", ft.Icons.DARK_MODE_ROUNDED, "чёрный и красный"),
                     option("light", ft.Icons.LIGHT_MODE_ROUNDED, "светлый фон"),
                     option("team", ft.Icons.PALETTE_ROUNDED, "акцент команды")], spacing=8)]
    if current == "team" and state.constructors:
        chips = []
        for c in state.constructors:
            color = ds.get_team_color(c["name"])
            active = ds.team_key(c["name"]) == ds.team_key(chosen_team)
            chips.append(ft.Container(
                ft.Row([ft.Container(width=12, height=12, bgcolor=color, border_radius=6),
                        txt(c["name"], 12, TEXT, bold=active)], spacing=6, tight=True),
                bgcolor=RAISED, border=ft.Border.all(2, color) if active else None, border_radius=20, ink=True,
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                on_click=lambda e, n=c["name"]: state.set_theme("team", n)))
        items.append(ft.Row(chips, wrap=True, spacing=6, run_spacing=6))
    return card(ft.Column(items, spacing=10))


def _notifications_card(state):
    def switch(kind, title, hint):
        return ft.Row([
            ft.Column([txt(title, 14, bold=True), txt(hint, 11, MUTED)], spacing=1, expand=True),
            ft.Switch(value=state.notifications_on(kind), active_color=ACCENT,
                      on_change=lambda e, k=kind: state.set_notifications(k, bool(e.control.value))),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    return card(ft.Column([
        txt("Уведомления", 16, bold=True, head=True),
        switch("sessions", "О сессиях", "За час до квалификации, спринта и гонки"),
        switch("results", "Итоги избранных", "Места и очки избранных пилотов после гонки"),
        button("Проверить уведомление", lambda e: state.test_notification(), primary=False,
               icon=ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED),
        txt("Приходят, пока приложение запущено (свёрнутое — тоже).", 11, DIM),
    ], spacing=10))


def build_settings(state):
    minutes = str(state.refresh_minutes())
    if minutes not in INTERVALS:
        minutes = "5"

    def on_interval(e):
        api.set_setting("refresh_minutes", e.control.value)
        state.start_refresher()
        state.render()

    st = state.status
    color = {"live": OK, "cached": WARN}.get(st["state"], DANGER)
    info = [_line("Состояние", STATE_TEXT.get(st["state"], "—"), color),
            _line("Обновлено", fmt_updated(st["updated_at"])),
            _line("Источник", "Jolpica F1 API"),
            _line("Размер базы", f"{db.db_size_kb()} КБ"),
            _line("Фото и логотипы", f"{media.cache_size_kb()} КБ в кэше")]
    if st["error"]:
        info.append(_line("Последняя ошибка", str(st["error"])[:90], WARN))

    body = [
        _theme_card(state),
        _notifications_card(state),
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
        card(ft.Column([
            txt("О приложении", 16, bold=True, head=True),
            txt("F1 Analytics Hub 2.0 — неофициальное фан-приложение о чемпионате Формулы-1.", 12, MUTED),
            txt("Данные: Jolpica F1 API, OpenF1. Фото пилотов, логотипы и изображения болидов © Formula 1 "
                "и команды; флаги — flagcdn.com. Приложение не связано с Formula 1 и FIA.", 11, DIM),
        ], spacing=6)),
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
                 ft.TextButton("Очистить", on_click=confirm, style=ft.ButtonStyle(color=ACCENT_TEXT))],
        bgcolor=SURFACE,
    ))
