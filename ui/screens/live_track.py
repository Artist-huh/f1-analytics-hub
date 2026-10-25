"""Live Timing, вкладка «Трасса»: контур трассы и точки пилотов.

Контур — canvas (рисуется один раз), точки — постоянные элементы поверх него с анимированной позицией:
снимок приходит раз в 5 секунд, а точка за это время плавно доезжает до нового места, а не прыгает.
"""
import contextlib

import flet as ft
import flet.canvas as cv

from design_system import *
from services import track_map
from ui.components import *

DOT = 14
CONTENT_PAD = 2 * SPACE_SM


class TrackMap:
    def __init__(self, state, data, outline, width):
        self.key = data.get("circuit_key")
        self.width = width
        self.height = track_map.fitted_height(outline, width)
        self.to_screen = track_map.project(outline, width, self.height)
        pts = [self.to_screen(x, y) for x, y in zip(outline["x"], outline["y"], strict=True)]
        path = [cv.Path.MoveTo(*pts[0])] + [cv.Path.LineTo(*p) for p in pts[1:]] + [cv.Path.Close()]
        shapes = [
            cv.Path(path, paint=ft.Paint(color=LINE_STRONG, stroke_width=9, style=ft.PaintingStyle.STROKE,
                                         stroke_join=ft.StrokeJoin.ROUND)),
            cv.Path(path, paint=ft.Paint(color=SURFACE_RAISED, stroke_width=4, style=ft.PaintingStyle.STROKE,
                                         stroke_join=ft.StrokeJoin.ROUND)),
            cv.Circle(*pts[0], 5, paint=ft.Paint(color=TEXT_PRIMARY)),            # старт / финиш
        ]
        for number, x, y in outline.get("corners") or []:
            px, py = self.to_screen(x, y)
            shapes.append(cv.Text(px + 6, py - 6, str(number),
                                  style=ft.TextStyle(size=9, color=TEXT_DIM, weight=ft.FontWeight.BOLD)))
        self.dots = {}
        layers = [cv.Canvas(shapes=shapes, width=width, height=self.height)]
        for number, info in (data.get("drivers") or {}).items():
            color = f"#{info['colour']}" if info.get("colour") else TEXT_DIM
            dot = ft.Container(
                ft.Row([ft.Container(width=DOT, height=DOT, border_radius=DOT / 2, bgcolor=color,
                                     border=ft.Border.all(2, TEXT_PRIMARY)),
                        ft.Text(info.get("code") or number, size=9, color=TEXT_PRIMARY, font_family=FONT_ITALIC)],
                       spacing=2, tight=True),
                left=0, top=0, visible=False, tooltip=info.get("code") or number,
                animate_position=anim(ANIM_GLIDE, ft.AnimationCurve.LINEAR))
            self.dots[str(number)] = dot
            layers.append(dot)
        self.stack = ft.Stack(layers, width=width, height=self.height)
        self.apply(data)

    def matches(self, data):
        return data.get("circuit_key") == self.key and set(map(str, (data.get("drivers") or {}))) == set(self.dots)

    def apply(self, data):
        """Новые позиции машин; -> сколько точек на трассе."""
        positions = data.get("positions") or {}
        shown = 0
        for number, dot in self.dots.items():
            p = positions.get(number)
            if not p or (p["x"] == 0 and p["y"] == 0):
                dot.visible = False
                continue
            px, py = self.to_screen(p["x"], p["y"])
            dot.left, dot.top, dot.visible = px - DOT / 2, py - DOT / 2, True
            dot.opacity = 0.45 if p.get("status") and p["status"] != "OnTrack" else 1
            shown += 1
        return shown

    def update(self):
        with contextlib.suppress(RuntimeError, AssertionError, AttributeError):   # экран уже перестроен
            self.stack.update()


def track_section(state, data):
    """Вкладка «Трасса»: контур из кэша (или загрузка) и точки пилотов."""
    from services import archive
    key, year = data.get("circuit_key"), data["session"].get("year") or 0
    if not key:
        return [empty_block(ft.Icons.MAP_ROUNDED, "Схема трассы недоступна",
                            "Поток F1 не сообщил, на какой трассе сессия.", art="track")]
    store = track_map.outline_key(key)
    fetch = lambda: track_map.fetch_outline(key, int(year))
    outline = archive.get(store, fetch, None, state.render)
    if not outline:
        if archive.loading(store):
            return [skeleton("Загружаем схему трассы…", "chart")]
        return [empty_block(ft.Icons.REFRESH_ROUNDED, "Схема трассы не загружена", "Нужен интернет.",
                            ("Повторить", lambda e: (archive.get(store, fetch, None, state.render, force=True),
                                                    state.render())), art="track")]
    width = max(240, content_width(state) - CONTENT_PAD)
    table = TrackMap(state, data, outline, width)
    state.ui["live_track"] = table
    on_track = sum(1 for d in table.dots.values() if d.visible)
    note = (f"На трассе: {on_track}. Точки обновляются раз в 5 секунд и плавно доезжают до нового места."
            if on_track else "Точки пилотов появятся во время сессии — поток F1 отдаёт позиции машин только в эфире.")
    return [AnimatedCard(table.stack, size="m"),
            ft.Text(note, size=FONT_CAPTION, color=TEXT_DIM),
            ft.Text("Контур трассы — MultiViewer API.", size=FONT_CAPTION, color=TEXT_DIM)]
