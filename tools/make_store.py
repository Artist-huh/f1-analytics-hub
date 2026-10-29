"""Материалы для магазинов приложений (Google Play, RuStore, App Store): баннер и экраны витрины с подписями.

    python tools/make_store.py <папка со снимками> [контур.json]

Снимки — экраны телефонного размера (скил /shots): 1_home, 2_live, 3_season, 4_drivers, 5_compare (.png).
Создаёт docs/store/:
  feature.png          1024×500 — баннер Google Play / RuStore
  screen_1…5.png       1080×1920 — экраны витрины: подпись сверху, телефон снизу
  store.pdf            то же для Canva: телефон — картинкой, подписи — редактируемым текстом (если есть reportlab)
Нужен Pillow; для store.pdf — reportlab.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.make_cover import carbon, outline_layer, phone  # noqa: E402
from tools.make_icon import gantry  # noqa: E402

OUT = ROOT / "docs" / "store"
FONTS = ROOT / "assets" / "fonts"
TEXT, SECONDARY = (255, 255, 255), (210, 210, 220)

# что показывает экран -> (заголовок, пояснение). Обычным языком, от лица пользователя.
SCREENS = [
    ("1_home", "До старта — огни и трасса", "Горит по огню за каждый день до гонки"),
    ("2_live", "Live Timing в эфире", "Позиции, отрывы, шины и секторы"),
    ("3_season", "Таблица как на трансляции", "Полоса цвета команды у каждого пилота"),
    ("4_drivers", "Все пилоты сезона", "Очки, победы и подиумы в цветах команд"),
    ("5_compare", "Сравни любых пилотов", "Очки, поулы и личные встречи бок о бок"),
]
SW, SH = 1080, 1920
CAPTION_H = 420          # верх экрана под подпись


def _font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def _wrap(draw, text, font, width):
    words, lines, line = text.split(), [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if draw.textlength(test, font=font) <= width:
            line = test
        else:
            lines.append(line)
            line = w
    return lines + [line]


def screen_background(shot):
    """Экран витрины без подписи (для PPTX: подпись добавится текстом поверх)."""
    img = carbon(SW, SH)
    ph = phone(shot, SH - CAPTION_H + 260)                 # низ телефона уходит за край — как в витринах
    x = (SW - ph.width) // 2
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([x + 20, CAPTION_H + 40, x + ph.width - 20, SH + 300],
                                             radius=110, fill=(0, 0, 0, 170))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(40)))
    img.alpha_composite(ph, (x, CAPTION_H))
    return img


def _title_size(title):
    """Размер заголовка в пикселях: от 76 вниз, пока не встанет в одну строку."""
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    size = 76
    while size > 56 and d.textlength(title, font=_font("Exo2-ExtraBoldItalic.ttf", size)) > SW - 140:
        size -= 2
    return size


def with_caption(img, title, sub):
    d = ImageDraw.Draw(img)
    tf, sf = _font("Exo2-ExtraBoldItalic.ttf", _title_size(title)), _font("Exo2-SemiBold.ttf", 38)
    y = 120
    for line in _wrap(d, title, tf, SW - 140):
        d.text((SW / 2, y), line, font=tf, fill=TEXT, anchor="mt")
        y += 92
    y += 18
    for line in _wrap(d, sub, sf, SW - 180):
        d.text((SW / 2, y), line, font=sf, fill=SECONDARY, anchor="mt")
        y += 52
    return img


def feature(outline):
    """Баннер 1024×500: огни и название слева, контур трассы справа."""
    w, h, ss = 1024, 500, 2
    img = carbon(w * ss, h * ss)
    if outline:
        # правее текста: точка старта не должна наезжать на название
        layer = outline_layer(outline, (round(w * ss * 0.62), 50 * ss, round(w * ss * 0.36), h * ss - 100 * ss))
        img.alpha_composite(layer.crop((0, 0, w * ss, h * ss)))
    lights, _ = gantry(h * ss, 300 * ss, cy=130 * ss)
    img.alpha_composite(lights, (70 * ss - (h * ss - 300 * ss) // 2, 0))
    d = ImageDraw.Draw(img)
    d.text((70 * ss, 205 * ss), "F1 Analytics Hub", font=_font("Exo2-ExtraBoldItalic.ttf", 64 * ss), fill=TEXT)
    d.text((70 * ss, 300 * ss), "Чемпионат, Live Timing и радио команд", font=_font("Exo2-SemiBold.ttf", 28 * ss),
           fill=SECONDARY)
    d.text((70 * ss, 342 * ss), "на телефоне и компьютере", font=_font("Exo2-SemiBold.ttf", 28 * ss), fill=SECONDARY)
    return img.resize((w, h), Image.LANCZOS)


def pdf(backgrounds, feature_png):
    """store.pdf для Canva: экран — картинкой, подписи — настоящим текстом (в Canva их можно править).
    Первая страница — баннер. PPTX загрузка в Canva не принимает, PDF — принимает и делает редактируемым."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except ImportError:
        print("reportlab не установлен — store.pdf пропущен")
        return
    pdfmetrics.registerFont(TTFont("Exo2XBI", str(FONTS / "Exo2-ExtraBoldItalic.ttf")))
    pdfmetrics.registerFont(TTFont("Exo2Semi", str(FONTS / "Exo2-SemiBold.ttf")))
    c = canvas.Canvas(str(OUT / "store.pdf"))
    c.setPageSize((1024, 500))                             # 1 пункт PDF = 1 пиксель картинки
    c.drawImage(str(feature_png), 0, 0, 1024, 500)
    c.showPage()
    for (_name, title, sub), bg in zip(SCREENS, backgrounds, strict=True):
        c.setPageSize((SW, SH))
        c.drawImage(str(bg), 0, 0, SW, SH)
        c.setFillColorRGB(*(v / 255 for v in TEXT))
        c.setFont("Exo2XBI", _title_size(title))
        c.drawCentredString(SW / 2, SH - 120 - _title_size(title) * 0.8, title)
        c.setFillColorRGB(*(v / 255 for v in SECONDARY))
        c.setFont("Exo2Semi", 38)
        c.drawCentredString(SW / 2, SH - 250, sub)
        c.showPage()
    c.save()
    print("store.pdf: баннер и экраны с редактируемыми подписями")


def main():
    shots = Path(sys.argv[1])
    outline = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")) if len(sys.argv) > 2 else None
    OUT.mkdir(parents=True, exist_ok=True)
    feature(outline).convert("RGB").save(OUT / "feature.png", optimize=True)
    backgrounds = []
    for i, (name, title, sub) in enumerate(SCREENS, 1):
        bg = screen_background(shots / f"{name}.png")
        raw = OUT / f"_bg_{i}.png"                        # для PDF — без подписи (её кладём текстом)
        bg.convert("RGB").save(raw, optimize=True)
        backgrounds.append(raw)
        with_caption(bg, title, sub).convert("RGB").save(OUT / f"screen_{i}.png", optimize=True)
    pdf(backgrounds, OUT / "feature.png")
    for raw in backgrounds:
        raw.unlink()
    print("готово:", OUT)


if __name__ == "__main__":
    main()
