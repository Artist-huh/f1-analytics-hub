"""Обложка для README и превью репозитория на GitHub (1280×640): название, стартовые огни,
главный экран в рамке телефона и контур трассы ближайшего этапа.

    python tools/make_cover.py <скриншот главной.png> [контур.json]

Скриншот — снимок окна телефонного размера (скил /shots: `shoot.sh <папка> home tab0`), полоса заголовка
окна обрезается. Контур — {x, y, rotation} из services.track_map (кэш archive), без него — только телефон.
Создаёт docs/cover.png. Нужен Pillow.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services import track_map  # noqa: E402
from tools.make_icon import gantry  # noqa: E402

W, H = 1280, 640
SS = 2                                     # рисуем в 2× и уменьшаем — гладкие края
CARBON_TOP, CARBON_BOTTOM = (42, 42, 55), (16, 16, 22)
TEXT, SECONDARY, MUTED = (255, 255, 255), (210, 210, 220), (171, 171, 184)
LIT = (255, 30, 16)
FONTS = ROOT / "assets" / "fonts"
TITLEBAR = 40                              # полоса заголовка окна Windows на снимке (при масштабе 125 %)


def carbon(w, h):
    img = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        d.line([(0, y), (w, y)], fill=tuple(round(CARBON_TOP[i] * (1 - t) + CARBON_BOTTOM[i] * t)
                                            for i in range(3)) + (255,))
    return img


def outline_layer(outline, box):
    """Контур трассы белой линией (как на герое главной), точка старта — красная."""
    x0, y0, w, h = box
    to_screen = track_map.project(outline, w, h, pad=10 * SS)
    pts = [(x0 + px, y0 + py) for px, py in (to_screen(x, y) for x, y in zip(outline["x"], outline["y"],
                                                                                 strict=True))]
    layer = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.line(pts + [pts[0]], fill=(255, 255, 255, 70), width=5 * SS, joint="curve")
    sx, sy = pts[0]
    d.ellipse([sx - 9 * SS, sy - 9 * SS, sx + 9 * SS, sy + 9 * SS], fill=LIT + (255,))
    return layer


def phone(shot_path, height):
    """Снимок главной в рамке телефона: чёрный корпус, скругления, мягкая тень."""
    shot = Image.open(shot_path).convert("RGBA")
    shot = shot.crop((0, TITLEBAR, shot.width, shot.height))
    bezel = 14 * SS
    inner_h = height - 2 * bezel
    inner_w = round(shot.width * inner_h / shot.height)
    shot = shot.resize((inner_w, inner_h), Image.LANCZOS)
    w = inner_w + 2 * bezel
    body = Image.new("RGBA", (w, height), (0, 0, 0, 0))
    ImageDraw.Draw(body).rounded_rectangle([0, 0, w - 1, height - 1], radius=58 * SS, fill=(6, 6, 9, 255),
                                           outline=(255, 255, 255, 40), width=2 * SS)
    mask = Image.new("L", (inner_w, inner_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, inner_w - 1, inner_h - 1], radius=44 * SS, fill=255)
    body.paste(shot, (bezel, bezel), mask)
    return body


def main():
    shot = sys.argv[1]
    outline = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")) if len(sys.argv) > 2 else None
    img = carbon(W * SS, H * SS)

    # справа: контур трассы за телефоном, телефон с тенью
    ph = phone(shot, round(H * SS * 1.12))
    px, py = W * SS - ph.width - 110 * SS, round(H * SS * 0.10)
    if outline:
        # правая половина, за телефоном: линия трассы не должна пересекать текст слева
        img.alpha_composite(outline_layer(outline, (round(W * SS * 0.55), 30 * SS, round(W * SS * 0.44),
                                                    H * SS - 60 * SS)))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([px + 20 * SS, py + 30 * SS, px + ph.width, py + ph.height],
                                             radius=60 * SS, fill=(0, 0, 0, 160))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(30 * SS)))
    img.alpha_composite(ph, (px, py))

    # слева: огни, название, что умеет, где работает
    left = 84 * SS
    lights, _ = gantry(H * SS, 300 * SS, cy=150 * SS)
    img.alpha_composite(lights.crop((0, 0, H * SS, H * SS)), (left - (H * SS - 300 * SS) // 2, 0))
    d = ImageDraw.Draw(img)
    title = ImageFont.truetype(str(FONTS / "Exo2-ExtraBoldItalic.ttf"), 78 * SS)
    body = ImageFont.truetype(str(FONTS / "Exo2-SemiBold.ttf"), 30 * SS)
    small = ImageFont.truetype(str(FONTS / "Exo2-SemiBold.ttf"), 24 * SS)
    d.text((left, 222 * SS), "F1 Analytics Hub", font=title, fill=TEXT)
    d.text((left, 336 * SS), "Чемпионат, Live Timing и радио команд", font=body, fill=SECONDARY)
    d.text((left, 378 * SS), "в одном приложении", font=body, fill=SECONDARY)
    d.text((left, 470 * SS), "Windows, macOS, Android, iPhone", font=small, fill=MUTED)

    out = ROOT / "docs" / "cover.png"
    img.resize((W, H), Image.LANCZOS).convert("RGB").save(out, optimize=True)
    print("обложка:", out)


if __name__ == "__main__":
    main()
