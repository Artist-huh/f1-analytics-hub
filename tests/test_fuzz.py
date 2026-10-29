"""Фаззинг разбора внешних данных: ответ портится сотнями способов — разбор либо отдаёт данные, либо бросает
свою ошибку (ApiError, F1LiveError), но не KeyError/TypeError/AttributeError. Те обходили запасные пути:
ронял фоновое обновление, OpenF1 не включался вместо сломанного потока. Сид фиксирован — тест детерминирован."""
import contextlib
import copy
import random
import unittest
from unittest import mock

from services import f1live, jolpica
from tests import test_data_layer

BAD = [None, "", "abc", 0, -1, 10**18, 1.5, [], {}, [None], {"x": None}, True, "\x00", "1:2:3:4"]


def _paths(obj, prefix=()):
    yield prefix
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _paths(v, prefix + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:3]):
            yield from _paths(v, prefix + (i,))


def mutations(sample, n, seed):
    rnd = random.Random(seed)
    paths = [p for p in _paths(sample) if p]
    for _ in range(n):
        data = copy.deepcopy(sample)
        for _ in range(rnd.randint(1, 3)):
            p = rnd.choice(paths)
            parent = data
            try:
                for k in p[:-1]:
                    parent = parent[k]
                if rnd.random() < 0.3 and isinstance(parent, dict):
                    parent.pop(p[-1], None)
                else:
                    parent[p[-1]] = rnd.choice(BAD)
            except (KeyError, IndexError, TypeError):
                pass
        yield data


def _driver(i):
    return {"driverId": f"d{i}", "givenName": "A", "familyName": f"B{i}", "code": f"D{i}", "nationality": "x"}


STANDINGS = {"StandingsTable": {"season": "2026", "StandingsLists": [{"round": "5", "DriverStandings": [
    {"position": str(i), "points": "10", "wins": "1", "Driver": _driver(i), "Constructors": [{"name": "T"}]}
    for i in (1, 2)]}]}}
SCHEDULE = {"RaceTable": {"season": "2026", "Races": [
    {"round": "1", "raceName": "GP", "date": "2026-03-08", "time": "05:00:00Z",
     "Circuit": {"circuitId": "albert_park", "circuitName": "Albert Park",
                 "Location": {"locality": "Melbourne", "country": "Australia"}},
     "Qualifying": {"date": "2026-03-07", "time": "06:00:00Z"}}]}}
RESULTS = {"total": "2", "RaceTable": {"season": "2026", "Races": [
    {"round": "1", "raceName": "GP", "date": "2026-03-08", "Circuit": {"circuitName": "AP", "Location": {}},
     "Results": [{"position": "1", "points": "25", "grid": "2", "status": "Finished", "Driver": _driver(1),
                  "Constructor": {"name": "T"}, "FastestLap": {"rank": "1"}}]}]}}


class FuzzTest(unittest.TestCase):
    def test_f1_stream_never_crashes_with_foreign_errors(self):
        for state in mutations(test_data_layer.F1LiveTest.STATE, 400, seed=11):
            with mock.patch.object(f1live, "fetch_state", return_value=state), \
                    _quiet(), contextlib.suppress(f1live.F1LiveError):
                f1live.fetch()

    def test_jolpica_parsers_raise_only_api_error(self):
        cases = [(STANDINGS, jolpica.fetch_standings), (STANDINGS, jolpica.fetch_constructor_standings),
                 (SCHEDULE, jolpica.fetch_schedule), (RESULTS, jolpica.fetch_season_results),
                 (RESULTS, jolpica.fetch_qualifying), (RESULTS, jolpica.fetch_sprints)]
        for sample, call in cases:
            for bad in mutations(sample, 250, seed=7):
                with self.subTest(call=call.__name__), \
                        mock.patch.object(jolpica, "_get", lambda path, params=None, b=bad: b), \
                        mock.patch.object(jolpica.time, "sleep"), contextlib.suppress(jolpica.ApiError):
                    call()


class _quiet:
    """Пропущенные строки пилота пишутся в журнал предупреждением — в выводе тестов они не нужны."""

    def __enter__(self):
        self._p = mock.patch.object(f1live.logger, "warning")
        self._p.start()

    def __exit__(self, *exc):
        self._p.stop()
        return False


if __name__ == "__main__":
    unittest.main()
