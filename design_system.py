"""F1 Analytics Hub — дизайн-система.

Фирменные цвета Формулы-1: красный #E10600 на угольно-чёрном #15151E, белый текст,
тёмно-серые поверхности и лёгкие красные градиенты. Цифры и заголовки — Exo 2
(есть кириллица), основной текст — системный шрифт.
"""

# === ПОВЕРХНОСТИ ===
BG_DEEPEST = "#000000"       # навигация, самый глубокий фон
BG_DEEP = "#0B0B10"
BG = "#15151E"               # фон страницы — фирменный «carbon black» F1
SURFACE = "#1E1E29"          # карточки
SURFACE_RAISED = "#272733"   # поднятые элементы, чипы
SURFACE_ELEVATED = "#31313E" # диалоги, выбранные элементы

LINE_SUBTLE = "#23232E"
LINE = "#2D2D3A"
LINE_STRONG = "#41414F"

# === ТЕКСТ ===
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#D2D2DC"
TEXT_MUTED = "#ABABB8"
TEXT_DIM = "#8E8E9C"
SECTOR_OVERALL, SECTOR_PERSONAL, SECTOR_NORMAL = "#A855F7", "#22C55E", "#F5C518"

# === АКЦЕНТ: F1 RED ===
F1_RED = "#E10600"
ACCENT_PRIMARY = F1_RED
ACCENT_GLOW = "#FF2A1F"      # ярче — hover, свечение
ACCENT_DEEP = "#8E0400"      # темнее — конец градиента
ACCENT_TEXT = "#FF5A4F"      # красный для мелкого текста (контраст ≥ 4.5:1 на тёмном)
ACCENT_SOFT = "#3A1416"      # красноватая поверхность (выделение, избранное)
ON_ACCENT = "#FFFFFF"        # текст и иконки на красном
ON_COLOR = "#FFFFFF"         # текст на цветных фонах (градиенты команд, hero) — белый в любой теме
INK = "#15151E"              # тёмный текст на светлых плашках (медали, белая кнопка) — в любой теме

SUCCESS = "#22C55E"
WARNING = "#F5A524"
DANGER = "#FF5A5C"
INFO = "#3B82F6"
GOLD = "#FFC93C"             # звёздочка избранного

# Градиенты
GRADIENT_RED = [ACCENT_GLOW, F1_RED, ACCENT_DEEP]
GRADIENT_SURFACE = [SURFACE_RAISED, SURFACE]

# === ТИПОГРАФИКА ===
FONT_DISPLAY = 48
FONT_H1 = 36
FONT_H2 = 28
FONT_H3 = 22
FONT_H4 = 18
FONT_BODY_LARGE = 16
FONT_BODY = 14
FONT_BODY_SMALL = 12
FONT_CAPTION = 11
FONT_TINY = 10
FONT_MICRO = 9

# Размер текста (настройка «Размер текста»): токены FONT_* умножаются на FONT_SCALE.
# Системный крупный шрифт Android Flutter применяет поверх сам — вёрстка проверяется на ×1.3.
FONT_SCALE = 1.0
FONT_SCALES = {"1.0": "Обычный", "1.15": "Крупный", "1.3": "Очень крупный"}
_FONT_BASE = {k: v for k, v in dict(globals()).items() if k.startswith("FONT_") and isinstance(v, int)}


def scaled(px):
    """Размер, который должен расти вместе с текстом (колонки таблиц, высота карточек)."""
    return round(px * FONT_SCALE)


def large_text():
    return FONT_SCALE >= 1.1


def apply_font_scale(scale=1.0):
    """Пересчитать размеры шрифтов; модули интерфейса затем перезагружаются (ui/theming.py)."""
    global FONT_SCALE
    try:
        scale = min(max(float(scale), 1.0), 1.5)
    except (TypeError, ValueError):
        scale = 1.0
    FONT_SCALE = scale
    globals().update({k: round(v * scale) for k, v in _FONT_BASE.items()})
    return scale

