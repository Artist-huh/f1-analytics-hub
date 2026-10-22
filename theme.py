# Дизайн-токены для виджетов из ui/widgets.py.
# Нейтральные цвета берутся из design_system, чтобы все экраны выглядели одинаково.
import design_system as ds

# Цвета Ferrari — только как смысловые акценты (команда, подиум)
ROSSO = "#E10600"
ROSSO_DEEP = "#6E0A07"
GIALLO = "#FFD200"

# Общая палитра приложения
ACCENT = ds.ACCENT_PRIMARY
ON_ACCENT = ds.BG_DEEP
BG = ds.BG
SURFACE = ds.SURFACE
RAISED = ds.SURFACE_RAISED
LINE = ds.LINE
TEXT = ds.TEXT_PRIMARY
MUTED = ds.TEXT_MUTED
DIM = ds.TEXT_DIM
OK = ds.SUCCESS
WARN = ds.WARNING

# Совместимость со старыми именами
FERRARI_RED, FERRARI_DARK_RED, FERRARI_BLACK = ROSSO, ROSSO_DEEP, BG
FERRARI_SURFACE, FERRARI_GRAY, FERRARI_CARD = SURFACE, SURFACE, RAISED
FERRARI_YELLOW, FERRARI_WHITE, FERRARI_MUTED = GIALLO, TEXT, MUTED

# Цвета шин (для экрана стратегии): S — soft, M — medium, H — hard
TYRES = {"S": "#E53935", "M": GIALLO, "H": TEXT}

# Цвет команды — одна таблица на всё приложение
team_color = ds.get_team_color


# Шрифт заголовков и цифр: узкий гротеск, как на табло.
# Лежит в assets/fonts (работает без сети); регистрируется в main.py через page.fonts.
FONT_HEAD = "BarlowCondensed"
FONT_FILE = "fonts/BarlowCondensed-Bold.ttf"
FONT_RACING = FONT_HEAD
