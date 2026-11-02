import 'dart:ffi';
import 'dart:io';
import 'dart:isolate';
import 'dart:typed_data';

import 'package:ffi/ffi.dart';

/// Декодер записи радио (src/radio_decode.c, miniaudio): файл mp3/wav -> моно 16 кГц float32 для Whisper.

typedef _DecodeC = Pointer<Float> Function(Pointer<Utf8> path, Pointer<Int64> frames);
typedef _Decode = Pointer<Float> Function(Pointer<Utf8> path, Pointer<Int64> frames);
typedef _FreeC = Void Function(Pointer<Void> pcm);
typedef _Free = void Function(Pointer<Void> pcm);

DynamicLibrary _open() {
  if (Platform.isAndroid) return DynamicLibrary.open('libflet_radio.so');
  if (Platform.isIOS) {
    // CocoaPods собирает пакет либо отдельным framework (use_frameworks!), либо прямо в приложение
    try {
      return DynamicLibrary.open('flet_radio.framework/flet_radio');
    } on ArgumentError {
      return DynamicLibrary.process();
    }
  }
  throw UnsupportedError('декодер радио есть только на Android и iPhone');
}

Float32List _decodeSync(String path) {
  final lib = _open();
  final decode = lib.lookupFunction<_DecodeC, _Decode>('f1_radio_decode');
  final free = lib.lookupFunction<_FreeC, _Free>('f1_radio_free');
  final cPath = path.toNativeUtf8();
  final frames = calloc<Int64>();
  try {
    final pcm = decode(cPath, frames);
    if (pcm == nullptr || frames.value == 0) {
      throw StateError('запись не декодирована: $path');
    }
    final copy = Float32List.fromList(pcm.asTypedList(frames.value));
    free(pcm.cast());
    return copy;
  } finally {
    calloc.free(cPath);
    calloc.free(frames);
  }
}

/// Декодирование в отдельном изоляте: длинная запись не подвешивает интерфейс.
Future<Float32List> decodeAudioFile(String path) => Isolate.run(() => _decodeSync(path));
