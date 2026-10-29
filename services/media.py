"""Фото пилотов, логотипы и болиды команд, флаги стран.

Источники:
  * OpenF1 (api.openf1.org/v1/drivers) — код пилота -> идентификатор портрета на formula1.com;
  * media.formula1.com — портреты на прозрачном фоне, логотипы и болиды команд текущего сезона;
  * flagcdn.com — флаги по ISO-коду страны.

Картинки сохраняются на диск (папка media рядом с базой): после первой загрузки они
показываются без сети. Интерфейс получает либо байты из кэша, либо URL — тогда
картинку загрузит сам Flutter, а prefetch() сохранит её к следующему запуску.
Изображения © Formula 1 / команды; приложение — некоммерческий фан-проект.
"""
import hashlib
import re
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

import requests

import design_system as ds

from . import db, log

OPENF1_DRIVERS = "https://api.openf1.org/v1/drivers"
F1_MEDIA = "https://media.formula1.com/image/upload"
FLAGS = "https://flagcdn.com"
REFS_TTL = 24 * 3600     # состав пилотов меняется редко
TIMEOUT = (3.05, 10)

# Размеры с запасом под экраны высокой плотности (×2)
# Размер — под отображение на экранах высокой плотности; q_auto:eco вдвое легче q_auto без видимой
# разницы. Важно: картинки уходят в окно байтами при каждой перерисовке (так они работают без сети),
# поэтому лишние килобайты — это задержка на каждом экране со списком пилотов.
SIZES = {
    "avatar": "c_fill,g_north,w_128,h_128/q_auto:eco",     # круглый аватар 32–72 px (голова и плечи)
    "portrait": "c_fill,g_north,w_300,h_375/q_auto:eco",   # карточка в «Пилотах» (~184 px по высоте)
    "hero": "c_fill,g_north,w_480,h_600/q_auto:eco",       # крупный портрет на странице пилота
    "logo": "c_fit,h_96/q_auto",
    "car": "c_fit,w_600/q_auto:eco",
}

logger = log.get("media")
_session = requests.Session()
_session.headers.update({"User-Agent": "F1AnalyticsHub/2.0 (fan project)"})

_bytes_lock = threading.Lock()
_bytes = OrderedDict()           # url -> bytes (последние использованные)
_BYTES_LIMIT = 300
_prefetch_lock = threading.Lock()
_prefetching = set()


# ---------------------------------------------------------------- адреса
def portrait_url(season, team_name, ref, kind="avatar"):
    slug = ds.team_slug(team_name)
    if not (season and slug and ref):
        return None
    return f"{F1_MEDIA}/{SIZES[kind]}/v1740000000/common/f1/{season}/{slug}/{ref}/{season}{slug}{ref}right.webp"


def team_url(season, team_name, kind="logo"):
    """kind: 'logo' — белый логотип, 'car' — болид в профиль (оба на прозрачном фоне)."""
    slug = ds.team_slug(team_name)
    if not (season and slug):
        return None
    suffix = "logowhite" if kind == "logo" else "carright"
    return f"{F1_MEDIA}/{SIZES[kind]}/v1740000000/common/f1/{season}/{slug}/{season}{slug}{suffix}.webp"


# Идентификатор трассы Jolpica -> имя схемы на formula1.com (остальные совпадают без «_»)
TRACK_SLUGS = {
    "albert_park": "melbourne", "villeneuve": "montreal", "monaco": "montecarlo",
    "red_bull_ring": "spielberg", "spa": "spafrancorchamps", "sepang": "kualalumpur",
    "marina_bay": "singapore", "americas": "austin", "rodriguez": "mexicocity", "vegas": "lasvegas",
    "losail": "lusail", "yas_marina": "yasmarina", "bahrain": "sakhir",
}


def track_url(season, circuit_id, dark_lines=False):
    """Схема трассы: белый контур (для тёмной темы) или чёрный (для светлой)."""
    if not (season and circuit_id):
        return None
    slug = TRACK_SLUGS.get(circuit_id, circuit_id.replace("_", ""))
    style = "blackoutline" if dark_lines else "whiteoutline"
    return f"{F1_MEDIA}/c_fit,w_600/q_auto:eco/v1740000000/common/f1/{season}/track/{season}track{slug}{style}.webp"


