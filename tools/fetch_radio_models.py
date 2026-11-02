"""Скачать модели радио в папку данных — для проверки сборки в CI (desktop_smoke.py --radio).

    python tools/fetch_radio_models.py [модель]     # по умолчанию base.en-q5_1 (~60 МБ) — быстрее в CI

Те же функции, что у кнопки «Скачать» в приложении: модель whisper.cpp с Hugging Face и перевод Argos.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("F1_HUB_LOG", "off")

from services import db, radio


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "base.en-q5_1"
    radio.models_dir().mkdir(parents=True, exist_ok=True)
    if not radio._whisper_file(model).exists():
        radio._download_whisper(model)
    if not (radio.argos_dir() / "model" / "model.bin").exists():
        radio._download_argos()
    db.set_setting("radio_model", model)
    print(f"модели радио готовы: {radio._whisper_file(model)}, перевод {radio.argos_dir()}")
    return 0 if radio.models_ready() else 1


if __name__ == "__main__":
    sys.exit(main())
