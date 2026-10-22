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
    "User-Agent": "FerrariLeclercHub/2.0 (student project)",
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


def fetch_standings():
    """-> (season, round, rows). rows пустой, если сезон ещё не начался."""
    mr = _get("current/driverStandings.json")
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
            })
        return season, str(block.get("round", "0")), rows
    except (KeyError, TypeError, IndexError) as exc:
        raise ApiError(f"standings: неожиданный формат ответа ({exc!r})") from exc


def fetch_driver_results(driver_id):
    """-> (season, rows) — результаты гонок пилота в текущем сезоне."""
    mr = _get(f"current/drivers/{driver_id}/results.json", params={"limit": 100})
    try:
        table = mr["RaceTable"]
        season = str(table.get("season", ""))
        rows = []
        for race in table.get("Races") or []:
            results = race.get("Results") or []
            if not results:
                continue
            res = results[0]
            circuit = race.get("Circuit", {})
            loc = circuit.get("Location", {})
            rows.append({
                "round": str(race["round"]),
                "race_name": race.get("raceName", ""),
                "circuit": circuit.get("circuitName", "—"),
                "country": loc.get("country", ""),
                "locality": loc.get("locality", ""),
                "date": race.get("date", ""),
                "position": str(res.get("positionText") or res.get("position", "—")),
                "grid": str(res.get("grid", "—")),
                "points": str(res.get("points", "0")),
                "status": res.get("status", ""),
            })
        return season, rows
    except (KeyError, TypeError) as exc:
        raise ApiError(f"results: неожиданный формат ответа ({exc!r})") from exc


def fetch_constructor_standings():
    """-> (season, round, rows) — Кубок конструкторов."""
    mr = _get("current/constructorStandings.json")
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
                "locality": loc.get("locality", ""),
                "country": loc.get("country", ""),
                "date": race["date"],
                "start_ts": start,
                "sessions": sessions,
            })
        return season, rows
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(f"schedule: неожиданный формат ответа ({exc!r})") from exc
