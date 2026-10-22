"""Локальная БД (SQLite): копия данных API + данные пользователя.

Кэш API (можно стереть):
  meta, standings, constructor_standings, race_results, schedule
Данные пользователя (clear_cache их не трогает):
  favorites — избранные пилоты, settings — настройки
"""
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS standings (
    season    TEXT    NOT NULL,
    driver_id TEXT    NOT NULL,
    position  INTEGER NOT NULL,
    points    REAL    NOT NULL,
    wins      INTEGER NOT NULL,
    code      TEXT,
    name      TEXT    NOT NULL,
    team      TEXT,
    PRIMARY KEY (season, driver_id)
);
CREATE TABLE IF NOT EXISTS race_results (
    season    TEXT    NOT NULL,
    driver_id TEXT    NOT NULL,
    round     INTEGER NOT NULL,
    race_name TEXT,
    circuit   TEXT,
    country   TEXT,
    locality  TEXT,
    date      TEXT,
    position  TEXT,
    grid      TEXT,
    points    REAL,
    status    TEXT,
    PRIMARY KEY (season, driver_id, round)
);
CREATE TABLE IF NOT EXISTS constructor_standings (
    season         TEXT    NOT NULL,
    constructor_id TEXT    NOT NULL,
    position       INTEGER NOT NULL,
    points         REAL    NOT NULL,
    wins           INTEGER NOT NULL,
    name           TEXT    NOT NULL,
    nationality    TEXT,
    PRIMARY KEY (season, constructor_id)
);
CREATE TABLE IF NOT EXISTS schedule (
    season    TEXT    NOT NULL,
    round     INTEGER NOT NULL,
    race_name TEXT,
    circuit   TEXT,
    locality  TEXT,
    country   TEXT,
    date      TEXT,
    start_ts  REAL    NOT NULL,
    sessions  TEXT    NOT NULL,
    PRIMARY KEY (season, round)
);
CREATE TABLE IF NOT EXISTS favorites (
    driver_id TEXT PRIMARY KEY,
    added_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_init_lock = threading.Lock()
_initialized = set()


def db_path() -> Path:
    """Где лежит БД. F1_HUB_DB — для тестов; FLET_APP_STORAGE_DATA — папка данных
    приложения во Flet-сборках; иначе — домашняя папка пользователя."""
    override = os.environ.get("F1_HUB_DB")
    if override:
        return Path(override)
    base = os.environ.get("FLET_APP_STORAGE_DATA") or (Path.home() / ".ferrari_leclerc_hub")
    return Path(base) / "f1_hub.db"


def _create_schema(path):
    con = sqlite3.connect(path, timeout=10)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(SCHEMA)
        con.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        con.commit()
    finally:
        con.close()


@contextmanager
def _connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = str(path)
    if key not in _initialized:
        with _init_lock:
            if key not in _initialized:
                _create_schema(path)
                _initialized.add(key)
    con = sqlite3.connect(path, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        with con:  # commit при успехе, rollback при исключении
            yield con
    finally:
        con.close()


def _fmt_points(value):
    return f"{value:g}"  # 25.0 -> "25", 12.5 -> "12.5"


# ---------- meta ----------
def get_meta(key):
    with _connect() as con:
        row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def fetched_at(key):
    """Unix-время последней успешной загрузки или None."""
    value = get_meta(key)
    return float(value) if value else None


def _meta_set(con, key, value):
    con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, str(value)))


# ---------- standings ----------
def save_standings(season, rnd, rows, fetched=None):
    """Атомарно заменяет весь зачёт сезона."""
    data = [
        (season, r["driver_id"], int(r["position"]), float(r["points"]), int(r["wins"]),
         r.get("code", ""), r["name"], r.get("team", ""))
        for r in rows
    ]
    with _connect() as con:
        con.execute("DELETE FROM standings WHERE season=?", (season,))
        con.executemany("INSERT INTO standings VALUES (?,?,?,?,?,?,?,?)", data)
        _meta_set(con, "standings_season", season)
        _meta_set(con, "standings_round", rnd)
        _meta_set(con, "standings_fetched_at", fetched or time.time())


def load_standings():
    """Зачёт в формате, который ожидает UI (все значения — строки)."""
    with _connect() as con:
        row = con.execute("SELECT value FROM meta WHERE key='standings_season'").fetchone()
        if not row:
            return []
        rows = con.execute(
            "SELECT * FROM standings WHERE season=? ORDER BY position", (row["value"],)
        ).fetchall()
    return [
        {
            "position": str(r["position"]),
            "points": _fmt_points(r["points"]),
            "wins": str(r["wins"]),
            "driver_id": r["driver_id"],
            "code": r["code"] or "",
            "name": r["name"],
            "team": r["team"] or "—",
            "season": r["season"],
        }
        for r in rows
    ]


