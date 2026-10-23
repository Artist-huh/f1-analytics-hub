"""Общее состояние приложения: данные, навигация, фоновое обновление.

Экраны только читают state и вызывают его методы. Всё, что должно пережить
перерисовку (выбранная вкладка, пилоты в сравнении), хранится в state.ui.
"""
import threading
import time

import design_system as ds
from services import f1_api as api, live, log, media, stats

logger = log.get("ui")

MAX_COMPARE = 4


class AppState:
    def __init__(self, page):
        self.page = page
        self.standings, self.constructors = [], []
        self.schedule = []
        self.season_results, self.qualifying, self.sprints = [], [], []
        self.stats = {}                 # driver_id -> статистика сезона (services.stats)
        self.media_refs = {}            # код пилота -> идентификатор портрета (OpenF1)
        self.favorites = []
        self.status = {"state": "empty", "updated_at": None, "error": None}
        self.refreshing = False
        self.tab, self.sub = 0, None
        self.ui = {}
        self.fresh = True               # экран только что открыт — элементы появляются с анимацией
        self.countdown = None           # (текст, номер этапа) — для обновления отсчёта на месте
        self.render = lambda: None      # подставляет main.py
        self.run_on_ui = lambda fn: fn()  # main.py: выполнить в цикле событий Flet
        self.on_theme_change = lambda name, team: None   # main.py: перекрасить интерфейс
        self._stop = None
        self._back = []                 # стек подэкранов для кнопки «назад»
        self._by_driver = {}
        self._live_watch = None         # поток обновления live-тайминга, пока открыт его экран

    # ---------- данные ----------
    def load(self):
        """Читает всё из локальной БД (мгновенно, без сети)."""
        try:
            self.standings = api.get_cached_standings()
            self.constructors = api.get_cached_constructors()
            self.schedule = api.get_cached_schedule()
            self.season_results = api.get_season_results()
            self.qualifying = api.get_qualifying()
            self.sprints = api.get_sprints()
            self.media_refs = api.get_driver_media()
            self.favorites = api.get_favorites()
            self.status = api.get_status()
            self.stats = stats.season_index(self.season_results, self.qualifying, self.sprints)
            self._by_driver = {
                "results": stats.group_by_driver(self.season_results),
                "quali": stats.group_by_driver(self.qualifying),
                "sprints": stats.group_by_driver(self.sprints),
            }
        except Exception:
            logger.exception("ошибка чтения данных из БД")

    @property
    def season(self):
        return self.standings[0]["season"] if self.standings else ""

    def driver_standings(self):
        return self.standings

    def constructor_standings(self):
        return self.constructors

    def next_race(self):
        return api.get_next_race()

    def driver(self, driver_id):
        return next((d for d in self.standings if d["driver_id"] == driver_id), None)

    def driver_results(self, driver_id):
        """Результаты гонок пилота за сезон (из общей таблицы результатов)."""
        return self._by_driver.get("results", {}).get(driver_id, [])

    def driver_quali(self, driver_id):
        return self._by_driver.get("quali", {}).get(driver_id, [])

    def driver_sprints(self, driver_id):
        return self._by_driver.get("sprints", {}).get(driver_id, [])

    def driver_stats(self, driver_id):
        return self.stats.get(driver_id) or stats.driver_stats([])

    def results_loading(self, driver_id):
        """Результатов ещё нет, но идёт обновление — показать индикатор, а не «пусто»."""
        return self.refreshing and not self.driver_results(driver_id)

    def teammates(self, driver):
        return [d for d in self.standings if d["team"] == driver["team"] and d["driver_id"] != driver["driver_id"]]

    def team_drivers(self, team_name):
        """Пилоты команды из Кубка конструкторов (названия в двух таблицах могут отличаться)."""
        key = ds.team_key(team_name)
        if key:
            return [d for d in self.standings if ds.team_key(d["team"]) == key]
        return [d for d in self.standings if d["team"] == team_name]

    def podiums(self):
        """round -> [P1, P2, P3] прошедших гонок."""
        return stats.podiums_by_round(self.season_results)

    def last_race(self):
        """(этап календаря или None, подиум) последней гонки с результатами."""
        podiums = self.podiums()
        if not podiums:
            return None, None
        rnd = max(podiums, key=int)
        race = next((r for r in self.schedule if r["round"] == rnd), None)
        return race or {"round": rnd, **podiums[rnd][0]}, podiums[rnd]

    def season_left(self, now=None):
        """(гонок осталось, спринтов осталось, у ближайшего уик-энда есть спринт)."""
        now = time.time() if now is None else now
        races = [r for r in self.schedule if api.race_state(r, now) != "past"]
        sprints = [s for r in self.schedule for s in r["sessions"] if s["key"] == "Sprint" and s["ts"] > now]
        next_sprint = bool(races) and any(s["key"] == "Sprint" and s["ts"] > now for s in races[0]["sessions"])
        return len(races), len(sprints), next_sprint

    def title_race(self, kind="drivers"):
        races, sprints, next_sprint = self.season_left()
        rows = self.standings if kind == "drivers" else self.constructors
        return {**stats.title_race(rows, races, sprints, kind, next_sprint), "races_left": races,
                "sprints_left": sprints}

    # ---------- картинки ----------
    def photo(self, driver, kind="avatar"):
        return media.driver_photo(driver, self.media_refs, kind) if driver else None

    def photo_by_id(self, driver_id, kind="avatar"):
        return self.photo(self.driver(driver_id), kind)

    def team_logo(self, team_name):
        return media.team_logo(team_name, self.season)

    def team_car(self, team_name):
        return media.team_car(team_name, self.season)

    def flag(self, nationality=None, country=None):
        iso = ds.nationality_iso(nationality) if nationality else ds.country_iso(country)
        return media.flag(iso), iso or ""

    # ---------- действия пользователя ----------
    def toggle_favorite(self, driver_id):
        api.toggle_favorite(driver_id)
        self.favorites = api.get_favorites()
        self.render()

    def refresh_now(self):
        if self.refreshing:
            return
        self.refreshing = True
        self.render()

        def job():
            try:
                api.refresh_all(force=True, manual=True)
            finally:
                self.refreshing = False
                self.load()
                self.render()

        threading.Thread(target=job, name="f1-manual-refresh", daemon=True).start()

    def clear_cache(self):
        api.clear_local_data()
        self.load()
        self.render()
        self.refresh_now()

    # ---------- сравнение ----------
    def compare_ids(self):
        """Пилоты в сравнении (2–4). По умолчанию — двое лидеров чемпионата."""
        ids = [i for i in self.ui.get("cmp", []) if self.driver(i)]
        for d in self.standings:
            if len(ids) >= 2:
                break
            if d["driver_id"] not in ids:
                ids.append(d["driver_id"])
        return ids[:MAX_COMPARE]

    def set_compare(self, ids):
        self.ui["cmp"] = list(dict.fromkeys(ids))[:MAX_COMPARE]
        self.render()

    def set_compare_and_open(self, ids):
        self.ui["cmp"] = list(dict.fromkeys(ids))[:MAX_COMPARE]
        self.open_sub("compare")

    def compare_with(self, driver_id):
        """«Сравнить» со страницы пилота: он и его напарник (или лидер)."""
        driver = self.driver(driver_id)
        mate = (self.teammates(driver) or [d for d in self.standings if d["driver_id"] != driver_id])[:1]
        self.ui["cmp"] = [driver_id] + [m["driver_id"] for m in mate]
        self.open_sub("compare")

    # ---------- навигация ----------
    def open_tab(self, index):
        self.tab, self.sub = index, None
        self._back.clear()
        self.render()

    def open_sub(self, name):
        if self.sub and self.sub != name:
            self._back.append(self.sub)
        self.sub = name
        self.render()

    def close_sub(self):
        """Назад: на предыдущий подэкран или на вкладку, с которой пришли."""
        self.sub = self._back.pop() if self._back else None
        self.render()

    def go_back(self):
        """Системная «назад» (Android, Esc): подэкран -> вкладка -> «Главная».
        False — дальше некуда (на Android приложение можно закрыть)."""
        if self.sub:
            self.close_sub()
        elif self.tab != 0:
            self.open_tab(0)
        else:
            return False
        return True

    def open_driver(self, driver_id):
        self.ui["driver_id"] = driver_id
        self.open_sub("driver_detail")

    def open_circuit(self, race):
        self.ui["circuit"] = race
        self.open_sub("circuit")

    def open_team(self, team_name):
        self.ui["team"] = team_name
        self.open_sub("team")

    def screen_key(self):
        detail = {"driver_detail": "driver_id", "team": "team", "circuit": "circuit"}.get(self.sub)
        value = self.ui.get(detail) if detail else None
        return (self.tab, self.sub, value.get("round") if isinstance(value, dict) else value)

    # ---------- live-тайминг ----------
    def watch_live(self, period=3.0):
        """Пока открыт экран live-тайминга — обновлять снимок (во время сессии раз в 10 с).
        Поток сам завершается, когда пользователь уходит с экрана."""
        if live.stale() and not live.snapshot()[2]:
            live.refresh(on_done=self.render)
        if self._live_watch and self._live_watch.is_alive():
            return

        def loop():
            while self.sub == "live":
                time.sleep(period)
                if self.sub == "live" and live.stale():
                    live.refresh(on_done=self.render)

        self._live_watch = threading.Thread(target=loop, name="f1-live-watch", daemon=True)
        self._live_watch.start()

    def live_now(self):
        """Идёт ли сейчас сессия по календарю: (этап, ключ сессии) или None."""
        return live.session_is_live(self.schedule)

    # ---------- оформление ----------
    def set_theme(self, name, team=None):
        """Сменить тему ('dark', 'light', 'team' + команда) и запомнить выбор."""
        api.set_setting("theme", name)
        api.set_setting("theme_team", team or "")
        self.on_theme_change(name, team)

    # ---------- клавиатура ----------
    def on_key(self, key, ctrl=False):
        """Горячие клавиши: F5 — обновить, Ctrl+F — поиск пилота, Ctrl+K — сравнение, Esc — назад.
        Возвращает True, если клавиша обработана."""
        key = (key or "").upper()
        if key == "F5":
            self.refresh_now()
        elif ctrl and key == "F":
            self.ui["drv_focus"] = True     # экран «Пилоты» поставит курсор в поле поиска
            self.open_tab(3)
        elif ctrl and key == "K":
            self.open_sub("compare")
        elif key == "ESCAPE" and self.sub:
            self.close_sub()
        else:
            return False
        return True

    # ---------- фон ----------
    def refresh_minutes(self):
        try:
            return min(max(int(api.get_setting("refresh_minutes", "5")), 1), 120)
        except ValueError:
            return 5

    def on_data_changed(self):
        """Зовётся из фонового потока: данные или статус изменились."""
        self.load()
        self.render()

    def start_refresher(self):
        if self._stop is not None:
            self._stop.set()
        self._stop = api.start_background_refresh(
            interval=self.refresh_minutes() * 60, on_update=self.on_data_changed
        )
