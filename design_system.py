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
TEXT_MUTED = "#9D9DAB"
TEXT_DIM = "#6E6E7C"

# === АКЦЕНТ: F1 RED ===
F1_RED = "#E10600"
ACCENT_PRIMARY = F1_RED
ACCENT_GLOW = "#FF2A1F"      # ярче — hover, свечение
ACCENT_DEEP = "#8E0400"      # темнее — конец градиента
ACCENT_TEXT = "#FF4136"      # красный для мелкого текста (контраст ≥ 4.5:1 на тёмном)
ACCENT_SOFT = "#3A1416"      # красноватая поверхность (выделение, избранное)
ON_ACCENT = "#FFFFFF"        # текст и иконки на красном
ON_COLOR = "#FFFFFF"         # текст на цветных фонах (градиенты команд, hero) — белый в любой теме

SUCCESS = "#22C55E"
WARNING = "#F5A524"
DANGER = "#FF4D4F"
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

FONT_HEADING = "Exo2"            # заголовки и цифры
FONT_HEADING_SEMI = "Exo2Semi"   # подзаголовки
FONT_DISPLAY_ITALIC = "Exo2XBI"  # крупные цифры, «гоночный» курсив
FONT_ITALIC = "Exo2BI"
FONTS = {                        # регистрируются в main.py через page.fonts (лежат в assets/)
    FONT_HEADING: "fonts/Exo2-Bold.ttf",
    FONT_HEADING_SEMI: "fonts/Exo2-SemiBold.ttf",
    FONT_DISPLAY_ITALIC: "fonts/Exo2-ExtraBoldItalic.ttf",
    FONT_ITALIC: "fonts/Exo2-BoldItalic.ttf",
}

# === ОТСТУПЫ ===
SPACE_XXS = 4
SPACE_XS = 8
SPACE_SM = 12
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 32
SPACE_XXL = 48

# === СКРУГЛЕНИЯ ===
RADIUS_SM = 8
RADIUS_MD = 14
RADIUS_LG = 20
RADIUS_XL = 28
RADIUS_FULL = 9999

# Минимальная зона нажатия (Material: 48 dp) — для пальца на телефоне
TOUCH = 48

# === АНИМАЦИИ (мс) ===
ANIM_FAST = 150
ANIM_NORMAL = 250
ANIM_SLOW = 400


def shadow(level=1, color=BG_DEEPEST):
    """Мягкая тень карточки: 1 — в покое, 2 — при наведении."""
    import flet as ft   # здесь, а не наверху: сервисы берут из модуля только данные о командах
    blur, dy, alpha = {1: (12, 4, 0.35), 2: (24, 10, 0.5)}.get(level, (12, 4, 0.35))
    return ft.BoxShadow(blur_radius=blur, spread_radius=0, offset=ft.Offset(0, dy),
                        color=ft.Colors.with_opacity(alpha, color))


def glow(color=F1_RED, strength=0.45):
    """Красное свечение для акцентных элементов."""
    import flet as ft
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
    team = TEAMS.get(team_key(team_name))
    return (team["color"], team["dark"]) if team else (SURFACE_RAISED, SURFACE)


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