FONT_HEADING = "Exo2"            # заголовки и цифры
FONT_HEADING_SEMI = "Exo2Semi"   # подзаголовки
FONT_DISPLAY_ITALIC = "Exo2XBI"  # крупные цифры, «гоночный» курсив
FONT_ITALIC = "Exo2BI"
FONT_MONO = "JBMonoBI"           # отрывы и времена кругов: моноширинные цифры, колонки не «дрожат»
FONTS = {                        # регистрируются в main.py через page.fonts (лежат в assets/)
    FONT_HEADING: "fonts/Exo2-Bold.ttf",
    FONT_HEADING_SEMI: "fonts/Exo2-SemiBold.ttf",
    FONT_DISPLAY_ITALIC: "fonts/Exo2-ExtraBoldItalic.ttf",
    FONT_ITALIC: "fonts/Exo2-BoldItalic.ttf",
    FONT_MONO: "fonts/JetBrainsMono-BoldItalic.ttf",
}

# === ОТСТУПЫ ===
SPACE_XXS = 4
SPACE_XS = 8
SPACE_SM = 12
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 32
SPACE_XXL = 48

# Цвета разделов для иконок меню и быстрого доступа: красный оставлен для LIVE и главных действий,
# чтобы акценты не спорили. В светлой теме иконки темнеют через readable_text().
SECTION_COLORS = {
    "live": "#FF5A5C", "race": "#4DA3FF", "compare": "#A77BFF", "predict": "#22C55E", "favorites": "#FFC93C",
    "title": "#FFB020", "history": "#FF8A3D", "strategy": "#2EC4B6", "mini": "#5AC8FA", "settings": "#9D9DAB",
}

# Портреты в карточках опускаются на столько вниз, чтобы над головой оставался воздух
PHOTO_DROP = 10

# === СКРУГЛЕНИЯ ===
RADIUS_SM = 8
RADIUS_MD = 14
RADIUS_LG = 20
RADIUS_XL = 28
RADIUS_FULL = 9999

# Три размера карточек на всё приложение — один ритм отступов и скруглений:
#   s — строки списков (радио, таблицы), m — обычные карточки, l — сводки и герои экранов
CARD_SIZES = {"s": (SPACE_XS, 12), "m": (SPACE_SM, RADIUS_MD), "l": (SPACE_MD, RADIUS_LG)}

# Минимальная зона нажатия (Material: 48 dp) — для пальца на телефоне
TOUCH = 48

# === АНИМАЦИИ (мс) ===
ANIM_FAST = 150
ANIM_NORMAL = 250
ANIM_SLOW = 400


def shadow(level=1, color="#000000"):
    """Мягкая тень карточки: 1 — в покое, 2 — при наведении."""
    import flet as ft  # здесь, а не наверху: сервисы берут из модуля только данные о командах
    blur, dy, alpha = {1: (12, 4, 0.35), 2: (24, 10, 0.5)}.get(level, (12, 4, 0.35))
    return ft.BoxShadow(blur_radius=blur, spread_radius=0, offset=ft.Offset(0, dy),
                        color=ft.Colors.with_opacity(alpha, color))


def glow(color=None, strength=0.45):
    """Свечение цвета акцента (красное в тёмной и светлой теме, цвет команды — в командной)."""
    import flet as ft
    color = color or ACCENT_PRIMARY
    return ft.BoxShadow(blur_radius=28, spread_radius=1, offset=ft.Offset(0, 6),
                        color=ft.Colors.with_opacity(strength, color))


# === КОМАНДЫ (сезон 2026) ===
# color — фирменный цвет команды (как в официальной графике F1), slug — имя в адресах
# медиа formula1.com (логотип, болид, портреты пилотов).
TEAMS = {
    "mclaren":      {"color": "#F47600", "dark": "#7A3B00", "slug": "mclaren"},
    "mercedes":     {"color": "#00D7B6", "dark": "#006B5B", "slug": "mercedes"},
    "red_bull":     {"color": "#4781D7", "dark": "#1E3A6B", "slug": "redbullracing"},
    "ferrari":      {"color": "#ED1131", "dark": "#76081A", "slug": "ferrari"},
    "williams":     {"color": "#1868DB", "dark": "#0B346E", "slug": "williams"},
    "rb":           {"color": "#6C98FF", "dark": "#2E4A8A", "slug": "racingbulls"},
    "aston_martin": {"color": "#229971", "dark": "#0F4C38", "slug": "astonmartin"},
    "haas":         {"color": "#9C9FA2", "dark": "#4B4D50", "slug": "haasf1team"},
    "audi":         {"color": "#F50537", "dark": "#7A021B", "slug": "audi"},
    "kick_sauber":  {"color": "#52E252", "dark": "#1F6B1F", "slug": "kicksauber"},
    "alpine":       {"color": "#00A1E8", "dark": "#004F73", "slug": "alpine"},
    "cadillac":     {"color": "#909090", "dark": "#454545", "slug": "cadillac"},
}

