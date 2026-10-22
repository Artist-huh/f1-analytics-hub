"""F1 Analytics Hub — современная дизайн-система

Палитра вдохновлена Formula 1: глубокие темные поверхности,
киберспортивные акценты, градиенты команд, адаптивная типографика.
"""

# === CORE PALETTE ===
# Темные поверхности с холодным оттенком (как асфальт ночной трассы)
BG_DEEPEST = "#05070C"      # Самый глубокий фон
BG_DEEP = "#0A0D12"         # Основной фон
BG = "#0F131C"              # Дефолтный фон страницы
SURFACE = "#161D2B"         # Карточки, панели
SURFACE_RAISED = "#1E2636"  # Поднятые элементы
SURFACE_ELEVATED = "#2A3442" # Модалки, дропдауны

# Границы и разделители
LINE_SUBTLE = "#1E2636"
LINE = "#2A3442"
LINE_STRONG = "#384556"

# Текст
TEXT_PRIMARY = "#F8FAFC"     # Основной текст
TEXT_SECONDARY = "#CBD5E1"   # Вторичный текст
TEXT_MUTED = "#94A3B8"       # Приглушенный
TEXT_DIM = "#64748B"         # Совсем тусклый

# === ACCENT COLORS ===
# Основной акцент — киберспортивный циан
ACCENT_PRIMARY = "#38BDF8"   # Яркий голубой (F1 digital)
ACCENT_GLOW = "#0EA5E9"      # Насыщенный
ACCENT_DEEP = "#0284C7"      # Темнее

# Дополнительные акценты
SUCCESS = "#10B981"          # Зеленый (победа)
WARNING = "#F59E0B"          # Оранжевый (предупреждение)
DANGER = "#EF4444"           # Красный (критично)
INFO = "#8B5CF6"             # Фиолетовый (инфо)

# === TEAM COLORS ===
# Цвета команд Ф1 2024/2025 с градиентами
TEAMS = {
    "red_bull": {"primary": "#3671C6", "secondary": "#1E3A8A", "accent": "#FFB800"},
    "ferrari": {"primary": "#E10600", "secondary": "#7C0A02", "accent": "#FFF200"},
    "mercedes": {"primary": "#27F4D2", "secondary": "#00D2BE", "accent": "#C0C0C0"},
    "mclaren": {"primary": "#FF8000", "secondary": "#FF6600", "accent": "#47C7FC"},
    "aston_martin": {"primary": "#229971", "secondary": "#00665F", "accent": "#CEDC00"},
    "alpine": {"primary": "#FF87BC", "secondary": "#0093CC", "accent": "#FF1E00"},
    "williams": {"primary": "#64C4FF", "secondary": "#00A0DE", "accent": "#E40046"},
    "rb": {"primary": "#6692FF", "secondary": "#4664C0", "accent": "#C92D4B"},
    "kick_sauber": {"primary": "#52E252", "secondary": "#00E701", "accent": "#FF3535"},
    "haas": {"primary": "#D0D3D6", "secondary": "#B6BABD", "accent": "#ED1B24"},
    "audi": {"primary": "#9B9FA6", "secondary": "#5C5F66", "accent": "#F50537"},
    "cadillac": {"primary": "#6E6E78", "secondary": "#3F3F46", "accent": "#C9A55C"},
}

# Порядок важен: более специфичные названия — раньше («racing bulls» до «red bull»).
TEAM_NEEDLES = [
    ("ferrari", "ferrari"), ("mercedes", "mercedes"), ("mclaren", "mclaren"),
    ("racing bulls", "rb"), ("rb f1", "rb"), ("red bull", "red_bull"),
    ("aston martin", "aston_martin"), ("alpine", "alpine"), ("williams", "williams"),
    ("haas", "haas"), ("audi", "audi"), ("sauber", "kick_sauber"), ("cadillac", "cadillac"),
]


def _team_key(team_name):
    low = (team_name or "").lower()
    return next((key for needle, key in TEAM_NEEDLES if needle in low), None)


def get_team_color(team_name: str, variant: str = "primary") -> str:
    """Получить цвет команды по имени"""
    colors = TEAMS.get(_team_key(team_name))
    return colors.get(variant, colors["primary"]) if colors else TEXT_DIM


def get_team_gradient(team_name: str) -> tuple[str, str]:
    """Получить градиент команды (primary -> secondary)"""
    colors = TEAMS.get(_team_key(team_name))
    return (colors["primary"], colors["secondary"]) if colors else (SURFACE, SURFACE_RAISED)

# === TYPOGRAPHY ===
# Адаптивные размеры через clamp() эмуляцию
FONT_DISPLAY = 48  # Большие заголовки
FONT_H1 = 36       # H1
FONT_H2 = 28       # H2
FONT_H3 = 22       # H3
FONT_H4 = 18       # H4
FONT_BODY_LARGE = 16
FONT_BODY = 14
FONT_BODY_SMALL = 12
FONT_CAPTION = 11

# Семейства шрифтов
FONT_HEADING = "BarlowCondensed"  # Для заголовков и цифр (assets/fonts)
FONT_MONO = "RobotoMono"        # Моноширинный (цифры, время)
FONT_BODY_FAMILY = "Inter"      # Основной текст

# === SPACING SYSTEM ===
SPACE_XXS = 4
SPACE_XS = 8
SPACE_SM = 12
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 32
SPACE_XXL = 48

# === BORDER RADIUS ===
RADIUS_SM = 6
RADIUS_MD = 12
RADIUS_LG = 16
RADIUS_XL = 24
RADIUS_FULL = 9999  # Для кнопок-пилюль

# === ANIMATION DURATIONS ===
ANIM_FAST = 150      # Быстрая (hover)
ANIM_NORMAL = 250    # Обычная
ANIM_SLOW = 400      # Медленная (переходы)

# === TIRE COMPOUNDS ===
TYRE_COLORS = {
    "SOFT": "#E53935",
    "MEDIUM": "#F59E0B",
    "HARD": "#F8FAFC",
    "INTERMEDIATE": "#10B981",
    "WET": "#3B82F6",
}

# === POSITION COLORS ===
# Цвета для позиций в гонке
POSITION_COLORS = {
    1: "#FFD700",  # Золото
    2: "#C0C0C0",  # Серебро
    3: "#CD7F32",  # Бронза
}

def get_position_color(position: int) -> str:
    """Получить цвет для позиции"""
    return POSITION_COLORS.get(position, TEXT_MUTED)

# === BREAKPOINTS (для адаптивности) ===
BREAKPOINT_MOBILE = 640
BREAKPOINT_TABLET = 768
BREAKPOINT_DESKTOP = 1024
BREAKPOINT_WIDE = 1280

# === Обратная совместимость ===
# Старые имена для плавной миграции
ROSSO = TEAMS["ferrari"]["primary"]
GIALLO = TEAMS["ferrari"]["accent"]
TEXT = TEXT_PRIMARY
MUTED = TEXT_MUTED
DIM = TEXT_DIM
OK = SUCCESS
WARN = WARNING
