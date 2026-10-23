"""Статистика сезона по всем пилотам — чистые функции без сети и БД.

Вход — строки из db.load_season_results() / load_qualifying() / load_sprints():
позиции строками ('1', '12', 'R' — сход, 'D' — дисквалификация, 'W' — не стартовал).
"""


def to_int(value, default=None):
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def driver_stats(results, quali=(), sprints=()):
    """Показатели одного пилота по его результатам гонок, квалификаций и спринтов."""
    positions = [to_int(r["position"]) for r in results]
    finished = [p for p in positions if p is not None]
    gains = []
    for r in results:
        pos, grid = to_int(r["position"]), to_int(r.get("grid"))
        if pos is not None and grid:           # grid 0 = старт с пит-лейна, не считаем
            gains.append(grid - pos)
    q_positions = [to_int(q["position"]) for q in quali if to_int(q["position"])]
    race_points = sum(_num(r["points"]) for r in results)
    sprint_points = sum(_num(s["points"]) for s in sprints)
    starts = sum(1 for r in results if r["position"] != "W")
    return {
        "starts": starts,
        "wins": sum(1 for p in finished if p == 1),
        "podiums": sum(1 for p in finished if p <= 3),
        "top10": sum(1 for p in finished if p <= 10),
        "poles": sum(1 for p in q_positions if p == 1),
        "fastest_laps": sum(1 for r in results if str(r.get("fastest_rank")) == "1"),
        "dnf": sum(1 for r, p in zip(results, positions) if p is None and r["position"] != "W"),
        "best": min(finished) if finished else None,
        "avg_finish": sum(finished) / len(finished) if finished else None,
        "avg_quali": sum(q_positions) / len(q_positions) if q_positions else None,
        "avg_gain": sum(gains) / len(gains) if gains else None,
        "race_points": race_points,
        "sprint_points": sprint_points,
        "points_per_race": (race_points + sprint_points) / starts if starts else None,
    }


def group_by_driver(rows):
    out = {}
    for r in rows:
        out.setdefault(r["driver_id"], []).append(r)
    return out


def season_index(results, quali, sprints):
    """driver_id -> driver_stats для всех пилотов сезона."""
    res, q, sp = group_by_driver(results), group_by_driver(quali), group_by_driver(sprints)
    return {d: driver_stats(res.get(d, []), q.get(d, []), sp.get(d, [])) for d in set(res) | set(q) | set(sp)}


def rounds(results, sprints=()):
    """Номера прошедших этапов по возрастанию."""
    return sorted({to_int(r["round"]) for r in list(results) + list(sprints) if to_int(r["round"])})


def cumulative_points(driver_results, driver_sprints, all_rounds):
    """Набор очков по ходу сезона (гонки + спринты): список значений по all_rounds."""
    per_round = {}
    for r in list(driver_results) + list(driver_sprints):
        n = to_int(r["round"])
        per_round[n] = per_round.get(n, 0.0) + _num(r["points"])
    total, out = 0.0, []
    for n in all_rounds:
        total += per_round.get(n, 0.0)
        out.append(total)
    return out


def head_to_head(results1, results2):
    """Кто финишировал выше на общих этапах. Сход проигрывает финишу; два схода — не в счёт.
    -> (побед первого, побед второго, [(этап, название, поз1, поз2), ...])"""
    by_round = {r["round"]: r for r in results2}
    w1 = w2 = 0
    races = []
    for r1 in results1:
        r2 = by_round.get(r1["round"])
        if not r2:
            continue
        p1, p2 = to_int(r1["position"]), to_int(r2["position"])
        if p1 is None and p2 is None:
            continue
        if p2 is None or (p1 is not None and p1 < p2):
            w1 += 1
        else:
            w2 += 1
        races.append((r1["round"], r1["race_name"], r1["position"], r2["position"]))
    return w1, w2, races


