"""Выравнивание нативных библиотек APK по 16 КБ (страницы памяти Android 15+ на новых телефонах).

    python tools/check_16k.py build/apk/app-arm64-v8a-release.apk [...]

Библиотека, у которой сегменты LOAD выровнены меньше чем на 16 КБ, на устройстве со страницами 16 КБ не
загрузится. Проверяются 64-битные ABI (arm64-v8a, x86_64): только там бывают такие страницы. Читаются ELF-заголовки
прямо из APK, без NDK. Код выхода 1 — есть невыровненные библиотеки (список печатается).
"""
import struct
import sys
import zipfile

PAGE = 16 * 1024
ABIS = ("arm64-v8a", "x86_64")


def load_alignments(data):
    """ELF64 -> выравнивание каждого сегмента PT_LOAD. Не ELF64 — пустой список."""
    if data[:4] != b"\x7fELF" or data[4] != 2:          # только 64-битные
        return []
    endian = "<" if data[5] == 1 else ">"
    phoff, = struct.unpack_from(endian + "Q", data, 0x20)
    phentsize, phnum = struct.unpack_from(endian + "HH", data, 0x36)
    out = []
    for i in range(phnum):
        p_type, = struct.unpack_from(endian + "I", data, phoff + i * phentsize)
        if p_type == 1:                                   # PT_LOAD
            p_align, = struct.unpack_from(endian + "Q", data, phoff + i * phentsize + 0x30)
            out.append(p_align)
    return out


def check(apk):
    bad, total = [], 0
    with zipfile.ZipFile(apk) as z:
        for name in z.namelist():
            if not (name.startswith("lib/") and name.endswith(".so") and name.split("/")[1] in ABIS):
                continue
            aligns = load_alignments(z.read(name))
            if not aligns:
                continue
            total += 1
            if min(aligns) < PAGE:
                bad.append(f"{name}: {min(aligns)} байт")
    return total, bad


def main(paths):
    failed = False
    for apk in paths:
        total, bad = check(apk)
        print(f"{apk}: библиотек {total}, без выравнивания 16 КБ — {len(bad)}")
        for line in bad:
            print("  " + line)
        failed |= bool(bad)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
