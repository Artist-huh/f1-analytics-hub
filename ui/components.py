"""Переиспользуемые элементы интерфейса в стиле F1: карточки с анимацией, фото пилотов,
логотипы команд, флаги, бейджи позиций, графики."""
import flet as ft
import flet.canvas as cv

from design_system import *


class ResponsiveContainer:
    """Точки перелома ширины окна"""

    @staticmethod
    def get_layout_columns(page_width: float) -> int:
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
    width = getattr(state.page, "width", None)
    return width if isinstance(width, (int, float)) and width > 0 else default


def is_narrow(state):
    """Совсем узкое окно (< 400 px): компактные карточки."""
    return page_width(state) < 400


def content_width(state):
    """Ширина области контента (без полей), чтобы рисовать графики нужного размера."""
    return min(page_width(state), 1100) - 2 * SPACE_MD


# ---------------------------------------------------------------- анимации
class FadeIn(ft.Container):
    """Плавное появление: прозрачность и лёгкий сдвиг снизу. index задаёт «лесенку» —
    у каждого следующего элемента анимация чуть длиннее. При обычной перерисовке
    (enabled=False) элемент появляется сразу, без анимации."""

    def __init__(self, content, index=0, enabled=True, **kwargs):
        duration = ANIM_NORMAL + min(index, 10) * 45
        super().__init__(
            content=content,
            opacity=0 if enabled else 1,
            offset=ft.Offset(0, 0.04) if enabled else ft.Offset(0, 0),
            animate_opacity=ft.Animation(duration, ft.AnimationCurve.EASE_OUT) if enabled else None,
            animate_offset=ft.Animation(duration, ft.AnimationCurve.EASE_OUT_CUBIC) if enabled else None,
            **kwargs,
        )
        self._fade = enabled

    def did_mount(self):
        if self._fade:
            self._fade = False
            self.opacity = 1
            self.offset = ft.Offset(0, 0)
            try:
                self.update()
            except Exception:   # страница уже перестроена — не страшно
                pass


class AnimatedCard(ft.Container):
    """Карточка: тень, подъём и подсветка рамки при наведении, «рябь» при нажатии."""

    def __init__(self, content: ft.Control, on_click=None, elevation_end: int = 2, accent=None, **kwargs):
        kwargs.setdefault("padding", SPACE_MD)
        kwargs.setdefault("bgcolor", SURFACE)
        kwargs.setdefault("border_radius", RADIUS_MD)
        self._accent = accent or LINE_STRONG
        kwargs.setdefault("border", ft.Border.all(1, LINE))
        super().__init__(
            content=content,
            ink=on_click is not None,
            on_click=on_click,
            shadow=shadow(1),
            animate=ft.Animation(ANIM_FAST, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(ANIM_FAST, ft.AnimationCurve.EASE_OUT),
            **kwargs,
        )
        self._border = self.border
        self.elevation_end = elevation_end
        if on_click is not None:
            self.on_hover = self._handle_hover

    def _handle_hover(self, e):
        hovered = e.data in (True, "true")
        self.scale = 1.015 if hovered else 1.0
        self.shadow = shadow(self.elevation_end if hovered else 1)
        self.border = ft.Border.all(1, self._accent) if hovered else self._border
        self.update()


class GradientButton(ft.Container):
    """Главная кнопка: красный градиент F1, белый текст, свечение."""

    def __init__(self, text: str, team_name: str = None, on_click=None, icon=None, expand=False, **kwargs):
        colors = list(get_team_gradient(team_name)) if team_name else [ACCENT_GLOW, F1_RED, ACCENT_DEEP]
        items = []
        if icon:
            items.append(ft.Icon(icon, color=ON_ACCENT, size=20))
        items.append(ft.Text(text, size=FONT_BODY, weight=ft.FontWeight.W_700, color=ON_ACCENT,
                             font_family=FONT_HEADING))
        super().__init__(
            content=ft.Row(items, alignment=ft.MainAxisAlignment.CENTER, spacing=SPACE_XS, tight=not expand),
            gradient=ft.LinearGradient(begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT, colors=colors),
            border_radius=RADIUS_FULL,
            padding=ft.Padding.symmetric(horizontal=SPACE_LG, vertical=SPACE_SM),
            height=TOUCH,
            alignment=ft.Alignment.CENTER,
            ink=True,
            on_click=on_click,
            expand=expand,
            shadow=glow(),
            **kwargs,
        )


# ---------------------------------------------------------------- картинки
DECODE_SCALE = 3   # декодировать под экран до ×3 плотности — не в исходном размере (память и время)


def image(src, width=None, height=None, fit=ft.BoxFit.CONTAIN, fallback=None, **kwargs):
    """Картинка из кэша/сети; при ошибке или без источника — fallback."""
    if not src:
        return fallback or ft.Container(width=width, height=height)
    if height and not width:
        kwargs.setdefault("cache_height", int(height * DECODE_SCALE))
    elif width and not height:
        kwargs.setdefault("cache_width", int(width * DECODE_SCALE))
    elif width and height:
        side = "cache_width" if width >= height else "cache_height"   # одна сторона — пропорции сохраняются
        kwargs.setdefault(side, int(max(width, height) * DECODE_SCALE))
    return ft.Image(src=src, width=width, height=height, fit=fit, error_content=fallback,
                    gapless_playback=True, filter_quality=ft.FilterQuality.HIGH, **kwargs)


def initials(code, size, color=ON_COLOR):
    return ft.Text((code or "?")[:3].upper(), size=max(10, int(size / 3)), weight=ft.FontWeight.BOLD,
                   color=color, font_family=FONT_DISPLAY_ITALIC)


class DriverAvatar(ft.Container):
    """Круглый портрет пилота на градиенте цвета команды; без фото — код пилота."""

    def __init__(self, driver_code: str, team_name: str, size: int = 48, src=None, on_click=None, ring=True,
                 **kwargs):
        top, bottom = get_team_gradient(team_name)
        fallback = ft.Container(initials(driver_code, size), alignment=ft.Alignment.CENTER,
                                width=size, height=size)
        super().__init__(
            content=image(src, size, size, fit=ft.BoxFit.COVER, fallback=fallback) if src else fallback,
            width=size,
            height=size,
            gradient=ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER,
                                       colors=[top, bottom]),
            border_radius=size / 2,
            border=ft.Border.all(2, top) if ring else None,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            alignment=ft.Alignment.CENTER,
            on_click=on_click,
            **kwargs,
        )


