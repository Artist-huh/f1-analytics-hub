"""Проверка бесплатных источников данных — раз в день в GitHub (sources.yml), чтобы узнать о поломке раньше
пользователей.

    python tools/check_sources.py

Ходит в источники теми же функциями, что и приложение, поэтому ловит и закрытие источника, и смену формата.
Код выхода 1 — если сломан источник, без которого раздел приложения пуст:
  Jolpica (чемпионат, календарь), поток F1 live timing (Live Timing во время сессии), контуры трасс MultiViewer.
OpenF1 — запасной: его отказ во время сессии (доступ закрыт) нормален, это предупреждение, а не поломка.
"""
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("F1_HUB_LOG", "off")

from services import f1live, jolpica, live, track_map
from ui.fmt import plural


def drivers(n):
    return f"{n} {plural(n, 'пилот', 'пилота', 'пилотов')}"


def check_jolpica():
    season, rnd, rows = jolpica.fetch_standings()
    if not rows:
        raise RuntimeError(f"сезон {season}: пустой личный зачёт")
    races = jolpica.fetch_schedule()[1]
    return f"сезон {season}, после этапа {rnd}: {drivers(len(rows))}, этапов в календаре: {len(races)}"


def check_f1_stream():
    data = f1live.fetch()
    if not data.get("rows"):
        raise RuntimeError("поток ответил, но без таблицы пилотов")
    return f"{data['session'].get('name', '?')}: {drivers(len(data['rows']))}"


def check_openf1():
    try:
        data = live.fetch_openf1()
    except live.LockedError:
        return "закрыт на время сессии — это нормально"
    return f"{data['session'].get('name', '?')}: {drivers(len(data['rows']))}"


def check_track_maps():
    year = datetime.now(timezone.utc).year
    try:
        meetings = track_map.fetch_meetings(year)
    except track_map.TrackMapError:
        meetings = track_map.fetch_meetings(year - 1)      # в январе календаря нового года может ещё не быть
    outline = track_map.fetch_outline(meetings[0][1], year)
    return f"{outline['name'] or 'трасса'}: точек контура: {len(outline['x'])}"


CHECKS = [
    ("Jolpica (чемпионат, календарь)", check_jolpica, True),
    ("Поток F1 live timing", check_f1_stream, True),
    ("OpenF1 (запасной)", check_openf1, False),
    ("Контуры трасс (MultiViewer)", check_track_maps, True),
]


def main():
    broken = []
    for name, check, critical in CHECKS:
        started = time.monotonic()
        try:
            result, ok = check(), True
        except Exception as exc:           # любая ошибка источника — это и есть то, что мы ищем
            result, ok = f"{type(exc).__name__}: {exc}", False
        mark = "ok  " if ok else ("СБОЙ" if critical else "внимание")
        print(f"{mark}  {name} ({time.monotonic() - started:.1f} с): {result}", flush=True)
        if not ok and critical:
            broken.append(name)
    if broken:
        print("\nСломано: " + ", ".join(broken))
        # аннотация в сводке прогона GitHub
        print(f"::error title=Источники данных::Не отвечает: {', '.join(broken)}")
        return 1
    print("\nВсе источники отвечают.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
