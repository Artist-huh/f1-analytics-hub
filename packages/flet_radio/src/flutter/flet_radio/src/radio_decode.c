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

// Запись радио — секунды; читаем не больше 5 минут (19 МБ отсчётов). Раньше файл разворачивался целиком:
// длинный mp3 с низким битрейтом занимал сотни мегабайт памяти телефона (аудит, SEC-8).
#define F1_RATE 16000
#define F1_MAX_FRAMES ((ma_uint64)F1_RATE * 60 * 5)

// Файл -> буфер float32 (моно, 16 кГц). Число отсчётов — в *frames; NULL и 0 — не получилось.
// Буфер освобождается f1_radio_free.
F1_EXPORT float *f1_radio_decode(const char *path, int64_t *frames) {
    *frames = 0;
    ma_decoder_config config = ma_decoder_config_init(ma_format_f32, 1, F1_RATE);
    ma_decoder decoder;
    if (ma_decoder_init_file(path, &config, &decoder) != MA_SUCCESS) {
        return NULL;
    }
    float *pcm = NULL;
    ma_uint64 cap = 0, count = 0;
    for (;;) {
        if (count == cap) {
            if (cap >= F1_MAX_FRAMES) {
                break;                                  // дальше 5 минут не читаем
            }
            ma_uint64 next = cap ? cap * 2 : (ma_uint64)F1_RATE * 30;
            if (next > F1_MAX_FRAMES) {
                next = F1_MAX_FRAMES;
            }
            float *grown = (float *)ma_realloc(pcm, (size_t)next * sizeof(float), NULL);
            if (grown == NULL) {
                ma_free(pcm, NULL);
                ma_decoder_uninit(&decoder);
                return NULL;
            }
            pcm = grown;
            cap = next;
        }
        ma_uint64 read = 0;
        ma_result result = ma_decoder_read_pcm_frames(&decoder, pcm + count, cap - count, &read);
        count += read;
        if (result != MA_SUCCESS || read == 0) {
            break;                                      // конец файла (MA_AT_END) или ошибка
        }
    }
    ma_decoder_uninit(&decoder);
    if (count == 0) {
        ma_free(pcm, NULL);
        return NULL;
    }
    *frames = (int64_t)count;
    return pcm;
}

F1_EXPORT void f1_radio_free(void *pcm) {
    ma_free(pcm, NULL);
}
