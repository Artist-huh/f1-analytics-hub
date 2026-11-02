// Декодирование записи радио (mp3/wav/flac) в моно 16 кГц float32 — формат, который ждёт Whisper.
// miniaudio (src/miniaudio.h, общественное достояние / MIT-0) — тот же декодер, что в версии для компьютера
// (пакет miniaudio), поэтому звук на входе Whisper одинаковый везде. Один код для Android и iPhone.
#define MINIAUDIO_IMPLEMENTATION
#define MA_NO_DEVICE_IO
#define MA_NO_ENCODING
#define MA_NO_GENERATION
#define MA_NO_RESOURCE_MANAGER
#define MA_NO_NODE_GRAPH
#define MA_NO_ENGINE
#include "miniaudio.h"

#include <stdint.h>

#if defined(_WIN32)
#define F1_EXPORT __declspec(dllexport)
#else
#define F1_EXPORT __attribute__((visibility("default"))) __attribute__((used))
#endif

// Файл -> буфер float32 (моно, 16 кГц). Число отсчётов — в *frames; NULL и 0 — не получилось.
// Буфер освобождается f1_radio_free.
F1_EXPORT float *f1_radio_decode(const char *path, int64_t *frames) {
    ma_decoder_config config = ma_decoder_config_init(ma_format_f32, 1, 16000);
    ma_uint64 count = 0;
    void *pcm = NULL;
    if (ma_decode_file(path, &config, &count, &pcm) != MA_SUCCESS || pcm == NULL) {
        *frames = 0;
        return NULL;
    }
    *frames = (int64_t)count;
    return (float *)pcm;
}

F1_EXPORT void f1_radio_free(void *pcm) {
    ma_free(pcm, NULL);
}
