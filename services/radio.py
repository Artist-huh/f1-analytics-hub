"""Радио команд: записи переговоров из OpenF1, офлайн-расшифровка и перевод на русский.

Всё бесплатно и без ключей:
  записи      — OpenF1 team_radio (во время сессий закрыт, как и остальной OpenF1);
  расшифровка — faster-whisper: Whisper small.en (~465 МБ, точнее на шумном радио) или base.en (~145 МБ);
  перевод     — модель Argos Translate en→ru (~100 МБ), запускается напрямую через CTranslate2 + SentencePiece.
Модели скачиваются один раз по кнопке и лежат в папке данных (models/). Только компьютер:
на Android тяжёлые библиотеки не собираются — там лента и проигрывание без перевода.
Готовые расшифровки кэшируются в таблице archive (ключ radio_tx:<url>) — второй раз не считаются.
"""
import io
import re
import shutil
import threading
import time
import zipfile
from pathlib import Path

import requests

from . import db, live, log

# Модель расшифровки на выбор: на настоящем радио small.en заметно точнее при почти той же скорости.
# Размер — вместе с моделью перевода (~200 МБ).
WHISPER_MODELS = {"small.en": ("Точная", 670), "base.en": ("Лёгкая", 350)}
DEFAULT_WHISPER = "small.en"
ARGOS_URL = "https://argos-net.com/v1/translate-en_ru-1_9.argosmodel"
F1_PROMPT = "Formula 1 team radio. Box, box. Tyres, lap, pit, gap, push, copy, mode, delta, safety car."
TIMEOUT = (5, 60)

logger = log.get("radio")
_lock = threading.Lock()
_models = {}                       # загруженные модели: "whisper", "translator", "sp"
_jobs = {}                         # url -> "pending" | текст ошибки
_queue = []
_worker = [None]
_download = {"state": None, "error": None, "progress": 0.0}   # state: None | "running" | "done" | "error"


def tx_key(url):
    return f"radio_tx:{url}"


def radio_key(race):
    return f"radio:{race.get('season')}:{race['round']}"


# ---------------------------------------------------------------- лента записей
def fetch_radio(year, race_date):
    """Записи гонки: {"start": ts старта, "drivers": {номер: {...}}, "messages": [{driver, url, ts}]} по времени."""
    session = live.race_session(year, race_date)
    key = session["session_key"]
    rows = live._query("team_radio", f"session_key={key}")
    if not rows:
        raise live.LiveError("OpenF1 не отдал записи радио этой гонки")
    messages = sorted(({"driver": str(r["driver_number"]), "url": r["recording_url"], "ts": live._ts(r["date"])}
                       for r in rows if r.get("recording_url") and r.get("date")), key=lambda m: m["ts"])
    return {"start": live._ts(session.get("date_start")), "drivers": live.session_drivers(key), "messages": messages}


# ---------------------------------------------------------------- модели
def models_dir() -> Path:
    return db.data_dir() / "models"


def argos_dir() -> Path:
    return models_dir() / "argos-en_ru"


def supported():
    """Есть ли библиотеки расшифровки (на Android и в урезанных сборках их нет)."""
    try:
        import ctranslate2  # noqa: F401
        import faster_whisper  # noqa: F401
        import sentencepiece  # noqa: F401
    except ImportError:
        return False
    return True


def _whisper_dir(name):
    return models_dir() / f"whisper-{name}"


def whisper_model():
    """Скачанная модель расшифровки (выбранная пользователем — в первую очередь) или None."""
    order = [db.get_setting("radio_model")] + list(WHISPER_MODELS)
    return next((n for n in order if n in WHISPER_MODELS and (_whisper_dir(n) / "model.bin").exists()), None)


def models_ready():
    return bool(whisper_model()) and (argos_dir() / "model" / "model.bin").exists()


def download_state():
    return dict(_download)


def download_models(on_done=None, model=DEFAULT_WHISPER):
    """Скачать модели расшифровки (model) и перевода в фоне. on_done() — после окончания (успех или ошибка)."""
    model = model if model in WHISPER_MODELS else DEFAULT_WHISPER
    db.set_setting("radio_model", model)
    with _lock:
        if _download["state"] == "running":
            return
        _download.update(state="running", error=None, progress=0.0)

    def job():
        try:
            models_dir().mkdir(parents=True, exist_ok=True)
            if not (_whisper_dir(model) / "model.bin").exists():
                from faster_whisper.utils import download_model
                download_model(model, output_dir=str(_whisper_dir(model)))
            _download["progress"] = 0.5
            if not (argos_dir() / "model" / "model.bin").exists():
                _download_argos()
            _download.update(state="done", progress=1.0)
        except Exception as exc:
            logger.warning("модели радио не скачались: %s", exc)
            _download.update(state="error", error=str(exc))
        if on_done:
            on_done()

    threading.Thread(target=job, name="f1-radio-models", daemon=True).start()


