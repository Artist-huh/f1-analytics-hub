"""Общее состояние приложения: данные, навигация, фоновое обновление.

Экраны только читают state и вызывают его методы. Всё, что должно пережить
перерисовку (выбранная вкладка, пилот в «Дуэли»), хранится в state.ui.
"""
import threading
import time

from services import f1_api as api, log

logger = log.get("ui")


class AppState:
    def __init__(self, page):
        self.page = page
        self.app = self  # Для совместимости с новыми экранами
        self.api = api   # Прямой доступ к API
        self.leclerc = None
        self.standings, self.constructors = [], []
        self.results, self.schedule = [], []
        self.favorites = []
        self.status = {"state": "empty", "updated_at": None, "error": None}
        self.refreshing = False
        self.tab, self.sub = 0, None
        self.ui = {}
        self.countdown = None           # (текст, номер этапа) — для обновления отсчёта на месте
        self.render = lambda: None      # подставляет main.py
        self.run_on_ui = lambda fn: fn()  # main.py: выполнить в цикле событий Flet
        self._stop = None
        self._back = []                 # стек подэкранов для кнопки «назад»
        self._results_requested = {}    # driver_id -> когда запрашивали результаты
        self._results_pending = set()   # запросы, ответ на которые ещё не пришёл

    # ---------- данные ----------
    def load(self):
        """Читает всё из локальной БД (мгновенно, без сети)."""
        try:
            self.standings = api.get_cached_standings()
            self.constructors = api.get_cached_constructors()
            self.results = api.get_cached_leclerc_results()
            self.schedule = api.get_cached_schedule()
            self.favorites = api.get_favorites()
            self.status = api.get_status()
            self.leclerc = next((d for d in self.standings if d["driver_id"] == api.LECLERC_ID), None)
        except Exception:
            logger.exception("ошибка чтения данных из БД")

    @property
    def season(self):
        return self.standings[0]["season"] if self.standings else ""

    def driver_standings(self):
        """Получить турнирную таблицу пилотов"""
        return self.standings

    def constructor_standings(self):
        """Получить турнирную таблицу команд"""
        return self.constructors

    def next_race(self):
        return api.get_next_race()

    def driver(self, driver_id):
        return next((d for d in self.standings if d["driver_id"] == driver_id), None)

    RESULTS_TTL = 1800  # сек. — как часто перезапрашивать результаты «чужого» пилота

    def driver_results(self, driver_id):
        """Результаты пилота из БД. Если их нет или они давно не обновлялись —
        один раз запрашивает в фоне и перерисовывает экран, когда данные придут."""
        rows = api.get_cached_results(driver_id)
        if driver_id == api.LECLERC_ID and rows:
            return rows                                   # обновляются фоновым циклом
        last = self._results_requested.get(driver_id, 0)
        if time.time() - last > self.RESULTS_TTL:
            self._results_requested[driver_id] = time.time()

            self._results_pending.add(driver_id)

            def job():
                try:
                    self._fetch_results(driver_id)
                finally:
                    self._results_pending.discard(driver_id)
                    self.render()

            threading.Thread(target=job, name=f"f1-results-{driver_id}", daemon=True).start()
        return rows

    def _fetch_results(self, driver_id):
        return api.refresh_results(driver_id)

    def results_loading(self, driver_id):
        """True, пока запрос результатов пилота ещё выполняется."""
        return driver_id in self._results_pending

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

    def open_driver(self, driver_id):
        self.ui["driver_id"] = driver_id
        self.open_sub("driver_detail")

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
