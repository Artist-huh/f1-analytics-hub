"""Каркас экрана и мелкие элементы: текст, карточка, вкладки-«пилюли», кнопки, статус сети."""
import flet as ft

from design_system import (
    ACCENT, ACCENT_DEEP, ACCENT_GLOW, BG, DIM, F1_RED, FONT_DISPLAY_ITALIC, FONT_HEADING, LINE, MUTED, OK,
    ON_ACCENT, RADIUS_FULL, RAISED, SURFACE, SURFACE_ELEVATED, TEXT, TOUCH, TYRES, WARN, DANGER, glow,
)


def txt(value, size=14, color=TEXT, bold=False, head=False, **kw):
    return ft.Text(
        str(value), size=size, color=color,
        weight=ft.FontWeight.BOLD if bold else None,
        font_family=FONT_HEADING if head else None, **kw,
    )


def card(content, bgcolor=SURFACE, radius=14, padding=14, on_click=None, border=None, **kw):
    return ft.Container(content=content, bgcolor=bgcolor, border_radius=radius,
                        padding=padding, on_click=on_click, border=border or ft.Border.all(1, LINE), **kw)


def pill(label, selected, on_click):
    """Вкладка-переключатель: выбранная — красная со свечением."""
    return ft.Container(
        content=txt(label, 13, ON_ACCENT if selected else MUTED, bold=True),
        gradient=ft.LinearGradient(begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT,
                                   colors=[ACCENT_GLOW, F1_RED]) if selected else None,
        bgcolor=None if selected else RAISED,
        border_radius=RADIUS_FULL,
        padding=ft.Padding.symmetric(horizontal=18, vertical=10),
        on_click=on_click, ink=True,
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
    )


def button(label, on_click, primary=True, icon=None):
    fg = ON_ACCENT if primary else TEXT
    row = []
    if icon:
        row.append(ft.Icon(icon, color=fg, size=18))
    row.append(txt(label, 14, fg, bold=True))
    return ft.Container(
        content=ft.Row(row, spacing=8, alignment=ft.MainAxisAlignment.CENTER),
        gradient=ft.LinearGradient(begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT,
                                   colors=[ACCENT_GLOW, F1_RED, ACCENT_DEEP]) if primary else None,
        bgcolor=None if primary else RAISED, border_radius=12, height=TOUCH,
        padding=ft.Padding.symmetric(horizontal=16), on_click=on_click, ink=True,
        shadow=glow(strength=0.3) if primary else None,
    )


def field_border(color, focused):
    """Рамка поля ввода / списка: тонкая линия color, при фокусе — focused в 2 px (Flet 1.0+)."""
    return {
        ft.ControlState.DEFAULT: ft.OutlineInputBorder(side=ft.BorderSide(1, color), border_radius=12),
        ft.ControlState.FOCUSED: ft.OutlineInputBorder(side=ft.BorderSide(2, focused), border_radius=12),
    }


def dropdown(**kw):
    """Выпадающий список на всю ширину (через Row + expand, без жёсткой ширины)."""
    return ft.Row([ft.Dropdown(expand=True, bgcolor=RAISED, border=field_border(LINE, ACCENT), color=TEXT, **kw)])


