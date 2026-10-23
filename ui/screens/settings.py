"""Настройки: оформление и размер текста, уведомления, обновление и локальные данные."""
import flet as ft

from design_system import *
from services import db, log, media
from services import f1_api as api
from ui.fmt import fmt_updated
from ui.widgets import button, card, dropdown, pill, screen, txt

INTERVALS = {"5": "каждые 5 минут", "10": "каждые 10 минут", "30": "каждые 30 минут"}
STATE_TEXT = {"live": "данные свежие", "cached": "показаны сохранённые данные", "empty": "данных нет"}


def _line(label, value, color=TEXT):
    return ft.Row([txt(label, 13, MUTED, expand=True), txt(value, 13, color, text_align=ft.TextAlign.RIGHT)],
                  vertical_alignment=ft.CrossAxisAlignment.START)


def _theme_card(state):
    """Оформление: тёмная / светлая / в цветах команды (+ выбор команды)."""
    import design_system as ds
    current, chosen_team = ds.THEME, ds.THEME_TEAM
    default_team = state.constructors[0]["name"] if state.constructors else None

    def option(key, icon, hint):
        active = current == key
        return ft.Container(
            ft.Column([ft.Icon(icon, color=ON_ACCENT if active else TEXT, size=22),
                       txt({"team": "Команда"}.get(key, ds.THEME_NAMES[key]), 12, ON_ACCENT if active else TEXT,
                           bold=True,
                           no_wrap=True),
                       txt(hint, 10, ON_ACCENT if active else MUTED, text_align=ft.TextAlign.CENTER)],
                      horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            expand=True, padding=ft.Padding.symmetric(horizontal=4, vertical=10), border_radius=12, ink=True,
            bgcolor=ACCENT if active else RAISED,
            on_click=lambda e, k=key: state.set_theme(k, chosen_team or (default_team if k == "team" else None)),
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
    current_scale = f"{ds.FONT_SCALE:g}" if ds.FONT_SCALE != 1 else "1.0"
    items += [txt("Размер текста", 14, bold=True),
              ft.Row([pill(label, key == current_scale, lambda e, k=key: state.set_font_scale(float(k)))
                      for key, label in ds.FONT_SCALES.items()], wrap=True, spacing=6, run_spacing=6)]
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


def build(state):
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
        button("Пройти знакомство заново", lambda e: (state.ui.pop("welcome", None), state.open_sub("welcome")),
               primary=False, icon=ft.Icons.WAVING_HAND_ROUNDED),
        card(ft.Column([
            txt("Обновление данных", 16, bold=True, head=True),
            dropdown(label="Автообновление", value=minutes,
                     options=[ft.DropdownOption(key=k, text=v) for k, v in INTERVALS.items()],
                     on_select=on_interval),
            button("Обновить сейчас", lambda e: state.refresh_now(), icon=ft.Icons.REFRESH),
            txt("Лимит Jolpica — около 200 запросов в час; при таких интервалах приложение укладывается с запасом.",
                11, DIM),
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
            txt("F1 Analytics Hub 2.2 — неофициальное фан-приложение о чемпионате Формулы-1.", 12, MUTED),
            txt("Данные: Jolpica F1 API, OpenF1. Фото пилотов, логотипы, болиды и схемы трасс © Formula 1 "
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
