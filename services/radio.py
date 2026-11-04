"""Радио команд: записи переговоров из OpenF1, офлайн-расшифровка и перевод на русский.

Всё бесплатно и без ключей:
  записи      — OpenF1 team_radio (во время сессий закрыт, как и остальной OpenF1);
  расшифровка — whisper.cpp (pywhispercpp): Whisper small.en (~190 МБ, точнее на шумном радио) или base.en
                (~60 МБ) в сжатом виде q5_1; mp3 декодирует miniaudio (без FFmpeg);
  перевод     — модель Argos Translate en→ru (~100 МБ), запускается напрямую через CTranslate2 + SentencePiece.
Модели скачиваются один раз по кнопке и лежат в папке данных (models/). whisper.cpp есть и для телефонов —
тот же движок и те же модели, поэтому расшифровка везде одинаковая.
До 2.7 расшифровка шла через faster-whisper: на 12 записях Гран-при Мексики whisper.cpp small.en-q5_1
распознаёт так же, на 20 % быстрее и в 2,5 раза меньше по размеру (сравнение — в истории коммита).
Готовые расшифровки кэшируются в таблице archive (ключ radio_tx:<url>) — второй раз не считаются.
"""
import hashlib
import os
import re
import shutil
import threading
import time
import zipfile
from pathlib import Path

import requests

from . import db, live, log

# Модель расшифровки на выбор: на настоящем радио small.en заметно точнее (base.en путает слова и на шуме
# пишет «[INAUDIBLE]»). Размер модели в МБ; перевод — ещё TRANSLATION_MB (Argos на компьютере, ML Kit на телефоне).
WHISPER_MODELS = {"small.en-q5_1": ("Точная", 190), "base.en-q5_1": ("Лёгкая", 60)}
TRANSLATION_MB = {"computer": 200, "phone": 60}     # пакет Argos — 196 МБ, модели ML Kit en и ru — ~60 МБ
DEFAULT_WHISPER = "small.en-q5_1"
# Модели разбирает нативный код (whisper.cpp, CTranslate2, SentencePiece), поэтому скачанный файл сверяется
# с SHA-256, а ссылка закреплена на коммите репозитория моделей: подмена файла на сервере или ответ вроде
# страницы входа в Wi-Fi не станут «моделью». Суммы — из LFS Hugging Face и проверены на скачанных файлах.
WHISPER_COMMIT = "5359861c739e955e79d9a303bcbc70fb988958b1"
WHISPER_URL = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/{WHISPER_COMMIT}/ggml-{{}}.bin"
WHISPER_SHA256 = {
    "small.en-q5_1": "bfdff4894dcb76bbf647d56263ea2a96645423f1669176f4844a1bf8e478ad30",
    "base.en-q5_1": "4baf70dd0d7c4247ba2b81fafd9c01005ac77c2f9ef064e00dcf195d0e2fdd2f",
}
MAX_WHISPER = 600 * 1024 * 1024
OLD_WHISPER_DIRS = ("whisper-small.en", "whisper-base.en")   # модели faster-whisper до 2.7 — больше не нужны
ARGOS_URL = "https://argos-net.com/v1/translate-en_ru-1_9.argosmodel"
ARGOS_SHA256 = "591d743ae103752b88ffc38785c50421320f4eff93c8967e0d3d2e14d4e27811"
MAX_ARGOS_UNPACKED = 600 * 1024 * 1024      # zip-бомба: маленький архив не распакуется в гигабайты
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


# ---------------------------------------------------------------- телефон
# На Android и iPhone расшифровку и перевод делает расширение flet_radio (whisper.cpp + Google ML Kit):
# main.py передаёт сюда run(метод, **аргументы) — вызов сервиса RadioEngine из рабочего потока.
_phone = {"run": None}


def attach_phone_engine(run):
    _phone["run"] = run


def on_phone():
    return _phone["run"] is not None


def download_mb(model):
    """Сколько скачивать для модели model вместе с переводом (МБ)."""
    return WHISPER_MODELS[model][1] + TRANSLATION_MB["phone" if on_phone() else "computer"]


