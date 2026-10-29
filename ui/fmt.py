"""Форматирование дат, времени и чисел для интерфейса (русская локаль)."""
import time

MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]

SESSION_NAMES = {
    "FirstPractice": "Практика 1",
    "SecondPractice": "Практика 2",
    "ThirdPractice": "Практика 3",
    "SprintQualifying": "Спринт-квалификация",
    "SprintShootout": "Спринт-квалификация",
    "Sprint": "Спринт",
    "Qualifying": "Квалификация",
    "Race": "Гонка",
}


# Jolpica отдаёт гражданство по-английски («Italian») — в интерфейсе показываем страну по-русски
NATIONS_RU = {
    "American": "США", "Argentine": "Аргентина", "Australian": "Австралия", "Austrian": "Австрия",
    "Belgian": "Бельгия", "Brazilian": "Бразилия", "British": "Великобритания", "Canadian": "Канада",
    "Chinese": "Китай", "Colombian": "Колумбия", "Czech": "Чехия", "Danish": "Дания", "Dutch": "Нидерланды",
    "Emirati": "ОАЭ", "Estonian": "Эстония", "Finnish": "Финляндия", "French": "Франция", "German": "Германия",
    "Hungarian": "Венгрия", "Indian": "Индия", "Indonesian": "Индонезия", "Irish": "Ирландия",
    "Israeli": "Израиль", "Italian": "Италия", "Japanese": "Япония", "Mexican": "Мексика", "Monegasque": "Монако",
    "New Zealander": "Новая Зеландия", "Polish": "Польша", "Portuguese": "Португалия", "Russian": "Россия",
    "Saudi": "Саудовская Аравия", "South African": "ЮАР", "Spanish": "Испания", "Swedish": "Швеция",
    "Swiss": "Швейцария", "Thai": "Таиланд", "Venezuelan": "Венесуэла",
}


def nation_ru(nationality):
    """«Italian» -> «Италия»; неизвестное оставляем как есть, чтобы не терять данные."""
    return NATIONS_RU.get((nationality or "").strip(), nationality or "")


def plural(n, one, few, many):
    """1 очко, 2 очка, 5 очков."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def fmt_day(ts):
    t = time.localtime(ts)
    return f"{WEEKDAYS[t.tm_wday]} {t.tm_mday} {MONTHS[t.tm_mon - 1]}"


def fmt_date(ts):
    t = time.localtime(ts)
    return f"{t.tm_mday} {MONTHS[t.tm_mon - 1]}"


def fmt_date_full(ts):
    """Полная дата: '15 мая 2024'."""
    t = time.localtime(ts)
    months_full = ["января", "февраля", "марта", "апреля", "мая", "июня",
                   "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    return f"{t.tm_mday} {months_full[t.tm_mon - 1]} {t.tm_year}"


def fmt_clock(ts):
    return time.strftime("%H:%M", time.localtime(ts))


def fmt_countdown(seconds):
    """Сколько осталось до старта: «6 д 4 ч», «3 ч 20 мин», «12 мин»."""
    seconds = int(seconds)
    if seconds <= 0:
        return "идёт сейчас"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days} д {hours} ч"
    if hours:
        return f"{hours} ч {minutes} мин"
    return f"{max(minutes, 1)} мин"


def fmt_updated(ts):
    if not ts:
        return "ещё не обновлялось"
    return f"сегодня в {fmt_clock(ts)}" if time.strftime("%Y%m%d", time.localtime(ts)) == time.strftime("%Y%m%d") \
        else f"{fmt_date(ts)}, {fmt_clock(ts)}"


def short_name(full_name):
    """'Andrea Kimi Antonelli' -> 'Antonelli'."""
    parts = (full_name or "").split()
    return parts[-1] if parts else ""


def to_int(value, default=None):
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default
