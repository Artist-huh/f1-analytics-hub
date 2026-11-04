"""О чём сообщать: события сезона из данных, которые приложение уже загрузило (без сети и интерфейса).

Каждая функция возвращает список (id, заголовок, текст). id стабилен: одно и то же событие получает один
и тот же id при каждой проверке, поэтому state шлёт его ровно один раз. Виды уведомлений (KINDS) включаются
по отдельности в «Настройках».

Push с сервера не используется: на iPhone он требует платного аккаунта Apple, на Android — своего сервера.
Уведомления строит само приложение, пока оно запущено (в том числе свёрнуто).
"""
from . import reference, stats

# ключ настройки notif_<ключ> -> (заголовок переключателя, пояснение). Порядок — порядок в «Настройках».
KINDS = {
    "sessions": ("Напоминания о сессиях", "За час до практик, квалификации, спринта и гонки"),
    "live": ("Начало сессии и флаги", "Сессия началась; сейфти-кар, VSC и красный флаг — пока открыт Live Timing"),
    "stage": ("Итоги этапа", "Поул, спринт и подиум гонки"),
    "results": ("Избранные пилоты", "Места и очки избранных после гонки, их движение в чемпионате"),
    "championship": ("Чемпионат", "Новый лидер, кто может оформить титул, чемпион определён"),
    "predictions": ("Прогнозы", "Напоминание до закрытия приёма и очки после гонки"),
}
STARTED_WINDOW = 10 * 60        # «сессия началась» — только в первые 10 минут, позже не сообщаем
PREDICT_LEAD = 3 * 3600         # напомнить о прогнозе за 3 часа до закрытия приёма
LIVE_FLAGS = ("Сейфти-кар", "Виртуальный сейфти-кар", "Красный флаг")


def _num(value):
    return stats.to_int(value)


def _last_name(standings, driver_id):
    for d in standings:
        if d["driver_id"] == driver_id:
            return d["name"].split()[-1]
    return driver_id


def _race_name(schedule, season, rnd):
    for race in schedule:
        if str(race["round"]) == str(rnd) and str(race.get("season", season)) == str(season):
            return race["race_name"]
    return f"этап {rnd}"


def _ordinal(n):
    return f"{n}-е"


# ---------------------------------------------------------------- live
def sessions_started(schedule, now):
    """Сессия началась (первые 10 минут после старта по календарю)."""
    out = []
    for race in schedule:
        for s in race["sessions"]:
            if 0 <= now - s["ts"] < STARTED_WINDOW:
                name = reference.SESSIONS.get(s["key"], s["key"])
                out.append((f"{race.get('season', '')}:{race['round']}:{s['key']}:start", f"{name}: старт",
                            f"{race['race_name']} — открой Live Timing: позиции, отрывы, шины"))
    return out


def live_flags(snapshot, previous=None):
    """Сейфти-кар, VSC, красный флаг: сообщаем, когда флаг появился (previous — флаг прошлого снимка), а не
    пока он держится. Раньше в id был номер круга: один сейфти-кар на 6 кругов давал 6 уведомлений, а второй
    красный флаг квалификации (кругов нет) терялся. id — время снимка, когда флаг появился."""
    if not snapshot or not snapshot.get("live") or snapshot.get("track") not in LIVE_FLAGS:
        return []
    if snapshot.get("track") == previous:
        return []
    session = snapshot.get("session") or {}
    lap = snapshot.get("lap") or ""
    name = reference.SESSIONS.get(session.get("name", ""), session.get("name") or "Сессия")
    where = name + (f", круг {lap}" if lap else "")
    key = f"{session.get('year', '')}:{session.get('location', '')}:{session.get('name', '')}"
    return [(f"{key}:flag:{snapshot['track']}:{int(snapshot.get('updated') or 0)}", snapshot["track"], where)]


# ---------------------------------------------------------------- итоги этапа
def stage_results(season, schedule, standings, season_results, qualifying, sprints):
    """Поул последней квалификации, подиум последнего спринта и последней гонки."""
    out = []
    if qualifying:
        rnd = max(_num(r["round"]) for r in qualifying)
        pole = next((r for r in qualifying if _num(r["round"]) == rnd and _num(r["position"]) == 1), None)
        if pole:
            out.append((f"{season}:{rnd}:pole", f"Поул: {_last_name(standings, pole['driver_id'])}",
                        f"{_race_name(schedule, season, rnd)} — квалификация завершена"))
    for rows, kind, label in ((sprints, "sprint", "Спринт"), (season_results, "race", "Гонка")):
        if not rows:
            continue
        rnd = max(_num(r["round"]) for r in rows)
        podium = sorted((r for r in rows if _num(r["round"]) == rnd and (_num(r["position"]) or 99) <= 3),
                        key=lambda r: _num(r["position"]))
        if len(podium) < 3:
            continue
        names = [_last_name(standings, r["driver_id"]) for r in podium]
        out.append((f"{season}:{rnd}:{kind}", f"{label}: победа — {names[0]}",
                    f"{_race_name(schedule, season, rnd)} — подиум: {', '.join(names)}"))
    return out


# ---------------------------------------------------------------- избранные
def favorites_moves(season, rnd, favorites, standings, previous):
    """Избранный пилот сменил место в чемпионате после этапа. previous — {driver_id: место} до этапа."""
    out = []
    for d in standings:
        was, now = previous.get(d["driver_id"]), _num(d["position"])
        if d["driver_id"] not in favorites or not was or not now or was == now:
            continue
        verb = "поднялся" if now < was else "опустился"
        out.append((f"{season}:{rnd}:move:{d['driver_id']}",
                    f"{d['name'].split()[-1]} {verb} на {_ordinal(now)} место",
                    f"Чемпионат: было {_ordinal(was)}, очков — {d['points']}"))
    return out