def track(season, circuit_id, dark_lines=False):
    return source(track_url(season, circuit_id, dark_lines))


def flag_url(iso):
    return f"{FLAGS}/w80/{iso}.png" if iso else None


# ---------------------------------------------------------------- справочник OpenF1
def _ref_from_headshot(url):
    """'.../CHALEC01_Charles_Leclerc/chalec01.png.transform/...' -> 'chalec01'."""
    m = re.search(r"/([a-z]{6}\d{2})\.png", url or "")
    return m.group(1) if m else ""


def _ref_row(d):
    return {"code": d["name_acronym"], "ref": _ref_from_headshot(d.get("headshot_url")),
            "number": str(d.get("driver_number") or ""), "team": d.get("team_name") or "",
            "headshot": d.get("headshot_url") or ""}


def fetch_refs(codes=()):
    """-> [{code, ref, number, team, headshot}] по последней сессии OpenF1.
    Пилотов из codes, которых в последней сессии нет (сменились по ходу сезона),
    ищем по коду — берём последнюю запись с фото."""
    resp = _session.get(OPENF1_DRIVERS, params={"session_key": "latest"}, timeout=TIMEOUT)
    resp.raise_for_status()
    rows = {d["name_acronym"]: _ref_row(d) for d in resp.json() if d.get("name_acronym")}
    for code in codes:
        if not code or code in rows:
            continue
        resp = _session.get(OPENF1_DRIVERS, params={"name_acronym": code}, timeout=TIMEOUT)
        if resp.status_code == 200:
            found = [d for d in resp.json() if d.get("headshot_url")]
            if found:
                rows[code] = _ref_row(found[-1])
    return list(rows.values())


def refresh_refs(force=False):
    """Обновить справочник раз в сутки. Ошибка не критична: остаются аватары с инициалами."""
    ts = db.fetched_at("media_fetched_at")
    if not force and ts and time.time() - ts < REFS_TTL:
        return True
    try:
        rows = fetch_refs([d["code"] for d in db.load_standings()])
        if rows:
            db.save_driver_media(rows)
        return True
    except (requests.RequestException, ValueError) as exc:
        logger.warning("справочник фото пилотов не обновлён: %s", exc)
        return False


# ---------------------------------------------------------------- для интерфейса
def driver_urls(driver, refs):
    """Адреса фото пилота: (портрет на прозрачном фоне или None, запасной headshot или None)."""
    ref = refs.get(driver.get("code") or "")
    if not ref:
        return None, None
    return ref["ref"], ref["headshot"] or None


def driver_photo(driver, refs, kind="avatar"):
    """Источник картинки для ft.Image (байты из кэша или URL) либо None — тогда аватар с инициалами."""
    ref, headshot = driver_urls(driver, refs)
    url = portrait_url(driver.get("season"), driver.get("team"), ref, kind) or headshot
    return source(url)


def team_logo(team_name, season):
    return source(team_url(season, team_name, "logo"))


def team_car(team_name, season):
    return source(team_url(season, team_name, "car"))


def flag(iso):
    return source(flag_url(iso))


# ---------------------------------------------------------------- дисковый кэш
def cache_dir():
    return db.db_path().parent / "media"


def _cache_file(url):
    ext = ".png" if url.endswith(".png") else ".webp"
    return cache_dir() / (hashlib.sha1(url.encode(), usedforsecurity=False).hexdigest()[:20] + ext)


def bundled_dir():
    """Картинки, встроенные в сборку рядом со снимком данных (data/media) — для первого
    запуска без сети. Создаются командой python -m services.seed export --refresh."""
    from . import seed
    return seed.default_path().parent / "media"


MAX_IMAGE = 8 * 1024 * 1024   # больше картинка интерфейса не бывает — дальше это не картинка


