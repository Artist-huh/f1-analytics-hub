"""F1 Analytics Hub — точка входа и навигация"""
import os
import threading
import time

import flet as ft

from services import f1_api, log
from design_system import *
from theme import FONT_HEAD, FONT_FILE
from ui.components import ResponsiveContainer
from ui.fmt import fmt_countdown
from ui.screens import home, season, calendar, drivers, driver_detail, compare, more, favorites
from ui.state import AppState

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Основные табы
TABS = [
    home.render,               # 0: Главная
    season.render,             # 1: Чемпионат
    calendar.build_calendar,   # 2: Календарь
    drivers.build,             # 3: Пилоты
    more.build_menu,           # 4: Ещё
]

# Подэкраны (sub-pages)
SUBS = {
    "driver_detail": driver_detail.build,
    "compare": compare.build,
    "favorites": favorites.build,
    "duel": more.build_duel,
    "strategy": more.build_strategy,
    "settings": more.build_settings,
}

TICK_SECONDS = 30
MAX_CONTENT_WIDTH = 1100   # шире контент не растягиваем — по бокам поля
NARROW_WIDTH = 400         # уже — компактные подписи
logger = log.get("main")


def build_screen(state):
    """Построить экран с обработкой ошибок"""
    try:
        return (SUBS[state.sub] if state.sub else TABS[state.tab])(state)
    except Exception as exc:
        logger.exception("ошибка построения экрана (tab=%s, sub=%s)", state.tab, state.sub)
        return ft.Column(
            [
                ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=64, color=DANGER),
                ft.Text("Не удалось показать экран", size=FONT_H3, color=TEXT_PRIMARY),
                ft.Text(repr(exc), size=FONT_BODY_SMALL, color=TEXT_MUTED),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=SPACE_MD,
        )


def run_on_ui(page, fn):
    """Выполнить fn в цикле событий Flet.

    page.update() из обычного потока во Flet 0.80+ не будит цикл событий: изменения
    доходят до окна только после следующего действия пользователя. Поэтому всё, что
    приходит из фоновых потоков и обработчиков, перерисовываем через run_task.
    """
    run_task = getattr(page, "run_task", None)
    if run_task is None:          # тесты: поддельная страница без цикла событий
        fn()
        return

    async def task():
        fn()

    try:
        run_task(task)
    except RuntimeError:          # сессия уже закрыта
        logger.info("перерисовка пропущена: сессия закрыта")


def main(page: ft.Page):
    page.title = "F1 Analytics Hub"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed=ACCENT_PRIMARY)
    page.bgcolor = BG
    page.padding = 0
    page.fonts = {FONT_HEAD: FONT_FILE}

    # Размеры окна
    try:
        page.window.width = 430
        page.window.height = 820
        page.window.min_width = 360
        page.window.min_height = 640
    except Exception:
        pass

    # Инициализация данных
    f1_api.bootstrap()
    state = AppState(page)
    state.load()

    # Контейнер контента
    content = ft.Container(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=SPACE_MD, vertical=SPACE_XS),
    )

    # Навигационная панель
    nav = ft.NavigationBar(
        selected_index=0,
        bgcolor=SURFACE,
        indicator_color=ACCENT_PRIMARY,
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
        height=70,
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.HOME_OUTLINED,
                selected_icon=ft.Icons.HOME_ROUNDED,
                label="Главная"
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.EMOJI_EVENTS_OUTLINED,
                selected_icon=ft.Icons.EMOJI_EVENTS_ROUNDED,
                label="Чемпионат"
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.CALENDAR_TODAY_OUTLINED,
                selected_icon=ft.Icons.CALENDAR_MONTH_ROUNDED,
                label="Календарь"
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
                selected_icon=ft.Icons.PERSON_ROUNDED,
                label="Пилоты"
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.MORE_HORIZ_ROUNDED,
                selected_icon=ft.Icons.MORE_HORIZ_ROUNDED,
                label="Ещё"
            ),
        ],
        on_change=lambda e: state.open_tab(e.control.selected_index),
    )

    pending = threading.Event()   # перерисовка уже запланирована — повторные запросы сливаются

    def redraw():
        pending.clear()
        state.countdown = None
        content.content = build_screen(state)
        nav.selected_index = state.tab
        page.update()

    def render():
        if not pending.is_set():
            pending.set()
            run_on_ui(page, redraw)

    state.render = render
    state.run_on_ui = lambda fn: run_on_ui(page, fn)
    page.navigation_bar = nav
    content.content = build_screen(state)
    page.add(content)

    def layout_class():
        width = page.width or 430
        return width < NARROW_WIDTH, ResponsiveContainer.is_mobile(width)

    def fit_width():
        """Контент не шире MAX_CONTENT_WIDTH (по центру); в узком окне подписи навигации — только у активной вкладки."""
        width = page.width or 430
        side = max(SPACE_MD, (width - MAX_CONTENT_WIDTH) / 2)
        content.padding = ft.Padding.symmetric(horizontal=side, vertical=SPACE_XS)
        nav.label_behavior = (ft.NavigationBarLabelBehavior.ONLY_SHOW_SELECTED if width < NARROW_WIDTH
                              else ft.NavigationBarLabelBehavior.ALWAYS_SHOW)

    # Экран перестраивается, только когда окно пересекает точку перелома
    layout = {"class": layout_class()}

    def on_resize(e):
        fit_width()
        current = layout_class()
        if current != layout["class"]:
            layout["class"] = current
            render()
        else:
            page.update()

    fit_width()
    page.update()
    page.on_resize = on_resize

    # Запуск фонового обновления; закрытая сессия отписывается от него
    state.start_refresher()
    page.on_close = lambda e: state._stop and state._stop.set()

    def tick():
        try:
            if state.sub is not None or state.tab != 0 or state.countdown is None:
                return
            text, rnd = state.countdown
            race = state.next_race()
            if race and race["round"] == rnd and race["state"] == "upcoming":
                text.value = fmt_countdown(race["seconds_left"])
                page.update()
            else:
                state.load()
                redraw()
        except Exception as exc:
            logger.warning("ticker: %r", exc)

    def ticker():
        """Обновление таймера обратного отсчета"""
        while True:
            time.sleep(TICK_SECONDS)
            run_on_ui(page, tick)

    threading.Thread(target=ticker, name="f1-ticker", daemon=True).start()


if __name__ == "__main__":
    ft.run(main, assets_dir=ASSETS_DIR)