def chip(label, bg=RAISED, fg=TEXT):
    return ft.Container(
        content=txt(label, 11, fg, bold=True), bgcolor=bg, border_radius=6,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def team_bar(color, height=36):
    return ft.Container(width=4, height=height, bgcolor=color, border_radius=2)


def vdivider():
    return ft.Container(width=1, height=40, bgcolor=LINE)


def tyre_chip(letter):
    return ft.Container(
        content=txt(letter, 13, TEXT, bold=True, head=True), width=30, height=30,
        border_radius=15, border=ft.Border.all(3, TYRES.get(letter, DIM)),
        alignment=ft.Alignment.CENTER,
    )


def status_chip(state, compact=False):
    """Индикатор данных (онлайн / из кэша); нажатие — обновить. compact — только точка и значок
    (узкий экран с длинным заголовком)."""
    if state.refreshing:
        label, color = "Обновление…", WARN
    else:
        label, color = {
            "live": ("Онлайн", OK), "cached": ("Из кэша", WARN),
        }.get(state.status["state"], ("Нет данных", DANGER))
    dot = ft.Container(width=8, height=8, bgcolor=color, border_radius=4,
                       shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.8, color)))
    items = [dot] + ([] if compact else [txt(label, 12, TEXT)]) + [ft.Icon(ft.Icons.REFRESH_ROUNDED, color=MUTED, size=16)]
    return ft.Container(
        content=ft.Row(items, spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
        bgcolor=RAISED, border_radius=RADIUS_FULL, height=36,
        padding=ft.Padding.symmetric(horizontal=12), on_click=lambda e: state.refresh_now(), ink=True,
        tooltip=f"{label} · обновить данные (F5)",
    )


def empty_state(state, title, hint):
    return ft.Column(
        [ft.Container(height=40), txt(title, 20, bold=True, head=True),
         txt(hint, 13, MUTED, text_align=ft.TextAlign.CENTER),
         ft.Container(height=8), button("Обновить", lambda e: state.refresh_now(), icon=ft.Icons.REFRESH_ROUNDED)],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6,
    )


def banner(state):
    """Понятное сообщение о проблемах с данными (None, если всё в порядке).
    Технический текст ошибки не показываем — он есть в «Настройках» и в журнале."""
    from ui.fmt import fmt_updated
    st = state.status
    if state.refreshing or st["state"] == "live":
        return None
    if st["state"] == "empty":
        if st["error"]:
            title = "Не удалось загрузить данные"
            hint = "Проверь подключение к интернету и нажми «Повторить»."
        else:
            return txt("Загружаем данные…", 12, MUTED)
    elif st["error"]:
        title = "Нет соединения с сервером данных"
        hint = f"Показаны сохранённые данные ({fmt_updated(st['updated_at'])}). Приложение повторит попытку само."
    else:
        return None
    return ft.Container(
        content=ft.Row(
            [ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, color=WARN, size=20),
             ft.Column([txt(title, 13, TEXT, bold=True), txt(hint, 11, MUTED)], expand=True, spacing=1),
             ft.Container(txt("Повторить", 12, TEXT, bold=True), bgcolor=RAISED, border_radius=8,
                          padding=ft.Padding.symmetric(horizontal=12, vertical=10), ink=True,
                          on_click=lambda e: state.refresh_now())],
            vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
        bgcolor=SURFACE, border=ft.Border.all(1, WARN), border_radius=12,
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
    )


def screen(state, title, body, subtitle=None, back=False):
    """Каркас экрана: закреплённая шапка + прокручиваемое тело.
    Элементы тела плавно появляются при переходе на экран (state.fresh)."""
    from ui.components import FadeIn
    left = []
    if back:
        left.append(ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, icon_color=TEXT, icon_size=24,
                                  on_click=lambda e: state.close_sub(), tooltip="Назад (Esc)",
                                  width=TOUCH, height=TOUCH))
    from ui.components import page_width
    # на телефоне длинный заголовок с кнопкой «назад» не помещается рядом с подписью «Онлайн»
    compact = page_width(state) < 480 and (back or len(title) > 10)
    titles = [ft.Text(title, size=28, color=TEXT, font_family=FONT_DISPLAY_ITALIC, max_lines=1,
                      overflow=ft.TextOverflow.ELLIPSIS)]
    if subtitle:
        titles.append(txt(subtitle, 12, MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS))
    header = ft.Row(
        left + [ft.Column(titles, spacing=0, expand=True), status_chip(state, compact)],
        vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=4,
    )
    note = banner(state)
    animate = getattr(state, "fresh", False)
    items = [FadeIn(item, index=i, enabled=animate) for i, item in enumerate(body)]
    items.append(ft.Container(height=SPACE_BOTTOM))
    return ft.Column(
        [header, ft.Container(height=8)] + ([note, ft.Container(height=6)] if note else [])
        + [ft.Column(items, scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)],
        expand=True, spacing=0,
    )


SPACE_BOTTOM = 12   # воздух под последним элементом, чтобы он не прилипал к нижнему меню