def supported():
    """Можно ли расшифровывать: на телефоне — есть расширение flet_radio, на компьютере — библиотеки."""
    from . import notify
    if notify.is_mobile():
        return on_phone()
    return not missing_libraries()


def missing_libraries():
    """Каких библиотек радио нет (пустой список — всё на месте). Нативная часть whisper.cpp не загрузится —
    ImportError или OSError (нет DLL в сборке)."""
    import importlib
    missing = []
    for name in ("pywhispercpp.model", "miniaudio", "ctranslate2", "sentencepiece"):
        try:
            importlib.import_module(name)
        except (ImportError, OSError) as exc:     # с причиной: «нет miniaudio» не говорит, чего не хватает
            missing.append(f"{name.split('.')[0]} ({type(exc).__name__}: {exc})")
    return missing


def _whisper_file(name):
    return models_dir() / f"ggml-{name}.bin"


def whisper_model():
    """Скачанная модель расшифровки (выбранная пользователем — в первую очередь) или None."""
    order = [db.get_setting("radio_model")] + list(WHISPER_MODELS)
    return next((n for n in order if n in WHISPER_MODELS and _whisper_file(n).exists()), None)


def _argos_ready():
    return (argos_dir() / "model" / "model.bin").exists() and (argos_dir() / "sentencepiece.model").exists()


def models_ready():
    if on_phone():
        return bool(whisper_model()) and db.get_setting("radio_translation") == "1"
    return bool(whisper_model()) and _argos_ready()


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
            if not _whisper_file(model).exists():
                _download_whisper(model)
            _remove_old_models()
            _download["progress"] = 0.5
            if on_phone():
                if not _phone["run"]("download_translation"):       # модели ML Kit en и ru
                    raise RuntimeError("модель перевода не скачалась")
                db.set_setting("radio_translation", "1")
            elif not _argos_ready():
                _download_argos()
            _download.update(state="done", progress=1.0)
        except Exception as exc:
            logger.warning("модели радио не скачались: %s", exc)
            _download.update(state="error", error=str(exc))
        if on_done:
            on_done()

    threading.Thread(target=job, name="f1-radio-models", daemon=True).start()


def _download_checked(url, part, sha256, limit, progress):
    """Скачать url в part, считая SHA-256 на лету. Не совпала сумма, больше limit или обрыв — part удаляется
    и бросается ошибка: на диске не остаётся ни обрывка, ни подменённого файла. progress(доля 0..1)."""
    digest, done = hashlib.sha256(), 0
    try:
        with requests.get(url, stream=True, timeout=TIMEOUT) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length") or 0)
            with open(part, "wb") as f:
                for chunk in resp.iter_content(1 << 20):
                    done += len(chunk)
                    if done > limit:
                        raise RuntimeError("файл больше ожидаемого — загрузка остановлена")
                    digest.update(chunk)
                    f.write(chunk)
                    if total:
                        progress(done / total)
        if digest.hexdigest() != sha256:
            raise RuntimeError("скачанный файл не совпал с ожидаемым (контрольная сумма) — повтори позже")
    except BaseException:
        part.unlink(missing_ok=True)
        raise


def _download_whisper(name):
    """Модель whisper.cpp с Hugging Face: проверка SHA-256, затем переименование — битая или подменённая
    модель не появится под рабочим именем."""
    target = _whisper_file(name)
    part = target.with_suffix(".part")
    _download_checked(WHISPER_URL.format(name), part, WHISPER_SHA256[name], MAX_WHISPER,
                      lambda share: _download.__setitem__("progress", 0.5 * share))
    os.replace(part, target)


def _remove_old_models():
    """Модели faster-whisper (до 2.7) занимают до 465 МБ и больше не используются."""
    for name in OLD_WHISPER_DIRS:
        shutil.rmtree(models_dir() / name, ignore_errors=True)


MAX_ARGOS = 400 * 1024 * 1024   # пакет en->ru — 196 МБ


