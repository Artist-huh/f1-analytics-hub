"""Переиспользуемые элементы нового дизайна (API Flet 0.80+)."""
import flet as ft
from design_system import *


class ResponsiveContainer:
    """Точки перелома ширины окна"""

    @staticmethod
    def get_layout_columns(page_width: float) -> int:
        """Получить количество колонок для grid layout"""
        if page_width < BREAKPOINT_MOBILE:
            return 1
        elif page_width < BREAKPOINT_TABLET:
            return 2
        elif page_width < BREAKPOINT_DESKTOP:
            return 3
        return 4

    @staticmethod
    def is_mobile(page_width: float) -> bool:
        return page_width < BREAKPOINT_TABLET

    @staticmethod
    def is_desktop(page_width: float) -> bool:
        return page_width >= BREAKPOINT_DESKTOP


def page_width(state, default=430):
    """Текущая ширина окна (в тестах у страницы её может не быть)."""
    return getattr(state.page, "width", None) or default


def is_narrow(state):
    """Совсем узкое окно (< 400 px): компактные карточки."""
    return page_width(state) < 400


class AnimatedCard(ft.Container):
    """Карточка с hover-эффектом"""

    def __init__(self, content: ft.Control, on_click=None, elevation_end: int = 8, **kwargs):
        kwargs.setdefault("padding", SPACE_MD)
        super().__init__(
            content=content,
            bgcolor=SURFACE,
            border_radius=RADIUS_MD,
            ink=on_click is not None,
            on_click=on_click,
            animate_scale=ft.Animation(ANIM_FAST, ft.AnimationCurve.EASE_OUT),
            **kwargs,
        )
        self.elevation_end = elevation_end
        if on_click is not None:
            self.on_hover = self._handle_hover

    def _handle_hover(self, e):
        hovered = e.data in (True, "true")
        self.scale = 1.02 if hovered else 1.0
        self.shadow = ft.BoxShadow(
            spread_radius=1,
            blur_radius=self.elevation_end,
            color=ft.Colors.with_opacity(0.5, "#000000"),
            offset=ft.Offset(0, 4),
        ) if hovered else None
        self.update()


class GradientButton(ft.Container):
    """Кнопка с градиентом команды"""

    def __init__(self, text: str, team_name: str = None, on_click=None, icon=None, expand=False, **kwargs):
        colors = get_team_gradient(team_name) if team_name else (ACCENT_PRIMARY, ACCENT_DEEP)
        items = []
        if icon:
            items.append(ft.Icon(icon, color=BG_DEEP, size=20))
        items.append(ft.Text(text, size=FONT_BODY, weight=ft.FontWeight.W_600, color=BG_DEEP))
        super().__init__(
            content=ft.Row(items, alignment=ft.MainAxisAlignment.CENTER, spacing=SPACE_XS),
            gradient=ft.LinearGradient(
                begin=ft.Alignment.CENTER_LEFT,
                end=ft.Alignment.CENTER_RIGHT,
                colors=[colors[0], colors[1]],
            ),
            border_radius=RADIUS_FULL,
            padding=ft.Padding.symmetric(horizontal=SPACE_LG, vertical=SPACE_SM),
            ink=True,
            on_click=on_click,
            expand=expand,
            **kwargs,
        )


class DriverAvatar(ft.Container):
    """Аватар пилота: круг цвета команды с кодом пилота"""

    def __init__(self, driver_code: str, team_name: str, size: int = 48, on_click=None, **kwargs):
        super().__init__(
            content=ft.Text(
                (driver_code or "?")[:3].upper(),
                size=int(size / 2.8),
                weight=ft.FontWeight.BOLD,
                color=BG_DEEP,
                font_family=FONT_HEADING,
            ),
            width=size,
            height=size,
            bgcolor=get_team_color(team_name),
            border_radius=RADIUS_FULL,
            alignment=ft.Alignment.CENTER,
            on_click=on_click,
            border=ft.Border.all(2, SURFACE_ELEVATED),
            **kwargs,
        )


