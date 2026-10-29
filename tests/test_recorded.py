"""Разбор настоящих ответов источников, записанных tools/record_fixtures.py (tests/recorded/).

Синтетические фикстуры в test_data_layer повторяют то, что мы думаем о формате; здесь — то, что источник
отдал на самом деле. Если Jolpica или поток F1 сменят формат, перезапись фикстур уронит этот тест раньше,
чем пользователи увидят пустые экраны.
"""
import gzip
import json
import os
import tempfile
import unittest
from unittest import mock

from services import db, f1live, jolpica, media
from services import f1_api as api

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recorded")


def load(name):
    with gzip.open(os.path.join(HERE, name), "rt", encoding="utf-8") as f:
        return json.load(f)


class Replay:
    """Подмена Session.get: отдаёт записанный ответ по пути и странице, незаписанный запрос — ошибка."""

    def __init__(self, responses):
        self.responses = responses
        self.missing = []

    def __call__(self, url, params=None, timeout=None):
        path = url.split("/ergast/f1/", 1)[-1]
        key = f"{path}?offset={(params or {}).get('offset', 0)}"
        if key not in self.responses:
            self.missing.append(key)
            raise AssertionError(f"нет записи для {key} — перезапишите: python tools/record_fixtures.py")
        resp = mock.Mock(status_code=200)
        resp.json.return_value = self.responses[key]
        return resp


class RecordedJolpicaTest(unittest.TestCase):
    """Полное обновление, как в приложении, — на записанных ответах; результат читается из настоящей базы."""

    @classmethod
    def setUpClass(cls):
        cls.rec = load("jolpica.json.gz")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {"F1_HUB_DB": os.path.join(self.tmp.name, "r.db"),
                                           "F1_HUB_SEED": os.path.join(self.tmp.name, "no-seed.json")})
        env.start()
        self.addCleanup(env.stop)
        api._state.update(error=None, fail_until=0.0)
        self.replay = Replay(self.rec["responses"])
        for target, attr, value in ((jolpica, "MIN_INTERVAL", 0), (jolpica, "PAGE_PAUSE", 0),
                                    (jolpica._session, "get", self.replay),
                                    (media, "refresh_refs", mock.Mock(return_value=True)),
                                    (media, "prefetch", mock.Mock(return_value=None))):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_full_refresh_on_real_responses(self):
        self.assertTrue(api.refresh_all(force=True, manual=True), api.get_status())
        self.assertEqual(self.replay.missing, [])

        standings = db.load_standings()
        self.assertEqual(len(standings), self.rec["drivers"])
        places = [int(r["position"]) for r in standings if str(r["position"]).isdigit()]
        self.assertEqual(places, sorted(places))                                  # по местам
        self.assertEqual(places[0], 1)
        ids = {r["driver_id"] for r in standings}
        for r in standings:
            self.assertTrue(r["name"] and r["team"] and r["code"], r)
            float(r["points"])                                                    # очки — число

        constructors = db.load_constructors()
        self.assertGreaterEqual(len(constructors), 10)
        self.assertTrue(all(c["name"] for c in constructors))

        results = db.load_season_results()
        rounds = {int(r["round"]) for r in results}
        self.assertEqual(max(rounds), int(self.rec["round"]))                     # все этапы до текущего
        self.assertTrue(ids & {r["driver_id"] for r in results})                  # те же пилоты, что в зачёте
        self.assertTrue(all(r["driver_id"] and r["team"] for r in results))
        winners = [r for r in results if str(r["position"]) == "1"]
        self.assertEqual(len(winners), len(rounds))                               # по победителю на этап

        schedule = db.load_schedule()
        self.assertGreaterEqual(len(schedule), int(self.rec["round"]))
        for race in schedule:
            self.assertTrue(race["start_ts"] > 0 and race["sessions"], race["race_name"])


class RecordedStreamTest(unittest.TestCase):
    """Снимок потока F1 live timing: разбор в таблицу экрана Live."""

    def test_snapshot_from_real_stream(self):
        rec = load("f1_stream.json.gz")
        data = f1live.snapshot(rec["state"], now=rec["now"])
        rows = data["rows"]
        self.assertGreaterEqual(len(rows), 18)
        self.assertEqual([r["position"] for r in rows], sorted(r["position"] for r in rows))
        for r in rows:
            self.assertRegex(r["code"], r"^[A-Z]{3}$")
            self.assertIn(r["tyre"], ("S", "M", "H", "I", "W", "", None))
        self.assertTrue(data["session"].get("name"))


if __name__ == "__main__":
    unittest.main()
