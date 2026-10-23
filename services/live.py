"""Live-тайминг через OpenF1: позиции, отрывы, шины, пит-стопы и сообщения дирекции гонки.

Берётся последняя сессия (session_key=latest). Во время сессии — свежие данные (OpenF1 может
отдавать их с задержкой: бесплатный доступ к данным в реальном времени ограничен), после — итог
последней сессии. Данные не сохраняются в БД: это «моментальный снимок», он обновляется,
пока открыт экран.
"""
import threading
import time
from datetime import datetime, timedelta, timezone

import requests

from . import log

API = "https://api.openf1.org/v1"
TIMEOUT = (3.05, 15)
MIN_INTERVAL = 0.4          # OpenF1 без ключа: несколько запросов в секунду
LIVE_MARGIN = 30 * 60       # сессия считается «идущей» ещё полчаса после официального конца
TYRES = {"SOFT": "S", "MEDIUM": "M", "HARD": "H", "INTERMEDIATE": "I", "WET": "W"}

logger = log.get("live")
_session = requests.Session()
_session.headers.update({"User-Agent": "F1AnalyticsHub/2.0 (fan project)"})
_throttle = threading.Lock()
_last = [0.0]


class LiveError(Exception):
    pass


LOCKED_TEXT = ("Во время сессии OpenF1 закрывает бесплатный доступ ко всем данным (и к прошлым гонкам). "
               "Данные появятся сами после окончания сессии.")


class LockedError(LiveError):
    """OpenF1 во время идущей сессии отвечает только с платным ключом — ждём окончания сессии."""

    def __str__(self):
        return LOCKED_TEXT


def _check(endpoint, data):
    if isinstance(data, list):
        return data
    detail = str(data.get("detail", data)) if isinstance(data, dict) else str(data)
    if "session in progress" in detail.lower() or "restricted to authenticated" in detail.lower():
        raise LockedError(detail)
    raise LiveError(f"{endpoint}: {detail}")


def _get(endpoint, query=""):
    with _throttle:
        pause = MIN_INTERVAL - (time.monotonic() - _last[0])
        if pause > 0:
            time.sleep(pause)
        _last[0] = time.monotonic()
    try:
        resp = _session.get(f"{API}/{endpoint}?session_key=latest{query}", timeout=TIMEOUT)
        data = resp.json() if resp.status_code in (401, 403) else None
        if data is None:
            resp.raise_for_status()
            data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise LiveError(f"{endpoint}: {exc}") from exc
    return _check(endpoint, data)        # {"detail": "..."} — лимит запросов, закрытый доступ и т.п.


