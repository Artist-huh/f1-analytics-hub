"""F1 Analytics Hub — точка входа и навигация"""
import os
import threading
import time

import flet as ft

import design_system as ds
from services import f1_api, log, notify
from design_system import *
from ui import theming
from ui.components import ResponsiveContainer, show_snack
from ui.fmt import fmt_countdown
from ui.screens import (home, season, calendar, circuit, drivers, driver_detail, compare, more, favorites, history,
                        live, mini, race_strategy, team, title)
from ui.state import AppState

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Основные табы и подэкраны. Собираются функцией: после смены темы модули экранов
# перезагружаются (ui/theming.py), и ссылки на их функции нужно взять заново.
TABS = []
SUBS = {}


def refresh_screens():
    TABS[:] = [
        home.render,               # 0: Главная
        season.render,             # 1: Чемпионат
        calendar.build_calendar,   # 2: Календарь
        drivers.build,             # 3: Пилоты
        more.build_menu,           # 4: Ещё
    ]
    SUBS.clear()
    SUBS.update({
        "driver_detail": driver_detail.build,
        "compare": compare.build,
        "favorites": favorites.build,
        "team": team.build,
        "history": history.build,
        "circuit": circuit.build,
        "live": live.build,
        "race_strategy": race_strategy.build,
        "title": title.build,
        "strategy": more.build_strategy,
        "settings": more.build_settings,
    })


refresh_screens()

TICK_SECONDS = 30
MAX_CONTENT_WIDTH = 1100   # шире контент не растягиваем — по бокам поля
NARROW_WIDTH = 400         # уже — компактные подписи
SWITCH_MS = 280            # смена экранов
logger = log.get("main")


def build_screen(state):
    """Построить экран с обработкой ошибок"""
    try:
        if getattr(state, "mini", False):
            return mini.build(state)
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


def apply_page_theme(page, nav=None):
    """Цвета окна, темы Flutter и нижнего меню — из текущей палитры (ds.*, не копии в этом модуле)."""
    page.theme_mode = ft.ThemeMode.LIGHT if ds.IS_LIGHT else ft.ThemeMode.DARK
    page.theme = ft.Theme(
        color_scheme_seed=ds.F1_RED,
        color_scheme=ft.ColorScheme(primary=ds.F1_RED, on_primary=ds.ON_ACCENT, secondary=ds.F1_RED,
                                    surface=ds.SURFACE, on_surface=ds.TEXT_PRIMARY),
    )
    page.dark_theme = page.theme
    page.bgcolor = ds.BG
    try:
        page.window.bgcolor = ds.BG
    except Exception:
        pass
    if nav is not None:
        nav.bgcolor = ds.BG_DEEPEST
        nav.indicator_color = ds.F1_RED
        nav.border = ft.Border.only(top=ft.BorderSide(1, ds.LINE))


def nav_bar(on_change):
    def dest(icon, selected, label):
        return ft.NavigationBarDestination(icon=icon, selected_icon=selected, label=label)

    return ft.NavigationBar(
        selected_index=0,
        bgcolor=ds.BG_DEEPEST,
        indicator_color=ds.F1_RED,
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
        height=72,
        elevation=0,
        border=ft.Border.only(top=ft.BorderSide(1, ds.LINE)),
        animation_duration=ft.Duration(milliseconds=SWITCH_MS),
        destinations=[
            dest(ft.Icons.HOME_OUTLINED, ft.Icons.HOME_ROUNDED, "Главная"),
            dest(ft.Icons.EMOJI_EVENTS_OUTLINED, ft.Icons.EMOJI_EVENTS_ROUNDED, "Чемпионат"),
            dest(ft.Icons.CALENDAR_TODAY_OUTLINED, ft.Icons.CALENDAR_MONTH_ROUNDED, "Календарь"),
            dest(ft.Icons.PERSON_OUTLINE_ROUNDED, ft.Icons.PERSON_ROUNDED, "Пилоты"),
            dest(ft.Icons.MORE_HORIZ_ROUNDED, ft.Icons.MORE_HORIZ_ROUNDED, "Ещё"),
        ],
        on_change=on_change,
    )


