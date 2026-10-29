"""Сравнение снимков экранов с эталоном — ловит вёрстку, которую тесты на заглушке не видят
(наезд фото на текст, обрезанные подписи, сбитые цвета темы).

    python tools/visual_check.py <папка для снимков> [--golden tests/visual/ci-windows] [--update]

Снимает экраны скриптом /shots в режиме FROZEN=1 (данные — data/seed.json, без сети, часы стоят), поэтому
снимок одинаков при каждом запуске. Сравнивает с эталоном: пиксель «другой», если канал отличается больше
чем на PIXEL; экран «изменился», если таких пикселей больше SHARE. Для изменившихся пишет картинку
<имя>-diff.png (отличия — красным).

Эталоны зависят от системы и масштаба экрана, поэтому они свои для машины GitHub (tests/visual/ci-windows,
их снимает visual.yml). Нет эталона — снимок сохраняется как новый, проверка не падает. --update —
перезаписать эталоны (после намеренной правки дизайна).
Только Windows: нужны venv проекта, PowerShell и Git Bash (как у /shots).
"""
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOOT = os.path.join(ROOT, ".claude", "skills", "shots", "scripts", "shoot.sh")
PIXEL = 48          # из 255: меньше — сглаживание шрифтов, не изменение
SHARE = 0.005       # 0,5 % пикселей экрана

# имя снимка -> (экран, переменные окружения)
SCREENS = {
    "home": ("tab0", {}),
    "season": ("tab1", {}),
    "calendar": ("tab2", {}),
    "drivers": ("tab3", {}),
    "driver": ("sub:driver_detail", {}),
    "driver-light-xl": ("sub:driver_detail", {"THEME": "light", "FONT": "1.3"}),
    "home-light": ("tab0", {"THEME": "light"}),
}


def shoot(out, name, shot, env):
    full = dict(os.environ, FROZEN="1", **env)
    subprocess.run(["bash", SHOOT, out, name, shot], env=full, check=False, timeout=120)
    path = os.path.join(out, f"{name}.png")
    if not os.path.exists(path):
        raise RuntimeError(f"{name}: снимок не получен, см. {name}.log")
    return path


def compare(shot, golden):
    """-> доля разных пикселей и картинка отличий (или None, если размеры разные)."""
    a, b = Image.open(shot).convert("RGB"), Image.open(golden).convert("RGB")
    if a.size != b.size:
        return 1.0, None
    mask = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > PIXEL else 0)
    share = mask.histogram()[255] / (a.size[0] * a.size[1])
    diff = Image.blend(a, Image.new("RGB", a.size, (255, 255, 255)), 0.6)
    diff.paste((230, 0, 0), mask=mask)
    return share, diff


def main(argv):
    out = argv[0]
    golden_dir = os.path.join(ROOT, "tests", "visual", "ci-windows")
    if "--golden" in argv:
        golden_dir = argv[argv.index("--golden") + 1]
    update = "--update" in argv
    os.makedirs(out, exist_ok=True)
    changed, new = [], []
    for name, (shot, env) in SCREENS.items():
        path = shoot(out, name, shot, env)
        golden = os.path.join(golden_dir, f"{name}.png")
        if update or not os.path.exists(golden):
            os.makedirs(golden_dir, exist_ok=True)
            shutil.copyfile(path, golden if update else os.path.join(out, f"{name}-new-golden.png"))
            new.append(name)
            print(f"эталон  {name}: {'перезаписан' if update else 'нет — снимок сохранён как новый'}")
            continue
        share, diff = compare(path, golden)
        if share > SHARE:
            changed.append(name)
            if diff is not None:
                diff.save(os.path.join(out, f"{name}-diff.png"))
            print(f"ИЗМЕНЁН {name}: {share:.2%} пикселей" + ("" if diff else " (другой размер)"))
            print(f"::error title=Снимок {name}::экран изменился на {share:.2%}; см. {name}-diff.png в артефакте")
        else:
            print(f"ok      {name}: {share:.3%}")
    if changed:
        print("\nЕсли изменение намеренное — обновите эталоны: запустите visual.yml с update=true "
              "и закоммитьте снимки из артефакта в tests/visual/ci-windows.")
        return 1
    if new and not update:
        print(f"\n::warning title=Эталоны::нет эталонов для {', '.join(new)} — снимки в артефакте (*-new-golden.png)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
