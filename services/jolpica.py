"""Клиент Jolpica F1 API (Ergast-совместимый). Только сеть и разбор JSON.

Ничего не знает ни про кэш, ни про интерфейс: либо возвращает разобранные
данные, либо бросает ApiError.
"""
import threading
import time
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://api.jolpi.ca/ergast/f1"
TIMEOUT = (3.05, 8)   # (connect, read), сек. Приложение не должно «висеть» на сети.
MIN_INTERVAL = 0.3    # Jolpica: ~4 запроса/с (burst) и ~200/час — не частим.


class ApiError(Exception):
    """Любая сетевая или форматная ошибка при обращении к API."""


_session = requests.Session()
_session.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=1,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            respect_retry_after_header=False,  # не ждать минутами из-за Retry-After
        )
    ),
)
_session.headers.update({
    "User-Agent": "F1AnalyticsHub/2.0 (fan project)",
    "Accept": "application/json",
})

_throttle_lock = threading.Lock()
_last_call = 0.0


def _get(path, params=None):
    global _last_call
    with _throttle_lock:
        pause = MIN_INTERVAL - (time.monotonic() - _last_call)
        if pause > 0:
            time.sleep(pause)
        _last_call = time.monotonic()
    try:
        resp = _session.get(f"{BASE_URL}/{path}", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()["MRData"]
    except (requests.RequestException, ValueError, KeyError) as exc:
        raise ApiError(f"{path}: {exc}") from exc


def fetch_standings(season="current"):
    """-> (season, round, rows). rows пустой, если сезон ещё не начался."""
    mr = _get(f"{season}/driverStandings.json", params={"limit": 100})
    try:
        table = mr["StandingsTable"]
        season = str(table.get("season", ""))
        lists = table.get("StandingsLists") or []
        if not lists:
            return season, "0", []
        block = lists[0]
        rows = []
        for item in block["DriverStandings"]:
            drv = item["Driver"]
            teams = item.get("Constructors") or []
            rows.append({
                "position": str(item["position"]),
                "points": str(item["points"]),
                "wins": str(item["wins"]),
                "driver_id": drv["driverId"],
                "code": drv.get("code", ""),
                "name": f"{drv['givenName']} {drv['familyName']}",
                "team": teams[-1]["name"] if teams else "—",  # последняя = текущая команда
                "nationality": drv.get("nationality", ""),
                "number": str(drv.get("permanentNumber", "")),
            })
        return season, str(block.get("round", "0")), rows
    except (KeyError, TypeError, IndexError) as exc:
        raise ApiError(f"standings: неожиданный формат ответа ({exc!r})") from exc


PAGE = 100   # больше Jolpica за один запрос не отдаёт


def _get_all(path):
    """Все страницы ответа (результаты сезона ~400 строк = 4-5 запросов). -> список Races."""
    races, offset, total = [], 0, None
    while total is None or offset < total:
        mr = _get(path, params={"limit": PAGE, "offset": offset})
        try:
            total = int(mr.get("total", 0))
            races += mr["RaceTable"].get("Races") or []
            season = str(mr["RaceTable"].get("season", ""))
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiError(f"{path}: неожиданный формат ответа ({exc!r})") from exc
        offset += PAGE
    return season, races


def _race_info(race):
    circuit = race.get("Circuit", {})
    loc = circuit.get("Location", {})
    return {
        "round": str(race["round"]),
        "race_name": race.get("raceName", ""),
        "circuit": circuit.get("circuitName", "—"),
        "country": loc.get("country", ""),
        "locality": loc.get("locality", ""),
        "date": race.get("date", ""),
    }


def fetch_season_results():
    """-> (season, round, rows) — результаты всех гонок сезона по всем пилотам.
    Гонка может быть разрезана между страницами — строки собираются по каждому Results."""
    season, races = _get_all("current/results.json")
    try:
        rows, last_round = [], 0
        for race in races:
            info = _race_info(race)
            last_round = max(last_round, int(race["round"]))
            for res in race.get("Results") or []:
                rows.append({
                    **info,
                    "driver_id": res["Driver"]["driverId"],
                    "position": str(res.get("positionText") or res.get("position", "—")),
                    "grid": str(res.get("grid", "")),
                    "points": str(res.get("points", "0")),
                    "status": res.get("status", ""),
                    "team": (res.get("Constructor") or {}).get("name", ""),
                    "fastest_rank": str((res.get("FastestLap") or {}).get("rank", "")),
                })
        return season, str(last_round), rows
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(f"results: неожиданный формат ответа ({exc!r})") from exc


def fetch_qualifying():
    """-> (season, rows) — позиции в квалификациях сезона (для поулов и среднего места)."""
    season, races = _get_all("current/qualifying.json")
    try:
        rows = [{"driver_id": q["Driver"]["driverId"], "round": str(race["round"]), "position": str(q["position"])}
                for race in races for q in race.get("QualifyingResults") or []]
        return season, rows
    except (KeyError, TypeError) as exc:
        raise ApiError(f"qualifying: неожиданный формат ответа ({exc!r})") from exc


def fetch_sprints():
    """-> (season, rows) — результаты спринтов (очки входят в график набора очков)."""
    season, races = _get_all("current/sprint.json")
    try:
        rows = [{"driver_id": r["Driver"]["driverId"], "round": str(race["round"]),
                 "position": str(r.get("positionText") or r.get("position", "—")),
                 "points": str(r.get("points", "0"))}
                for race in races for r in race.get("SprintResults") or []]
        return season, rows
    except (KeyError, TypeError) as exc:
        raise ApiError(f"sprint: неожиданный формат ответа ({exc!r})") from exc


def fetch_constructor_standings(season="current"):
    """-> (season, round, rows) — Кубок конструкторов (с 1958 года)."""
    mr = _get(f"{season}/constructorStandings.json", params={"limit": 100})
    try:
        table = mr["StandingsTable"]
        season = str(table.get("season", ""))
        lists = table.get("StandingsLists") or []
        if not lists:
            return season, "0", []
        block = lists[0]
        rows = []
        for item in block["ConstructorStandings"]:
            c = item["Constructor"]
            rows.append({
                "position": str(item["position"]),
                "points": str(item["points"]),
                "wins": str(item["wins"]),
                "constructor_id": c["constructorId"],
                "name": c["name"],
                "nationality": c.get("nationality", ""),
            })
        return season, str(block.get("round", "0")), rows
    except (KeyError, TypeError, IndexError) as exc:
        raise ApiError(f"constructors: неожиданный формат ответа ({exc!r})") from exc


_SESSION_KEYS = (
    "FirstPractice", "SecondPractice", "ThirdPractice",
    "SprintQualifying", "SprintShootout", "Sprint", "Qualifying",
)


def _to_ts(date, clock):
    """'2026-03-08' + '04:00:00Z' -> unix-время (UTC)."""
    clock = (clock or "00:00:00Z").rstrip("Z")
    return datetime.fromisoformat(f"{date}T{clock}").replace(tzinfo=timezone.utc).timestamp()


def fetch_schedule():
    """-> (season, rows) — календарь сезона с временем сессий (UTC unix)."""
    mr = _get("current.json", params={"limit": 100})
    try:
        table = mr["RaceTable"]
        season = str(table.get("season", ""))
        rows = []
        for race in table.get("Races") or []:
            start = _to_ts(race["date"], race.get("time"))
            sessions = [
                {"key": k, "ts": _to_ts(race[k]["date"], race[k].get("time"))}
                for k in _SESSION_KEYS if k in race
            ]
            sessions.append({"key": "Race", "ts": start})
            sessions.sort(key=lambda x: x["ts"])
            circuit = race.get("Circuit", {})
            loc = circuit.get("Location", {})
            rows.append({
                "round": str(race["round"]),
                "race_name": race.get("raceName", ""),
                "circuit": circuit.get("circuitName", "—"),
                "circuit_id": circuit.get("circuitId", ""),
                "locality": loc.get("locality", ""),
                "country": loc.get("country", ""),
                "date": race["date"],
                "start_ts": start,
                "sessions": sessions,
            })
        return season, rows
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(f"schedule: неожиданный формат ответа ({exc!r})") from exc


# ---------------------------------------------------------------- архив
def _person(drv):
    return {"driver_id": drv.get("driverId", ""), "code": drv.get("code", ""),
            "name": f"{drv.get('givenName', '')} {drv.get('familyName', '')}".strip(),
            "nationality": drv.get("nationality", "")}


def _winner_rows(races):
    rows = []
    for race in races:
        res = (race.get("Results") or [{}])[0]
        rows.append({**_race_info(race), "season": str(race.get("season", "")),
                     "circuit_id": race.get("Circuit", {}).get("circuitId", ""),
                     **_person(res.get("Driver", {})),
                     "team": (res.get("Constructor") or {}).get("name", ""),
                     "grid": str(res.get("grid", ""))})
    return rows


def fetch_season_archive(year):
    """Сезон year целиком: личный зачёт, Кубок конструкторов (с 1958), победители гонок."""
    _, rounds, standings = fetch_standings(str(year))
    constructors = fetch_constructor_standings(str(year))[2] if int(year) >= 1958 else []
    _, races = _get_all(f"{year}/results/1.json")
    try:
        winners = _winner_rows(races)
    except (KeyError, TypeError) as exc:
        raise ApiError(f"archive {year}: неожиданный формат ответа ({exc!r})") from exc
    return {"season": str(year), "rounds": rounds, "standings": standings, "constructors": constructors,
            "winners": winners}


def fetch_circuit_stats(circuit_id):
    """Трасса за все годы: победители, обладатели поула, авторы быстрых кругов (данные о кругах — с 2004)."""
    _, wins = _get_all(f"circuits/{circuit_id}/results/1.json")
    _, poles = _get_all(f"circuits/{circuit_id}/qualifying/1.json")
    _, fastest = _get_all(f"circuits/{circuit_id}/fastest/1/results.json")
    try:
        pole_rows = []
        for race in poles:
            q = (race.get("QualifyingResults") or [{}])[0]
            pole_rows.append({"season": str(race.get("season", "")), **_person(q.get("Driver", {})),
                              "team": (q.get("Constructor") or {}).get("name", ""),
                              "time": q.get("Q3") or q.get("Q2") or q.get("Q1") or ""})
        fastest_rows = []
        for race in fastest:
            for res in race.get("Results") or []:
                lap = res.get("FastestLap") or {}
                if str(lap.get("rank")) != "1":
                    continue
                fastest_rows.append({"season": str(race.get("season", "")), **_person(res.get("Driver", {})),
                                     "team": (res.get("Constructor") or {}).get("name", ""),
                                     "time": (lap.get("Time") or {}).get("time", "")})
        return {"circuit_id": circuit_id, "winners": _winner_rows(wins), "poles": pole_rows, "fastest": fastest_rows}
    except (KeyError, TypeError) as exc:
        raise ApiError(f"circuit {circuit_id}: неожиданный формат ответа ({exc!r})") from exc