# Порядок важен: более специфичные названия — раньше («racing bulls» до «red bull»).
TEAM_NEEDLES = [
    ("ferrari", "ferrari"), ("mercedes", "mercedes"), ("mclaren", "mclaren"),
    ("racing bulls", "rb"), ("rb f1", "rb"), ("red bull", "red_bull"),
    ("aston martin", "aston_martin"), ("alpine", "alpine"), ("williams", "williams"),
    ("haas", "haas"), ("audi", "audi"), ("sauber", "kick_sauber"), ("cadillac", "cadillac"),
]


def team_key(team_name):
    low = (team_name or "").lower()
    return next((key for needle, key in TEAM_NEEDLES if needle in low), None)


def team_slug(team_name):
    """'Red Bull Racing' -> 'redbullracing' (для адресов медиа); None для незнакомой команды."""
    team = TEAMS.get(team_key(team_name))
    return team["slug"] if team else None


def get_team_color(team_name: str, variant: str = "color") -> str:
    team = TEAMS.get(team_key(team_name))
    if not team:
        return TEXT_DIM
    return team["dark"] if variant in ("dark", "secondary") else team["color"]


def get_team_gradient(team_name: str) -> tuple[str, str]:
    """Фон карточек пилота и команды под белым текстом. Светлые цвета (Mercedes, Sauber) сверху
    притемняются до контраста 3:1 с белым — порог WCAG для крупного текста."""
    team = TEAMS.get(team_key(team_name))
    if not team:
        return SURFACE_RAISED, SURFACE
    top = team["color"]
    for step in range(1, 11):
        if contrast(ON_COLOR, top) >= 3.0:
            break
        top = _mix(team["color"], team["dark"], step / 10)
    return top, team["dark"]


# === СТРАНЫ: флаги (ISO 3166-1 alpha-2 для flagcdn.com) ===
NATIONALITY_ISO = {
    "American": "us", "Argentine": "ar", "Australian": "au", "Austrian": "at", "Belgian": "be",
    "Brazilian": "br", "British": "gb", "Canadian": "ca", "Chinese": "cn", "Danish": "dk",
    "Dutch": "nl", "Finnish": "fi", "French": "fr", "German": "de", "Indian": "in",
    "Irish": "ie", "Italian": "it", "Japanese": "jp", "Mexican": "mx", "Monegasque": "mc",
    "New Zealander": "nz", "Polish": "pl", "Russian": "ru", "Spanish": "es", "Swedish": "se",
    "Swiss": "ch", "Thai": "th", "Colombian": "co", "Venezuelan": "ve", "Indonesian": "id",
    "Estonian": "ee", "Israeli": "il", "Portuguese": "pt", "Hungarian": "hu", "Czech": "cz",
    "Emirati": "ae", "Saudi": "sa",
}
COUNTRY_ISO = {
    "Australia": "au", "China": "cn", "Japan": "jp", "Bahrain": "bh", "Saudi Arabia": "sa",
    "USA": "us", "United States": "us", "Italy": "it", "Monaco": "mc", "Spain": "es",
    "Canada": "ca", "Austria": "at", "UK": "gb", "United Kingdom": "gb", "Great Britain": "gb",
    "Belgium": "be", "Hungary": "hu", "Netherlands": "nl", "Azerbaijan": "az", "Singapore": "sg",
    "Mexico": "mx", "Brazil": "br", "Qatar": "qa", "UAE": "ae", "United Arab Emirates": "ae",
    "Portugal": "pt", "France": "fr", "Germany": "de", "Turkey": "tr", "Russia": "ru",
    "Vietnam": "vn", "South Africa": "za", "Argentina": "ar", "Korea": "kr", "India": "in",
    "Malaysia": "my", "Thailand": "th", "Morocco": "ma", "Sweden": "se", "Switzerland": "ch",
    "Rwanda": "rw", "Indonesia": "id", "Swiss": "ch",
}