def _download_argos():
    """Пакет Argos — zip с папкой model/ (CTranslate2) и sentencepiece.model. Распаковываем только их."""
    tmp = models_dir() / "argos.part"
    with requests.get(ARGOS_URL, stream=True, timeout=TIMEOUT) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length") or 0)
        done = 0
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(1 << 16):
                f.write(chunk)
                done += len(chunk)
                if total:
                    _download["progress"] = 0.5 + 0.5 * done / total
    extract_argos(tmp)
    tmp.unlink(missing_ok=True)


def extract_argos(package):
    target = argos_dir()
    shutil.rmtree(target, ignore_errors=True)
    with zipfile.ZipFile(package) as z:
        for info in z.infolist():
            parts = Path(info.filename).parts[1:]          # без корневой папки пакета
            if not parts or info.is_dir() or not (parts[0] == "model" or parts[0] == "sentencepiece.model"):
                continue
            out = target.joinpath(*parts)
            out.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst)
    if not (target / "model" / "model.bin").exists():
        raise RuntimeError("в пакете перевода нет модели")


def _load_models():
    with _lock:
        name = whisper_model()
        if _models.get("whisper_name") != name:
            from faster_whisper import WhisperModel
            _models["whisper"] = WhisperModel(str(_whisper_dir(name)), device="cpu", compute_type="int8")
            _models["whisper_name"] = name
        if "translator" not in _models:
            import ctranslate2
            import sentencepiece
            _models["translator"] = ctranslate2.Translator(str(argos_dir() / "model"), device="cpu",
                                                           compute_type="int8")
            # байтами, а не путём: SentencePiece на Windows не открывает файл по пути с кириллицей
            # (папка пользователя «Андрей») — NOT_FOUND при существующем файле
            proto = (argos_dir() / "sentencepiece.model").read_bytes()
            _models["sp"] = sentencepiece.SentencePieceProcessor(model_proto=proto)
    return _models


# ---------------------------------------------------------------- расшифровка и перевод
def split_sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


# Жаргон радио модель перевода не знает («box» -> «коробка», «push» -> «толкать»): перед переводом
# заменяем его обычными словами, после — поправляем устоявшиеся русские термины.
JARGON_EN = [
    (r"\bbox,?\s+box\b", "make a pit stop"),
    (r"\bbox\b", "make a pit stop"),
    (r"\bstay out\b", "stay on track"),
    (r"\blift and coast\b", "save fuel"),
    (r"\bflat out\b", "at full speed"),
    (r"\bpushing\b", "attacking"),
    (r"\bpush\b", "attack"),
]
JARGON_RU = [
    (r"(виртуальн\w+ )?(машин|автомобил)\w* безопасности",
     lambda m: "виртуальный сейфти-кар" if m[1] else "сейфти-кар"),
]


def _plain_english(text):
    # повторы «box this lap, box this lap» модель склеивает в бессмыслицу — оставляем один
    text = re.sub(r"\b(\w[\w ']{1,40}?)[,.!]?\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    for pattern, repl in JARGON_EN:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text


def _fix_russian(text):
    for pattern, repl in JARGON_RU:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text[:1].upper() + text[1:]


def translate(text):
    """en -> ru по предложениям (Argos так же режет текст перед моделью)."""
    m = _load_models()
    sentences = split_sentences(_plain_english(text))
    if not sentences:
        return ""
    tokens = [m["sp"].encode(s, out_type=str) for s in sentences]
    results = m["translator"].translate_batch(tokens, beam_size=4, max_decoding_length=256)
    return " ".join(_fix_russian(m["sp"].decode(r.hypotheses[0])) for r in results).strip()


def transcribe_audio(audio):
    """Путь к файлу или поток (mp3/wav) -> английский текст."""
    segments, _ = _load_models()["whisper"].transcribe(audio, beam_size=5, initial_prompt=F1_PROMPT,
                                                       condition_on_previous_text=False)
    return " ".join(s.text.strip() for s in segments).strip()


def process(url):
    """Скачать запись, расшифровать, перевести. -> {"en", "ru"} (и в кэш)."""
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    en = transcribe_audio(io.BytesIO(resp.content))
    result = {"en": en, "ru": translate(en) if en else "", "at": time.time()}
    db.save_archive(tx_key(url), result)
    return result


def cached(url):
    return db.load_archive(tx_key(url))[0]


def status(url):
    """None — не запрашивали, "pending" — в очереди или считается, иначе — текст ошибки."""
    return _jobs.get(url)


def request(url, on_done=None):
    """Поставить запись в очередь расшифровки (один фоновый поток — модели тяжёлые)."""
    with _lock:
        if _jobs.get(url) == "pending":
            return
        _jobs[url] = "pending"
        _queue.append((url, on_done))
        if _worker[0] and _worker[0].is_alive():
            return
        _worker[0] = threading.Thread(target=_work, name="f1-radio-tx", daemon=True)
        _worker[0].start()


def _work():
    while True:
        with _lock:
            if not _queue:
                return
            url, on_done = _queue.pop(0)
        try:
            process(url)
            _jobs.pop(url, None)
        except Exception as exc:
            logger.warning("радио %s не расшифровано: %s", url, exc)
            _jobs[url] = f"не получилось: {exc}"[:200]
        if on_done:
            on_done()
