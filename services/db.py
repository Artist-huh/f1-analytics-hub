"""Локальная БД (SQLite): копия данных API + данные пользователя.

Кэш API (можно стереть):
  meta, standings, constructor_standings, race_results, qualifying, sprint_results,
  schedule, driver_media
Данные пользователя (clear_cache их не трогает):
  favorites — избранные пилоты, settings — настройки, predictions — прогнозы игры
"""
import json
import os
import shutil
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 4   # v4: schedule.circuit_id, таблица archive
APP_DIR = ".f1_analytics_hub"
LEGACY_DIRS = (".ferrari_leclerc_hub",)   # старое имя папки — база переносится при первом запуске

CACHE_TABLES = ("standings", "constructor_standings", "race_results", "qualifying", "sprint_results",
                "schedule", "driver_media", "archive", "meta")

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS standings (
    season      TEXT    NOT NULL,
    driver_id   TEXT    NOT NULL,
    position    INTEGER NOT NULL,
    points      REAL    NOT NULL,
    wins        INTEGER NOT NULL,
    code        TEXT,
    name        TEXT    NOT NULL,
    team        TEXT,
    nationality TEXT,
    number      TEXT,
    PRIMARY KEY (season, driver_id)
);
CREATE TABLE IF NOT EXISTS race_results (
    season       TEXT    NOT NULL,
    driver_id    TEXT    NOT NULL,
    round        INTEGER NOT NULL,
    race_name    TEXT,
    circuit      TEXT,
    country      TEXT,
    locality     TEXT,
    date         TEXT,
    position     TEXT,
    grid         TEXT,
    points       REAL,
    status       TEXT,
    team         TEXT,
    fastest_rank TEXT,
    PRIMARY KEY (season, driver_id, round)
);
CREATE TABLE IF NOT EXISTS qualifying (
    season    TEXT    NOT NULL,
    driver_id TEXT    NOT NULL,
    round     INTEGER NOT NULL,
    position  INTEGER NOT NULL,
    PRIMARY KEY (season, driver_id, round)
);
CREATE TABLE IF NOT EXISTS sprint_results (
    season    TEXT    NOT NULL,
    driver_id TEXT    NOT NULL,
    round     INTEGER NOT NULL,
    position  TEXT,
    points    REAL,
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
    circuit_id TEXT,
    PRIMARY KEY (season, round)
);
CREATE TABLE IF NOT EXISTS archive (
    key     TEXT PRIMARY KEY,
    json    TEXT NOT NULL,
    fetched REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS driver_media (
    code     TEXT PRIMARY KEY,
    ref      TEXT,
    number   TEXT,
    team     TEXT,
    headshot TEXT
);
CREATE TABLE IF NOT EXISTS predictions (
    season  TEXT    NOT NULL,
    round   INTEGER NOT NULL,
    pole    TEXT,
    p1      TEXT,
    p2      TEXT,
    p3      TEXT,
    saved   REAL    NOT NULL,
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


def data_dir() -> Path:
    """Папка данных: FLET_APP_STORAGE_DATA во Flet-сборках (Android, .exe), иначе домашняя папка."""
    base = os.environ.get("FLET_APP_STORAGE_DATA")
    return Path(base) if base else Path.home() / APP_DIR


def db_path() -> Path:
    """Где лежит БД. F1_HUB_DB — для тестов и особых случаев."""
    override = os.environ.get("F1_HUB_DB")
    if override:
        return Path(override)
    return data_dir() / "f1_hub.db"


def _migrate_legacy_dir(path):
    """Перенести базу из старой папки (избранное и настройки пользователя)."""
    if path.exists() or os.environ.get("F1_HUB_DB") or os.environ.get("FLET_APP_STORAGE_DATA"):
        return
    for name in LEGACY_DIRS:
        old = Path.home() / name / path.name
        if old.is_file():
            try:
                for suffix in ("", "-wal", "-shm"):
                    src = Path(str(old) + suffix)
                    if src.is_file():
                        shutil.copy2(src, Path(str(path) + suffix))
            except OSError:
                pass
            return


def _create_schema(path):
    con = sqlite3.connect(path, timeout=10)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        version = con.execute("PRAGMA user_version").fetchone()[0]
        if version != SCHEMA_VERSION:
            # Кэш API пересоздаётся по новой схеме (данные скачаются заново),
            # избранное и настройки не трогаем.
            for table in CACHE_TABLES:
                con.execute(f"DROP TABLE IF EXISTS {table}")
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
                _migrate_legacy_dir(path)
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


def set_meta(key, value):
    with _connect() as con:
        _meta_set(con, key, value)


def fetched_at(key):
    """Unix-время последней успешной загрузки или None."""
    value = get_meta(key)
    return float(value) if value else None


def _meta_set(con, key, value):
    con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, str(value)))


