"""Генератор иконки приложения: курсивные «F1» на чёрном, красная гоночная полоса,
фрагмент шахматного флага. Это собственный знак приложения (не официальный логотип F1).

    python tools/make_icon.py

Создаёт:
  assets/icon.png          1024×1024 — Windows/macOS/Linux, сплэш
  assets/icon.ico          16–256 px — .exe
  assets/icon_android.png  1024×1024 на прозрачном фоне с полями под адаптивную иконку
                           (фон задаётся в pyproject.toml: tool.flet.android.adaptive_icon_background)
  assets/splash_android.png
Нужен Pillow (pip install pillow).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONT = ASSETS / "fonts" / "Exo2-ExtraBoldItalic.ttf"

RED = (225, 6, 0)
RED_GLOW = (255, 42, 31)
BLACK = (21, 21, 30)
WHITE = (255, 255, 255)
S = 1024


def mark(size=S, background=True, scale=1.0):
    """Сам знак. background=False — без чёрной подложки (для адаптивной иконки Android)."""
    big = size * 4                     # рисуем в 4× и уменьшаем — гладкие края
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if background:
        d.rounded_rectangle([0, 0, big - 1, big - 1], radius=int(big * 0.22), fill=BLACK + (255,))

    c = big / 2
    k = big * scale

    # красная гоночная полоса по диагонали, с градиентом
    band = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    h = k * 0.30
    skew = k * 0.18
    top = c - h / 2 + k * 0.06
    poly = [(c - k * 0.62 + skew, top), (c + k * 0.62 + skew, top),
            (c + k * 0.62 - skew, top + h), (c - k * 0.62 - skew, top + h)]
    bd.polygon(poly, fill=RED + (255,))
    grad = Image.new("RGBA", (big, big))
    gd = ImageDraw.Draw(grad)
    for y in range(big):
        t = y / big
        t = max(0.0, min(1.0, (t - 0.35) / 0.4))     # градиент только в пределах полосы
        col = tuple(int(RED_GLOW[i] * (1 - t) + RED[i] * t) for i in range(3))
        gd.line([(0, y), (big, y)], fill=col + (255,))
    band = Image.composite(grad, band, band.split()[3])
    # тонкие «линии скорости» над полосой
    for i, (w, off) in enumerate([(0.30, 0.10), (0.20, 0.17)]):
        y0 = top - k * off
        bd2 = ImageDraw.Draw(band)
        x0 = c - k * 0.55 + skew * 0.6 + i * k * 0.08
        bd2.polygon([(x0, y0), (x0 + k * w, y0), (x0 + k * w - k * 0.025, y0 + k * 0.035),
                     (x0 - k * 0.025, y0 + k * 0.035)], fill=RED + (255,))
    if background:
        mask = Image.new("L", (big, big), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, big - 1, big - 1], radius=int(big * 0.22), fill=255)
        band.putalpha(Image.composite(band.split()[3], Image.new("L", (big, big), 0), mask))
    img.alpha_composite(band)

    # шахматный фрагмент под полосой: 2 ряда клеток с наклоном, как у курсива
    cell = k * 0.06
    x0, y0 = c + k * 0.05, top + h + k * 0.07
    for row in range(2):
        for col in range(7):
            if (row + col) % 2:
                continue
            x = x0 + col * cell - row * cell * 0.4
            y = y0 + row * cell
            d.polygon([(x + cell * 0.4, y), (x + cell * 1.4, y), (x + cell, y + cell), (x, y + cell)],
                      fill=WHITE + (235,))

    # «F1» курсивом с тенью
    font = ImageFont.truetype(str(FONT), int(k * 0.56))
    text = "F1"
    box = d.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    tx, ty = c - tw / 2 - box[0] - k * 0.02, c - th / 2 - box[1] - k * 0.03
    shadow = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((tx + k * 0.015, ty + k * 0.02), text, font=font, fill=(0, 0, 0, 170))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(k * 0.02)))
    d = ImageDraw.Draw(img)
    d.text((tx, ty), text, font=font, fill=WHITE + (255,))
    return img.resize((size, size), Image.LANCZOS)


def main():
    icon = mark()
    icon.save(ASSETS / "icon.png")
    icon.save(ASSETS / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    # адаптивная иконка Android: система обрезает края, поэтому знак — в центральных ~60 %
    mark(background=False, scale=0.62).save(ASSETS / "icon_android.png")
    splash = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    splash.alpha_composite(mark(int(S * 0.5)), (S // 4, S // 4))
    splash.save(ASSETS / "splash_android.png")
    print("Иконки записаны в", ASSETS)


if __name__ == "__main__":
    main()