def main(page: ft.Page):
    page.title = "F1 Analytics Hub"
    page.padding = 0
    page.fonts = dict(FONTS)

    # Размеры окна на десктопе (на телефоне игнорируются)
    try:
        page.window.width = 440
        page.window.height = 880
        page.window.min_width = 360
        page.window.min_height = 640
    except Exception:
        pass

    # Инициализация данных
    f1_api.bootstrap()
    state = AppState(page)
    state.load()

    # Тема оформления из настроек (до построения первого экрана)
    saved_theme = f1_api.get_setting("theme", "dark")
    if saved_theme != "dark":
        theming.apply(saved_theme, f1_api.get_setting("theme_team"))
        refresh_screens()
    apply_page_theme(page)

    # Контент: экраны сменяются с анимацией (только при переходе, не при обновлении данных)
    switcher = ft.AnimatedSwitcher(
        content=ft.Container(),
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=ft.Duration(milliseconds=SWITCH_MS),
        reverse_duration=ft.Duration(milliseconds=SWITCH_MS // 2),
        switch_in_curve=ft.AnimationCurve.EASE_OUT,
        switch_out_curve=ft.AnimationCurve.EASE_IN,
        expand=True,
    )
    content = ft.Container(
        content=switcher,
        expand=True,
        padding=ft.Padding.symmetric(horizontal=SPACE_MD, vertical=SPACE_XS),
    )
    nav = nav_bar(lambda e: state.open_tab(e.control.selected_index))

    def on_theme_change(name, team_name):
        """Настройки -> «Оформление»: новая палитра, перезагрузка экранов, перерисовка."""
        theming.apply(name, team_name)
        refresh_screens()
        apply_page_theme(page, nav)
        state.render()

    state.on_theme_change = on_theme_change

    normal = {}

    def on_mini_change(enabled):
        """Мини-виджет: маленькое окно поверх остальных; обратно — прежний размер."""
        try:
            # ограничения и размер — отдельными обновлениями: иначе новый размер упирается в старый минимум
            if enabled:
                normal.update(width=page.window.width, height=page.window.height)
                page.window.min_width, page.window.min_height = 300, 240
                page.update()
                page.window.width, page.window.height = 340, 300
                page.window.always_on_top = True
                content.padding = ft.Padding.all(SPACE_SM)
            else:
                page.window.always_on_top = False
                page.window.width = normal.get("width") or 440
                page.window.height = normal.get("height") or 880
                page.update()
                page.window.min_width, page.window.min_height = 360, 640
                fit_width()
        except Exception as exc:
            logger.warning("мини-виджет: %r", exc)

    state.on_mini_change = on_mini_change

    # Уведомления: системные (Windows/macOS/Linux, Android) или плашка в приложении
    state.notifier = notify.Notifier(
        run_async=getattr(page, "run_task", None),
        fallback=lambda title, text: show_snack(page, f"{title}: {text}"),
    )
    if notify.is_android() and (state.notifications_on("sessions") or state.notifications_on("results")):
        notify.android_request_permission()
    shown = {"key": None}
    pending = threading.Event()   # перерисовка уже запланирована — повторные запросы сливаются

    def redraw():
        pending.clear()
        key = state.screen_key()
        state.fresh = key != shown["key"]
        shown["key"] = key
        state.countdown = None
        switcher.duration = ft.Duration(milliseconds=SWITCH_MS if state.fresh else 0)
        switcher.content = ft.Container(build_screen(state), expand=True, key=str(time.monotonic()))
        nav.selected_index = state.tab
        page.navigation_bar = None if state.mini else nav
        page.update()

    def render():
        if not pending.is_set():
            pending.set()
            run_on_ui(page, redraw)

    state.render = render
    state.run_on_ui = lambda fn: run_on_ui(page, fn)
    page.navigation_bar = nav
    shown["key"] = state.screen_key()
    switcher.content = ft.Container(build_screen(state), expand=True)
    page.add(ft.SafeArea(content, expand=True, avoid_intrusions_bottom=False))

    def layout_class():
        width = page.width or 440
        return width < NARROW_WIDTH, ResponsiveContainer.is_mobile(width), width >= MAX_CONTENT_WIDTH

    def fit_width():
        """Контент не шире MAX_CONTENT_WIDTH (по центру); в узком окне подписи навигации — только у активной вкладки."""
        width = page.width or 440
        side = max(SPACE_MD, (width - MAX_CONTENT_WIDTH) / 2)
        content.padding = ft.Padding.symmetric(horizontal=side, vertical=SPACE_XS)
        nav.label_behavior = (ft.NavigationBarLabelBehavior.ONLY_SHOW_SELECTED if width < NARROW_WIDTH
                              else ft.NavigationBarLabelBehavior.ALWAYS_SHOW)

    # Экран перестраивается, когда окно пересекает точку перелома или меняется ширина графиков
    layout = {"class": layout_class(), "width": page.width}

    def on_resize(e):
        fit_width()
        current = layout_class()
        width = page.width or 0
        if current != layout["class"] or abs(width - (layout["width"] or 0)) > 80:
            layout["class"], layout["width"] = current, width
            render()
        else:
            page.update()

    fit_width()
    page.update()
    page.on_resize = on_resize
    page.on_keyboard_event = lambda e: state.on_key(e.key, e.ctrl or e.meta)

    # Системная «назад» на Android: подэкран -> вкладка -> «Главная», и только потом выход
    async def on_confirm_pop(e):
        handled = state.go_back()
        await e.control.confirm_pop(not handled)

    try:
        root = page.views[0]
        root.can_pop = False
        root.on_confirm_pop = on_confirm_pop
    except (AttributeError, IndexError, TypeError):
        pass

    # Запуск фонового обновления; закрытая сессия отписывается от него
    state.start_refresher()
    page.on_close = lambda e: state._stop and state._stop.set()

    def tick():
        try:
            state.check_notifications()
        except Exception as exc:
            logger.warning("уведомления: %r", exc)
        try:
            on_home = state.sub is None and state.tab == 0
            if state.countdown is None or not (on_home or state.mini):
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
