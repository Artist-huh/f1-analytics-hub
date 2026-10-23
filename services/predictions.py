"""Игра в прогнозы: поул и подиум до старта квалификации, очки за точность после гонки.

Прогнозы — данные пользователя (таблица predictions): очистка кэша их не трогает.
Очки:
  поул угадан                         — 5
  пилот на своей позиции подиума      — 5 за каждого
  пилот на подиуме, но на другой      — 2 за каждого
  весь подиум в точном порядке        — бонус 5
Максимум — 25 за этап.
"""
import time

from . import db

POLE_POINTS = 5
EXACT_POINTS = 5
PODIUM_POINTS = 2
PERFECT_BONUS = 5
MAX_POINTS = POLE_POINTS + 3 * EXACT_POINTS + PERFECT_BONUS

PICKS = ("pole", "p1", "p2", "p3")


def lock_time(race):
    """Приём прогнозов закрывается со стартом квалификации (если её нет в расписании — со стартом гонки)."""
    quali = next((s["ts"] for s in race.get("sessions", []) if s["key"] == "Qualifying"), None)
    return quali or race["start_ts"]


def is_open(race, now=None):
    return (time.time() if now is None else now) < lock_time(race)


def score(pick, actual_pole, actual_podium):
    """Очки и разбор по пунктам. pick — {pole, p1, p2, p3}; actual_podium — [P1, P2, P3] (driver_id).
    -> {"total": n, "items": {ключ: (очки, пояснение)}, "complete": есть ли результаты}"""
    if not actual_podium or len(actual_podium) < 3:
        return {"total": 0, "items": {}, "complete": False}
    items = {}
    if actual_pole:
        ok = pick.get("pole") == actual_pole
        items["pole"] = (POLE_POINTS if ok else 0, "поул угадан" if ok else "мимо")
    for i, key in enumerate(("p1", "p2", "p3")):
        chosen = pick.get(key)
        if chosen == actual_podium[i]:
            items[key] = (EXACT_POINTS, "точно")
        elif chosen in actual_podium:
            items[key] = (PODIUM_POINTS, "на подиуме, но на другом месте")
        else:
            items[key] = (0, "мимо")
    if [pick.get(k) for k in ("p1", "p2", "p3")] == list(actual_podium):
        items["bonus"] = (PERFECT_BONUS, "весь подиум в точном порядке")
    return {"total": sum(p for p, _ in items.values()), "items": items, "complete": True}


# ---------------------------------------------------------------- хранение
def save(season, rnd, pick):
    with db._connect() as con:
        con.execute("INSERT OR REPLACE INTO predictions VALUES (?,?,?,?,?,?,?)",
                    (str(season), int(rnd), pick.get("pole"), pick.get("p1"), pick.get("p2"), pick.get("p3"),
                     time.time()))


def load(season, rnd):
    with db._connect() as con:
        row = con.execute("SELECT * FROM predictions WHERE season=? AND round=?", (str(season), int(rnd))).fetchone()
    return {k: row[k] for k in PICKS} if row else {}


def load_season(season):
    """round -> прогноз."""
    with db._connect() as con:
        rows = con.execute("SELECT * FROM predictions WHERE season=? ORDER BY round", (str(season),)).fetchall()
    return {str(r["round"]): {k: r[k] for k in PICKS} for r in rows}


def season_stats(picks, results_by_round, poles_by_round):
    """Сводка сезона: очки, этапов с прогнозом, точных попаданий, лучший этап.
    results_by_round: round -> [P1, P2, P3]; poles_by_round: round -> driver_id."""
    scored = []
    exact = 0
    for rnd, pick in picks.items():
        s = score(pick, poles_by_round.get(rnd), results_by_round.get(rnd))
        if s["complete"]:
            scored.append((rnd, s["total"]))
            exact += sum(1 for k, (p, _) in s["items"].items() if k != "bonus" and p == (POLE_POINTS if k == "pole"
                                                                                         else EXACT_POINTS))
    best = max(scored, key=lambda x: x[1], default=None)
    return {"points": sum(p for _, p in scored), "rounds": len(scored), "exact": exact, "best": best,
            "max": len(scored) * MAX_POINTS}