# ---------------------------------------------------------------- чемпионат
def championship(season, rnd, standings, previous_leader, title):
    """Новый лидер; лидер может оформить титул на ближайшем этапе; чемпион определён.
    title — результат AppState.title_race() (stats.title_race + races_left)."""
    out = []
    if not standings:
        return out
    leader = standings[0]
    name = leader["name"].split()[-1]
    if previous_leader and previous_leader != leader["driver_id"]:
        out.append((f"{season}:{rnd}:leader:{leader['driver_id']}", f"Новый лидер чемпионата: {name}",
                    f"{leader['points']} очков после этапа {rnd}"))
    if title.get("clinched"):
        out.append((f"{season}:champion", f"{name} — чемпион мира {season}!",
                    "Титул оформлен: соперники уже не догонят"))
    elif title.get("next_clinch") is not None and len(standings) > 1:
        terms = title.get("next_clinch_terms") or [(standings[1], title["next_clinch"])]
        out.append((f"{season}:{rnd}:clinch", f"{name} может стать чемпионом на следующем этапе",
                    "Для этого нужно " + ", ".join(_clinch_term(r, n) for r, n in terms)))
    return out


def _clinch_term(rival, need):
    """Условие против одного соперника: опередить, не уступить или уступить не больше чем на N."""
    who = rival["name"].split()[-1]
    if need > 0:
        return f"набрать на {need} {_points(need)} больше, чем {who}"
    if need == 0:
        return f"набрать не меньше, чем {who}"
    return f"уступить {who} не больше {-need} {_points(-need)}"


def _points(n):
    from ui.fmt import plural
    return plural(n, "очко", "очка", "очков")


# ---------------------------------------------------------------- прогнозы
def prediction_reminder(season, race, lock_ts, has_pick, now):
    """Приём прогнозов закрывается в ближайшие 3 часа, а прогноза нет."""
    if not race or has_pick or not 0 < lock_ts - now <= PREDICT_LEAD:
        return []
    hours = max(1, round((lock_ts - now) / 3600))
    return [(f"{season}:{race['round']}:predict", "Прогноз ещё не сделан",
             f"{race['race_name']}: приём закроется через {hours} ч — выбери поул и подиум")]


def prediction_scored(season, schedule, picks, season_results, qualifying):
    """Очки за прогноз на последнюю прошедшую гонку. picks — {round: прогноз}."""
    from . import predictions
    if not season_results:
        return []
    rnd = max(_num(r["round"]) for r in season_results)
    pick = picks.get(str(rnd))
    if not pick:
        return []
    podium = [r["driver_id"] for r in sorted(
        (r for r in season_results if _num(r["round"]) == rnd and (_num(r["position"]) or 99) <= 3),
        key=lambda r: _num(r["position"]))]
    pole = next((r["driver_id"] for r in qualifying if _num(r["round"]) == rnd and _num(r["position"]) == 1), None)
    result = predictions.score(pick, pole, podium)
    if not result["complete"]:
        return []
    return [(f"{season}:{rnd}:predict-score", f"Прогноз: {result['total']} из {predictions.MAX_POINTS} очков",
             f"{_race_name(schedule, season, rnd)} — разбор на экране «Прогнозы»")]


# ---------------------------------------------------------------- при закрытом приложении (Android)
PLAN_HORIZON = 14 * 86400       # будильники — на две недели вперёд (ближайшие этапы)
PLAN_MAX = 40


def planned(schedule, now, kinds_on, lead, prediction=None):
    """События с заранее известным временем — для системного будильника Android, чтобы они пришли и при
    закрытом приложении. kinds_on — включённые виды; prediction — (этап, время закрытия приёма) или None.
    id — те же, что у уведомлений из приложения. -> [{id, at_ms, title, text}] по времени."""
    from ui.fmt import fmt_clock, fmt_day
    out = []
    remind = set(reference.REMIND_SESSIONS)
    for race in schedule:
        for s in race["sessions"]:
            name = reference.SESSIONS.get(s["key"], s["key"])
            base = f"{race.get('season', '')}:{race['round']}:{s['key']}"
            when = f"{race['race_name']} · старт {fmt_day(s['ts'])} в {fmt_clock(s['ts'])}"
            if "sessions" in kinds_on and s["key"] in remind:
                out.append({"id": base, "at": s["ts"] - lead, "title": f"{name} через {lead // 60} мин",
                            "text": when})
            if "live" in kinds_on:
                out.append({"id": f"{base}:start", "at": s["ts"], "title": f"{name}: старт",
                            "text": f"{race['race_name']} — открой Live Timing: позиции, отрывы, шины"})
    if "predictions" in kinds_on and prediction:
        race, lock_ts = prediction
        out.append({"id": f"{race.get('season', '')}:{race['round']}:predict", "at": lock_ts - PREDICT_LEAD,
                    "title": "Прогноз ещё не сделан",
                    "text": f"{race['race_name']}: приём закроется через 3 ч — выбери поул и подиум"})
    soon = sorted((a for a in out if now < a["at"] <= now + PLAN_HORIZON), key=lambda a: a["at"])[:PLAN_MAX]
    return [{"id": a["id"], "at_ms": int(a["at"] * 1000), "title": a["title"], "text": a["text"]} for a in soon]
