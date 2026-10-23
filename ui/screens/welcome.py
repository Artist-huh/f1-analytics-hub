"""Первый запуск: любимая команда и пилоты -> тема команды, избранное и уведомления за три шага"""
import flet as ft

from design_system import *
from services import f1_api as api
from ui.components import *
from ui.widgets import button, screen

STEPS = ["Команда", "Пилоты", "Уведомления"]


def needed(state):
    """Показывать ли знакомство: впервые, и есть кого выбирать. У тех, кто уже настроил приложение
    (есть избранное или своя тема) до этой версии, не показываем."""
    if api.get_setting("onboarded") == "1" or not state.standings:
        return False
    if state.favorites or api.get_setting("theme"):
        api.set_setting("onboarded", "1")
        return False
    return True


def _draft(state):
    return state.ui.setdefault("welcome", {"step": 0, "team": None, "drivers": [],
                                           "sessions": True, "results": True})


def build(state):
    w = _draft(state)
    step = w["step"]
    body = [_dots(step)]
    body += [_team_step, _drivers_step, _notify_step][step](state, w)
    nav = []
    if step:
        nav.append(button("Назад", lambda e: _go(state, step - 1), primary=False, icon=ft.Icons.ARROW_BACK_ROUNDED))
    nav.append(ft.Container(expand=True))
    nav.append(button("Готово" if step == len(STEPS) - 1 else "Дальше",
                      lambda e: finish(state) if step == len(STEPS) - 1 else _go(state, step + 1),
                      icon=ft.Icons.CHECK_ROUNDED if step == len(STEPS) - 1 else ft.Icons.ARROW_FORWARD_ROUNDED))
    body.append(ft.Row(nav, spacing=SPACE_SM))
    body.append(ft.TextButton("Пропустить — настрою потом", on_click=lambda e: skip(state)))
    return screen(state, "Добро пожаловать", body, subtitle=f"Шаг {step + 1} из {len(STEPS)}: {STEPS[step]}")


def _go(state, step):
    w = _draft(state)
    if step == 1 and w["team"] and not w["drivers"]:
        w["drivers"] = [d["driver_id"] for d in state.team_drivers(w["team"])]   # пилоты команды — сразу отмечены
    w["step"] = step
    state.render()


def _dots(step):
    return ft.Row([ft.Container(height=6, expand=True, border_radius=3, bgcolor=F1_RED if i <= step else LINE_STRONG)
                   for i in range(len(STEPS))], spacing=SPACE_XS)


# ---------------------------------------------------------------- шаги
def _team_step(state, w):
    def pick(name):
        w["team"] = None if w["team"] == name else name
        w["drivers"] = []
        state.render()

    tiles = []
    for team in state.constructors:
        chosen = w["team"] == team["name"]
        tiles.append(ft.Container(
            ft.Row([TeamLogo(team["name"], state.team_logo(team["name"]), size=32),
                    ft.Text(team["name"], size=FONT_BODY_SMALL, color=TEXT_PRIMARY, expand=True, max_lines=2,
                            weight=ft.FontWeight.W_600 if chosen else None),
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED if chosen else ft.Icons.CIRCLE_OUTLINED,
                            color=get_team_color(team["name"]) if chosen else TEXT_DIM, size=18)],
                   spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=SPACE_XS, border_radius=RADIUS_MD, ink=True, bgcolor=SURFACE_RAISED if chosen else SURFACE,
            border=ft.Border.all(2, get_team_color(team["name"]) if chosen else LINE_STRONG),
            on_click=lambda e, n=team["name"]: pick(n),
            col={"xs": 6, "md": 4}))
    return [ft.Text("За какую команду болеешь? Приложение перекрасится в её цвета.", size=FONT_BODY,
                    color=TEXT_SECONDARY),
            ft.ResponsiveRow(tiles, spacing=SPACE_XS, run_spacing=SPACE_XS),
            ft.Text("Можно не выбирать — останется тёмная тема.", size=FONT_CAPTION, color=TEXT_DIM)]


def _drivers_step(state, w):
    def toggle(driver_id):
        w["drivers"] = [i for i in w["drivers"] if i != driver_id] if driver_id in w["drivers"] \
            else w["drivers"] + [driver_id]
        state.render()

    chips = []
    for d in state.standings:
        chosen = d["driver_id"] in w["drivers"]
        chips.append(ft.Container(
            ft.Text(d["name"], size=FONT_BODY_SMALL,
                    color=readable_on(get_team_color(d["team"])) if chosen else TEXT_SECONDARY),
            bgcolor=get_team_color(d["team"]) if chosen else SURFACE_RAISED, border_radius=RADIUS_FULL, ink=True,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10), on_click=lambda e, i=d["driver_id"]: toggle(i),
            tooltip=f"{d['name']}, {d['team']}"))
    n = len(w["drivers"])
    return [ft.Text("Любимые пилоты попадут в «Избранное»: их результаты — отдельным списком и в уведомлениях.",
                    size=FONT_BODY, color=TEXT_SECONDARY),
            ft.Row(chips, wrap=True, spacing=SPACE_XS, run_spacing=SPACE_XS),
            ft.Text(f"Выбрано: {n}" if n else "Пока никого — можно и так.", size=FONT_CAPTION, color=TEXT_DIM)]


def _notify_step(state, w):
    def switch(kind):
        def handler(e):
            w[kind] = bool(e.control.value)
            state.render()
        return handler

    rows = [("sessions", "Напоминания о сессиях", "За час до квалификации, спринта и гонки"),
            ("results", "Результаты моих пилотов", "Когда появятся итоги гонки")]
    return [ft.Text("Что сообщать?", size=FONT_BODY, color=TEXT_SECONDARY)] + [
        AnimatedCard(ft.Row([ft.Column([ft.Text(title, size=FONT_BODY, color=TEXT_PRIMARY),
                                        ft.Text(hint, size=FONT_CAPTION, color=TEXT_MUTED)], spacing=2, expand=True),
                             ft.Switch(value=w[kind], active_color=F1_RED, on_change=switch(kind),
                                       label=None, tooltip=title)],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=SPACE_SM)
        for kind, title, hint in rows]


# ---------------------------------------------------------------- итог
def finish(state):
    w = _draft(state)
    for driver_id in w["drivers"]:
        if driver_id not in state.favorites:
            api.toggle_favorite(driver_id)
    state.favorites = api.get_favorites()
    for kind in ("sessions", "results"):
        state.set_notifications(kind, w[kind])          # на Android включение спросит разрешение
    _leave(state)
    if w["team"]:
        state.set_theme("team", w["team"])              # перекрашивает и перерисовывает
    else:
        state.render()
    show_snack(state.page, "Готово! Настройки можно поменять в «Ещё» → «Настройки»")


def skip(state):
    _leave(state)
    state.render()


def _leave(state):
    """Знакомство пройдено: больше не показываем, возвращаемся на «Главную»."""
    api.set_setting("onboarded", "1")
    state.ui.pop("welcome", None)
    state._back.clear()
    state.tab, state.sub = 0, None
