"""Собрать чемпионов всех сезонов из Jolpica в data/champions.json (встраивается в приложение).

    python tools/build_champions.py            # 1950 … прошлый сезон
    python tools/build_champions.py 2026       # … до указанного года включительно

У Jolpica нет запроса «все чемпионы сразу» — по одному запросу на сезон (Кубок конструкторов — с 1958),
поэтому список собирается заранее, а не в приложении. Текущий сезон приложение берёт из живого зачёта.
"""
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services import jolpica  # noqa: E402

OUT = ROOT / "data" / "champions.json"


def champion(path):
    for attempt in range(4):
        try:
            mr = jolpica._get(path)
            lists = mr["StandingsTable"].get("StandingsLists") or []
            return lists[0] if lists else None
        except jolpica.ApiError as exc:
            print("  повтор:", exc)
            time.sleep(5 * (attempt + 1))
    raise SystemExit(f"не удалось получить {path}")


def main():
    last = int(sys.argv[1]) if len(sys.argv) > 1 else date.today().year - 1
    rows = []
    for year in range(1950, last + 1):
        d = champion(f"{year}/driverStandings/1.json")
        c = champion(f"{year}/constructorStandings/1.json") if year >= 1958 else None
        if not d:
            continue
        ds = d["DriverStandings"][0]
        drv = ds["Driver"]
        row = {
            "season": str(year),
            "rounds": d.get("round", ""),
            "driver_id": drv["driverId"],
            "code": drv.get("code", ""),
            "name": f"{drv['givenName']} {drv['familyName']}",
            "nationality": drv.get("nationality", ""),
            "team": (ds.get("Constructors") or [{}])[-1].get("name", ""),
            "points": ds["points"],
            "wins": ds["wins"],
        }
        if c:
            cs = c["ConstructorStandings"][0]
            row.update(constructor=cs["Constructor"]["name"], constructor_points=cs["points"],
                       constructor_wins=cs["wins"], constructor_nationality=cs["Constructor"].get("nationality", ""))
        rows.append(row)
        print(year, row["name"], row.get("constructor", ""))
        time.sleep(0.6)       # Jolpica: ~4 запроса в секунду и ~200 в час без ключа
    OUT.write_text(json.dumps({"version": 1, "until": str(last), "champions": rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("записано:", OUT, len(rows))


if __name__ == "__main__":
    main()