def _download_argos():
    """Пакет Argos — zip с папкой model/ (CTranslate2) и sentencepiece.model. Распаковываем только их."""
    tmp = models_dir() / "argos.part"
    try:
        _download_checked(ARGOS_URL, tmp, ARGOS_SHA256, MAX_ARGOS,
                          lambda share: _download.__setitem__("progress", 0.5 + 0.5 * share))
        extract_argos(tmp)
    finally:
        tmp.unlink(missing_ok=True)


def extract_argos(package):
    """Распаковка во временную папку и замена прежней модели, только если в пакете есть обе части:
    сбой или неполный пакет не оставят «готовую» модель без токенизатора и не сотрут рабочую."""
    target = argos_dir()
    staging = target.with_name(target.name + ".new")
    shutil.rmtree(staging, ignore_errors=True)
    try:
        with zipfile.ZipFile(package) as z:
            unpacked = 0
            for info in z.infolist():
                parts = Path(info.filename).parts[1:]          # без корневой папки пакета
                if not parts or info.is_dir() or not (parts[0] == "model" or parts[0] == "sentencepiece.model"):
                    continue
                out = staging.joinpath(*parts)
                # «zip slip»: model/../../файл вывел бы запись за пределы папки модели — такие пути пропускаем
                if not out.resolve().is_relative_to(staging.resolve()):
                    continue
                unpacked += info.file_size
                if unpacked > MAX_ARGOS_UNPACKED:
                    raise RuntimeError("пакет перевода распаковывается в слишком большой объём")
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        if not ((staging / "model" / "model.bin").exists() and (staging / "sentencepiece.model").exists()):
            raise RuntimeError("в пакете перевода нет модели или токенизатора")
        shutil.rmtree(target, ignore_errors=True)
        os.replace(staging, target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _load_models():
    with _lock:
        name = whisper_model()
        if _models.get("whisper_name") != name:
            from pywhispercpp.model import Model
            # suppress_nst: без него на шуме мотора модель пишет «[Music]» вместо фразы;
            # no_context: каждая запись — отдельный разговор, прошлый текст не подсказывает следующий
            _models["whisper"] = Model(str(_whisper_file(name)), redirect_whispercpp_logs_to=None,
                                       n_threads=os.cpu_count() or 4, initial_prompt=F1_PROMPT, no_context=True,
                                       suppress_nst=True, print_progress=False, print_realtime=False)
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
    (r"козыр[её]к", "визор"),                      # «visor» — стекло шлема, не козырёк кепки
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


def decode_audio(data):
    """mp3/wav (байты) -> моно 16 кГц float32 — то, что ждёт Whisper. miniaudio вместо FFmpeg."""
    import miniaudio
    import numpy as np
    decoded = miniaudio.decode(data, output_format=miniaudio.SampleFormat.FLOAT32, nchannels=1, sample_rate=16000)
    return np.frombuffer(decoded.samples, dtype=np.float32)


def transcribe_audio(data):
    """Запись (байты mp3/wav) -> английский текст."""
    segments = _load_models()["whisper"].transcribe(decode_audio(data))
    return " ".join(s.text.strip() for s in segments).strip()


def _process_on_phone(data):
    """Телефон: запись — во временный файл, расшифровка и перевод — в расширении flet_radio."""
    tmp = models_dir() / f"radio-{threading.get_ident()}.mp3"
    tmp.write_bytes(data)
    try:
        en = _phone["run"]("transcribe", model_path=str(_whisper_file(whisper_model())), audio_path=str(tmp),
                           prompt=F1_PROMPT, threads=min(os.cpu_count() or 4, 4))
    finally:
        tmp.unlink(missing_ok=True)
    ru = _phone["run"]("translate", text=_plain_english(en)) if en else ""
    # ML Kit переводит текст целиком — правим термины по предложениям, как на компьютере
    return en, " ".join(_fix_russian(s) for s in split_sentences(ru))


def process(url):
    """Скачать запись, расшифровать, перевести. -> {"en", "ru"} (и в кэш)."""
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    if on_phone():
        en, ru = _process_on_phone(resp.content)
    else:
        en = transcribe_audio(resp.content)
        ru = translate(en) if en else ""
    result = {"en": en, "ru": ru, "at": time.time()}
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
