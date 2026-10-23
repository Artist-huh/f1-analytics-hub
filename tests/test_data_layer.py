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

from services import archive, db, f1_api, jolpica, media, notify, seed, stats


def standings_json(points_lec="126", season="2026", rnd="10", empty=False):
    def drv(pos, pts, wins, did, code, given, family, team, nat, number):
        return {
            "position": pos, "positionText": pos, "points": pts, "wins": wins,
            "Driver": {"driverId": did, "code": code, "givenName": given, "familyName": family,
                       "nationality": nat, "permanentNumber": number},
            "Constructors": [{"name": team}],
        }
    lists = [] if empty else [{
        "season": season, "round": rnd,
        "DriverStandings": [
            drv("1", "204", "6", "antonelli", "ANT", "Andrea Kimi", "Antonelli", "Mercedes", "Italian", "12"),
            drv("10", "39", "0", "lawson", "LAW", "Liam", "Lawson", "Racing Bulls", "New Zealander", "30"),  # "10" после "9"
            drv("4", points_lec, "0", "leclerc", "LEC", "Charles", "Leclerc", "Ferrari", "Monegasque", "16"),
        ],
    }]
    return {"MRData": {"StandingsTable": {"season": season, "StandingsLists": lists}}}


def _res(driver_id, team, pos_text, pts, grid, fastest=None):
    r = {"position": "20" if not pos_text.isdigit() else pos_text, "positionText": pos_text, "points": pts,
         "grid": grid, "status": "Finished" if pos_text.isdigit() else "Retired",
         "Driver": {"driverId": driver_id}, "Constructor": {"name": team}}
    if fastest:
        r["FastestLap"] = {"rank": fastest}
    return r


def _race(rnd, name, key, rows):
    return {"round": rnd, "raceName": name, "date": "2026-03-08",
            "Circuit": {"circuitName": "Circuit", "Location": {"locality": "City", "country": "Italy"}},
            key: rows}


def results_json():
    """3 гонки, 3 пилота. Леклер: P3, сход, P2 (17.5 очка) — порядок этапов в ответе перемешан."""
    return {"MRData": {"total": "9", "RaceTable": {"season": "2026", "Races": [
        _race("2", "Chinese GP", "Results", [_res("antonelli", "Mercedes", "2", "18", "2"),
                                             _res("lawson", "Racing Bulls", "10", "1", "12"),
                                             _res("leclerc", "Ferrari", "R", "0", "4")]),
        _race("1", "Australian GP", "Results", [_res("antonelli", "Mercedes", "1", "25", "1", fastest="1"),
                                                _res("leclerc", "Ferrari", "3", "15", "4"),
                                                _res("lawson", "Racing Bulls", "R", "0", "10")]),
        _race("3", "Japanese GP", "Results", [_res("antonelli", "Mercedes", "1", "25", "1", fastest="1"),
                                              _res("leclerc", "Ferrari", "2", "17.5", "3"),
                                              _res("lawson", "Racing Bulls", "W", "0", "0")]),
    ]}}}


def qualifying_json():
    def q(driver_id, pos):
        return {"position": pos, "Driver": {"driverId": driver_id}}
    return {"MRData": {"total": "7", "RaceTable": {"season": "2026", "Races": [
        _race("1", "Australian GP", "QualifyingResults", [q("antonelli", "1"), q("leclerc", "4")]),
        _race("2", "Chinese GP", "QualifyingResults", [q("leclerc", "1"), q("antonelli", "2")]),
        _race("3", "Japanese GP", "QualifyingResults", [q("antonelli", "1"), q("leclerc", "3"), q("lawson", "15")]),
    ]}}}


