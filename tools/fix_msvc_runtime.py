"""Перед сборкой .exe: заменить устаревшую msvcp140.dll из пакета winrt системной (Windows).

    python tools/fix_msvc_runtime.py

winrt (системные уведомления, через desktop-notifier) приносит свою msvcp140.dll версии 14.29, а sentencepiece
(перевод радио) и другие библиотеки собраны Visual Studio 2022 17.10+ и требуют 14.40 и новее. Если первой
загрузится старая копия, процесс падает с ошибкой сегментации: так падал упаковщик (PyInstaller) и могло
падать приложение при первом переводе. Новая msvcp140 совместима со старым кодом, поэтому копия winrt
заменяется системной (C:\\Windows\\System32), если та новее. Прежняя сохраняется рядом как .dll.old.
"""
import os
import shutil
import sys
import sysconfig


def file_version(path):
    """Версия DLL (14, 44, 35211, 0) из ресурсов Windows или None."""
    import ctypes
    from ctypes import wintypes
    size = ctypes.windll.version.GetFileVersionInfoSizeW(path, None)
    if not size:
        return None
    buf = ctypes.create_string_buffer(size)
    if not ctypes.windll.version.GetFileVersionInfoW(path, 0, size, buf):
        return None
    info, length = ctypes.c_void_p(), wintypes.UINT()
    if not ctypes.windll.version.VerQueryValueW(buf, "\\", ctypes.byref(info), ctypes.byref(length)):
        return None
    ms, ls = ctypes.cast(info, ctypes.POINTER(wintypes.DWORD))[2:4]
    return ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF


def main():
    if sys.platform != "win32":
        return 0
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # консоль Windows в CI — cp1252, без кириллицы
    bundled = os.path.join(sysconfig.get_paths()["purelib"], "winrt", "msvcp140.dll")
    system = os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"), "System32", "msvcp140.dll")
    if not os.path.exists(bundled):
        print("msvcp140: winrt без своей копии — менять нечего")
        return 0
    old, new = file_version(bundled), file_version(system)
    if not new or not old or new <= old:
        print(f"msvcp140: winrt {old}, система {new} — оставляем как есть")
        return 0
    shutil.copyfile(bundled, bundled + ".old")
    shutil.copyfile(system, bundled)
    print(f"msvcp140: winrt {'.'.join(map(str, old))} заменена системной {'.'.join(map(str, new))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
