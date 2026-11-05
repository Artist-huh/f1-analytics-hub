import 'dart:io';

import 'package:flet/flet.dart';
import 'package:flutter/foundation.dart';
import 'package:google_mlkit_translation/google_mlkit_translation.dart';
import 'package:whisper_cpp_flutter_plus/whisper_cpp_flutter_plus.dart';

import 'decode.dart';

/// Радио команд на телефоне: расшифровка whisper.cpp (те же модель и настройки, что на компьютере)
/// и перевод en -> ru через Google ML Kit (офлайн, бесплатно). Жаргон F1 до и после перевода правит Python.
class RadioEngineService extends FletService {
  RadioEngineService({required super.control});

  WhisperEngine? _engine;
  String? _modelPath;
  OnDeviceTranslator? _translator;

  @override
  void init() {
    super.init();
    control.addInvokeMethodListener(_invokeMethod);
  }

  Future<dynamic> _invokeMethod(String name, dynamic args) async {
    final a = Map<String, dynamic>.from((args ?? {}) as Map);
    switch (name) {
      case "transcribe":
        return _transcribe(a["model_path"] as String, a["audio_path"] as String, a["prompt"] as String? ?? "",
            (a["threads"] as num?)?.toInt() ?? 4);
      case "decode_frames": // проверка декодера: сколько отсчётов 16 кГц в записи
        return (await decodeAudioFile(a["audio_path"] as String)).length;
      case "translate":
        return _translate(a["text"] as String);
      case "translation_ready":
        return OnDeviceTranslatorModelManager().isModelDownloaded(TranslateLanguage.russian.bcpCode);
      case "download_translation":
        final manager = OnDeviceTranslatorModelManager();
        final en = await manager.downloadModel(TranslateLanguage.english.bcpCode, isWifiRequired: false);
        final ru = await manager.downloadModel(TranslateLanguage.russian.bcpCode, isWifiRequired: false);
        return en && ru;
      case "info":
        return {"whisper": WhisperEngine.version, "system": WhisperEngine.systemInfo};
      default:
        throw Exception("Unknown RadioEngine method: $name");
    }
  }

  Future<String> _transcribe(String modelPath, String audioPath, String prompt, int threads) async {
    if (_engine == null || _modelPath != modelPath) {
      _engine?.dispose();
      _engine = await WhisperEngine.load(modelPath, config: _whisperConfig());
      _modelPath = modelPath;
    }
    final pcm = await decodeAudioFile(audioPath);
    final started = DateTime.now();
    // настройки — как в services/radio.py на компьютере: подсказка о жаргоне F1, каждая запись отдельно,
    // без пометок «[Music]» на шуме мотора
    final task = _engine!.transcribe(pcm,
        options: TranscribeOptions(
          language: "en",
          initialPrompt: prompt.isEmpty ? null : prompt,
          noContext: true,
          suppressNonSpeechTokens: true,
          threads: threads,
        ));
    final result = await task.result;
    debugPrint("RadioEngine: ${pcm.length / 16000} с звука за ${DateTime.now().difference(started).inMilliseconds} мс");
    return result.text.trim();
  }

  /// Симулятор iPhone: Metal там неполный, и whisper.cpp падал (SIGTRAP) в начале расшифровки —
  /// считаем на процессоре и без Core ML. На телефонах — автоматический выбор: Metal, иначе процессор.
  static WhisperConfig _whisperConfig() {
    final simulator = Platform.isIOS && Platform.environment.containsKey('SIMULATOR_DEVICE_NAME');
    if (simulator) {
      debugPrint("RadioEngine: симулятор iPhone — whisper.cpp на процессоре");
      return const WhisperConfig(backend: WhisperBackend.cpu, coreMlMode: WhisperCoreMlMode.disabled);
    }
    return const WhisperConfig();
  }

  Future<String> _translate(String text) async {
    _translator ??= OnDeviceTranslator(sourceLanguage: TranslateLanguage.english, targetLanguage: TranslateLanguage.russian);
    return _translator!.translateText(text);
  }

  @override
  void dispose() {
    control.removeInvokeMethodListener(_invokeMethod);
    _engine?.dispose();
    _translator?.close();
    super.dispose();
  }
}
