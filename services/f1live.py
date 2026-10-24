"""Официальный поток live timing F1 (livetiming.formula1.com, SignalR Core) — бесплатно и без ключа.

OpenF1 на время сессии закрывает бесплатный доступ, а поток самой F1 отдаёт текущее состояние
сессии сразу в ответ на подписку: таблицу, шины, флаги, сообщения дирекции, записи радио.
Постоянное соединение не держим: каждый снимок — negotiate -> websocket -> Subscribe -> ответ
с полным состоянием -> закрыть (1–2 с). Так нет склейки обновлений и переподключений.
"""
import asyncio
import json
import time
from datetime import datetime, timedelta, timezone

import requests

from . import log, track_map

BASE = "https://livetiming.formula1.com"
STATIC = f"{BASE}/static/"
TOPICS = ["SessionInfo", "DriverList", "TimingData", "TimingAppData", "LapCount", "TrackStatus",
          "RaceControlMessages", "TeamRadio", "ExtrapolatedClock", "Position.z", "WeatherData"]
TIMEOUT = 15
RS = "\x1e"                      # разделитель сообщений SignalR
TYRES = {"SOFT": "S", "MEDIUM": "M", "HARD": "H", "INTERMEDIATE": "I", "WET": "W"}
TRACK_STATUS = {"1": None, "2": "Жёлтый флаг", "4": "Сейфти-кар", "5": "Красный флаг",
                "6": "Виртуальный сейфти-кар", "7": "VSC заканчивается"}
FINISHED = {"Finished", "Finalised", "Ends"}

logger = log.get("f1live")


class F1LiveError(Exception):
    pass


# ---------------------------------------------------------------- получение состояния
async def _subscribe(topics):
    import websockets
    s = requests.Session()
    neg = s.post(f"{BASE}/signalrcore/negotiate?negotiateVersion=1", timeout=TIMEOUT)
    if neg.status_code != 200:
        raise F1LiveError(f"negotiate: HTTP {neg.status_code}")
    token = neg.json()["connectionToken"]
    cookie = "; ".join(f"{k}={v}" for k, v in s.cookies.items())
    url = f"wss://livetiming.formula1.com/signalrcore?id={token}"
    async with websockets.connect(url, additional_headers={"Cookie": cookie}, max_size=None,
                                  open_timeout=TIMEOUT) as ws:
        await ws.send(json.dumps({"protocol": "json", "version": 1}) + RS)
        await asyncio.wait_for(ws.recv(), TIMEOUT)
        await ws.send(json.dumps({"type": 1, "invocationId": "0", "target": "Subscribe",
                                  "arguments": [topics]}) + RS)
        end = time.monotonic() + TIMEOUT
        while time.monotonic() < end:
            raw = await asyncio.wait_for(ws.recv(), max(0.1, end - time.monotonic()))
            for part in raw.split(RS):
                if not part:
                    continue
                msg = json.loads(part)
                if msg.get("type") == 3 and msg.get("invocationId") == "0":
                    if msg.get("error"):
                        raise F1LiveError(msg["error"])
                    return msg.get("result") or {}
    raise F1LiveError("нет ответа на подписку")


def fetch_state(topics=None):
    """Текущее состояние сессии по темам. -> dict (сырые данные F1)."""
    try:
        return asyncio.run(_subscribe(topics or TOPICS))
    except F1LiveError:
        raise
    except Exception as exc:          # сеть, websocket, формат
        raise F1LiveError(f"{type(exc).__name__}: {exc}") from exc


