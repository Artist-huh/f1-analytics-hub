"""Генератор знака приложения: пять горящих стартовых огней на карбоне — момент перед «lights out».
Тот же мотив, что у героя главной экрана (ui/screens/home.py, start_lights). Собственный знак
приложения, не логотип Формулы-1.

    python tools/make_icon.py

Создаёт:
  assets/icon.png          1024×1024 — Windows/macOS/Linux, iPhone, web (flet build берёт icon.*)
  assets/icon.ico          16–256 px — .exe
  assets/icon_android.png  1024×1024 на прозрачном фоне с полями под адаптивную иконку
                           (фон задаётся в pyproject.toml: tool.flet.android.adaptive_icon_background)
  assets/splash.png        заставка при запуске (Android, iPhone, web): огни на прозрачном фоне,
                           фон заставки — tool.flet.splash.color
Нужен Pillow (pip install pillow).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

CARBON_TOP, CARBON_BOTTOM = (42, 42, 55), (16, 16, 22)   # design_system.HERO_CARBON
HOUSING = (5, 5, 7)                                     # LIGHT_HOUSING
LIT = (255, 30, 16)                                     # LIGHT_ON
S = 1024
LIGHTS = 5


def _carbon(big, radius):
    """Подложка: вертикальный градиент карбона со скруглёнными углами."""
    grad = Image.new("RGBA", (big, big))
    gd = ImageDraw.Draw(grad)
    for y in range(big):
        t = y / (big - 1)
        gd.line([(0, y), (big, y)], fill=tuple(round(CARBON_TOP[i] * (1 - t) + CARBON_BOTTOM[i] * t)
                                               for i in range(3)) + (255,))
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, big - 1, big - 1], radius=radius, fill=255)
    grad.putalpha(mask)
    # тонкая светлая обводка (как у карточки героя): на тёмной панели задач край не сливается с фоном
    edge = max(2, big // 128)
    ImageDraw.Draw(grad).rounded_rectangle([edge // 2, edge // 2, big - 1 - edge // 2, big - 1 - edge // 2],
                                           radius=radius, outline=(255, 255, 255, 34), width=edge)
    return grad


def gantry(big, width, cy=None):
    """Пять горящих огней в общем корпусе (один ряд — на 16 px это пять ясных точек). -> RGBA big×big."""
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    lens_gap = width * 0.035
    pad = width * 0.045
    lens = (width - 2 * pad - lens_gap * (LIGHTS - 1)) / LIGHTS
    h = lens + 2 * pad
    x0, y0 = (big - width) / 2, (cy if cy is not None else big / 2) - h / 2
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0, y0, x0 + width, y0 + h], radius=h * 0.5, fill=HOUSING + (255,))
    centers = [(x0 + pad + lens / 2 + i * (lens + lens_gap), y0 + h / 2) for i in range(LIGHTS)]
    glow = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for cx, cy in centers:
        r = lens / 2 * 1.35
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=LIT + (200,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(lens * 0.28)))   # свечение, как glow() в приложении
    d = ImageDraw.Draw(img)
    for cx, cy in centers:
        r = lens / 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=LIT + (255,))
        # блик на стекле: светлее того же красного, а не серое пятно
        hr = r * 0.42
        hx, hy = cx - r * 0.28, cy - r * 0.30
        d.ellipse([hx - hr, hy - hr * 0.7, hx + hr, hy + hr * 0.7], fill=(255, 92, 70, 255))
    return img, y0 + h


def chequer(img, x0, y0, width, rows=2, cols=9):
    """Клетчатая полоса финиша с наклоном, как у курсива Exo 2."""
    d = ImageDraw.Draw(img)
    cell = width / cols
    for row in range(rows):
        for col in range(cols):
            if (row + col) % 2:
                continue
            x = x0 + col * cell - row * cell * 0.35
            y = y0 + row * cell
            d.polygon([(x + cell * 0.35, y), (x + cell * 1.35, y), (x + cell, y + cell), (x, y + cell)],
                      fill=(255, 255, 255, 230))


def mark(size=S, background=True, scale=1.0):
    """Знак. background=False — без подложки (адаптивная иконка Android, заставка)."""
    big = size * 4                                       # рисуем в 4× и уменьшаем — гладкие края
    img = _carbon(big, int(big * 0.22)) if background else Image.new("RGBA", (big, big), (0, 0, 0, 0))
    if not background:                                   # адаптивная иконка и заставка: только огни
        img.alpha_composite(gantry(big, big * 0.80 * scale)[0])
        return img.resize((size, size), Image.LANCZOS)
    lights, bottom = gantry(big, big * 0.80 * scale, cy=big * 0.44)
    img.alpha_composite(lights)
    w = big * 0.54
    chequer(img, (big - w) / 2 + big * 0.03, bottom + big * 0.075, w)
    return img.resize((size, size), Image.LANCZOS)


def main():
    icon = mark()
    icon.save(ASSETS / "icon.png")
    icon.save(ASSETS / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    # адаптивная иконка Android: система обрезает края, поэтому знак — в центральных ~60 %
    mark(background=False, scale=0.70).save(ASSETS / "icon_android.png")
    # заставка Android 12 тоже показывает знак в круге — огни занимают его середину
    mark(background=False, scale=0.62).save(ASSETS / "splash.png")
    old = ASSETS / "splash_android.png"                  # прежнее имя: flet build взял бы его для Android
    if old.exists():
        old.unlink()
    print("Иконки и заставка записаны в", ASSETS)


if __name__ == "__main__":
    main()