def sprint_json():
    return {"MRData": {"total": "2", "RaceTable": {"season": "2026", "Races": [
        _race("2", "Chinese GP", "SprintResults", [_res("antonelli", "Mercedes", "1", "8", "1"),
                                                   _res("leclerc", "Ferrari", "3", "6", "2")]),
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
             "Circuit": {"circuitId": "c" + rnd, "circuitName": "C" + rnd,
                         "Location": {"locality": "L", "country": "Italy"}},
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
    def __init__(self, payload, status=200, content=b""):
        self.payload = payload
        self.status_code = status
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self.payload


def router(standings=None, results=None, constructors=None, schedule=None, fail=False):
    """Подмена Session.get. Считает вызовы; недостающие фикстуры подставляет сама."""
    calls = []
    payloads = {
        "driverStandings": standings or standings_json(),
        "constructorStandings": constructors or constructors_json(),
        "qualifying.json": qualifying_json(),
        "sprint.json": sprint_json(),
        "results.json": results or results_json(),
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


def driver(driver_id):
    return next((d for d in f1_api.get_cached_standings() if d["driver_id"] == driver_id), None)


class DataLayerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["F1_HUB_DB"] = os.path.join(self.tmp.name, "t.db")
        seed_env = mock.patch.dict(os.environ, {"F1_HUB_SEED": os.path.join(self.tmp.name, "no-seed.json")})
        seed_env.start()   # снимок и встроенные картинки из data/ тестам не видны
        self.addCleanup(seed_env.stop)
        f1_api._state.update(error=None, fail_until=0.0)
        for target, attr, value in ((jolpica, "MIN_INTERVAL", 0),
                                    (media, "refresh_refs", mock.Mock(return_value=True)),   # без OpenF1
                                    (media, "prefetch", mock.Mock(return_value=None))):      # без картинок
            patcher = mock.patch.object(target, attr, value)
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
        self.patch_net()
        self.assertTrue(f1_api.refresh_all(force=True))
        st = f1_api.get_cached_standings()
        self.assertEqual([d["position"] for d in st], ["1", "4", "10"])  # числовая сортировка
        lec = driver("leclerc")
        self.assertEqual((lec["points"], lec["wins"], lec["team"], lec["season"], lec["nationality"], lec["number"]),
                         ("126", "0", "Ferrari", "2026", "Monegasque", "16"))
        res = f1_api.get_cached_results("leclerc")
        self.assertEqual([r["round"] for r in res], ["1", "2", "3"])       # по порядку этапов
        self.assertEqual(res[1]["position"], "R")                           # сход сохранён
        self.assertEqual(res[2]["points"], "17.5")                          # дробные очки
        self.assertEqual(f1_api.get_status()["state"], "live")

    def test_season_results_for_all_drivers(self):
        self.patch_net()
        f1_api.refresh_all(force=True)
        rows = f1_api.get_season_results()
        self.assertEqual(len(rows), 9)                                      # все пилоты, все гонки
        self.assertEqual([r["driver_id"] for r in rows if r["round"] == "1"], ["antonelli", "leclerc", "lawson"])
        self.assertEqual(len(f1_api.get_qualifying()), 7)
        self.assertEqual(f1_api.get_sprints()[0]["points"], "8")
        idx = stats.season_index(rows, f1_api.get_qualifying(), f1_api.get_sprints())
        ant, lec, law = idx["antonelli"], idx["leclerc"], idx["lawson"]
        self.assertEqual((ant["wins"], ant["podiums"], ant["poles"], ant["fastest_laps"], ant["dnf"]), (2, 3, 2, 2, 0))
        self.assertEqual((lec["wins"], lec["podiums"], lec["poles"], lec["dnf"], lec["best"]), (0, 2, 1, 1, 2))
        self.assertEqual((law["starts"], law["dnf"]), (2, 1))              # «не стартовал» — не сход
        self.assertEqual(ant["race_points"] + ant["sprint_points"], 76)

    def test_results_refetched_only_on_new_round(self):
        fake = self.patch_net()
        f1_api.refresh_all(force=True)
        n = sum("results.json" in u for u in fake.calls)
        f1_api.refresh_all(force=True)                                      # тот же этап -> не перезапрашиваем
        self.assertEqual(sum("results.json" in u for u in fake.calls), n)
        self.patch_net(standings=standings_json(rnd="11"))                  # в зачёте новый этап
        fake2 = jolpica._session.get
        f1_api.refresh_all(force=True)
        self.assertEqual(sum("results.json" in u for u in fake2.calls), 1)

    # --- нет сети и нет кэша: никаких выдуманных данных ---
    def test_no_network_no_cache_returns_empty(self):
        self.patch_net(fail=True)
        self.assertFalse(f1_api.refresh_all(force=True))
        self.assertEqual(f1_api.get_cached_standings(), [])
        self.assertEqual(f1_api.get_season_results(), [])
        st = f1_api.get_status()
        self.assertEqual(st["state"], "empty")
        self.assertIsNotNone(st["error"])

    # --- сеть пропала после успеха: показываем последнюю реальную копию ---
    def test_network_loss_keeps_last_real_data(self):
        self.patch_net()
        f1_api.refresh_all(force=True)
        self.patch_net(fail=True)
        self.assertFalse(f1_api.refresh_all(force=True))
        self.assertEqual(driver("leclerc")["points"], "126")
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
        self.patch_net()
        f1_api.refresh_all(force=True)
        self.patch_net(standings=standings_json(empty=True))
        self.assertTrue(f1_api.refresh_standings(force=True))
        self.assertEqual(len(f1_api.get_cached_standings()), 3)

    # --- новое обновление заменяет старые значения целиком ---
    def test_update_replaces_values(self):
        self.patch_net(standings=standings_json("126"))
        f1_api.refresh_all(force=True)
        self.patch_net(standings=standings_json("144", rnd="11"))
        f1_api.refresh_all(force=True)
        self.assertEqual(driver("leclerc")["points"], "144")
        self.assertEqual(len(f1_api.get_cached_standings()), 3)

    # --- битый формат ответа = ошибка, а не падение ---
    def test_malformed_response(self):
        self.patch_net(standings={"MRData": {"StandingsTable": {"StandingsLists": [{"DriverStandings": [{}]}]}}})
        self.assertFalse(f1_api.refresh_standings(force=True))
        self.assertEqual(f1_api.get_cached_standings(), [])

    def test_malformed_results_keep_old_copy(self):
        self.patch_net()
        f1_api.refresh_all(force=True)
        bad = {"MRData": {"total": "1", "RaceTable": {"Races": [{"round": "1", "Results": [{}]}]}}}
        self.patch_net(results=bad)
        self.assertFalse(f1_api.refresh_season_results(force=True, ignore_ttl=True))
        self.assertEqual(len(f1_api.get_season_results()), 9)

    # --- фоновый поток: обновляет и зовёт on_update только при изменениях ---
    def test_background_refresh_calls_on_update(self):
        self.patch_net()
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
        self.assertEqual(driver("leclerc")["points"], "126")

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
            self.patch_net()                               # сеть вернулась
            self.assertTrue(got_live.wait(5))
            stop.set()
        self.assertEqual(driver("leclerc")["name"], "Charles Leclerc")

    def test_constructors_and_schedule_roundtrip(self):
        self.patch_net()
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
        fake = self.patch_net()
        f1_api.refresh_all(force=True)
        n = sum("current.json" in u for u in fake.calls)
        f1_api.refresh_all(force=True)                      # календарь свежий -> не перезапрашиваем
        self.assertEqual(sum("current.json" in u for u in fake.calls), n)
        f1_api.refresh_all(force=True, manual=True)         # «Обновить сейчас» -> перезапрос
        self.assertEqual(sum("current.json" in u for u in fake.calls), n + 1)

    def test_next_race_and_states(self):
        self.patch_net()
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
        self.patch_net()
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
        self.assertEqual(f1_api.get_season_results(), [])
        self.assertEqual(f1_api.get_status()["state"], "empty")
        self.assertEqual(f1_api.get_favorites(), ["leclerc"])            # не стёрлось
        self.assertEqual(f1_api.get_setting("refresh_minutes"), "10")

    def test_old_schema_drops_cache_keeps_user_data(self):
        """БД прошлой версии: кэш API пересоздаётся по новой схеме, избранное и настройки остаются."""
        import sqlite3
        path = os.environ["F1_HUB_DB"]
        con = sqlite3.connect(path)
        con.executescript("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);"
                          "INSERT INTO meta VALUES('standings_season','2026');"
                          "CREATE TABLE standings(season TEXT, driver_id TEXT, position INTEGER, points REAL,"
                          " wins INTEGER, code TEXT, name TEXT, team TEXT);"
                          "CREATE TABLE favorites(driver_id TEXT PRIMARY KEY, added_at REAL NOT NULL);"
                          "INSERT INTO favorites VALUES('leclerc', 1);"
                          "CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);"
                          "INSERT INTO settings VALUES('refresh_minutes','30');"
                          "PRAGMA user_version=2;")
        con.commit(); con.close()
        self.assertEqual(f1_api.get_favorites(), ["leclerc"])
        self.assertEqual(f1_api.get_setting("refresh_minutes"), "30")
        self.assertIsNone(db.get_meta("standings_season"))                # старый кэш сброшен
        self.patch_net()
        self.assertTrue(f1_api.refresh_all(force=True))                    # новая схема работает
        self.assertEqual(driver("leclerc")["nationality"], "Monegasque")

    def test_legacy_data_dir_is_migrated(self):
        home = Path(self.tmp.name) / "home"
        old = home / ".ferrari_leclerc_hub"
        old.mkdir(parents=True)
        os.environ["F1_HUB_DB"] = str(old / "f1_hub.db")
        f1_api.toggle_favorite("hamilton")
        db._initialized.clear()
        os.environ.pop("F1_HUB_DB")
        env = {k: v for k, v in os.environ.items() if k != "FLET_APP_STORAGE_DATA"}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(Path, "home", return_value=home):
            self.assertEqual(db.db_path(), home / ".f1_analytics_hub" / "f1_hub.db")
            self.assertEqual(f1_api.get_favorites(), ["hamilton"])           # избранное переехало
        os.environ["F1_HUB_DB"] = os.path.join(self.tmp.name, "t.db")

    def test_chain_stops_on_first_failure(self):
        fake = self.patch_net(fail=True)
        self.assertFalse(f1_api.refresh_all(force=True))
        self.assertEqual(len(fake.calls), 1)                  # дальше первого запроса не идём

    def test_live_window_follows_refresh_interval(self):
        self.patch_net()
        f1_api.refresh_all(force=True)
        later = time.time() + 20 * 60                       # данным 20 минут
        with mock.patch.object(time, "time", return_value=later):
            f1_api._config["interval"] = 300
            self.assertEqual(f1_api.get_status()["state"], "cached")
            f1_api._config["interval"] = 1800               # пользователь выбрал «раз в 30 минут»
            self.assertEqual(f1_api.get_status()["state"], "live")
        f1_api._config["interval"] = f1_api.REFRESH_INTERVAL

    # ================= снимок данных =================
    def _populate(self):
        self.patch_net()
        self.assertTrue(f1_api.refresh_all(force=True))
        db.save_driver_media([{"code": "LEC", "ref": "chalec01", "number": "16", "team": "Ferrari",
                               "headshot": "https://x/chalec01.png"}])

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

        def everything():
            return (f1_api.get_cached_standings(), f1_api.get_cached_constructors(), f1_api.get_season_results(),
                    f1_api.get_qualifying(), f1_api.get_sprints(), f1_api.get_cached_schedule(),
                    f1_api.get_driver_media())

        before = everything()
        os.environ["F1_HUB_DB"] = os.path.join(self.tmp.name, "second.db")   # чистая БД
        self.assertEqual(f1_api.get_cached_standings(), [])
        self.assertTrue(seed.import_if_empty(snap))
        self.assertEqual(before, everything())
        st = f1_api.get_status()
        self.assertEqual(st["state"], "cached")            # снимок не выдаётся за свежие данные
        self.assertAlmostEqual(st["updated_at"], old, places=3)

    def test_seed_never_overwrites_existing_data(self):
        self._populate()
        snap = os.path.join(self.tmp.name, "seed.json")
        seed.export_snapshot(snap)
        self.patch_net(standings=standings_json("999"))
        f1_api.refresh_all(force=True)                       # в БД новее, чем в снимке
        self.assertFalse(seed.import_if_empty(snap))
        self.assertEqual(driver("leclerc")["points"], "999")

    def test_seed_bad_files_are_ignored(self):
        bad = os.path.join(self.tmp.name, "bad.json")
        self.assertFalse(seed.import_if_empty(os.path.join(self.tmp.name, "missing.json")))
        write = lambda text: Path(bad).write_text(text, encoding="utf-8")  # noqa: E731
        write("{not json")
        self.assertFalse(seed.import_if_empty(bad))
        write('{"version": 1, "exported_at": 1, "season": "2026", "standings": []}')   # старая версия
        self.assertFalse(seed.import_if_empty(bad))
        write('{"version": 2, "exported_at": 1, "season": "2026"}')   # нет standings
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
        self.patch_net()
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

    # ================= единый фоновый поток =================
    def _threads(self):
        return [t for t in threading.enumerate() if t.name == "f1-refresh" and t.is_alive()]

    def test_one_refresh_thread_for_many_subscribers(self):
        self.patch_net()
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
                self.patch_net(standings=standings_json(str(100 + i)))
                time.sleep(0.25)
            h_good.set()
            f1_api.shutdown()                                  # дождаться цикла, пока подмена ещё действует
        self.assertEqual(calls["bad"], 2)                      # после 2 ошибок отключён
        self.assertGreaterEqual(calls["good"], 3)              # хороший подписчик продолжает получать
        h_bad.set()

    def test_interval_change_wakes_loop(self):
        fake = self.patch_net()
        h1 = f1_api.start_background_refresh(interval=3600)
        time.sleep(0.3)
        n = len(fake.calls)                                    # первое обновление выполнено
        h2 = f1_api.start_background_refresh(interval=3600)    # новый интервал -> немедленное обновление
        time.sleep(0.3)
        self.assertGreater(len(fake.calls), n)
        h1.set(); h2.set()


class MediaTest(unittest.TestCase):
    """Фото, логотипы, флаги: адреса, справочник OpenF1, дисковый кэш с запасным фото."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["F1_HUB_DB"] = os.path.join(self.tmp.name, "m.db")
        seed_env = mock.patch.dict(os.environ, {"F1_HUB_SEED": os.path.join(self.tmp.name, "no-seed.json")})
        seed_env.start()
        self.addCleanup(seed_env.stop)
        media.clear_memory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.environ.pop, "F1_HUB_DB", None)
        self.addCleanup(media.clear_memory)

    def test_urls(self):
        url = media.portrait_url("2026", "Red Bull Racing", "maxver01")
        self.assertIn("/common/f1/2026/redbullracing/maxver01/2026redbullracingmaxver01right.webp", url)
        self.assertIn("racingbulls", media.team_url("2026", "RB F1 Team", "logo"))       # старое название команды
        self.assertTrue(media.team_url("2026", "Ferrari", "car").endswith("2026ferraricarright.webp"))
        self.assertIsNone(media.team_url("2026", "Unknown Team"))
        self.assertEqual(media.flag_url("mc"), "https://flagcdn.com/w80/mc.png")
        self.assertEqual(media._ref_from_headshot(
            "https://media.formula1.com/x/CHALEC01_Charles_Leclerc/chalec01.png.transform/1col/image.png"), "chalec01")

    def test_refs_and_missing_driver_lookup(self):
        latest = [{"name_acronym": "LEC", "driver_number": 16, "team_name": "Ferrari",
                   "headshot_url": "https://m/CHALEC01_Charles_Leclerc/chalec01.png.transform/1col/image.png"}]
        by_code = [{"name_acronym": "TSU", "headshot_url": None},
                   {"name_acronym": "TSU", "driver_number": 22, "team_name": "Racing Bulls",
                    "headshot_url": "https://m/YUKTSU01_Yuki_Tsunoda/yuktsu01.png.transform/1col/image.png"},
                   {"name_acronym": "TSU", "headshot_url": None}]

        def fake_get(url, params=None, timeout=None):
            return FakeResponse(by_code if params.get("name_acronym") else latest)

        with mock.patch.object(media._session, "get", fake_get):
            rows = {r["code"]: r for r in media.fetch_refs(["LEC", "TSU"])}
        self.assertEqual(rows["LEC"]["ref"], "chalec01")
        self.assertEqual(rows["TSU"]["ref"], "yuktsu01")           # нашли по коду, последнюю запись с фото

    def test_cache_with_fallback(self):
        driver_row = {"code": "TSU", "team": "RB F1 Team", "season": "2026"}
        refs = {"TSU": {"code": "TSU", "ref": "yuktsu01", "headshot": "https://m/fallback.png"}}
        url = media.portrait_url("2026", "RB F1 Team", "yuktsu01")
        self.assertEqual(media.driver_photo(driver_row, refs), url)          # ещё не скачано -> URL

        def fake_get(u, timeout=None):
            if u == url:
                return FakeResponse(None, status=404)                      # портрета за сезон нет
            return FakeResponse(None, content=b"PNGDATA")

        with mock.patch.object(media._session, "get", fake_get):
            items = media.all_urls([driver_row], [], [], refs)
            self.assertIn((url, "https://m/fallback.png"), items)
            media.prefetch(items).join(10)
        self.assertEqual(media.driver_photo(driver_row, refs), b"PNGDATA")   # запасное фото под основным адресом
        self.assertIsNone(media.driver_photo({"code": "XXX", "team": "", "season": "2026"}, refs))

    def test_bundled_media_used_when_cache_is_empty(self):
        """Первый запуск без сети: фото из data/media, встроенной в сборку рядом со снимком."""
        url = media.flag_url("mc")
        bundled = Path(os.environ["F1_HUB_SEED"]).parent / "media"
        bundled.mkdir(parents=True, exist_ok=True)
        (bundled / media._cache_file(url).name).write_bytes(b"FLAG")
        self.assertEqual(media.flag("mc"), b"FLAG")

    def test_offline_prefetch_is_harmless(self):
        def fail(u, timeout=None):
            raise requests.ConnectionError("offline")

        with mock.patch.object(media._session, "get", fail):
            media.prefetch([("https://flagcdn.com/w80/it.png", None)]).join(10)
        self.assertEqual(media.flag("it"), "https://flagcdn.com/w80/it.png")


class ArchiveTest(unittest.TestCase):
    """История сезонов и трассы: загрузка в фоне, кэш, ошибки сети, разбор ответа, рекорды."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["F1_HUB_DB"] = os.path.join(self.tmp.name, "a.db")
        seed_env = mock.patch.dict(os.environ, {"F1_HUB_SEED": os.path.join(self.tmp.name, "seed.json")})
        seed_env.start()
        self.addCleanup(seed_env.stop)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.environ.pop, "F1_HUB_DB", None)

    def _wait(self, key):
        for _ in range(200):
            if not archive.loading(key):
                return
            time.sleep(0.01)

    def test_get_caches_and_respects_ttl(self):
        calls = []
        done = threading.Event()
        fetch = lambda: calls.append(1) or {"n": len(calls)}   # noqa: E731
        self.assertIsNone(archive.get("k", fetch, ttl=None, on_done=done.set))   # сначала — пусто, загрузка в фоне
        self.assertTrue(done.wait(3))
        self._wait("k")
        self.assertEqual(archive.get("k", fetch, ttl=None), {"n": 1})            # прошлый сезон — бессрочно
        self.assertEqual(len(calls), 1)
        with mock.patch.object(time, "time", return_value=time.time() + 10):
            self.assertEqual(archive.get("k", fetch, ttl=5), {"n": 1})          # устарело: старое + перезагрузка
        self._wait("k")
        self.assertEqual(len(calls), 2)

    def test_error_is_reported_and_old_copy_kept(self):
        def boom():
            raise jolpica.ApiError("offline")
        archive.get("e", boom)
        self._wait("e")
        self.assertIn("offline", archive.error("e"))
        self.assertIsNone(db.load_archive("e")[0])

    def test_season_archive_parsing(self):
        winners = {"MRData": {"total": "2", "RaceTable": {"season": "2010", "Races": [
            _race("1", "Bahrain GP", "Results", [{"Driver": {"driverId": "alonso", "code": "ALO", "givenName": "Fernando",
                                                            "familyName": "Alonso", "nationality": "Spanish"},
                                                 "Constructor": {"name": "Ferrari"}, "grid": "3"}]),
        ]}}}

        def fake_get(url, params=None, timeout=None):
            if "driverStandings" in url:
                return FakeResponse(standings_json(season="2010", rnd="19"))
            if "constructorStandings" in url:
                return FakeResponse(constructors_json())
            return FakeResponse(winners)

        with mock.patch.object(jolpica._session, "get", fake_get), mock.patch.object(jolpica, "MIN_INTERVAL", 0):
            data = jolpica.fetch_season_archive(2010)
        self.assertEqual((data["rounds"], len(data["standings"]), data["constructors"][0]["name"]),
                         ("19", 3, "Ferrari"))
        self.assertEqual((data["winners"][0]["name"], data["winners"][0]["team"]), ("Fernando Alonso", "Ferrari"))
        with mock.patch.object(jolpica._session, "get", fake_get), mock.patch.object(jolpica, "MIN_INTERVAL", 0):
            self.assertEqual(jolpica.fetch_season_archive(1955)["constructors"], [])   # Кубок — с 1958 года

    def test_champions_and_records(self):
        rows = [{"season": "2021", "name": "Max Verstappen", "nationality": "Dutch", "constructor": "Mercedes", "wins": "10"},
                {"season": "2020", "name": "Lewis Hamilton", "nationality": "British", "constructor": "Mercedes", "wins": "11"},
                {"season": "2019", "name": "Lewis Hamilton", "nationality": "British", "constructor": "Mercedes", "wins": "11"}]
        Path(os.environ["F1_HUB_SEED"]).parent.joinpath("champions.json").write_text(
            json.dumps({"version": 1, "champions": list(reversed(rows))}), encoding="utf-8")
        self.assertEqual([r["season"] for r in archive.champions()], ["2021", "2020", "2019"])   # новые сверху
        rec = archive.records(archive.champions())
        self.assertEqual(rec["drivers"][0], ("Lewis Hamilton", 2))
        self.assertEqual(rec["teams"][0], ("Mercedes", 3))
        self.assertEqual(rec["best_wins"]["wins"], "11")

    def test_bundled_champions_file_is_complete(self):
        """Встроенный список: каждый сезон с 1950 года, у каждого — чемпион."""
        path = Path(__file__).resolve().parent.parent / "data" / "champions.json"
        rows = json.loads(path.read_text(encoding="utf-8"))["champions"]
        seasons = [int(r["season"]) for r in rows]
        self.assertEqual(seasons, list(range(1950, seasons[-1] + 1)))
        self.assertTrue(all(r["name"] and r["team"] for r in rows))
        self.assertEqual(next(r for r in rows if r["season"] == "1950")["name"], "Nino Farina")


class NotifyTest(unittest.TestCase):
    def _race(self, start):
        return {"season": "2026", "round": "18", "race_name": "United States Grand Prix",
                "sessions": [{"key": "FirstPractice", "ts": start - 2 * 86400},
                             {"key": "Qualifying", "ts": start - 86400}, {"key": "Race", "ts": start}]}

    def test_due_reminders(self):
        now = time.time()
        race = self._race(now + 86400 + 1800)            # квалификация через 30 минут
        due = notify.due_reminders([race], now)
        self.assertEqual([d[0] for d in due], ["2026:18:Qualifying"])
        self.assertIn("Квалификация через 30 мин", due[0][1])
        self.assertEqual(notify.due_reminders([race], now, sent={"2026:18:Qualifying"}), [])   # уже напомнили
        self.assertEqual(notify.due_reminders([self._race(now + 3 * 86400)], now), [])         # ещё рано
        practice = self._race(now + 2 * 86400 + 600)
        self.assertEqual(notify.due_reminders([practice], now), [])                            # о практике — нет

    def test_favorites_result(self):
        standings = [{"driver_id": "leclerc", "name": "Charles Leclerc"}, {"driver_id": "lawson", "name": "Liam Lawson"}]
        results = [{"round": "17", "race_name": "Singapore GP", "season": "2026", "driver_id": "leclerc",
                    "position": "2", "points": "18"},
                   {"round": "17", "race_name": "Singapore GP", "season": "2026", "driver_id": "lawson",
                    "position": "R", "points": "0"},
                   {"round": "16", "race_name": "Old GP", "season": "2026", "driver_id": "leclerc",
                    "position": "1", "points": "25"}]
        nid, title, text = notify.favorites_result(["leclerc", "lawson"], standings, results)
        self.assertEqual((nid, title, text), ("2026:17:result", "Итоги: Singapore GP", "Leclerc — P2 (+18), Lawson — сход"))
        self.assertIsNone(notify.favorites_result(["norris"], standings, results))

    def test_notifier_falls_back_to_in_app(self):
        shown = []
        n = notify.Notifier(run_async=None, fallback=lambda t, b: shown.append(t))
        self.assertEqual(n.send("x", "Заголовок", "Текст"), "in-app")
        self.assertEqual(shown, ["Заголовок"])
        tasks = []
        with mock.patch.object(notify, "DesktopNotifier", mock.Mock()):
            self.assertEqual(notify.Notifier(run_async=tasks.append).send("y", "T", "B"), "desktop")
        self.assertEqual(len(tasks), 1)                    # корутина отдана в цикл событий Flet


class StatsTest(unittest.TestCase):
    def test_cumulative_and_head_to_head(self):
        a = [{"round": "1", "position": "1", "points": "25"}, {"round": "2", "position": "R", "points": "0"},
             {"round": "3", "position": "4", "points": "12"}]
        b = [{"round": "1", "position": "2", "points": "18"}, {"round": "2", "position": "5", "points": "10"},
             {"round": "3", "position": "R", "points": "0"}]
        sprints = [{"round": "2", "points": "8"}]
        self.assertEqual(stats.cumulative_points(a, sprints, [1, 2, 3]), [25, 33, 45])
        a_named = [dict(r, race_name="GP") for r in a]
        b_named = [dict(r, race_name="GP") for r in b]
        w1, w2, races = stats.head_to_head(a_named, b_named)
        self.assertEqual((w1, w2, len(races)), (2, 1, 3))
        self.assertEqual(stats.quali_head_to_head([{"round": "1", "position": "3"}, {"round": "2", "position": "1"}],
                                                  [{"round": "1", "position": "2"}, {"round": "2", "position": "5"}]),
                         (1, 1))

    def test_finishing_ahead_of_group(self):
        group = {
            "a": [{"round": "1", "position": "3"}, {"round": "2", "position": "R"}],
            "b": [{"round": "1", "position": "5"}, {"round": "2", "position": "7"}],
            "c": [{"round": "1", "position": "1"}],                       # во 2-й гонке не участвовал
        }
        self.assertEqual(stats.finishing_ahead(group), {"a": 0, "b": 0, "c": 1})

    def test_title_race(self):
        rows = [{"points": p} for p in ("340", "238", "229", "100")]
        r = stats.title_race(rows, 6, 2)                   # 6×25 + 2×8 = 166 очков
        self.assertEqual(r["available"], 166)
        self.assertEqual([c[1] for c in r["contenders"]], [340, 238, 229])   # 100 + 166 < 340 — выбыл
        self.assertFalse(r["clinched"])
        self.assertIsNone(r["next_clinch"])                # за одну гонку отрыв до >141 не нарастить
        r = stats.title_race(rows, 4, 1)                   # 108 очков, отрыв 102
        self.assertEqual(r["next_clinch"], 0)              # достаточно не уступить второму
        self.assertTrue(stats.title_race(rows, 1, 0)["clinched"])
        r = stats.title_race([{"points": "300"}, {"points": "280"}], 2, 0)
        self.assertEqual(r["next_clinch"], 6)              # после гонки останется 25: отрыв нужен 26
        teams = stats.title_race([{"points": "358"}, {"points": "285"}], 2, 0, "teams")
        self.assertEqual(teams["available"], 86)           # 2 × (25 + 18)

    def test_podiums_by_round(self):
        rows = [{"round": "1", "position": p, "driver_id": d} for p, d in (("2", "b"), ("1", "a"), ("3", "c"), ("4", "d"))]
        self.assertEqual([r["driver_id"] for r in stats.podiums_by_round(rows)["1"]], ["a", "b", "c"])
        self.assertEqual(stats.podiums_by_round(rows[:2]), {})            # неполный подиум не показываем


if __name__ == "__main__":
    unittest.main()
