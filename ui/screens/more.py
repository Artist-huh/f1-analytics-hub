"""Раздел «Ещё»: меню разделов (стратегия и настройки — в strategy.py и settings.py)."""
import flet as ft

from design_system import *
from services import notify
from ui.components import icon_badge
from ui.widgets import card, screen, txt


# ---------------------------------------------------------------- меню
def _tile(icon, title, hint, on_click, section="settings"):
    return card(ft.Row(
        [icon_badge(icon, SECTION_COLORS[section], size=42),
         ft.Column([txt(title, 16, bold=True), txt(hint, 12, MUTED)], expand=True, spacing=1),
         ft.Icon(ft.Icons.CHEVRON_RIGHT, color=DIM)],
        vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
        on_click=on_click, ink=True)


def build_menu(state):
    body = [
        _tile(ft.Icons.COMPARE_ARROWS, "Сравнение пилотов", "2–4 пилота: очки, победы, поулы, личные встречи",
              lambda e: state.open_sub("compare"), section="compare"),
        _tile(ft.Icons.SENSORS, "Live-тайминг", "Позиции, отрывы, шины и пит-стопы — сейчас или итог сессии",
              lambda e: state.open_sub("live"), section="live"),
        _tile(ft.Icons.EMOJI_EVENTS, "Борьба за титул", "Кто ещё может стать чемпионом и что нужно лидеру",
              lambda e: state.open_sub("title"), section="title"),
        _tile(ft.Icons.SPORTS_SCORE, "Прогнозы", "Угадай поул и подиум — очки за точность и итог сезона",
              lambda e: state.open_sub("predict"), section="predict"),
        _tile(ft.Icons.HISTORY_EDU, "История сезонов", "Чемпионы, зачёты и победители с 1950 года",
              lambda e: state.open_sub("history"), section="history"),
        _tile(ft.Icons.STAR_ROUNDED, "Избранное", "Мои пилоты и их результаты",
              lambda e: state.open_sub("favorites"), section="favorites"),
        _tile(ft.Icons.TIMELINE, "Стратегия", "Какие шины и сколько остановок на трассе",
              lambda e: state.open_sub("strategy"), section="strategy"),
        _tile(ft.Icons.SETTINGS, "Настройки", "Оформление, уведомления, обновление данных",
              lambda e: state.open_sub("settings")),
    ]
    if not notify.is_android():
        body.insert(-1, _tile(ft.Icons.PICTURE_IN_PICTURE_ALT, "Мини-виджет",
                              "Окно поверх остальных: таймер и топ-3 (Ctrl+M)",
                              lambda e: state.toggle_mini(), section="mini"))
    return screen(state, "Ещё", body)
