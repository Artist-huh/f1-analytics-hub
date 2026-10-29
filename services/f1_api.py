"""Единая точка доступа к данным для UI.

Принципы:
  * Только реальные данные: из API или из последней успешной копии в SQLite.
    Выдуманных «запасных» значений нет — если данных нет, UI получает пустой список.
  * Чтение мгновенное: get_cached_*() никогда не ходит в сеть.
  * Обновление — в фоне (start_background_refresh), с экспоненциальной паузой при сбоях.
"""
import hashlib
import json
import threading
import time

from . import db, jolpica, log, media, seed

REFRESH_INTERVAL = 300   # сек. 2 запроса / 5 мин = 24 в час при лимите Jolpica ~200
RESULTS_TTL = 6 * 3600   # результаты сезона перезапрашиваем при новом этапе или раз в 6 часов
RESULTS_RETRY = 1800     # результаты отстают от зачёта (ещё не опубликованы) — повтор через 30 минут
FAIL_COOLDOWN = 20       # сек. после сбоя не долбим сеть при обычных (не ручных) вызовах
SCHEDULE_TTL = 6 * 3600  # календарь меняется редко — не чаще раза в 6 часов
RACE_DURATION = 2 * 3600 # сколько считаем гонку «идущей» после старта

_lock = threading.RLock()
_state = {"error": None, "fail_until": 0.0}
_config = {"interval": REFRESH_INTERVAL}  # текущий интервал фонового обновления


logger = log.get("api")


def _mark_ok():
    _state["error"] = None
    _state["fail_until"] = 0.0


def _mark_fail(exc):
    _state["error"] = str(exc)
    _state["fail_until"] = time.time() + FAIL_COOLDOWN
    logger.warning("сеть недоступна, остаёмся на данных из БД: %s", exc)


# ---------- обновление из сети ----------
def _refresh(fetch_and_save, force):
    with _lock:
        if not force and time.time() < _state["fail_until"]:
            return False
        try:
            fetch_and_save()
            _mark_ok()
            return True
        except Exception as exc:  # фоновый поток не должен падать ни при каких ошибках
            _mark_fail(exc)
            return False


def refresh_standings(force=False):
    def job():
        season, rnd, rows = jolpica.fetch_standings()
        if rows:  # пустой ответ (сезон не начался) не должен стирать старую копию
            db.save_standings(season, rnd, rows)
    return _refresh(job, force)


def refresh_constructors(force=False):
    def job():
        season, rnd, rows = jolpica.fetch_constructor_standings()
        if rows:
            db.save_constructors(season, rnd, rows)
    return _refresh(job, force)


def refresh_season_results(force=False, ignore_ttl=False):
    """Результаты гонок, квалификации и спринты всех пилотов (~10 запросов).
    Один раз на каждый новый этап зачёта; если результаты отстают от зачёта (их ещё
    не опубликовали) — повтор раз в RESULTS_RETRY; иначе — раз в RESULTS_TTL."""
    standings_round = db.get_meta("standings_round")
    ts = db.fetched_at("results_fetched_at")
    age = time.time() - ts if ts is not None else float("inf")
    complete = db.get_meta("results_round") == standings_round
    if (not ignore_ttl and db.get_meta("results_for_round") == standings_round
            and age < (RESULTS_TTL if complete else RESULTS_RETRY)):
        return True

    def job():
        season, rnd, rows = jolpica.fetch_season_results()
        q_season, quali = jolpica.fetch_qualifying()
        s_season, sprints = jolpica.fetch_sprints()
        if rows:
            db.save_season_results(season, rnd, rows)
        if quali:
            db.save_qualifying(q_season, quali)
        if sprints:
            db.save_sprints(s_season, sprints)
        db.set_meta("results_for_round", standings_round or "")
    return _refresh(job, force)


def refresh_schedule(force=False, ignore_ttl=False):
    ts = db.fetched_at("schedule_fetched_at")
    complete = all(r.get("circuit_id") for r in db.load_schedule())   # старый снимок — без идентификаторов трасс
    if not ignore_ttl and complete and ts is not None and time.time() - ts < SCHEDULE_TTL:
        return True  # свежий календарь уже есть

    def job():
        season, rows = jolpica.fetch_schedule()
        if rows:
            db.save_schedule(season, rows)
    return _refresh(job, force)


def refresh_all(force=False, manual=False):
    """Обновить всё, что нужно UI. Первая же сетевая ошибка прерывает цепочку.
    manual=True (кнопка «Обновить») игнорирует TTL календаря."""
    steps = (
        lambda: refresh_standings(force),
        lambda: refresh_constructors(force),
        lambda: refresh_season_results(force, ignore_ttl=manual),
        lambda: refresh_schedule(force, ignore_ttl=manual),
    )
    ok = all(step() for step in steps)  # all() останавливается на первом False
    if ok:
        refresh_media(force=manual)
    return ok


def refresh_media(force=False):
    """Справочник фото (OpenF1) и скачивание картинок в кэш. Сбой не критичен: данные
    остаются «свежими», а вместо фото будут инициалы."""
    media.refresh_refs(force=force)
    return media.prefetch(media.all_urls(db.load_standings(), db.load_constructors(),
                                         db.load_schedule(), db.load_driver_media()))


def bootstrap():
    """Вызывается один раз при старте: если БД пуста и есть data/seed.json — загрузить его."""
    return seed.import_if_empty()


# ---------- чтение (мгновенное, из БД) ----------
def get_cached_standings():
    return db.load_standings()


def get_cached_results(driver_id):
    return db.load_results(driver_id)


def get_season_results():
    return db.load_season_results()


def get_qualifying():
    return db.load_qualifying()