# ---------------------------------------------------------------- разбор
def _ts(utc):
    """'2026-10-23T17:27:36.720675Z' -> unix."""
    try:
        return datetime.strptime(utc[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def _local_ts(text, offset):
    """Время сессии F1 — местное время трассы + GmtOffset '-05:00:00'."""
    try:
        dt = datetime.fromisoformat(text)
        sign = -1 if offset.startswith("-") else 1
        h, m, s = (int(x) for x in offset.lstrip("+-").split(":"))
        return (dt.replace(tzinfo=timezone.utc) - sign * timedelta(hours=h, minutes=m, seconds=s)).timestamp()
    except (TypeError, ValueError, AttributeError):
        return None


def _items(value):
    """Списки в потоке F1 приходят то списком, то словарём {"0": ..., "1": ...}."""
    if isinstance(value, dict):
        return [value[k] for k in sorted(value, key=lambda k: int(k) if str(k).isdigit() else 0)]
    return value or []


def sector_state(sector):
    """Сектор: overall — лучший в сессии (фиолетовый), personal — личный лучший (зелёный),
    normal — пройден (жёлтый), none — ещё не пройден на этом круге."""
    if not isinstance(sector, dict) or not sector.get("Value"):
        return "none"
    if sector.get("OverallFastest"):
        return "overall"
    if sector.get("PersonalFastest"):
        return "personal"
    return "normal"


def weather(data):
    """WeatherData -> {air, track, humidity, wind, rain} (числа) или None."""
    if not data:
        return None

    def num(key):
        try:
            return float(data.get(key))
        except (TypeError, ValueError):
            return None
    return {"air": num("AirTemp"), "track": num("TrackTemp"), "humidity": num("Humidity"),
            "wind": num("WindSpeed"), "rain": str(data.get("Rainfall", "0")) not in ("0", "", "None")}


def fmt_gap(value):
    text = (value or "").strip() if isinstance(value, str) else ""
    if not text:
        return ""
    return text.replace("LAPS", "кр.").replace("LAP", "кр.")


def snapshot(state, now=None):
    """Сырые данные F1 -> снимок в формате экрана Live (как services.live.fetch) + радио."""
    now = time.time() if now is None else now
    info = state.get("SessionInfo") or {}
    if not info:
        raise F1LiveError("нет данных о сессии")
    meeting = info.get("Meeting") or {}
    offset = info.get("GmtOffset", "00:00:00")
    start, end = _local_ts(info.get("StartDate"), offset), _local_ts(info.get("EndDate"), offset)
    status = (info.get("SessionStatus") or (state.get("SessionStatus") or {}).get("Status") or "")
    live = status not in FINISHED and bool(start and end and start - 15 * 60 <= now <= end + 30 * 60)
    racing = (info.get("Type") or "") == "Race"
    drivers = state.get("DriverList") or {}
    timing = (state.get("TimingData") or {}).get("Lines") or {}
    app = (state.get("TimingAppData") or {}).get("Lines") or {}
    rows = []
    for number, t in timing.items():
        if not isinstance(t, dict) or not str(t.get("Position", "")).isdigit():
            continue
        d = drivers.get(number) or {}
        stints = _items((app.get(number) or {}).get("Stints"))
        last = stints[-1] if stints else {}
        interval = t.get("IntervalToPositionAhead")
        rows.append({
            "position": int(t["Position"]), "number": int(number) if str(number).isdigit() else number,
            "code": d.get("Tla") or str(number), "name": (d.get("FullName") or "").title(),
            "team": d.get("TeamName", ""), "colour": f"#{d['TeamColour']}" if d.get("TeamColour") else None,
            "gap": fmt_gap(t.get("GapToLeader") if racing else t.get("TimeDiffToFastest")),
            "interval": fmt_gap(interval.get("Value") if isinstance(interval, dict) else
                                t.get("TimeDiffToPositionAhead")),
            "tyre": TYRES.get((last.get("Compound") or "").upper(), "?") if last else "",
            "tyre_age": last.get("TotalLaps") if last else None,
            "pits": int(t.get("NumberOfPitStops") or max(0, len(stints) - 1)),
            "in_pit": bool(t.get("InPit")), "retired": bool(t.get("Retired") or t.get("Stopped")),
            "best": ((t.get("BestLapTime") or {}).get("Value") or ""),
            "last": ((t.get("LastLapTime") or {}).get("Value") or ""),
            "laps": t.get("NumberOfLaps") or 0,
            "sectors": [sector_state(s) for s in _items(t.get("Sectors"))][:3],
        })
    rows.sort(key=lambda r: r["position"])
    lap = state.get("LapCount") or {}
    messages = _items((state.get("RaceControlMessages") or {}).get("Messages"))
    path = info.get("Path") or ""
    radio = [{"driver": str(c.get("RacingNumber")), "url": STATIC + path + c["Path"], "ts": _ts(c.get("Utc"))}
             for c in _items((state.get("TeamRadio") or {}).get("Captures")) if c.get("Path") and path]
    track = state.get("TrackStatus") or {}
    clock = state.get("ExtrapolatedClock") or {}
    return {
        "session": {"name": info.get("Name", ""), "type": info.get("Type", ""),
                    "country": (meeting.get("Country") or {}).get("Name", ""), "location": meeting.get("Location", ""),
                    "circuit": (meeting.get("Circuit") or {}).get("ShortName", ""), "start": start, "end": end,
                    "year": int(path[:4]) if path[:4].isdigit() else None, "status": status},
        "live": live,
        "racing": racing,
        "rows": rows,
        "lap": lap.get("CurrentLap") or 0,
        "total_laps": lap.get("TotalLaps"),
        "remaining": clock.get("Remaining") if not racing else None,
        "track": TRACK_STATUS.get(str(track.get("Status"))),
        "messages": [{"time": _ts(m.get("Utc")), "text": m.get("Message", ""), "flag": m.get("Flag"),
                      "lap": m.get("Lap")} for m in messages[-6:]][::-1],
        "radio": sorted(radio, key=lambda r: r["ts"] or 0),
        "positions": track_map.decode_positions(state.get("Position.z")),      # только во время сессии
        "weather": weather(state.get("WeatherData")),
        "circuit_key": (meeting.get("Circuit") or {}).get("Key"),
        "drivers": {str(n): {"code": d.get("Tla", ""), "team": d.get("TeamName", ""), "colour": d.get("TeamColour")}
                    for n, d in drivers.items() if isinstance(d, dict)},
        "source": "F1",
        "updated": now,
    }


def fetch(now=None):
    return snapshot(fetch_state(), now)
