"""Мелкие переиспользуемые элементы интерфейса."""
import flet as ft

from theme import (
    ACCENT, ON_ACCENT, ROSSO, SURFACE, RAISED, LINE, TEXT, MUTED, DIM, OK, WARN, FONT_HEAD, TYRES,
)


def txt(value, size=14, color=TEXT, bold=False, head=False, **kw):
    return ft.Text(
        str(value), size=size, color=color,
        weight=ft.FontWeight.BOLD if bold else None,
        font_family=FONT_HEAD if head else None, **kw,
    )


def card(content, bgcolor=SURFACE, radius=14, padding=14, on_click=None, border=None, **kw):
    return ft.Container(content=content, bgcolor=bgcolor, border_radius=radius,
                        padding=padding, on_click=on_click, border=border, **kw)


def pill(label, selected, on_click):
    return ft.Container(
        content=txt(label, 13, ON_ACCENT if selected else MUTED, bold=selected),
        bgcolor=ACCENT if selected else RAISED, border_radius=20,
        padding=ft.Padding.symmetric(horizontal=16, vertical=8), on_click=on_click, ink=True,
    )


def button(label, on_click, primary=True, icon=None):
    fg = ON_ACCENT if primary else TEXT
    row = []
    if icon:
        row.append(ft.Icon(icon, color=fg, size=18))
    row.append(txt(label, 14, fg, bold=True))
    return ft.Container(
        content=ft.Row(row, spacing=8, alignment=ft.MainAxisAlignment.CENTER),
        bgcolor=ACCENT if primary else RAISED, border_radius=10,
        padding=ft.Padding.symmetric(horizontal=16, vertical=12), on_click=on_click, ink=True,
    )


def dropdown(**kw):
    """Выпадающий список на всю ширину (через Row + expand, без жёсткой ширины)."""
    return ft.Row([ft.Dropdown(expand=True, bgcolor=RAISED, border_color=LINE, focused_border_color=ACCENT, color=TEXT, **kw)])


def chip(label, bg=RAISED, fg=TEXT):
    return ft.Container(
        content=txt(label, 11, fg, bold=True), bgcolor=bg, border_radius=6,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def team_bar(color, height=36):
    return ft.Container(width=4, height=height, bgcolor=color, border_radius=2)


def vdivider():
    return ft.Container(width=1, height=40, bgcolor=LINE)


def stat(label, value, color=TEXT, size=40):
    return ft.Column(
        [txt(value, size, color, bold=True, head=True), txt(label, 12, MUTED)],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0, expand=True,
    )


def stat_row(stats):
    """stats — список готовых stat(); между ними тонкие разделители."""
    items = []
    for i, s in enumerate(stats):
        if i:
            items.append(vdivider())
        items.append(s)
    return ft.Row(items, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def ratio_bar(fraction, color, height=4):
    """Полоска, заполненная на fraction (0..1). Через expand-пропорции, без измерения ширины."""
    n = max(0, min(100, int(fraction * 100)))
    return ft.Row(
        [
            ft.Container(expand=n or None, height=height, bgcolor=color, border_radius=2),
            ft.Container(expand=(100 - n) or None, height=height, bgcolor=LINE, border_radius=2),
        ],
        spacing=0,
    )


def bar_chart(items, height=110):
    """items: (подпись, значение, цвет, текст_сверху). Столбики прокручиваются вбок."""
    top = max((v for _, v, _, _ in items), default=0)
    cols = []
    for label, value, color, caption in items:
        h = max(3, int(height * value / top)) if top else 3
        cols.append(ft.Column(
            [txt(caption, 11, MUTED), ft.Container(width=22, height=h, bgcolor=color, border_radius=4),
             txt(label, 11, DIM)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4,
        ))
    return ft.Row(cols, spacing=10, vertical_alignment=ft.CrossAxisAlignment.END, scroll=ft.ScrollMode.AUTO)


def tyre_chip(letter):
    return ft.Container(
        content=txt(letter, 13, TEXT, bold=True, head=True), width=30, height=30,
        border_radius=15, border=ft.Border.all(3, TYRES.get(letter, DIM)),
        alignment=ft.Alignment.CENTER,
    )


def status_chip(state):
    if state.refreshing:
        label, color = "Обновление…", WARN
    else:
        label, color = {
            "live": ("Онлайн", OK), "cached": ("Из кэша", WARN),
        }.get(state.status["state"], ("Нет данных", ROSSO))
    return ft.Container(
        content=ft.Row(
            [ft.Container(width=8, height=8, bgcolor=color, border_radius=4),
             txt(label, 12, TEXT), ft.Icon(ft.Icons.REFRESH_ROUNDED, color=MUTED, size=16)],
            spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=RAISED, border_radius=16,
        padding=ft.Padding.symmetric(horizontal=10, vertical=6), on_click=lambda e: state.refresh_now(),
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
                          padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                          on_click=lambda e: state.refresh_now())],
            vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
        bgcolor=SURFACE, border=ft.Border.all(1, WARN), border_radius=10,
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
    )


def screen(state, title, body, subtitle=None, back=False):
    """Каркас экрана: закреплённая шапка + прокручиваемое тело."""
    left = []
    if back:
        left.append(ft.Container(
            content=ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, color=TEXT, size=22),
            on_click=lambda e: state.close_sub(), padding=6,
        ))
    titles = [txt(title, 30, bold=True, head=True)]
    if subtitle:
        titles.append(txt(subtitle, 12, MUTED))
    header = ft.Row(
        left + [ft.Column(titles, spacing=0, expand=True), status_chip(state)],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    note = banner(state)
    return ft.Column(
        [header, ft.Container(height=8)] + ([note, ft.Container(height=6)] if note else [])
        + [ft.Column(body, scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)],
        expand=True, spacing=0,
    )