def get_sprints():
    return db.load_sprints()


def get_driver_media():
    return db.load_driver_media()


def get_cached_constructors():
    return db.load_constructors()


def get_cached_schedule():
    return db.load_schedule()


def race_state(race, now=None):
    """'past' — гонка прошла, 'live' — идёт, 'upcoming' — впереди."""
    now = time.time() if now is None else now
    if now > race["start_ts"] + RACE_DURATION:
        return "past"
    return "live" if now >= race["start_ts"] else "upcoming"


def get_next_race(now=None):
    """Ближайшая (или идущая сейчас) гонка из кэша календаря; None, если календаря нет
    или сезон закончен."""
    now = time.time() if now is None else now
    for race in db.load_schedule():
        if race_state(race, now) != "past":
            return {**race, "state": race_state(race, now), "seconds_left": race["start_ts"] - now}
    return None


# ---------- данные пользователя ----------
get_favorites = db.get_favorites
toggle_favorite = db.toggle_favorite
get_setting = db.get_setting
set_setting = db.set_setting


def clear_local_data():
    """Стереть копию данных API (избранное и настройки сохраняются)."""
    with _lock:
        db.clear_cache()
        _state["error"] = None


# ---------- статус для индикатора в UI ----------
def get_status():
    """state: 'live'   — данные свежие, последний запрос успешен
              'cached' — показываем копию из БД (сеть недоступна/данные устарели)
              'empty'  — данных нет вообще
    """
    ts = db.fetched_at("standings_fetched_at")
    if ts is None:
        state = "empty"
    elif _state["error"] is None and time.time() - ts < 2 * _config["interval"] + 30:
        state = "live"
    else:
        state = "cached"
    return {"state": state, "updated_at": ts, "error": _state["error"]}


# ---------- фоновое обновление ----------
def _signature():
    payload = json.dumps(
        [db.load_standings(), db.load_constructors(), db.load_schedule(),
         db.get_meta("results_fetched_at"), db.get_meta("media_fetched_at")],
        sort_keys=True,
    )
    return get_status()["state"], hashlib.sha1(payload.encode(), usedforsecurity=False).hexdigest()


MAX_CALLBACK_FAILURES = 3   # столько ошибок подряд — подписчик считается закрытой сессией

_loop_lock = threading.Lock()
_loop = None


class _Loop:
    """Единственный на процесс цикл обновления; у него может быть много подписчиков
    (например, несколько вкладок браузера в веб-режиме)."""

    def __init__(self, interval):
        self.interval = interval
        self.subs = {}                  # token -> [callback, подряд_ошибок]
        self.wake = threading.Event()   # разбудить цикл (сменился интервал или остановка)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name="f1-refresh", daemon=True)

    def _notify(self):
        for token, entry in list(self.subs.items()):
            callback = entry[0]
            if callback is None:
                continue
            try:
                callback()
                entry[1] = 0
            except Exception as exc:
                entry[1] += 1
                logger.warning("on_update завершился ошибкой (%d/%d): %r", entry[1], MAX_CALLBACK_FAILURES, exc)
                if entry[1] >= MAX_CALLBACK_FAILURES:
                    logger.info("подписчик отключён (вероятно, сессия закрыта)")
                    self._drop(token)

    def _drop(self, token):
        with _loop_lock:
            self.subs.pop(token, None)
            if not self.subs:
                self.stop.set()
                self.wake.set()

    def _run(self):
        delay, failures = 0, 0
        while not self.stop.is_set():
            self.wake.wait(delay)
            self.wake.clear()
            if self.stop.is_set():
                break
            before = _signature()
            ok = refresh_all(force=True)
            if before != _signature():
                self._notify()
            failures = 0 if ok else failures + 1
            # успех -> обычный интервал; сбой -> 15, 30, 60... сек, но не дольше interval
            delay = self.interval if ok else min(15 * 2 ** (failures - 1), self.interval)


class _Handle:
    """Возвращается из start_background_refresh; set() отписывает вызвавшего."""

    def __init__(self, loop, token):
        self._loop, self._token, self._done = loop, token, False

    def set(self):
        if not self._done:
            self._done = True
            self._loop._drop(self._token)

    def is_set(self):
        return self._done


def start_background_refresh(interval=REFRESH_INTERVAL, on_update=None):
    """Подписывается на фоновое обновление и при необходимости запускает единый поток.
    Первое обновление — сразу, затем раз в `interval` секунд. Повторный вызов не создаёт
    второй поток: он лишь добавляет подписчика и обновляет интервал.
    on_update() вызывается из фонового потока при изменении данных или статуса.
    Возвращает объект с методом set() — отписка (поток останавливается без подписчиков)."""
    global _loop
    token = object()
    with _loop_lock:
        if _loop is None or _loop.stop.is_set():
            _loop = _Loop(interval)
            _loop.subs[token] = [on_update, 0]
            _loop.thread.start()
        else:
            _loop.interval = interval
            _loop.subs[token] = [on_update, 0]
            _loop.wake.set()           # новый интервал действует сразу
        loop = _loop
    _config["interval"] = interval
    return _Handle(loop, token)


def shutdown(timeout=5.0):
    """Остановить фоновый цикл и дождаться, пока он допишет текущее обновление в БД.
    Вызывается при закрытии окна (и в тестах — перед удалением временной БД)."""
    with _loop_lock:
        loop = _loop
        if loop is None:
            return True
        loop.subs.clear()
        loop.stop.set()
        loop.wake.set()
    if loop.thread.is_alive() and loop.thread is not threading.current_thread():
        loop.thread.join(timeout)
    return not loop.thread.is_alive()