def is_image(data):
    """PNG, JPEG, WEBP или GIF по сигнатуре. Портал авторизации Wi-Fi (кафе, отель) отвечает на любой адрес
    HTML-страницей с кодом 200 — без проверки она сохранялась бы вместо фото пилота навсегда."""
    return bool(data) and len(data) <= MAX_IMAGE and (
        data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff"
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP") or data[:6] in (b"GIF87a", b"GIF89a"))


def source(url):
    """Байты из кэша (или из встроенных в сборку), если картинка есть, иначе сам URL."""
    if not url:
        return None
    with _bytes_lock:
        data = _bytes.get(url)
        if data is not None:
            _bytes.move_to_end(url)
            return data
    path = _cache_file(url)
    try:
        data = path.read_bytes()
        if not is_image(data):                     # кэш испорчен (ответ портала Wi-Fi, обрыв) — убрать и скачать заново
            path.unlink(missing_ok=True)
            raise OSError("в кэше не картинка")
    except OSError:
        try:
            data = (bundled_dir() / path.name).read_bytes()
        except OSError:
            return url
    with _bytes_lock:
        _bytes[url] = data
        while len(_bytes) > _BYTES_LIMIT:
            _bytes.popitem(last=False)
    return data


def _download(item):
    """item — (url, запасной_url): если основной адрес не отдал картинку (например, нет
    портрета пилота за этот сезон), под его именем сохраняется запасная."""
    url, fallback = item
    path = _cache_file(url)
    if path.exists():
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    for candidate in (url, fallback):
        if not candidate:
            continue
        try:
            resp = _session.get(candidate, timeout=TIMEOUT)
        except requests.RequestException:
            return False
        if resp.status_code == 200 and is_image(resp.content):
            try:
                tmp = path.with_suffix(path.suffix + ".part")
                tmp.write_bytes(resp.content)
                tmp.replace(path)
                return True
            except OSError:
                return False
    return False


def all_urls(standings, constructors, schedule, refs):
    """Всё, что показывает интерфейс: [(url, запасной_url)] — аватары и портреты,
    логотипы и болиды, флаги."""
    items = []
    for d in standings:
        ref, headshot = driver_urls(d, refs)
        for kind in ("avatar", "portrait", "hero"):
            url = portrait_url(d.get("season"), d.get("team"), ref, kind)
            items.append((url, headshot) if url else (headshot, None))
        items.append((flag_url(ds.nationality_iso(d.get("nationality"))), None))
    for c in constructors:
        items += [(team_url(c.get("season"), c["name"], "logo"), None),
                  (team_url(c.get("season"), c["name"], "car"), None)]
    for r in schedule:
        items.append((flag_url(ds.country_iso(r.get("country"))), None))
        for dark_lines in (False, True):
            items.append((track_url(r.get("season"), r.get("circuit_id"), dark_lines), None))
    return list({url: (url, fb) for url, fb in items if url}.values())


def prefetch(items, on_done=None, workers=4):
    """Скачать недостающие картинки в фоне (несколько потоков, без повторов).
    items — [(url, запасной_url)] или просто [url]."""
    items = [i if isinstance(i, tuple) else (i, None) for i in items]
    with _prefetch_lock:
        todo = [i for i in items if i[0] not in _prefetching and not _cache_file(i[0]).exists()]
        _prefetching.update(u for u, _ in todo)
    if not todo:
        return None

    def job():
        try:
            cache_dir().mkdir(parents=True, exist_ok=True)
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="f1-media") as pool:
                ok = sum(pool.map(_download, todo))
            logger.info("картинки сохранены: %d из %d", ok, len(todo))
        finally:
            with _prefetch_lock:
                _prefetching.difference_update(u for u, _ in todo)
            if on_done:
                on_done()

    thread = threading.Thread(target=job, name="f1-media-prefetch", daemon=True)
    thread.start()
    return thread


def cache_size_kb():
    try:
        return round(sum(p.stat().st_size for p in cache_dir().glob("*")) / 1024)
    except OSError:
        return 0


def clear_memory():
    with _bytes_lock:
        _bytes.clear()
