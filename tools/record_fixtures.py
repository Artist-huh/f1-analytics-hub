"""Записать настоящие ответы источников для тестов (tests/recorded/, сжато gzip).

    python tools/record_fixtures.py

Сохраняет ответы Jolpica на все запросы текущего сезона (зачёт, Кубок, результаты, квалификации, спринты,
календарь — со всеми страницами) и снимок потока F1 live timing. Тест tests/test_recorded.py прогоняет через
них разбор данных приложения: так ловится смена формата, которую синтетические фикстуры не покажут.
Перезаписывать после заметных изменений у источников или раз в сезон.
"""
import gzip
import json
import os
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("F1_HUB_LOG", "off")

from services import f1live, jolpica  # noqa: E402

OUT = os.path.join(ROOT, "tests", "recorded")


def key(url, params):
    """Ключ записи: путь запроса и номер страницы — по ним тест находит ответ."""
    path = url.split("/ergast/f1/", 1)[-1]
    offset = (params or {}).get("offset", 0)
    return f"{path}?offset={offset}"


def record_jolpica():
    responses = {}
    real_get = jolpica._session.get

    def get(url, params=None, **kw):
        resp = real_get(url, params=params, **kw)
        if resp.status_code == 200:
            responses[key(url, params)] = resp.json()
        return resp

    jolpica._session.get = get
    try:
        season, rnd, standings = jolpica.fetch_standings()
        jolpica.fetch_constructor_standings()          # как в приложении: сезон «current»
        jolpica.fetch_season_results()
        jolpica.fetch_qualifying()
        jolpica.fetch_sprints()
        jolpica.fetch_schedule()
    finally:
        jolpica._session.get = real_get
    return {"season": season, "round": rnd, "drivers": len(standings), "responses": responses}


def save(name, payload):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{name}: {os.path.getsize(path) // 1024} КБ")


def main():
    recorded_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    data = record_jolpica()
    data["recorded_at"] = recorded_at
    save("jolpica.json.gz", data)
    print(f"  сезон {data['season']}, этап {data['round']}, запросов: {len(data['responses'])}")
    state = f1live.fetch_state()
    save("f1_stream.json.gz", {"recorded_at": recorded_at, "now": time.time(), "state": state})
    info = state.get("SessionInfo") or {}
    print(f"  поток F1: {(info.get('Meeting') or {}).get('Name', '?')}, {info.get('Name', '?')}")


if __name__ == "__main__":
    main()