def flag(src, height=14, code=""):
    """Флаг страны 4:3 со скруглением; без картинки — ISO-код."""
    width = round(height * 4 / 3)
    fallback = ft.Container(ft.Text(code.upper(), size=max(8, height * 0.55), color=TEXT_MUTED,
                                    weight=ft.FontWeight.BOLD),
                            width=width, height=height, alignment=ft.Alignment.CENTER,
                            bgcolor=SURFACE_ELEVATED, border_radius=2)
    if not src:
        return fallback if code else ft.Container(width=0)
    return ft.Container(image(src, width, height, fit=ft.BoxFit.COVER, fallback=fallback),
                        width=width, height=height, border_radius=3, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        border=ft.Border.all(0.5, ft.Colors.with_opacity(0.25, TEXT_DIM)))


class TeamLogo(ft.Container):
    """Белый логотип команды на квадрате цвета команды; без логотипа — первая буква."""

    def __init__(self, team_name, src=None, size=40, **kwargs):
        top, bottom = get_team_gradient(team_name)
        fallback = ft.Text((team_name or "?")[:1].upper(), size=size * 0.45, color=ON_COLOR,
                           weight=ft.FontWeight.BOLD, font_family=FONT_HEADING)
        super().__init__(
            content=image(src, size * 0.72, size * 0.72, fallback=fallback) if src else fallback,
            width=size, height=size,
            gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                       colors=[top, bottom]),
            border_radius=size * 0.28,
            alignment=ft.Alignment.CENTER,
            **kwargs,
        )


class PositionBadge(ft.Container):
    """Позиция: золото/серебро/бронза для подиума, курсивные цифры как на табло F1."""

    def __init__(self, position, size: int = 32, **kwargs):
        try:
            pos = int(position)
        except (TypeError, ValueError):
            pos = 0
        podium = pos in POSITION_COLORS
        super().__init__(
            content=ft.Text(str(pos) if pos else "—", size=size * 0.5, color=INK if podium else TEXT_PRIMARY,
                            font_family=FONT_DISPLAY_ITALIC),
            width=size,
            height=size,
            bgcolor=POSITION_COLORS[pos] if podium else SURFACE_RAISED,
            border_radius=RADIUS_SM,
            alignment=ft.Alignment.CENTER,
            **kwargs,
        )


