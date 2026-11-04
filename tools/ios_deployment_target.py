"""Поднять минимальную версию iOS в проекте Flutter, который создаёт flet build (CI, macOS).

    python3 tools/ios_deployment_target.py 15.5

Шаблон сборки Flet 1.0.5 вшивает iOS 13.0 (Podfile и проект Xcode), а настройки в pyproject.toml для этого нет.
Расширению радио (packages/flet_radio) нужны whisper_cpp_flutter_plus (iOS 14) и Google ML Kit (iOS 15.5),
поэтому pod install на 13.0 падает. Порядок в CI: flet build (создаёт build/flutter и падает на pod install) ->
этот скрипт -> flet build ещё раз: проект перегенерируется только при смене данных шаблона, правка остаётся.
"""
import re
import sys
from pathlib import Path

IOS = Path("build/flutter/ios")


MLKIT_REQUIRE = ("require File.expand_path('.symlinks/plugins/google_mlkit_commons/ios/scripts/"
                 "apple_silicon_simulator', __dir__)\n")
MLKIT_CALL = "  mlkit_apple_silicon_simulator_patch(installer)\n"


def mlkit_simulator_patch(text):
    """У Google ML Kit нет arm64 для симулятора, а раннеры macOS — Apple Silicon: Xcode падал с
    «Framework 'Pods_Runner' not found». google_mlkit_commons ≥ 0.12 даёт помощник для Podfile
    (подключается вручную): require в начале и вызов в post_install. Повторный запуск ничего не дублирует."""
    if "mlkit_apple_silicon_simulator_patch" in text:
        return text
    text, n = re.subn(r"^(require File\.expand_path\(.*podhelper.*\n)", r"\1" + MLKIT_REQUIRE.replace("\\", r"\\"),
                      text, count=1, flags=re.M)
    if not n:
        text = MLKIT_REQUIRE + text
    # в конце блока post_install (после настроек Flutter), перед его закрывающим end в начале строки
    text, n = re.subn(r"^(post_install do \|installer\|\n(?:.*\n)*?)(end\b)", r"\1" + MLKIT_CALL + r"\2", text,
                      count=1, flags=re.M)
    if not n:
        text += "\npost_install do |installer|\n" + MLKIT_CALL + "end\n"
    return text


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "15.5"
    podfile, project = IOS / "Podfile", IOS / "Runner.xcodeproj" / "project.pbxproj"
    if not podfile.exists() or not project.exists():
        print(f"нет {podfile} или {project} — сначала flet build должен создать проект")
        return 1
    text = podfile.read_text(encoding="utf-8")
    text, n_pod = re.subn(r"^#?\s*platform :ios, '[\d.]+'", f"platform :ios, '{version}'", text, flags=re.M)
    text = mlkit_simulator_patch(text)
    podfile.write_text(text, encoding="utf-8")
    text = project.read_text(encoding="utf-8")
    text, n_proj = re.subn(r"IPHONEOS_DEPLOYMENT_TARGET = [\d.]+;", f"IPHONEOS_DEPLOYMENT_TARGET = {version};", text)
    project.write_text(text, encoding="utf-8")
    print(f"iOS {version}: Podfile — {n_pod}, проект Xcode — {n_proj} мест")
    return 0 if n_pod and n_proj else 1


if __name__ == "__main__":
    sys.exit(main())
