"""F1 Analytics Hub — точка входа и навигация"""
import contextlib
import os
import threading
import time

import flet as ft

import design_system as ds
from design_system import *
from services import f1_api, log, notify, widget
from services import live as live_service
from ui import theming
from ui.components import ResponsiveContainer, show_snack
from ui.fmt import fmt_countdown
from ui.screens import (
    calendar,
    circuit,
    compare,
    driver_detail,
    drivers,
    favorites,
    history,
    home,
    home_blocks,
    live,
    mini,
    more,
    predict,
    race,
    season,
    settings,
    strategy,
    team,
    title,
    welcome,
)
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
        "race_strategy": race.build,
        "title": title.build,
        "predict": predict.build,
        "welcome": welcome.build,
        "home_edit": home_blocks.build_editor,
        "strategy": strategy.build,
        "settings": settings.build,
    })


refresh_screens()

# Подэкраны, которые открываются отдельной страницей навигатора поверх текущего экрана:
# тогда Flutter «перевозит» фото пилота (Hero) из списка на его страницу и обратно.
OVERLAY_SUBS = {"driver_detail"}
TICK_SECONDS = 30
MAX_CONTENT_WIDTH = 1100   # шире контент не растягиваем — по бокам поля
NARROW_WIDTH = 400         # уже — компактные подписи
SWITCH_MS = ds.ANIM_SCREEN  # смена экранов
logger = log.get("main")