def _latest_season(con, key):
    row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


# ---------- standings ----------
def save_standings(season, rnd, rows, fetched=None):
    """Атомарно заменяет весь зачёт сезона."""
    data = [
        (season, r["driver_id"], int(r["position"]), float(r["points"]), int(r["wins"]),
         r.get("code", ""), r["name"], r.get("team", ""), r.get("nationality", ""), r.get("number", ""))
        for r in rows
    ]
    with _connect() as con:
        con.execute("DELETE FROM standings WHERE season=?", (season,))
        con.executemany("INSERT INTO standings VALUES (?,?,?,?,?,?,?,?,?,?)", data)
        _meta_set(con, "standings_season", season)
        _meta_set(con, "standings_round", rnd)
        _meta_set(con, "standings_fetched_at", fetched or time.time())


def load_standings():
    """Зачёт в формате, который ожидает UI (все значения — строки)."""
    with _connect() as con:
        season = _latest_season(con, "standings_season")
        if not season:
            return []
        rows = con.execute("SELECT * FROM standings WHERE season=? ORDER BY position", (season,)).fetchall()
    return [
        {
            "position": str(r["position"]),
            "points": _fmt_points(r["points"]),
            "wins": str(r["wins"]),
            "driver_id": r["driver_id"],
            "code": r["code"] or "",
            "name": r["name"],
            "team": r["team"] or "—",
            "nationality": r["nationality"] or "",
            "number": r["number"] or "",
            "season": r["season"],
        }
        for r in rows
    ]


# ---------- результаты гонок (все пилоты сезона) ----------
def _result_tuple(season, r):
    return (season, r["driver_id"], int(r["round"]), r.get("race_name", ""), r.get("circuit", ""),
            r.get("country", ""), r.get("locality", ""), r.get("date", ""), r["position"],
            r.get("grid", ""), float(r.get("points") or 0), r.get("status", ""), r.get("team", ""),
            r.get("fastest_rank", ""))


