import io
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import requests

from services import db, f1_api, jolpica, seed


def standings_json(points_lec="126", season="2026", rnd="10", empty=False):
    def drv(pos, pts, wins, did, code, given, family, team):
        return {
            "position": pos, "positionText": pos, "points": pts, "wins": wins,
            "Driver": {"driverId": did, "code": code, "givenName": given, "familyName": family},
            "Constructors": [{"name": team}],
        }
    lists = [] if empty else [{
        "season": season, "round": rnd,
        "DriverStandings": [
            drv("1", "204", "6", "antonelli", "ANT", "Andrea Kimi", "Antonelli", "Mercedes"),
            drv("10", "39", "0", "lawson", "LAW", "Liam", "Lawson", "Racing Bulls"),  # "10" после "9"
            drv("4", points_lec, "0", "leclerc", "LEC", "Charles", "Leclerc", "Ferrari"),
        ],
    }]
    return {"MRData": {"StandingsTable": {"season": season, "StandingsLists": lists}}}


def results_json():
    def race(rnd, name, pos_text, pts, grid):
        return {
            "round": rnd, "raceName": name, "date": "2026-03-08",
            "Circuit": {"circuitName": "Circuit", "Location": {"locality": "City", "country": "Country"}},
            "Results": [{"position": "20" if pos_text == "R" else pos_text, "positionText": pos_text,
                         "points": pts, "grid": grid, "status": "Finished"}],
        }
    return {"MRData": {"RaceTable": {"season": "2026", "Races": [
        race("2", "Chinese GP", "R", "0", "4"),
        race("1", "Australian GP", "3", "15", "4"),
        race("3", "Japanese GP", "2", "17.5", "3"),
    ]}}}


def constructors_json():
    def c(pos, pts, wins, cid, name):
        return {"position": pos, "points": pts, "wins": wins,
                "Constructor": {"constructorId": cid, "name": name, "nationality": "X"}}
    return {"MRData": {"StandingsTable": {"season": "2026", "StandingsLists": [{
        "round": "10", "ConstructorStandings": [
            c("2", "285", "0", "ferrari", "Ferrari"),
            c("1", "358", "6", "mercedes", "Mercedes"),
        ]}]}}}


def schedule_json():
    def race(rnd, name, date, with_sprint=False):
        r = {"round": rnd, "raceName": name, "date": date, "time": "13:00:00Z",
             "Circuit": {"circuitName": "C" + rnd, "Location": {"locality": "L", "country": "K"}},
             "FirstPractice": {"date": date, "time": "11:30:00Z"},
             "Qualifying": {"date": date, "time": "12:00:00Z"}}
        if with_sprint:
            r["Sprint"] = {"date": date, "time": "10:00:00Z"}
        return r
    return {"MRData": {"RaceTable": {"season": "2026", "Races": [
        race("2", "Second GP", "2026-03-15", with_sprint=True),
        race("1", "First GP", "2026-03-08"),
        race("3", "Third GP", "2026-04-05"),
    ]}}}


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def router(standings=None, results=None, constructors=None, schedule=None, fail=False):
    """Подмена Session.get. Считает вызовы; недостающие фикстуры подставляет сама."""
    calls = []
    payloads = {
        "driverStandings": standings,
        "constructorStandings": constructors or constructors_json(),
        "results.json": results,
        "current.json": schedule or schedule_json(),
    }

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        if fail:
            raise requests.ConnectionError("no network")
        for key, payload in payloads.items():
            if key in url:
                return FakeResponse(payload)
        raise AssertionError(f"unexpected url {url}")

    fake_get.calls = calls
    return fake_get


class DataLayerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["F1_HUB_DB"] = os.path.join(self.tmp.name, "t.db")
        f1_api._state.update(error=None, fail_until=0.0)
        patcher = mock.patch.object(jolpica, "MIN_INTERVAL", 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        f1_api.shutdown()          # фоновый поток не должен писать в БД следующего теста
        os.environ.pop("F1_HUB_DB", None)
        self.tmp.cleanup()

    def patch_net(self, **kw):
        fake = router(**kw)
        p = mock.patch.object(jolpica._session, "get", fake)
        p.start()
        self.addCleanup(p.stop)
        return fake

    # --- данные корректны и в нужной форме ---
    def test_refresh_and_read_back(self):
        self.patch_net(standings=standings_json(), results=results_json())
        self.assertTrue(f1_api.refresh_all(force=True))
        st = f1_api.get_cached_standings()
        self.assertEqual([d["position"] for d in st], ["1", "4", "10"])  # числовая сортировка
        lec = f1_api.get_leclerc_stats()
        self.assertEqual((lec["points"], lec["wins"], lec["team"], lec["season"]),
                         ("126", "0", "Ferrari", "2026"))
        res = f1_api.get_cached_leclerc_results()
        self.assertEqual([r["round"] for r in res], ["1", "2", "3"])       # по порядку этапов
        self.assertEqual(res[1]["position"], "R")                           # сход сохранён
        self.assertEqual(res[2]["points"], "17.5")                          # дробные очки
        self.assertEqual(f1_api.get_status()["state"], "live")

    # --- нет сети и нет кэша: никаких выдуманных данных ---
    def test_no_network_no_cache_returns_empty(self):
        self.patch_net(fail=True)
        self.assertEqual(f1_api.get_current_driver_standings(), [])
        self.assertIsNone(f1_api.get_leclerc_stats())
        self.assertEqual(f1_api.get_leclerc_race_results(), [])
        st = f1_api.get_status()
        self.assertEqual(st["state"], "empty")
        self.assertIsNotNone(st["error"])

    # --- сеть пропала после успеха: показываем последнюю реальную копию ---
    def test_network_loss_keeps_last_real_data(self):
        self.patch_net(standings=standings_json(), results=results_json())
        f1_api.refresh_all(force=True)
        self.patch_net(fail=True)
        self.assertFalse(f1_api.refresh_all(force=True))
        self.assertEqual(f1_api.get_leclerc_stats()["points"], "126")
        self.assertEqual(f1_api.get_status()["state"], "cached")

    # --- пауза после сбоя: не молотим сеть ---
    def test_cooldown_after_failure(self):
        fake = self.patch_net(fail=True)
        f1_api.refresh_standings()
        n = len(fake.calls)
        self.assertFalse(f1_api.refresh_standings())     # обычный вызов — без сети
        self.assertEqual(len(fake.calls), n)
        f1_api.refresh_standings(force=True)             # ручное обновление — обходит паузу
        self.assertGreater(len(fake.calls), n)

    # --- сезон ещё не начался: пустой ответ не стирает копию ---
    def test_empty_standings_do_not_wipe_cache(self):
        self.patch_net(standings=standings_json(), results=results_json())
        f1_api.refresh_all(force=True)
        self.patch_net(standings=standings_json(empty=True), results=results_json())
        self.assertTrue(f1_api.refresh_standings(force=True))
        self.assertEqual(len(f1_api.get_cached_standings()), 3)

    # --- новое обновление заменяет старые значения целиком ---
    def test_update_replaces_values(self):
        self.patch_net(standings=standings_json("126"), results=results_json())
        f1_api.refresh_all(force=True)
        self.patch_net(standings=standings_json("144", rnd="11"), results=results_json())
        f1_api.refresh_all(force=True)
        self.assertEqual(f1_api.get_leclerc_stats()["points"], "144")
        self.assertEqual(len(f1_api.get_cached_standings()), 3)

    # --- битый формат ответа = ошибка, а не падение ---
    def test_malformed_response(self):
        self.patch_net(standings={"MRData": {"StandingsTable": {"StandingsLists": [{"DriverStandings": [{}]}]}}},
                       results=results_json())
        self.assertFalse(f1_api.refresh_standings(force=True))
        self.assertEqual(f1_api.get_cached_standings(), [])

    # --- фоновый поток: обновляет и зовёт on_update только при изменениях ---
    def test_background_refresh_calls_on_update(self):
        self.patch_net(standings=standings_json(), results=results_json())
        updates = []
        done = threading.Event()

        def on_update():
            updates.append(f1_api.get_status()["state"])
            done.set()

        stop = f1_api.start_background_refresh(interval=0.2, on_update=on_update)
        self.assertTrue(done.wait(3))
        time.sleep(0.7)            # ещё несколько циклов без изменений данных
        stop.set()
        self.assertEqual(updates, ["live"])               # данные не менялись -> один вызов
        self.assertEqual(f1_api.get_leclerc_stats()["points"], "126")

    def test_background_recovers_after_outage(self):
        self.patch_net(fail=True)
        states = []
        got_live = threading.Event()

        def on_update():
            s = f1_api.get_status()["state"]
            states.append(s)
            if s == "live":
                got_live.set()

        with mock.patch.object(f1_api, "REFRESH_INTERVAL", 0.2):
            stop = f1_api.start_background_refresh(interval=0.2, on_update=on_update)
            time.sleep(0.3)
            self.patch_net(standings=standings_json(), results=results_json())  # сеть вернулась
            self.assertTrue(got_live.wait(5))
            stop.set()
        self.assertEqual(f1_api.get_leclerc_stats()["name"], "Charles Leclerc")

    # ================= этап 2 =================
    def test_constructors_and_schedule_roundtrip(self):
        self.patch_net(standings=standings_json(), results=results_json())
        self.assertTrue(f1_api.refresh_all(force=True))
        cons = f1_api.get_cached_constructors()
        self.assertEqual([c["name"] for c in cons], ["Mercedes", "Ferrari"])
        sched = f1_api.get_cached_schedule()
        self.assertEqual([r["round"] for r in sched], ["1", "2", "3"])
        keys = [x["key"] for x in sched[1]["sessions"]]      # этап 2 — спринтовый уик-энд
        self.assertEqual(keys, ["Sprint", "FirstPractice", "Qualifying", "Race"])  # по времени (UTC)
        self.assertEqual([x["key"] for x in sched[0]["sessions"]], ["FirstPractice", "Qualifying", "Race"])
        self.assertTrue(all(isinstance(x["ts"], float) for x in sched[0]["sessions"]))

    def test_schedule_ttl_and_manual_refresh(self):
        fake = self.patch_net(standings=standings_json(), results=results_json())
        f1_api.refresh_all(force=True)
        n = sum("current.json" in u for u in fake.calls)
        f1_api.refresh_all(force=True)                      # календарь свежий -> не перезапрашиваем
        self.assertEqual(sum("current.json" in u for u in fake.calls), n)
        f1_api.refresh_all(force=True, manual=True)         # «Обновить сейчас» -> перезапрос
        self.assertEqual(sum("current.json" in u for u in fake.calls), n + 1)

    def test_next_race_and_states(self):
        self.patch_net(standings=standings_json(), results=results_json())
        f1_api.refresh_all(force=True)
        sched = {r["round"]: r for r in f1_api.get_cached_schedule()}
        r1, r2 = sched["1"]["start_ts"], sched["2"]["start_ts"]
        nxt = f1_api.get_next_race(now=r1 - 3600)
        self.assertEqual((nxt["round"], nxt["state"]), ("1", "upcoming"))
        self.assertAlmostEqual(nxt["seconds_left"], 3600)
        live = f1_api.get_next_race(now=r1 + 1800)           # гонка идёт
        self.assertEqual((live["round"], live["state"]), ("1", "live"))
        after = f1_api.get_next_race(now=r1 + 3 * 3600)      # прошла -> следующая
        self.assertEqual(after["round"], "2")
        self.assertIsNone(f1_api.get_next_race(now=sched["3"]["start_ts"] + 99999))  # сезон окончен
        self.assertEqual(f1_api.race_state(sched["1"], now=r2), "past")

    def test_favorites_and_settings_survive_cache_clear(self):
        self.patch_net(standings=standings_json(), results=results_json())
        f1_api.refresh_all(force=True)
        self.assertTrue(f1_api.toggle_favorite("leclerc"))
        self.assertTrue(f1_api.toggle_favorite("norris"))
        self.assertFalse(f1_api.toggle_favorite("norris"))   # повторный клик снимает
        self.assertEqual(f1_api.get_favorites(), ["leclerc"])
        self.assertEqual(f1_api.get_setting("refresh_minutes", "5"), "5")
        f1_api.set_setting("refresh_minutes", 10)
        f1_api.clear_local_data()
        self.assertEqual(f1_api.get_cached_standings(), [])
        self.assertEqual(f1_api.get_cached_schedule(), [])
        self.assertEqual(f1_api.get_status()["state"], "empty")
        self.assertEqual(f1_api.get_favorites(), ["leclerc"])            # не стёрлось
        self.assertEqual(f1_api.get_setting("refresh_minutes"), "10")

    def test_old_db_gets_new_tables(self):
        """БД из этапа 1 (user_version=1, без новых таблиц) должна дорасти без потери данных."""
        import sqlite3
        path = os.environ["F1_HUB_DB"]
        con = sqlite3.connect(path)
        con.executescript("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);"
                          "INSERT INTO meta VALUES('standings_season','2026');"
                          "PRAGMA user_version=1;")
        con.commit(); con.close()
        self.assertEqual(f1_api.get_favorites(), [])
        self.assertTrue(f1_api.toggle_favorite("leclerc"))
        self.assertEqual(db.get_meta("standings_season"), "2026")

    def test_chain_stops_on_first_failure(self):
        fake = self.patch_net(fail=True)
        self.assertFalse(f1_api.refresh_all(force=True))
        self.assertEqual(len(fake.calls), 1)                  # дальше первого запроса не идём


    def test_live_window_follows_refresh_interval(self):
        self.patch_net(standings=standings_json(), results=results_json())
        f1_api.refresh_all(force=True)
        later = time.time() + 20 * 60                       # данным 20 минут
        with mock.patch.object(time, "time", return_value=later):
            f1_api._config["interval"] = 300
            self.assertEqual(f1_api.get_status()["state"], "cached")
            f1_api._config["interval"] = 1800               # пользователь выбрал «раз в 30 минут»
            self.assertEqual(f1_api.get_status()["state"], "live")
        f1_api._config["interval"] = f1_api.REFRESH_INTERVAL


    # ================= этап 3: снимок данных =================
    def _populate(self):
        self.patch_net(standings=standings_json(), results=results_json())
        self.assertTrue(f1_api.refresh_all(force=True))

    def test_seed_roundtrip_into_empty_db(self):
        self._populate()
        snap = os.path.join(self.tmp.name, "seed.json")
        self.assertEqual(str(seed.export_snapshot(snap)), snap)
        old = time.time() - 3 * 86400                         # снимок трёхдневной давности
        with open(snap, encoding="utf-8") as f:
            data = json.load(f)
        data["exported_at"] = old
        with open(snap, "w", encoding="utf-8") as f:
            json.dump(data, f)
        before = (f1_api.get_cached_standings(), f1_api.get_cached_constructors(),
                  f1_api.get_cached_leclerc_results(), f1_api.get_cached_schedule())
        stamp = old
        os.environ["F1_HUB_DB"] = os.path.join(self.tmp.name, "second.db")   # чистая БД
        self.assertEqual(f1_api.get_cached_standings(), [])
        self.assertTrue(seed.import_if_empty(snap))
        after = (f1_api.get_cached_standings(), f1_api.get_cached_constructors(),
                 f1_api.get_cached_leclerc_results(), f1_api.get_cached_schedule())
        self.assertEqual(before, after)
        st = f1_api.get_status()
        self.assertEqual(st["state"], "cached")            # снимок не выдаётся за свежие данные
        self.assertAlmostEqual(st["updated_at"], stamp, places=3)

    def test_seed_never_overwrites_existing_data(self):
        self._populate()
        snap = os.path.join(self.tmp.name, "seed.json")
        seed.export_snapshot(snap)
        self.patch_net(standings=standings_json("999"), results=results_json())
        f1_api.refresh_all(force=True)                       # в БД новее, чем в снимке
        self.assertFalse(seed.import_if_empty(snap))
        self.assertEqual(f1_api.get_leclerc_stats()["points"], "999")

    def test_seed_bad_files_are_ignored(self):
        bad = os.path.join(self.tmp.name, "bad.json")
        self.assertFalse(seed.import_if_empty(os.path.join(self.tmp.name, "missing.json")))
        write = lambda text: Path(bad).write_text(text, encoding="utf-8")  # noqa: E731
        write("{not json")
        self.assertFalse(seed.import_if_empty(bad))
        write('{"version": 99}')
        self.assertFalse(seed.import_if_empty(bad))
        write('{"version": 1, "exported_at": 1, "season": "2026"}')   # нет standings
        self.assertFalse(seed.import_if_empty(bad))
        self.assertEqual(f1_api.get_cached_standings(), [])

    def test_seed_cli_survives_console_without_cyrillic(self):
        """Английская Windows (cp1252): раньше print() с русским текстом ронял python -m services.seed."""
        raw = io.BytesIO()
        out = io.TextIOWrapper(raw, encoding="cp1252")
        with mock.patch("sys.stdout", out):
            self.assertEqual(seed.main(["import", os.path.join(self.tmp.name, "none.json")]), 0)
        out.flush()
        self.assertIn(b"\\u", raw.getvalue())

    def test_seed_export_requires_data_and_cli(self):
        self.assertIsNone(seed.export_snapshot(os.path.join(self.tmp.name, "x.json")))
        out = os.path.join(self.tmp.name, "cli.json")
        self.patch_net(standings=standings_json(), results=results_json())
        self.assertEqual(seed.main(["export", "--refresh", out]), 0)
        self.assertTrue(os.path.isfile(out))
        self.patch_net(fail=True)
        os.environ["F1_HUB_DB"] = os.path.join(self.tmp.name, "empty.db")
        self.assertEqual(seed.main(["export", "--refresh", out]), 1)          # нет сети -> код 1

    def test_bootstrap_uses_env_path(self):
        self._populate()
        snap = os.path.join(self.tmp.name, "seed.json")
        seed.export_snapshot(snap)
        os.environ["F1_HUB_DB"] = os.path.join(self.tmp.name, "fresh.db")
        with mock.patch.dict(os.environ, {"F1_HUB_SEED": snap}):
            self.assertTrue(f1_api.bootstrap())
            self.assertFalse(f1_api.bootstrap())             # повторно ничего не делает
        self.assertEqual(len(f1_api.get_cached_standings()), 3)

    # ================= этап 3: единый фоновый поток =================
    def _threads(self):
        return [t for t in threading.enumerate() if t.name == "f1-refresh" and t.is_alive()]

    def test_one_refresh_thread_for_many_subscribers(self):
        self.patch_net(standings=standings_json(), results=results_json())
        got = {"a": threading.Event(), "b": threading.Event()}
        h1 = f1_api.start_background_refresh(interval=60, on_update=got["a"].set)
        h2 = f1_api.start_background_refresh(interval=60, on_update=got["b"].set)
        self.assertTrue(got["a"].wait(3))
        self.assertEqual(len(self._threads()), 1)             # поток один на процесс
        h1.set()
        self.assertEqual(len(self._threads()), 1)             # второй подписчик ещё жив
        h2.set()
        for _ in range(50):
            if not self._threads():
                break
            time.sleep(0.05)
        self.assertEqual(self._threads(), [])                 # без подписчиков поток остановился

    def test_dead_subscriber_is_dropped(self):
        """Закрытая вкладка (callback падает) не должна жить в памяти и тормозить обновления."""
        calls = {"bad": 0, "good": 0}

        def bad():
            calls["bad"] += 1
            raise RuntimeError("session closed")

        def good():
            calls["good"] += 1

        with mock.patch.object(f1_api, "MAX_CALLBACK_FAILURES", 2):
            h_bad = f1_api.start_background_refresh(interval=0.1, on_update=bad)
            h_good = f1_api.start_background_refresh(interval=0.1, on_update=good)
            for i in range(8):                                 # меняем данные -> каждый цикл есть on_update
                self.patch_net(standings=standings_json(str(100 + i)), results=results_json())
                time.sleep(0.25)
            h_good.set()
            f1_api.shutdown()                                  # дождаться цикла, пока подмена ещё действует
        self.assertEqual(calls["bad"], 2)                      # после 2 ошибок отключён
        self.assertGreaterEqual(calls["good"], 3)              # хороший подписчик продолжает получать
        h_bad.set()

    def test_interval_change_wakes_loop(self):
        fake = self.patch_net(standings=standings_json(), results=results_json())
        h1 = f1_api.start_background_refresh(interval=3600)
        time.sleep(0.3)
        n = len(fake.calls)                                    # первое обновление выполнено
        h2 = f1_api.start_background_refresh(interval=3600)    # новый интервал -> немедленное обновление
        time.sleep(0.3)
        self.assertGreater(len(fake.calls), n)
        h1.set(); h2.set()


if __name__ == "__main__":
    unittest.main()
