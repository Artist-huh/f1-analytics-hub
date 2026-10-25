"""Схема трассы для Live Timing и главной: контур (MultiViewer API, бесплатно) и позиции машин (поток F1, Position.z).

Обе системы координат совпадают — это координаты F1 live timing. Контур кэшируется навсегда (archive),
позиции приходят в каждом снимке. Проекция на экран — чистая функция project().
"""
import base64
import json
import math
import zlib
from datetime import datetime

import requests

API = "https://api.multiviewer.app/api/v1/circuits"
MEETINGS = "https://api.openf1.org/v1/meetings"
MEETING_DAYS = 5               # этап (практики) начинается за 2–3 дня до гонки
TIMEOUT = (5, 20)
MAX_POINTS = 320                 # контуру хватает — меньше данных в окно и быстрее рисование


class TrackMapError(Exception):
    pass


def outline_key(circuit_key):
    return f"track:{circuit_key}"


def fetch_outline(circuit_key, year):
    """Контур трассы: {x, y, rotation, corners: [(номер, x, y)], name}. Пробует год сессии и прошлые."""
    last = None
    for y in (year, year - 1, year - 2):
        try:
            resp = requests.get(f"{API}/{circuit_key}/{y}", timeout=TIMEOUT, headers={"User-Agent": "f1-analytics-hub"})
            if resp.status_code != 200:
                last = f"HTTP {resp.status_code}"
                continue
            d = resp.json()
        except (requests.RequestException, ValueError) as exc:
            last = str(exc)
            continue
        xs, ys = d.get("x") or [], d.get("y") or []
        if len(xs) < 10 or len(xs) != len(ys):
            last = "пустой контур"
            continue
        step = max(1, len(xs) // MAX_POINTS)
        corners = [(c.get("number"), c["trackPosition"]["x"], c["trackPosition"]["y"])
                   for c in d.get("corners") or [] if c.get("trackPosition")]
        return {"x": xs[::step], "y": ys[::step], "rotation": float(d.get("rotation") or 0), "corners": corners,
                "name": d.get("circuitName", "")}
    raise TrackMapError(f"контур трассы {circuit_key} не загружен: {last}")


def meetings_key(year):
    return f"meetings:{year}"


def fetch_meetings(year):
    """Этапы сезона из расписания OpenF1 (бесплатно): [(начало этапа, ключ трассы)] — ключ тот же, что у контуров."""
    try:
        resp = requests.get(MEETINGS, params={"year": year}, timeout=TIMEOUT,
                            headers={"User-Agent": "f1-analytics-hub"})
        resp.raise_for_status()
        rows = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise TrackMapError(f"расписание этапов {year} не загружено: {exc}") from exc
    out = []
    for m in rows if isinstance(rows, list) else []:
        try:
            start = datetime.fromisoformat(m["date_start"]).timestamp()
        except (KeyError, TypeError, ValueError):
            continue
        if m.get("circuit_key") and "test" not in (m.get("meeting_name") or "").lower():
            out.append((start, m["circuit_key"]))
    if not out:
        raise TrackMapError(f"в расписании {year} нет этапов")
    return out


def circuit_for(meetings, race_ts):
    """Ключ трассы гонки: этап, который начался не раньше чем за MEETING_DAYS дней до старта гонки."""
    for start, key in meetings or []:
        if 0 <= race_ts - start <= MEETING_DAYS * 86400:
            return key
    return None


def decode_positions(z):
    """Position.z (base64 + deflate) -> {номер: {x, y, status}} по последнему кадру."""
    if not z:
        return {}
    try:
        data = json.loads(zlib.decompress(base64.b64decode(z), -zlib.MAX_WBITS))
    except (ValueError, zlib.error, TypeError):
        return {}
    frames = data.get("Position") or []
    if not frames:
        return {}
    entries = frames[-1].get("Entries") or {}
    return {str(n): {"x": e.get("X", 0), "y": e.get("Y", 0), "status": e.get("Status", "")}
            for n, e in entries.items() if isinstance(e, dict)}


def project(outline, width, height, pad=16):
    """-> функция (x, y) -> (px, py): поворот на rotation, ось Y вверх, вписать в прямоугольник с полями."""
    angle = math.radians(outline.get("rotation") or 0)
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    def rotate(x, y):
        return x * cos_a - y * sin_a, x * sin_a + y * cos_a

    pts = [rotate(x, y) for x, y in zip(outline["x"], outline["y"], strict=True)]
    min_x, max_x = min(p[0] for p in pts), max(p[0] for p in pts)
    min_y, max_y = min(p[1] for p in pts), max(p[1] for p in pts)
    span_x, span_y = max(max_x - min_x, 1), max(max_y - min_y, 1)
    scale = min((width - 2 * pad) / span_x, (height - 2 * pad) / span_y)
    off_x = (width - span_x * scale) / 2
    off_y = (height - span_y * scale) / 2

    def to_screen(x, y):
        rx, ry = rotate(x, y)
        return off_x + (rx - min_x) * scale, height - (off_y + (ry - min_y) * scale)

    return to_screen


def fitted_height(outline, width, pad=16, max_ratio=0.85):
    """Высота поля под контур: по пропорциям трассы, но не выше max_ratio от ширины."""
    angle = math.radians(outline.get("rotation") or 0)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    rx = [x * cos_a - y * sin_a for x, y in zip(outline["x"], outline["y"], strict=True)]
    ry = [x * sin_a + y * cos_a for x, y in zip(outline["x"], outline["y"], strict=True)]
    ratio = (max(ry) - min(ry)) / max(max(rx) - min(rx), 1)
    return round(min(max(ratio, 0.45), max_ratio) * (width - 2 * pad) + 2 * pad)
