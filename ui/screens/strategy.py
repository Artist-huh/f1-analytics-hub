"""Стратегия на трассу: прикидки по кругам, износу и шинам для ближайшего этапа."""
import flet as ft

from design_system import *
from ui.widgets import card, dropdown, screen, txt, tyre_chip

# Базовые прикидки приложения (не официальные планы команды): круги, износ, обгоны, шины по порядку.
TRACKS = {
    "Monaco":      {"laps": 78, "wear": "низкий",  "overtake": "очень сложно", "stints": ["S", "H"],
                    "note": "На узкой трассе позиция важнее скорости. Один стоп — меньше риска потерять место."},
    "Monza":       {"laps": 53, "wear": "средний", "overtake": "легко",        "stints": ["M", "H"],
                    "note": "Храм скорости. Классический один стоп."},
    "Silverstone": {"laps": 52, "wear": "высокий", "overtake": "средне",       "stints": ["S", "M", "H"],
                    "note": "Быстрые повороты изнашивают резину. Два стопа дают свежие шины."},
    "Spa":         {"laps": 44, "wear": "средний", "overtake": "легко",        "stints": ["M", "H"],
                    "note": "Длинный круг, один стоп. Погода может изменить всё."},
    "Hungaroring": {"laps": 70, "wear": "средний", "overtake": "сложно",       "stints": ["S", "M", "S"],
                    "note": "Узко, как в Монако. Свежие мягкие в конце — для атаки."},
    "Suzuka":      {"laps": 53, "wear": "высокий", "overtake": "средне",       "stints": ["M", "H", "S"],
                    "note": "Техничная трасса: баланс скорости и износа."},
    "Baku":        {"laps": 51, "wear": "низкий",  "overtake": "с DRS",        "stints": ["S", "H"],
                    "note": "Длинная прямая и Safety Car часто решают гонку."},
    "Singapore":   {"laps": 62, "wear": "высокий", "overtake": "сложно",       "stints": ["S", "M", "S"],
                    "note": "Ночная уличная трасса: сильный износ, два стопа."},
}
_NEEDLES = {"monaco": "Monaco", "monza": "Monza", "silverstone": "Silverstone", "spa": "Spa",
            "hungaro": "Hungaroring", "suzuka": "Suzuka", "baku": "Baku", "marina bay": "Singapore",
            "singapore": "Singapore"}


def _guess_track(race):
    if race:
        text = f"{race['circuit']} {race['race_name']} {race['locality']}".lower()
        for needle, name in _NEEDLES.items():
            if needle in text:
                return name
    return None


def build(state):
    chosen = state.ui.get("track") or _guess_track(state.next_race()) or "Monaco"

    def on_select(e):
        if e.control.value:
            state.ui["track"] = e.control.value
            state.render()

    t = TRACKS[chosen]
    stops = len(t["stints"]) - 1
    chips = []
    for i, letter in enumerate(t["stints"]):
        if i:
            chips.append(ft.Icon(ft.Icons.CHEVRON_RIGHT, color=DIM, size=18))
        chips.append(tyre_chip(letter))
    body = [
        dropdown(label="Трасса", value=chosen, options=[ft.DropdownOption(key=n, text=n) for n in TRACKS],
                 on_select=on_select),
        card(ft.Column([
            txt(chosen, 26, bold=True, head=True),
            txt(f"{t['laps']} кругов · износ {t['wear']} · обгоны: {t['overtake']}", 12, MUTED),
            ft.Container(height=6),
            ft.Row(chips, spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            txt(f"{stops} {'пит-стоп' if stops == 1 else 'пит-стопа'}", 16, bold=True),
            txt(t["note"], 13, MUTED),
            ft.Container(height=4),
            ft.Row([tyre_chip("S"), txt("мягкие", 12, MUTED), tyre_chip("M"), txt("средние", 12, MUTED),
                    tyre_chip("H"), txt("жёсткие", 12, MUTED)], spacing=6, wrap=True),
        ], spacing=3), size="l"),
        txt("Это базовые прикидки приложения, а не официальные планы команд.", 11, DIM),
    ]
    return screen(state, "Стратегия", body, subtitle="План пит-стопов по трассам", back=True)
