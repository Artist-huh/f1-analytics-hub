"""Архив: история сезонов с 1950 года и статистика трасс.

Загружается по запросу (когда пользователь открыл год или трассу), в фоне, и кэшируется в
таблице archive: прошлые сезоны не меняются и хранятся бессрочно, текущий — обновляется
раз в CURRENT_TTL. Список чемпионов всех лет встроен в приложение (data/champions.json,
tools/build_champions.py) — у API нет запроса «все чемпионы сразу».
"""
import json
import threading
import time
from collections import Counter

from . import db, jolpica, log, seed

CURRENT_TTL = 6 * 3600
CIRCUIT_TTL = 7 * 86400     # статистика трассы меняется раз в год — после гонки на ней
FIRST_SEASON = 1950

logger = log.get("archive")
_lock = threading.Lock()
_pending = set()
_errors = {}


def season_key(year):
    return f"season:{year}"


def circuit_key(circuit_id):
    return f"circuit:{circuit_id}"


def _fresh(key, ttl):
    data, fetched = db.load_archive(key)
    if data is None:
        return None, False
    return data, ttl is None or time.time() - fetched < ttl


def get(key, fetch, ttl=None, on_done=None):
    """Данные из кэша (или None) и запуск фоновой загрузки, если их нет или они устарели.
    on_done() вызывается из фонового потока, когда загрузка закончилась (успешно или нет)."""
    data, fresh = _fresh(key, ttl)
    if fresh:
        return data
    with _lock:
        if key in _pending:
            return data
        _pending.add(key)

    def job():
        try:
            db.save_archive(key, fetch())
            _errors.pop(key, None)
        except Exception as exc:       # сеть, лимит API, формат — показываем сохранённое или сообщение
            _errors[key] = str(exc)
            logger.warning("архив %s не загружен: %s", key, exc)
        finally:
            with _lock:
                _pending.discard(key)
            if on_done:
                on_done()

    threading.Thread(target=job, name=f"f1-archive-{key}", daemon=True).start()
    return data


def loading(key):
    return key in _pending


def error(key):
    return _errors.get(key)


def season(year, current_season, on_done=None):
    ttl = CURRENT_TTL if str(year) == str(current_season) else None
    return get(season_key(year), lambda: jolpica.fetch_season_archive(year), ttl, on_done)


def circuit(circuit_id, on_done=None):
    return get(circuit_key(circuit_id), lambda: jolpica.fetch_circuit_stats(circuit_id), CIRCUIT_TTL, on_done)


# ---------------------------------------------------------------- чемпионы
def champions():
    """Чемпионы прошлых сезонов из встроенного списка (новые сезоны — сверху)."""
    path = seed.default_path().parent / "champions.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))["champions"]
    except (OSError, ValueError, KeyError):
        return []
    return sorted(rows, key=lambda r: -int(r["season"]))


def records(rows):
    """Рекорды по встроенному списку: больше всего титулов у пилотов, команд и стран."""
    drivers = Counter(r["name"] for r in rows)
    teams = Counter(r["constructor"] for r in rows if r.get("constructor"))
    nations = Counter(r["nationality"] for r in rows if r.get("nationality"))
    first = {}
    for r in sorted(rows, key=lambda r: int(r["season"])):
        first.setdefault(r["name"], r)
    return {"drivers": drivers.most_common(10), "teams": teams.most_common(10), "nations": nations.most_common(10),
            "best_wins": max(rows, key=lambda r: int(r.get("wins") or 0), default=None),
            "first_titles": first}