class PositionBadge(ft.Container):
    """Бейдж позиции: золото/серебро/бронза для подиума"""

    def __init__(self, position, size: int = 32, **kwargs):
        try:
            pos = int(position)
        except (TypeError, ValueError):
            pos = 0
        podium = pos in POSITION_COLORS
        super().__init__(
            content=ft.Text(
                str(pos) if pos else "—",
                size=size // 2,
                weight=ft.FontWeight.BOLD,
                color=BG_DEEP if podium else TEXT_PRIMARY,
                font_family=FONT_HEADING,
            ),
            width=size,
            height=size,
            bgcolor=POSITION_COLORS[pos] if podium else SURFACE_ELEVATED,
            border_radius=RADIUS_SM,
            alignment=ft.Alignment.CENTER,
            **kwargs,
        )


class StatCard(ft.Container):
    """Карточка статистики"""

    def __init__(self, label: str, value: str, icon=None, color: str = ACCENT_PRIMARY, subtitle: str = None,
                 compact: bool = False, **kwargs):
        items = []
        if icon:
            items.append(ft.Icon(icon, color=color, size=22))
        items += [
            ft.Text(str(value), size=FONT_H4 if compact else FONT_H3, weight=ft.FontWeight.BOLD, color=color,
                    font_family=FONT_HEADING, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(label, size=FONT_CAPTION, color=TEXT_MUTED, text_align=ft.TextAlign.CENTER),
        ]
        if subtitle:
            items.append(ft.Text(subtitle, size=FONT_CAPTION, color=TEXT_DIM, text_align=ft.TextAlign.CENTER))
        kwargs.setdefault("expand", True)
        super().__init__(
            content=ft.Column(items, spacing=SPACE_XXS, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=SURFACE,
            border_radius=RADIUS_MD,
            padding=SPACE_SM,
            border=ft.Border.all(1, LINE),
            **kwargs,
        )


class SectionHeader(ft.Container):
    """Заголовок секции с опциональной кнопкой действия"""

    def __init__(self, title: str, subtitle: str = None, action_text: str = None, on_action=None, **kwargs):
        title_column = [ft.Text(title, size=FONT_H4, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY)]
        if subtitle:
            title_column.append(ft.Text(subtitle, size=FONT_BODY_SMALL, color=TEXT_MUTED))
        row = [ft.Column(title_column, spacing=SPACE_XXS, expand=True)]
        if action_text and on_action:
            row.append(ft.TextButton(action_text, on_click=on_action, style=ft.ButtonStyle(color=ACCENT_PRIMARY)))
        super().__init__(
            content=ft.Row(row, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(top=SPACE_XS),
            **kwargs,
        )


def progress_bar(fraction: float, color: str, height: int = 4) -> ft.Row:
    """Полоса, заполненная на fraction (0..1) — через пропорции expand, без измерения ширины."""
    n = max(0, min(100, round(fraction * 100)))
    return ft.Row(
        [
            ft.Container(expand=n or None, height=height, bgcolor=color, border_radius=RADIUS_SM),
            ft.Container(expand=(100 - n) or None, height=height, bgcolor=SURFACE_ELEVATED, border_radius=RADIUS_SM),
        ],
        spacing=0,
    )


def empty_block(icon, title: str, hint: str = None) -> ft.Container:
    """Пустое состояние внутри экрана"""
    items = [ft.Icon(icon, size=56, color=TEXT_DIM), ft.Text(title, size=FONT_H4, color=TEXT_MUTED,
                                                             text_align=ft.TextAlign.CENTER)]
    if hint:
        items.append(ft.Text(hint, size=FONT_BODY_SMALL, color=TEXT_DIM, text_align=ft.TextAlign.CENTER))
    return ft.Container(
        content=ft.Column(items, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=SPACE_SM),
        padding=SPACE_XL,
        alignment=ft.Alignment.CENTER,
    )


def create_divider(vertical: bool = False) -> ft.Container:
    """Создать разделитель"""
    if vertical:
        return ft.Container(width=1, height=36, bgcolor=LINE)
    return ft.Container(height=1, bgcolor=LINE)


def show_snack(page, message: str, color: str = SURFACE_ELEVATED):
    """Короткое уведомление внизу окна"""
    page.show_dialog(ft.SnackBar(content=ft.Text(message, color=TEXT_PRIMARY), bgcolor=color))