def save_season_results(season, rnd, rows, fetched=None):
    """Заменяет результаты всех гонок сезона (все пилоты)."""
    with _connect() as con:
        con.execute("DELETE FROM race_results WHERE season=?", (season,))
        con.executemany("INSERT INTO race_results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [_result_tuple(season, r) for r in rows])
        _meta_set(con, "results_season", season)
        _meta_set(con, "results_round", rnd)
        _meta_set(con, "results_fetched_at", fetched or time.time())


def _result_dict(r):
    return {
        "driver_id": r["driver_id"],
        "round": str(r["round"]),
        "race_name": r["race_name"],
        "circuit": r["circuit"],
        "country": r["country"],
        "locality": r["locality"],
        "date": r["date"],
        "position": r["position"],
        "grid": r["grid"],
        "points": _fmt_points(r["points"] or 0),
        "status": r["status"],
        "team": r["team"] or "",
        "fastest_rank": r["fastest_rank"] or "",
        "season": r["season"],
    }


def load_season_results():
    """Все результаты гонок последнего сезона: по этапам, внутри этапа — по позиции."""
    with _connect() as con:
        season = _latest_season(con, "results_season")
        if not season:
            return []
        rows = con.execute(
            "SELECT * FROM race_results WHERE season=? ORDER BY round, "
            "CAST(position AS INTEGER) = 0, CAST(position AS INTEGER)", (season,)).fetchall()
    return [_result_dict(r) for r in rows]


def load_results(driver_id):
    """Результаты одного пилота за последний сезон, по этапам."""
    with _connect() as con:
        season = _latest_season(con, "results_season")
        if not season:
            return []
        rows = con.execute("SELECT * FROM race_results WHERE season=? AND driver_id=? ORDER BY round",
                           (season, driver_id)).fetchall()
    return [_result_dict(r) for r in rows]


# ---------- квалификации и спринты ----------
def save_qualifying(season, rows):
    with _connect() as con:
        con.execute("DELETE FROM qualifying WHERE season=?", (season,))
        con.executemany("INSERT INTO qualifying VALUES (?,?,?,?)",
                        [(season, r["driver_id"], int(r["round"]), int(r["position"])) for r in rows])
        _meta_set(con, "qualifying_season", season)


def load_qualifying():
    with _connect() as con:
        season = _latest_season(con, "qualifying_season")
        if not season:
            return []
        rows = con.execute("SELECT * FROM qualifying WHERE season=? ORDER BY round, position", (season,)).fetchall()
    return [{"driver_id": r["driver_id"], "round": str(r["round"]), "position": str(r["position"])} for r in rows]


def save_sprints(season, rows):
    with _connect() as con:
        con.execute("DELETE FROM sprint_results WHERE season=?", (season,))
        con.executemany("INSERT INTO sprint_results VALUES (?,?,?,?,?)",
                        [(season, r["driver_id"], int(r["round"]), r["position"], float(r.get("points") or 0))
                         for r in rows])
        _meta_set(con, "sprints_season", season)


def load_sprints():
    with _connect() as con:
        season = _latest_season(con, "sprints_season")
        if not season:
            return []
        rows = con.execute("SELECT * FROM sprint_results WHERE season=? ORDER BY round", (season,)).fetchall()
    return [{"driver_id": r["driver_id"], "round": str(r["round"]), "position": r["position"],
             "points": _fmt_points(r["points"] or 0)} for r in rows]


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
        season = _latest_season(con, "constructors_season")
        if not season:
            return []
        rows = con.execute(
            "SELECT * FROM constructor_standings WHERE season=? ORDER BY position", (season,)).fetchall()
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
         r["date"], float(r["start_ts"]), json.dumps(r["sessions"]), r.get("circuit_id", ""))
        for r in rows
    ]
    with _connect() as con:
        con.execute("DELETE FROM schedule WHERE season=?", (season,))
        con.executemany("INSERT INTO schedule VALUES (?,?,?,?,?,?,?,?,?,?)", data)
        _meta_set(con, "schedule_season", season)
        _meta_set(con, "schedule_fetched_at", fetched or time.time())


def load_schedule():
    with _connect() as con:
        season = _latest_season(con, "schedule_season")
        if not season:
            return []
        rows = con.execute("SELECT * FROM schedule WHERE season=? ORDER BY round", (season,)).fetchall()
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
            "circuit_id": r["circuit_id"] or "",
            "season": r["season"],
        }
        for r in rows
    ]


# ---------- архив: история сезонов, статистика трасс (JSON по ключу) ----------
def save_archive(key, data, fetched=None):
    with _connect() as con:
        con.execute("INSERT OR REPLACE INTO archive VALUES (?, ?, ?)",
                    (key, json.dumps(data, ensure_ascii=False), fetched or time.time()))


def load_archive(key):
    """-> (данные, время загрузки) или (None, None)."""
    with _connect() as con:
        row = con.execute("SELECT json, fetched FROM archive WHERE key=?", (key,)).fetchone()
    return (json.loads(row["json"]), row["fetched"]) if row else (None, None)


# ---------- медиа пилотов (OpenF1) ----------
def save_driver_media(rows, fetched=None):
    with _connect() as con:
        con.execute("DELETE FROM driver_media")
        con.executemany("INSERT OR REPLACE INTO driver_media VALUES (?,?,?,?,?)",
                        [(r["code"], r.get("ref", ""), r.get("number", ""), r.get("team", ""),
                          r.get("headshot", "")) for r in rows])
        _meta_set(con, "media_fetched_at", fetched or time.time())


def load_driver_media():
    """code -> {ref, number, team, headshot}."""
    with _connect() as con:
        rows = con.execute("SELECT * FROM driver_media").fetchall()
    return {r["code"]: {"code": r["code"], "ref": r["ref"] or "", "number": r["number"] or "",
                        "team": r["team"] or "", "headshot": r["headshot"] or ""} for r in rows}


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
        for table in CACHE_TABLES:
            con.execute(f"DELETE FROM {table}")


def db_size_kb():
    try:
        return round(db_path().stat().st_size / 1024)
    except OSError:
        return 0
