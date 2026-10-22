"""Начальный снимок данных: позволяет показать реальные данные при первом запуске без сети.

Снимок — JSON-файл data/seed.json рядом с приложением (или путь из F1_HUB_SEED).
Создать его нужно один раз, при наличии интернета, и положить в сборку:

    python -m services.seed export --refresh        # скачать свежие данные и записать data/seed.json
    python -m services.seed export                  # записать то, что уже есть в БД
    python -m services.seed import                  # загрузить снимок в пустую БД

Снимок импортируется только в ПУСТУЮ базу и помечается временем создания, поэтому
интерфейс честно показывает «Из кэша» и дату, а не выдаёт его за свежие данные.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import db, log

logger = log.get("seed")
VERSION = 1


def default_path():
    override = os.environ.get("F1_HUB_SEED")
    if override:
        return Path(override)
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))  # _MEIPASS — PyInstaller
    return base / "data" / "seed.json"


def export_snapshot(path=None, driver_id="leclerc"):
    """Записывает текущее содержимое БД в JSON. Возвращает путь или None, если БД пуста."""
    standings = db.load_standings()
    if not standings:
        logger.warning("экспорт снимка отменён: в БД нет данных")
        return None
    snapshot = {
        "version": VERSION,
        "exported_at": db.fetched_at("standings_fetched_at") or time.time(),
        "season": standings[0]["season"],
        "round": db.get_meta("standings_round") or "0",
        "standings": standings,
        "constructors": db.load_constructors(),
        "constructors_round": db.get_meta("constructors_round") or "0",
        "driver_id": driver_id,
        "results": db.load_results(driver_id),
        "schedule": db.load_schedule(),
    }
    path = Path(path) if path else default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("снимок записан: %s", path)
    return path


def import_if_empty(path=None):
    """Загружает снимок, если БД пуста. True — данные импортированы."""
    path = Path(path) if path else default_path()
    try:
        if db.load_standings() or not path.is_file():
            return False
        snap = json.loads(path.read_text(encoding="utf-8"))
        if snap.get("version") != VERSION:
            logger.warning("снимок %s другой версии (%s) — пропущен", path, snap.get("version"))
            return False
        stamp = float(snap["exported_at"])
        season = str(snap["season"])
        db.save_standings(season, snap.get("round", "0"), snap["standings"], fetched=stamp)
        if snap.get("constructors"):
            db.save_constructors(season, snap.get("constructors_round", "0"), snap["constructors"], fetched=stamp)
        if snap.get("results"):
            db.save_results(season, snap.get("driver_id", "leclerc"), snap["results"], fetched=stamp)
        if snap.get("schedule"):
            db.save_schedule(season, snap["schedule"], fetched=stamp)
        logger.info("импортирован начальный снимок данных (сезон %s) из %s", season, path)
        return True
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("снимок не импортирован (%s): %r", path, exc)
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m services.seed", description=__doc__.split("\n")[0])
    parser.add_argument("action", choices=["export", "import"])
    parser.add_argument("path", nargs="?", help="файл снимка (по умолчанию data/seed.json)")
    parser.add_argument("--refresh", action="store_true", help="перед экспортом скачать данные из API")
    args = parser.parse_intermixed_args(argv)  # путь можно писать и после --refresh
    if args.action == "export":
        if args.refresh:
            from . import f1_api
            if not f1_api.refresh_all(force=True, manual=True):
                print("Не удалось скачать данные — проверь подключение к интернету.")
                return 1
        out = export_snapshot(args.path)
        print(f"Снимок записан: {out}" if out else "В базе нет данных — сначала запусти с --refresh.")
        return 0 if out else 1
    print("Импортировано." if import_if_empty(args.path) else "Ничего не импортировано (БД не пуста или снимка нет).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
