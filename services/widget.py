"""Виджет на главный экран Android (расширение packages/flet_home_widget).

Что показать — чистая функция widget_data(). Отправка — только на Android и только при изменении:
отсчёт до старта виджет ведёт сам (Chronometer), поэтому раз в секунду ничего слать не нужно.
"""
import time

from . import log, notify

logger = log.get("widget")
SESSION_NAMES = {"FirstPractice": "Практика 1", "SecondPractice": "Практика 2", "ThirdPractice": "Практика 3",
                 "SprintQualifying": "Спринт-квалификация", "SprintShootout": "Спринт-квалификация",
                 "Sprint": "Спринт", "Qualifying": "Квалификация", "Race": "Гонка"}


def widget_data(schedule, standings, live_now=None, live_data=None, now=None):
    """-> {title, subtitle, start_ms, top, status, live} для виджета."""
    now = time.time() if now is None else now
    stamp = time.strftime("%H:%M", time.localtime(now))
    if live_now:
        race, key = live_now
        rows = (live_data or {}).get("rows") or []
        top = "   ".join(f"{r['position']}. {r['code']}" for r in rows[:3]) if rows else "Открой Live Timing"
        extra = ""
        if live_data and live_data.get("racing") and live_data.get("lap"):
            extra = f"круг {live_data['lap']}" + (f"/{live_data['total_laps']}" if live_data.get("total_laps") else "")
        elif live_data and live_data.get("remaining"):
            extra = f"осталось {live_data['remaining']}"
        subtitle = " · ".join(x for x in (race["race_name"], extra, (live_data or {}).get("track") or "") if x)
        return {"title": SESSION_NAMES.get(key, key), "subtitle": subtitle, "start_ms": 0, "top": top,
                "status": f"обновлено в {stamp}", "live": True}
    upcoming = [r for r in schedule if r["start_ts"] > now]
    leaders = "\n".join(f"{d['position']}. {d['name'].split()[-1]} — {d['points']}" for d in standings[:3])
    if not upcoming:
        return {"title": "Сезон завершён", "subtitle": "", "start_ms": 0, "top": leaders,
                "status": f"обновлено в {stamp}", "live": False}
    race = min(upcoming, key=lambda r: r["start_ts"])
    when = time.strftime("%d.%m, %H:%M", time.localtime(race["start_ts"]))
    return {"title": race["race_name"], "subtitle": f"Этап {race['round']} · {when}",
            "start_ms": int(race["start_ts"] * 1000), "top": leaders, "status": f"обновлено в {stamp}",
            "live": False}


class Widget:
    """Отправитель данных в виджет; на компьютере ничего не делает."""

    def __init__(self, page):
        self.page = page
        self.service = None
        self.sent = None
        self.enabled = notify.is_android()

    def push(self, data):
        """Отправить, если данные изменились (кроме времени «обновлено»)."""
        if not self.enabled:
            return False
        key = {k: v for k, v in data.items() if k != "status"}
        if key == self.sent:
            return False
        if self.service is None:
            try:
                from flet_home_widget import HomeWidget
            except ImportError as exc:
                logger.warning("виджет недоступен: %r", exc)
                self.enabled = False
                return False
            self.service = HomeWidget()            # регистрируется на текущей странице
        self.sent = key
        service = self.service

        async def send():
            try:
                count = await service.update(**data)
                logger.info("виджет обновлён, на экране: %s", count)
            except Exception as exc:
                logger.warning("виджет не обновлён: %r", exc)

        self.page.run_task(send)
        return True