def build_screen(state):
    """Построить экран с обработкой ошибок"""
    try:
        if getattr(state, "mini", False):
            return mini.build(state)
        return (SUBS[state.sub] if state.sub else TABS[state.tab])(state)
    except Exception:
        logger.exception("ошибка построения экрана (tab=%s, sub=%s)", state.tab, state.sub)
        # текст ошибки — в журнале (logger.exception выше), пользователю — что делать дальше
        return ft.Column(
            [
                ft.Icon(ft.Icons.ERROR_ROUNDED, size=64, color=DANGER),
                ft.Text("Не удалось показать экран", size=FONT_H3, color=TEXT_PRIMARY),
                ft.Text("Попробуй открыть его ещё раз или вернись на главную. Подробности записаны в журнал "
                        "приложения — его можно приложить к сообщению об ошибке.",
                        size=FONT_BODY_SMALL, color=TEXT_MUTED, text_align=ft.TextAlign.CENTER),
                ft.Row([ft.FilledTonalButton("Повторить", icon=ft.Icons.REFRESH_ROUNDED,
                                             on_click=lambda e: state.render()),
                        ft.TextButton("На главную", on_click=lambda e: state.open_tab(0))],
                       alignment=ft.MainAxisAlignment.CENTER, spacing=SPACE_SM),
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
    # «меньше движения» — переходы страниц без анимации
    zoom = ft.PageTransitionTheme.NONE if ds.REDUCE_MOTION else ft.PageTransitionTheme.ZOOM
    page.theme = ft.Theme(
        color_scheme_seed=ds.F1_RED,
        color_scheme=ft.ColorScheme(primary=ds.ACCENT_FILL, on_primary=ds.ON_ACCENT, secondary=ds.ACCENT_FILL,
                                    surface=ds.SURFACE, on_surface=ds.TEXT_PRIMARY),
        # у перехода на страницу пилота должна быть длительность — иначе фото (Hero) «перелетает» мгновенно
        page_transitions=ft.PageTransitionsTheme(android=zoom, windows=zoom, linux=zoom, macos=zoom,
                                                 ios=zoom if ds.REDUCE_MOTION else ft.PageTransitionTheme.CUPERTINO),
    )
    page.dark_theme = page.theme
    page.bgcolor = ds.BG
    with contextlib.suppress(Exception):
        page.window.bgcolor = ds.BG
    if nav is not None:
        nav.animation_duration = ft.Duration(milliseconds=0 if ds.REDUCE_MOTION else SWITCH_MS)
        nav.bgcolor = ds.BG_DEEPEST
        nav.indicator_color = ds.ACCENT_FILL      # белая иконка выбранной вкладки — ≥ 4.5:1 и в теме команды
        nav.border = ft.Border.only(top=ft.BorderSide(1, ds.LINE))


def nav_bar(on_change):
    def dest(icon, selected, label):
        return ft.NavigationBarDestination(icon=icon, selected_icon=selected, label=label)

    return ft.NavigationBar(
        selected_index=0,
        bgcolor=ds.BG_DEEPEST,
        indicator_color=ds.ACCENT_FILL,
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
        height=72,
        elevation=0,
        border=ft.Border.only(top=ft.BorderSide(1, ds.LINE)),
        animation_duration=ft.Duration(milliseconds=0 if ds.REDUCE_MOTION else SWITCH_MS),   # «меньше движения»
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
    if welcome.needed(state):
        state.sub = "welcome"       # первый запуск: команда, пилоты, уведомления

    # Тема оформления из настроек (до построения первого экрана)
    saved_theme = f1_api.get_setting("theme", "dark")
    saved_scale = f1_api.get_setting("font_scale", "1.0")
    saved_motion = f1_api.get_setting("reduce_motion")          # "1" / "0" — выбор пользователя, None — как в системе
    ds.apply_reduce_motion(saved_motion == "1")
    if saved_theme != "dark" or saved_scale != "1.0":
        theming.apply(saved_theme, f1_api.get_setting("theme_team"), font_scale=saved_scale)
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

    def on_minimize():
        page.window.minimized = True
        page.update()

    state.on_minimize = on_minimize

    def on_lifecycle(e):
        """Фон / возврат. HIDE/PAUSE присылает Android, когда приложение свёрнуто. На компьютере сворачивание
        даёт лишь INACTIVE — как и потеря фокуса (мини-виджет поверх окон), поэтому его фоном не считаем."""
        logger.info("жизненный цикл: %s", e.state)
        if e.state in (ft.AppLifecycleState.PAUSE, ft.AppLifecycleState.HIDE):
            state.set_background(True)
        elif e.state in (ft.AppLifecycleState.RESUME, ft.AppLifecycleState.SHOW):
            state.set_background(False)

    page.on_app_lifecycle_state_change = on_lifecycle

    # Уведомления: системные (Windows/macOS/Linux, Android) или плашка в приложении
    state.notifier = notify.Notifier(
        run_async=getattr(page, "run_task", None),
        fallback=lambda title, text: show_snack(page, f"{title}: {text}"),
    )
    if notify.is_android() and (state.notifications_on("sessions") or state.notifications_on("results")):
        notify.android_request_permission(page)
    shown = {"key": None}
    pending = threading.Event()   # перерисовка уже запланирована — повторные запросы сливаются

    overlay = {"view": None, "body": None}

    def overlay_redraw():
        """Страница пилота поверх текущего экрана (экран под ней не трогаем — источник Hero на месте)."""
        body = ft.Container(build_screen(state), expand=True)
        if overlay["view"] is None:
            holder = ft.Container(body, expand=True, padding=content.padding)
            view = ft.View(route="/" + state.sub, controls=[ft.SafeArea(holder, expand=True,
                                                                        avoid_intrusions_bottom=False)],
                           bgcolor=ds.BG, padding=0, can_pop=False)
            view.on_confirm_pop = on_overlay_pop          # «назад» Android: снимаем страницу сами (с анимацией)
            overlay.update(view=view, body=holder)
            page.views.append(view)
            with contextlib.suppress(Exception):
                page.route = view.route                   # смена маршрута запускает анимацию перехода
        else:
            overlay["body"].content = body
            overlay["body"].padding = content.padding
        page.update()

    def close_overlay():
        if overlay["view"] is not None:
            with contextlib.suppress(ValueError):
                page.views.remove(overlay["view"])
            overlay.update(view=None, body=None)
            with contextlib.suppress(Exception):
                page.route = "/"

    def redraw():
        pending.clear()
        if state.sub in OVERLAY_SUBS and not state.mini and hasattr(page, "views"):
            overlay_redraw()
            return
        reopened = overlay["view"] is not None
        close_overlay()
        if reopened and state.screen_key() == shown["key"]:
            page.update()                             # вернулись на тот же экран — фото улетает обратно на место
            return
        key = state.screen_key()
        state.fresh = key != shown["key"]
        shown["key"] = key
        state.countdown = None
        switcher.duration = ft.Duration(milliseconds=SWITCH_MS if state.fresh and not ds.REDUCE_MOTION else 0)
        switcher.content = ft.Container(build_screen(state), expand=True, key=str(time.monotonic()))
        nav.selected_index = state.tab
        page.navigation_bar = None if state.mini or state.sub == "welcome" else nav
        page.update()

    def render():
        if not pending.is_set():
            pending.set()
            run_on_ui(page, redraw)

    state.render = render
    state.run_on_ui = lambda fn: run_on_ui(page, fn)
    page.navigation_bar = None if state.sub == "welcome" else nav
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

    async def on_overlay_pop(e):
        """«Назад» на странице пилота: сначала ответить Flutter (страница ещё зарегистрирована), потом закрыть её.
        Наоборот нельзя — ответ пришёл бы к уже снятой странице (RuntimeError «Control … is not registered»)."""
        await e.control.confirm_pop(False)
        state.go_back()

    try:
        root = page.views[0]
        root.can_pop = False
        root.on_confirm_pop = on_confirm_pop
    except (AttributeError, IndexError, TypeError):
        pass

    # Запуск фонового обновления; закрытая сессия отписывается от него
    state.start_refresher()
    page.on_close = lambda e: state._stop and state._stop.set()

    home_widget = widget.Widget(page)          # виджет на главный экран Android

    def update_widget():
        try:
            home_widget.push(widget.widget_data(state.schedule, state.standings, state.live_now(),
                                                live_service.snapshot()[0]))
        except Exception as exc:
            logger.warning("виджет: %r", exc)

    def tick():
        update_widget()
        try:
            state.check_notifications()
        except Exception as exc:
            logger.warning("уведомления: %r", exc)
        if state.background:                   # в фоне окно не перерисовываем
            return
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
    update_widget()                            # сразу после запуска — данные из кэша

    async def follow_system_motion():
        """Пользователь не выбирал «меньше движения» сам — берём системную настройку."""
        try:
            features = await ft.SemanticsService().get_accessibility_features()
        except Exception as exc:
            logger.info("настройки доступности системы недоступны: %r", exc)
            return
        if features.disable_animations or features.reduce_motion:
            logger.info("в системе отключены анимации — включаем «меньше движения»")
            ds.apply_reduce_motion(True)
            state.on_theme_change(ds.THEME, ds.THEME_TEAM)

    if saved_motion is None and getattr(page, "run_task", None):
        page.run_task(follow_system_motion)


if __name__ == "__main__":
    ft.run(main, assets_dir=ASSETS_DIR)