def nationality_iso(nationality):
    return NATIONALITY_ISO.get((nationality or "").strip())


def country_iso(country):
    return COUNTRY_ISO.get((country or "").strip())


# === ШИНЫ ===
TYRE_COLORS = {"SOFT": "#FF3333", "MEDIUM": "#FFD12E", "HARD": "#F0F0F0",
               "INTERMEDIATE": "#43B02A", "WET": "#0067AD"}
TYRES = {"S": TYRE_COLORS["SOFT"], "M": TYRE_COLORS["MEDIUM"], "H": TYRE_COLORS["HARD"]}

# === ПОЗИЦИИ ===
POSITION_COLORS = {1: "#FFC93C", 2: "#C9CED6", 3: "#D9894A"}   # золото, серебро, бронза


def get_position_color(position: int) -> str:
    return POSITION_COLORS.get(position, TEXT_MUTED)


# === ТОЧКИ ПЕРЕЛОМА ===
BREAKPOINT_MOBILE = 640
BREAKPOINT_TABLET = 768
BREAKPOINT_DESKTOP = 1024
BREAKPOINT_WIDE = 1280

# === Короткие имена для ui/widgets.py ===
ACCENT = ACCENT_PRIMARY
RAISED = SURFACE_RAISED
TEXT = TEXT_PRIMARY
MUTED = TEXT_MUTED
DIM = TEXT_DIM
OK = SUCCESS
WARN = WARNING
team_color = get_team_color


# === ТЕМЫ ===
# Значения меняются на месте функцией apply_theme(); модули интерфейса после этого
# перезагружаются (ui/theming.py), потому что берут цвета через «from design_system import *».
# Текст и статусные цвета — с контрастом не меньше 4.5:1 к фону, карточке и чипу в каждой теме
# (WCAG AA для обычного текста; проверяется в tests/test_accessibility.py).
_DARK = {
    "BG_DEEPEST": "#000000", "BG_DEEP": "#0B0B10", "BG": "#15151E", "SURFACE": "#1E1E29",
    "SURFACE_RAISED": "#272733", "SURFACE_ELEVATED": "#31313E",
    "LINE_SUBTLE": "#23232E", "LINE": "#2D2D3A", "LINE_STRONG": "#41414F",
    "TEXT_PRIMARY": "#FFFFFF", "TEXT_SECONDARY": "#D2D2DC", "TEXT_MUTED": "#ABABB8", "TEXT_DIM": "#8E8E9C",
    "SUCCESS": "#22C55E", "WARNING": "#F5A524", "DANGER": "#FF5A5C", "GOLD": "#FFC93C",
    # секторы, как на графике F1: лучший в сессии / личный лучший / пройден
    "SECTOR_OVERALL": "#A855F7", "SECTOR_PERSONAL": "#22C55E", "SECTOR_NORMAL": "#F5C518",
}
_LIGHT = {
    "BG_DEEPEST": "#FFFFFF", "BG_DEEP": "#E4E4EA", "BG": "#F3F3F6", "SURFACE": "#FFFFFF",
    "SURFACE_RAISED": "#ECECF1", "SURFACE_ELEVATED": "#E1E1E8",
    "LINE_SUBTLE": "#ECECF1", "LINE": "#DCDCE3", "LINE_STRONG": "#C3C3CD",
    "TEXT_PRIMARY": "#15151E", "TEXT_SECONDARY": "#3A3A46", "TEXT_MUTED": "#4F4F5A", "TEXT_DIM": "#62626E",
    "SUCCESS": "#0F7A35", "WARNING": "#9A4A00", "DANGER": "#C62828", "GOLD": "#8A5A00",
    "SECTOR_OVERALL": "#7E22CE", "SECTOR_PERSONAL": "#15803D", "SECTOR_NORMAL": "#A16207",
}
# OLED: чистый чёрный фон (пиксели AMOLED-экрана гаснут — меньше расход батареи), карточки чуть светлее
_OLED = dict(_DARK, **{
    "BG_DEEPEST": "#000000", "BG_DEEP": "#000000", "BG": "#000000", "SURFACE": "#0E0E13",
    "SURFACE_RAISED": "#18181F", "SURFACE_ELEVATED": "#22222B",
    "LINE_SUBTLE": "#141419", "LINE": "#1D1D25", "LINE_STRONG": "#32323D",
})
_RED = {"F1_RED": "#E10600", "ACCENT_GLOW": "#FF2A1F", "ACCENT_DEEP": "#8E0400"}
THEME_NAMES = {"dark": "Тёмная", "oled": "OLED", "light": "Светлая", "team": "Цвета команды"}
THEME = "dark"
THEME_TEAM = None
IS_LIGHT = False