def quali_head_to_head(quali1, quali2):
    """Кто квалифицировался выше на общих этапах -> (первый, второй)."""
    by_round = {q["round"]: to_int(q["position"]) for q in quali2}
    w1 = w2 = 0
    for q in quali1:
        b = by_round.get(q["round"])
        a = to_int(q["position"])
        if a is None or b is None:
            continue
        if a < b:
            w1 += 1
        elif b < a:
            w2 += 1
    return w1, w2


def finishing_ahead(selected_results):
    """Для 2+ пилотов: сколько раз каждый финишировал выше ВСЕХ остальных выбранных.
    selected_results: {driver_id: [results]} -> {driver_id: количество}."""
    by_round = {}
    for driver_id, rows in selected_results.items():
        for r in rows:
            by_round.setdefault(r["round"], {})[driver_id] = to_int(r["position"])
    wins = {d: 0 for d in selected_results}
    for positions in by_round.values():
        if len(positions) < len(selected_results):
            continue                                # кто-то из выбранных не участвовал
        ranked = [(p, d) for d, p in positions.items() if p is not None]
        if ranked:
            wins[min(ranked)[1]] += 1
    return wins


def podiums_by_round(results):
    """round -> [P1, P2, P3] (строки результатов) для прошедших гонок."""
    out = {}
    for r in results:
        p = to_int(r["position"])
        if p and p <= 3:
            out.setdefault(r["round"], [None, None, None])[p - 1] = r
    return {k: v for k, v in out.items() if all(v)}


def fmt_avg(value, digits=1):
    return "—" if value is None else f"{value:.{digits}f}"


# ---------------------------------------------------------------- борьба за титул
RACE_MAX = {"drivers": 25, "teams": 25 + 18}     # победа (у команды — 1-е и 2-е место)
SPRINT_MAX = {"drivers": 8, "teams": 8 + 7}      # очки за быстрый круг отменены с 2025 года


def remaining_points(races_left, sprints_left, kind="drivers"):
    return races_left * RACE_MAX[kind] + sprints_left * SPRINT_MAX[kind]


def title_race(rows, races_left, sprints_left, kind="drivers", next_has_sprint=False):
    """Кто ещё может стать чемпионом.

    rows — зачёт по порядку мест (у каждой строки "points"). Возвращает словарь:
      available — сколько очков ещё разыгрывается (одному участнику);
      contenders — [(строка, очки, максимум_возможных, отставание)] для тех, кто ещё в борьбе;
      clinched — лидер уже чемпион (никто не догонит даже при идеальном раскладе);
      next_clinch — на сколько очков лидеру нужно опередить второго в ближайшей гонке (уик-энде),
                    чтобы оформить титул досрочно; None — в ближайшую гонку это невозможно или уже чемпион.
    Ничьи по очкам решаются числом побед — здесь не учитываются: «может стать» = может хотя бы сравняться.
    """
    if not rows:
        return {"available": 0, "contenders": [], "clinched": False, "next_clinch": None}
    available = remaining_points(races_left, sprints_left, kind)
    leader = _num(rows[0]["points"])
    contenders = []
    for r in rows:
        pts = _num(r["points"])
        best = pts + available
        if best >= leader:
            contenders.append((r, pts, best, leader - pts))
    clinched = len(rows) == 1 or leader - _num(rows[1]["points"]) > available
    next_clinch = None
    if not clinched and len(rows) > 1 and races_left > 0:
        after = available - RACE_MAX[kind] - (SPRINT_MAX[kind] if next_has_sprint else 0)
        lead = leader - _num(rows[1]["points"])
        weekend_max = RACE_MAX[kind] + (SPRINT_MAX[kind] if next_has_sprint else 0)
        need = after - lead + 1          # отрыв после уик-энда должен стать больше, чем останется очков
        if need <= weekend_max:
            next_clinch = max(need, 0)
    return {"available": available, "contenders": contenders, "clinched": clinched, "next_clinch": next_clinch}
