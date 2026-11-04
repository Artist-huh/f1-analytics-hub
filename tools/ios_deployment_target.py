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


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "15.5"
    podfile, project = IOS / "Podfile", IOS / "Runner.xcodeproj" / "project.pbxproj"
    if not podfile.exists() or not project.exists():
        print(f"нет {podfile} или {project} — сначала flet build должен создать проект")
        return 1
    text = podfile.read_text(encoding="utf-8")
    text, n_pod = re.subn(r"^#?\s*platform :ios, '[\d.]+'", f"platform :ios, '{version}'", text, flags=re.M)
    podfile.write_text(text, encoding="utf-8")
    text = project.read_text(encoding="utf-8")
    text, n_proj = re.subn(r"IPHONEOS_DEPLOYMENT_TARGET = [\d.]+;", f"IPHONEOS_DEPLOYMENT_TARGET = {version};", text)
    project.write_text(text, encoding="utf-8")
    print(f"iOS {version}: Podfile — {n_pod}, проект Xcode — {n_proj} мест")
    return 0 if n_pod and n_proj else 1


if __name__ == "__main__":
    sys.exit(main())