def _mix(a, b, t):
    """Смесь двух цветов #RRGGBB: t=0 — a, t=1 — b."""
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#" + "".join(f"{round(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t):02X}" for i in (0, 2, 4))


def _luminance(color):
    c = color.lstrip("#")
    ch = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    ch = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in ch]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def contrast(a, b):
    """Контраст двух цветов #RRGGBB по WCAG: 1 (нет) … 21 (чёрный на белом)."""
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _readable_accent(color, background, target=4.5):
    """Акцент для мелкого текста: цвет команды, осветлённый настолько, чтобы читался на фоне."""
    for step in range(3, 11):
        candidate = _mix(color, "#FFFFFF", step / 10)
        if contrast(candidate, background) >= target:
            return candidate
    return "#FFFFFF"


def readable_text(color, target=4.5, background=None):
    """Цветной текст на карточке (цвет команды, медали): смещается к основному цвету текста темы,
    пока не наберёт нужный контраст. В тёмной теме яркие цвета обычно проходят как есть,
    в светлой бирюзовый Mercedes или золото темнеют. target=3 — для крупных цифр."""
    background = background or SURFACE
    for step in range(0, 11):
        candidate = _mix(color, TEXT_PRIMARY, step / 10)
        if contrast(candidate, background) >= target:
            return candidate
    return TEXT_PRIMARY


def readable_on(color):
    """Цвет текста на цветной плашке (цвет команды и т. п.): белый или тёмный — что контрастнее."""
    return ON_COLOR if contrast(ON_COLOR, color) >= contrast(INK, color) else INK


def apply_theme(name="dark", team=None):
    """Переключить палитру: 'dark', 'oled' (чистый чёрный), 'light' или 'team' (акцент — цвет команды team)."""
    global THEME, THEME_TEAM, IS_LIGHT
    g = globals()
    base = _LIGHT if name == "light" else _OLED if name == "oled" else _DARK
    g.update(base)
    accent = dict(_RED)
    team_colors = TEAMS.get(team_key(team)) if name == "team" else None
    if team_colors:
        accent = {"F1_RED": team_colors["color"], "ACCENT_GLOW": _mix(team_colors["color"], "#FFFFFF", 0.25),
                  "ACCENT_DEEP": team_colors["dark"]}
    g.update(accent)
    g["ACCENT_PRIMARY"] = g["ACCENT"] = g["F1_RED"]
    if name == "light":
        g["ACCENT_TEXT"] = "#C80500"
        g["ACCENT_SOFT"] = "#FDE3E1"
    else:
        g["ACCENT_TEXT"] = _readable_accent(g["F1_RED"], base["SURFACE_RAISED"]) if team_colors else "#FF5A4F"
        g["ACCENT_SOFT"] = _mix(g["F1_RED"], base["BG"], 0.78)
    g["GRADIENT_RED"] = [g["ACCENT_GLOW"], g["F1_RED"], g["ACCENT_DEEP"]]
    g["GRADIENT_SURFACE"] = [g["SURFACE_RAISED"], g["SURFACE"]]
    g["RAISED"], g["TEXT"] = g["SURFACE_RAISED"], g["TEXT_PRIMARY"]
    g["MUTED"], g["DIM"] = g["TEXT_MUTED"], g["TEXT_DIM"]
    g["OK"], g["WARN"] = g["SUCCESS"], g["WARNING"]
    THEME = name if name in THEME_NAMES else "dark"
    THEME_TEAM, IS_LIGHT = (team if team_colors else None), name == "light"
    if name == "team" and not team_colors:
        THEME = "dark"
    return THEME