def _ts(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def _last_by_driver(rows):
    out = {}
    for r in sorted(rows, key=lambda r: r.get("date") or ""):
        out[r["driver_number"]] = r
    return out


def fmt_gap(value):
    """Отрыв OpenF1: число секунд или строка «+1 LAP»."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.replace("LAPS", "кр.").replace("LAP", "кр.")
    return f"+{value:.3f}" if value else ""


def build_table(session, drivers, positions, intervals, stints, pits):
    """Сводная таблица (чистая функция): по местам — пилот, отрыв, шины, пит-стопы."""
    info = {d["driver_number"]: d for d in drivers}
    pos = _last_by_driver(positions)
    gaps = _last_by_driver(intervals)
    stint = {}
    for s in sorted(stints, key=lambda s: s.get("stint_number") or 0):
        stint[s["driver_number"]] = s
    current_lap = max((s.get("lap_end") or s.get("lap_start") or 0 for s in stints), default=0)
    pit_count = {}
    for p in pits:
        pit_count[p["driver_number"]] = pit_count.get(p["driver_number"], 0) + 1
    rows = []
    for number, p in pos.items():
        d = info.get(number, {})
        st = stint.get(number, {})
        age = None
        if st:
            last_lap = st.get("lap_end") or current_lap
            age = (st.get("tyre_age_at_start") or 0) + max(0, last_lap - (st.get("lap_start") or last_lap))
        g = gaps.get(number, {})
        rows.append({
            "position": p["position"], "number": number, "code": d.get("name_acronym", str(number)),
            "name": d.get("full_name", "").title(), "team": d.get("team_name", ""),
            "colour": f"#{d['team_colour']}" if d.get("team_colour") else None,
            "gap": fmt_gap(g.get("gap_to_leader")), "interval": fmt_gap(g.get("interval")),
            "tyre": TYRES.get((st.get("compound") or "").upper(), "?") if st else "",
            "tyre_age": age, "pits": pit_count.get(number, 0),
        })
    rows.sort(key=lambda r: r["position"])
    return {"rows": rows, "lap": current_lap}


def fetch(now=None):
    """Снимок последней сессии. -> {session, live, rows, lap, messages, updated}"""
    now = time.time() if now is None else now
    sessions = _get("sessions")
    if not sessions:
        raise LiveError("нет данных о сессии")
    s = sessions[-1]
    start, end = _ts(s.get("date_start")), _ts(s.get("date_end"))
    live = bool(start and end and start <= now <= end + LIVE_MARGIN)
    drivers = _get("drivers")
    positions = _get("position")
    last_change = max((_ts(p["date"]) or 0 for p in positions), default=now)
    since = (now - 90) if live else (last_change - 120)       # отрывы — только за последние минуты
    stamp = datetime.fromtimestamp(since, timezone.utc).isoformat()
    racing = (s.get("session_type") or "").lower() == "race"   # «Race» — и гонка, и спринт
    intervals = _get("intervals", f"&date>{stamp}") if racing else []
    stints = _get("stints")
    pits = _get("pit")
    messages = _get("race_control")
    table = build_table(s, drivers, positions, intervals, stints, pits)
    return {
        "session": {"name": s.get("session_name", ""), "type": s.get("session_type", ""),
                    "country": s.get("country_name", ""), "location": s.get("location", ""),
                    "circuit": s.get("circuit_short_name", ""), "start": start, "end": end,
                    "year": s.get("year")},
        "live": live,
        "racing": racing,
        "rows": table["rows"],
        "lap": table["lap"],
        "messages": [{"time": _ts(m.get("date")), "text": m.get("message", ""), "flag": m.get("flag"),
                      "lap": m.get("lap_number")} for m in messages[-6:]][::-1],
        "updated": now,
    }


# ---------------------------------------------------------------- кэш и фоновое обновление
_state = {"data": None, "error": None, "loading": False, "error_at": 0.0, "locked": False}
_lock = threading.Lock()
REFRESH_LIVE = 10           # сек. — пока сессия идёт
REFRESH_DONE = 300          # после сессии снимок почти не меняется


def snapshot():
    return _state["data"], _state["error"], _state["loading"]


ERROR_PAUSE = 30           # после ошибки — пауза перед повтором
LOCKED_PAUSE = 120         # доступ закрыт на время сессии — спрашиваем реже


def stale():
    if _state["error"]:
        pause = LOCKED_PAUSE if _state["locked"] else ERROR_PAUSE
        if time.time() - _state["error_at"] < pause:
            return False
    data = _state["data"]
    if not data:
        return True
    period = REFRESH_LIVE if data["live"] else REFRESH_DONE
    return time.time() - data["updated"] > period


def refresh(on_done=None):
    """Обновить снимок в фоне (не чаще одного запроса одновременно)."""
    with _lock:
        if _state["loading"]:
            return
        _state["loading"] = True

    def job():
        try:
            _state["data"] = fetch()
            _state["error"] = None
        except LiveError as exc:
            _state["error"] = str(exc)
            _state["error_at"] = time.time()
            _state["locked"] = isinstance(exc, LockedError)
            logger.warning("live-тайминг не обновлён: %s", exc)
        finally:
            _state["loading"] = False
            if on_done:
                on_done()

    threading.Thread(target=job, name="f1-live", daemon=True).start()


def session_is_live(schedule, now=None):
    """По календарю: идёт ли сейчас какая-нибудь сессия (без запроса к OpenF1).
    -> (этап, ключ сессии) или None. Длительность сессии считаем ~2 ч."""
    now = time.time() if now is None else now
    for race in schedule:
        for s in race["sessions"]:
            if s["ts"] <= now <= s["ts"] + 2 * 3600:
                return race, s["key"]
    return None


# ---------------------------------------------------------------- стратегия шин прошедшей гонки
def _query(endpoint, query):
    """Запрос к OpenF1 с произвольными параметрами (не только последняя сессия)."""
    with _throttle:
        pause = MIN_INTERVAL - (time.monotonic() - _last[0])
        if pause > 0:
            time.sleep(pause)
        _last[0] = time.monotonic()
    try:
        resp = _session.get(f"{API}/{endpoint}?{query}", timeout=TIMEOUT)
        data = resp.json() if resp.status_code in (401, 403) else None
        if data is None:
            resp.raise_for_status()
            data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise LiveError(f"{endpoint}: {exc}") from exc
    return _check(endpoint, data)


def race_session(year, race_date, session_name="Race"):
    """Сессия OpenF1 гонки (или спринта) по дате старта: названия этапов у OpenF1 и Jolpica различаются."""
    sessions = _query("sessions", f"year={year}&session_type=Race")
    match = [s for s in sessions if (s.get("date_start") or "")[:10] == race_date
             and s.get("session_name") == session_name]
    if not match:
        raise LiveError(f"нет сессии «{session_name}» за {race_date}")
    return match[0]


def session_drivers(key):
    """Номер -> {code, team, colour}."""
    return {str(d["driver_number"]): {"code": d.get("name_acronym", ""), "team": d.get("team_name", ""),
                                      "colour": d.get("team_colour")} for d in _query("drivers", f"session_key={key}")}


def fetch_strategy(year, race_date, session_name="Race"):
    """Стинты и пит-стопы гонки (или спринта) по дате. -> данные для экрана стратегии."""
    key = race_session(year, race_date, session_name)["session_key"]
    stints = _query("stints", f"session_key={key}")
    if not stints:
        raise LiveError("OpenF1 ещё не опубликовал стинты этой гонки")
    pits = _query("pit", f"session_key={key}")
    return {
        "session_key": key,
        "laps": max((s.get("lap_end") or s.get("lap_start") or 0) for s in stints),
        "drivers": session_drivers(key),
        "stints": [{"driver": str(s["driver_number"]), "n": s.get("stint_number") or 0,
                    "start": s.get("lap_start") or 1, "end": s.get("lap_end") or s.get("lap_start") or 1,
                    "tyre": TYRES.get((s.get("compound") or "").upper(), "?"),
                    "age": s.get("tyre_age_at_start") or 0} for s in stints],
        "pits": [{"driver": str(p["driver_number"]), "lap": p.get("lap_number"),
                  "duration": p.get("pit_duration")} for p in pits],
    }


def strategy_rows(data, order=()):
    """Полосы стратегии (чистая функция): [{code, team, colour, stints:[{tyre, start, end, laps, age}], pits}].
    order — коды пилотов по местам финиша; остальные — в конце по номеру."""
    by_driver = {}
    for s in sorted(data["stints"], key=lambda s: (s["driver"], s["n"])):
        by_driver.setdefault(s["driver"], []).append(s)
    pits = {}
    for p in data["pits"]:
        pits.setdefault(p["driver"], []).append(p)
    rows = []
    for number, stints in by_driver.items():
        info = data["drivers"].get(number, {})
        rows.append({"number": number, "code": info.get("code") or number, "team": info.get("team", ""),
                     "colour": f"#{info['colour']}" if info.get("colour") else None,
                     "stints": [{**s, "laps": max(1, s["end"] - s["start"] + 1)} for s in stints],
                     "pits": sorted((p for p in pits.get(number, []) if p["lap"]), key=lambda p: p["lap"])})
    rank = {code: i for i, code in enumerate(order)}
    rows.sort(key=lambda r: (rank.get(r["code"], 999), int(r["number"]) if r["number"].isdigit() else 999))
    return rows