class StatCard(ft.Container):
    """Карточка показателя: иконка, крупное число, подпись."""

    def __init__(self, label: str, value: str, icon=None, color: str = TEXT_PRIMARY, subtitle: str = None,
                 compact: bool = False, **kwargs):
        items = []
        if icon:
            items.append(ft.Icon(icon, color=color, size=18 if compact else 20))
        items += [
            ft.Text(str(value), size=FONT_H4 if compact else FONT_H3, color=color,
                    font_family=FONT_DISPLAY_ITALIC, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(label, size=FONT_CAPTION, color=TEXT_MUTED, text_align=ft.TextAlign.CENTER, max_lines=2),
        ]
        if subtitle:
            items.append(ft.Text(subtitle, size=FONT_CAPTION, color=TEXT_DIM, text_align=ft.TextAlign.CENTER,
                                 max_lines=1, overflow=ft.TextOverflow.ELLIPSIS))
        kwargs.setdefault("expand", True)
        super().__init__(
            content=ft.Column(items, spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=SURFACE,
            border_radius=RADIUS_MD,
            padding=ft.Padding.symmetric(horizontal=SPACE_XS, vertical=SPACE_SM),
            border=ft.Border.all(1, LINE),
            **kwargs,
        )


class SectionHeader(ft.Container):
    """Заголовок секции: красная полоска слева, как в графике F1, и кнопка действия."""

    def __init__(self, title: str, subtitle: str = None, action_text: str = None, on_action=None, **kwargs):
        title_column = [ft.Text(title.upper(), size=FONT_BODY_LARGE, color=TEXT_PRIMARY, font_family=FONT_ITALIC)]
        if subtitle:
            title_column.append(ft.Text(subtitle, size=FONT_BODY_SMALL, color=TEXT_MUTED))
        row = [ft.Container(width=4, height=22, bgcolor=F1_RED, border_radius=2),
               ft.Column(title_column, spacing=0, expand=True)]
        if action_text and on_action:
            row.append(ft.Container(
                ft.Row([ft.Text(action_text, size=FONT_BODY_SMALL, color=ACCENT_TEXT, weight=ft.FontWeight.W_600),
                        ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=ACCENT_TEXT, size=18)], spacing=0, tight=True),
                on_click=on_action, ink=True, border_radius=RADIUS_SM,
                padding=ft.Padding.symmetric(horizontal=SPACE_XS, vertical=SPACE_XS)))
        super().__init__(
            content=ft.Row(row, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=SPACE_XS),
            padding=ft.Padding.only(top=SPACE_SM),
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
    if vertical:
        return ft.Container(width=1, height=36, bgcolor=LINE)
    return ft.Container(height=1, bgcolor=LINE)


def show_snack(page, message: str, color: str = SURFACE_ELEVATED):
    """Короткое уведомление внизу окна"""
    page.show_dialog(ft.SnackBar(content=ft.Text(message, color=TEXT_PRIMARY), bgcolor=color))


def star_button(active, on_click, size=22):
    """Звёздочка избранного с зоной нажатия 48 px."""
    return ft.IconButton(
        icon=ft.Icons.STAR_ROUNDED if active else ft.Icons.STAR_BORDER_ROUNDED,
        icon_color=GOLD if active else TEXT_DIM, icon_size=size,
        tooltip="Убрать из избранного" if active else "В избранное",
        on_click=on_click, width=TOUCH, height=TOUCH,
    )


# ---------------------------------------------------------------- графики
def line_chart(series, labels, width, height=200, y_suffix=""):
    """Линейный график на canvas. series — [(подпись, цвет, [значения]), ...] одинаковой длины,
    labels — подписи оси X. Сетка по Y из 4 линий, точка и значение на конце каждой линии."""
    width = max(200, width)
    left, right, top, bottom = 34, 44, 10, 22
    plot_w, plot_h = width - left - right, height - top - bottom
    n = max((len(v) for _, _, v in series), default=0)
    peak = max((max(v) for _, _, v in series if v), default=0) or 1
    step = _nice_step(peak / 4)
    peak = step * 4

    def x(i):
        return left + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)

    def y(v):
        return top + plot_h * (1 - v / peak)

    shapes = []
    grid = ft.Paint(color=LINE, stroke_width=1, style=ft.PaintingStyle.STROKE)
    label_style = ft.TextStyle(size=10, color=TEXT_DIM)
    for k in range(5):
        value = step * k
        shapes.append(cv.Line(left, y(value), left + plot_w, y(value), paint=grid))
        shapes.append(cv.Text(left - 6, y(value), f"{value:g}", style=label_style,
                              alignment=ft.Alignment.CENTER_RIGHT))
    every = max(1, n // 8)
    for i, label in enumerate(labels):
        if i % every == 0 or i == n - 1:
            shapes.append(cv.Text(x(i), height - 4, str(label), style=label_style,
                                  alignment=ft.Alignment.BOTTOM_CENTER))
    for idx, (name, color, values) in enumerate(series):
        if not values:
            continue
        dashed = [6, 4] if idx >= 1 and any(c == color for _, c, _ in series[:idx]) else None
        paint = ft.Paint(color=color, stroke_width=2.5, style=ft.PaintingStyle.STROKE,
                         stroke_cap=ft.StrokeCap.ROUND, stroke_join=ft.StrokeJoin.ROUND,
                         stroke_dash_pattern=dashed)
        elements = [cv.Path.MoveTo(x(0), y(values[0]))] + [cv.Path.LineTo(x(i), y(v)) for i, v in enumerate(values)]
        shapes.append(cv.Path(elements, paint=paint))
        shapes.append(cv.Circle(x(len(values) - 1), y(values[-1]), 4, paint=ft.Paint(color=color)))
        shapes.append(cv.Text(x(len(values) - 1) + 7, y(values[-1]), f"{values[-1]:g}{y_suffix}",
                              style=ft.TextStyle(size=11, color=color, weight=ft.FontWeight.BOLD),
                              alignment=ft.Alignment.CENTER_LEFT))
    return cv.Canvas(shapes=shapes, width=width, height=height)


def _nice_step(raw):
    """Круглый шаг сетки: 1, 2, 5, 10, 20, 50, ..."""
    if raw <= 0:
        return 1
    magnitude = 10 ** (len(str(int(raw))) - 1)
    for k in (1, 2, 5, 10):
        if raw <= k * magnitude:
            return k * magnitude
    return 10 * magnitude


def legend(series):
    """Подписи к линиям графика."""
    return ft.Row([
        ft.Row([ft.Container(width=14, height=4, bgcolor=color, border_radius=2),
                ft.Text(name, size=FONT_CAPTION, color=TEXT_SECONDARY)], spacing=6, tight=True)
        for name, color, _ in series
    ], wrap=True, spacing=SPACE_SM, run_spacing=SPACE_XXS)


def series_chart(series, width, height=240, y_min=None, y_max=None, invert=False, y_format=None, ticks=5,
                 end_labels=True):
    """График по точкам (x, y) на canvas. series — [(подпись, цвет, [(x, y), ...], толщина)].
    invert=True — меньшие значения сверху (позиции: P1 вверху). Ось Y не обязана начинаться с нуля
    (время круга). y_format(v) — подпись делений; end_labels — значение у конца каждой линии."""
    width = max(220, width)
    left, right, top, bottom = 40, 46 if end_labels else 12, 10, 22
    plot_w, plot_h = width - left - right, height - top - bottom
    xs = [x for *_, pts, _w in series for x, _ in pts]
    ys = [y for *_, pts, _w in series for _, y in pts]
    if not xs:
        return ft.Container(height=height)
    x0, x1 = min(xs), max(xs)
    lo = y_min if y_min is not None else min(ys)
    hi = y_max if y_max is not None else max(ys)
    if hi == lo:
        hi = lo + 1
    fmt = y_format or (lambda v: f"{v:g}")

    def x(v):
        return left + plot_w * ((v - x0) / (x1 - x0) if x1 > x0 else 0.5)

    def y(v):
        frac = (v - lo) / (hi - lo)
        return top + plot_h * (frac if invert else 1 - frac)

    shapes = []
    grid = ft.Paint(color=LINE, stroke_width=1, style=ft.PaintingStyle.STROKE)
    label_style = ft.TextStyle(size=10, color=TEXT_DIM)
    for k in range(ticks):
        v = lo + (hi - lo) * k / (ticks - 1)
        shapes.append(cv.Line(left, y(v), left + plot_w, y(v), paint=grid))
        shapes.append(cv.Text(left - 6, y(v), fmt(v), style=label_style, alignment=ft.Alignment.CENTER_RIGHT))
    span = x1 - x0
    step = max(1, round(span / 6 / 5) * 5) if span > 10 else 1
    for v in range(int(x0), int(x1) + 1):
        if (v - x0) % step == 0 or v == x1:
            if v == x1 or x1 - v >= step / 2:
                shapes.append(cv.Text(x(v), height - 4, str(v), style=label_style,
                                      alignment=ft.Alignment.BOTTOM_CENTER))
    for name, color, pts, line_w in series:
        if not pts:
            continue
        paint = ft.Paint(color=color, stroke_width=line_w, style=ft.PaintingStyle.STROKE,
                         stroke_cap=ft.StrokeCap.ROUND, stroke_join=ft.StrokeJoin.ROUND)
        elements = [cv.Path.MoveTo(x(pts[0][0]), y(pts[0][1]))] + [cv.Path.LineTo(x(a), y(b)) for a, b in pts[1:]]
        shapes.append(cv.Path(elements, paint=paint))
        if end_labels and line_w >= 2:
            ex, ey = pts[-1]
            shapes.append(cv.Circle(x(ex), y(ey), 3.5, paint=ft.Paint(color=color)))
            shapes.append(cv.Text(x(ex) + 6, y(ey), name, style=ft.TextStyle(size=10, color=color,
                                                                            weight=ft.FontWeight.BOLD),
                                  alignment=ft.Alignment.CENTER_LEFT))
    return cv.Canvas(shapes=shapes, width=width, height=height)


def fmt_lap(seconds):
    """97.3 -> '1:37.300'."""
    if seconds is None:
        return "—"
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:06.3f}"
