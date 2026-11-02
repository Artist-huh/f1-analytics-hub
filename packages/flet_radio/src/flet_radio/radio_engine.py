import flet as ft


@ft.control("RadioEngine")
class RadioEngine(ft.Service):
    """Сервис радио на телефоне (Dart: lib/src/radio_engine.dart).

    Расшифровка — whisper.cpp с теми же моделью и настройками, что на компьютере; запись декодирует
    miniaudio (src/radio_decode.c). Перевод en -> ru — Google ML Kit на устройстве.
    """

    async def transcribe(self, model_path: str, audio_path: str, prompt: str = "", threads: int = 4,
                         timeout: float = 600) -> str:
        """Запись (файл mp3/wav) -> английский текст. Модель ggml — файл на устройстве."""
        return await self._invoke_method(
            method_name="transcribe",
            arguments={"model_path": model_path, "audio_path": audio_path, "prompt": prompt, "threads": threads},
            timeout=timeout,
        )

    async def decode_frames(self, audio_path: str) -> int:
        """Сколько отсчётов 16 кГц в записи (проверка декодера)."""
        return await self._invoke_method(method_name="decode_frames", arguments={"audio_path": audio_path},
                                         timeout=60)

    async def translate(self, text: str) -> str:
        return await self._invoke_method(method_name="translate", arguments={"text": text}, timeout=120)

    async def translation_ready(self) -> bool:
        return await self._invoke_method(method_name="translation_ready", timeout=30)

    async def download_translation(self) -> bool:
        """Скачать модели перевода ML Kit (en и ru, ~30 МБ каждая) — один раз."""
        return await self._invoke_method(method_name="download_translation", timeout=900)

    async def info(self) -> dict:
        return await self._invoke_method(method_name="info", timeout=30)