# ---------- race results ----------
def save_results(season, driver_id, rows, fetched=None):
    data = [
        (season, driver_id, int(r["round"]), r["race_name"], r["circuit"], r["country"],
         r["locality"], r["date"], r["position"], r["grid"], float(r["points"]), r["status"])
        for r in rows
    ]
    with _connect() as con:
        con.execute("DELETE FROM race_results WHERE season=? AND driver_id=?", (season, driver_id))
        con.executemany("INSERT INTO race_results VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", data)
        _meta_set(con, f"results_fetched_at:{driver_id}", fetched or time.time())


def load_results(driver_id):
    with _connect() as con:
        row = con.execute(
            "SELECT MAX(season) AS s FROM race_results WHERE driver_id=?", (driver_id,)
        ).fetchone()
        if not row or row["s"] is None:
            return []
        rows = con.execute(
            "SELECT * FROM race_results WHERE season=? AND driver_id=? ORDER BY round",
            (row["s"], driver_id),
        ).fetchall()
    return [
        {
            "round": str(r["round"]),
            "race_name": r["race_name"],
            "circuit": r["circuit"],
            "country": r["country"],
            "locality": r["locality"],
            "date": r["date"],
            "position": r["position"],
            "grid": r["grid"],
            "points": _fmt_points(r["points"]),
            "status": r["status"],
            "season": r["season"],
        }
        for r in rows
    ]


# ---------- constructor standings ----------
def save_constructors(season, rnd, rows, fetched=None):
    data = [
        (season, r["constructor_id"], int(r["position"]), float(r["points"]),
         int(r["wins"]), r["name"], r.get("nationality", ""))
        for r in rows
    ]
    with _connect() as con:
        con.execute("DELETE FROM constructor_standings WHERE season=?", (season,))
        con.executemany("INSERT INTO constructor_standings VALUES (?,?,?,?,?,?,?)", data)
        _meta_set(con, "constructors_season", season)
        _meta_set(con, "constructors_round", rnd)
        _meta_set(con, "constructors_fetched_at", fetched or time.time())


def load_constructors():
    with _connect() as con:
        row = con.execute("SELECT value FROM meta WHERE key='constructors_season'").fetchone()
        if not row:
            return []
        rows = con.execute(
            "SELECT * FROM constructor_standings WHERE season=? ORDER BY position", (row["value"],)
        ).fetchall()
    return [
        {
            "position": str(r["position"]),
            "points": _fmt_points(r["points"]),
            "wins": str(r["wins"]),
            "constructor_id": r["constructor_id"],
            "name": r["name"],
            "nationality": r["nationality"] or "",
            "season": r["season"],
        }
        for r in rows
    ]


# ---------- schedule ----------
def save_schedule(season, rows, fetched=None):
    data = [
        (season, int(r["round"]), r["race_name"], r["circuit"], r["locality"], r["country"],
         r["date"], float(r["start_ts"]), json.dumps(r["sessions"]))
        for r in rows
    ]
    with _connect() as con:
        con.execute("DELETE FROM schedule WHERE season=?", (season,))
        con.executemany("INSERT INTO schedule VALUES (?,?,?,?,?,?,?,?,?)", data)
        _meta_set(con, "schedule_season", season)
        _meta_set(con, "schedule_fetched_at", fetched or time.time())


def load_schedule():
    with _connect() as con:
        row = con.execute("SELECT value FROM meta WHERE key='schedule_season'").fetchone()
        if not row:
            return []
        rows = con.execute(
            "SELECT * FROM schedule WHERE season=? ORDER BY round", (row["value"],)
        ).fetchall()
    return [
        {
            "round": str(r["round"]),
            "race_name": r["race_name"],
            "circuit": r["circuit"],
            "locality": r["locality"],
            "country": r["country"],
            "date": r["date"],
            "start_ts": r["start_ts"],
            "sessions": json.loads(r["sessions"]),
            "season": r["season"],
        }
        for r in rows
    ]


# ---------- favorites ----------
def get_favorites():
    with _connect() as con:
        rows = con.execute("SELECT driver_id FROM favorites ORDER BY added_at").fetchall()
    return [r["driver_id"] for r in rows]


def toggle_favorite(driver_id):
    """Добавляет/убирает пилота. Возвращает True, если теперь он в избранном."""
    with _connect() as con:
        exists = con.execute("SELECT 1 FROM favorites WHERE driver_id=?", (driver_id,)).fetchone()
        if exists:
            con.execute("DELETE FROM favorites WHERE driver_id=?", (driver_id,))
            return False
        con.execute("INSERT INTO favorites VALUES (?, ?)", (driver_id, time.time()))
        return True


# ---------- settings ----------
def get_setting(key, default=None):
    with _connect() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with _connect() as con:
        con.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, str(value)))


# ---------- обслуживание ----------
def clear_cache():
    """Стирает копию данных API. Избранное и настройки остаются."""
    with _connect() as con:
        for table in ("standings", "constructor_standings", "race_results", "schedule", "meta"):
            con.execute(f"DELETE FROM {table}")


def db_size_kb():
    try:
        return round(db_path().stat().st_size / 1024)
    except OSError:
        return 0
