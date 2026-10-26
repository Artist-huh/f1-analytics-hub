"""PostToolUse (Edit|Write): ruff check --fix для изменённого .py-файла проекта.

Что ruff не смог исправить сам, возвращается Claude как контекст — он поправит сразу, а не при коммите.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUFF = os.path.join(ROOT, "venv", *(("Scripts", "ruff.exe") if os.name == "nt" else ("bin", "ruff")))


def main():
    data = json.loads(sys.stdin.buffer.read().decode("utf-8"))   # Claude Code шлёт UTF-8 (кириллица в пути)
    path = (data.get("tool_input") or {}).get("file_path") or ""
    if not path.endswith(".py") or not os.path.isfile(path):
        return
    if not os.path.abspath(path).startswith(ROOT):          # файлы вне проекта не трогаем
        return
    ruff = RUFF if os.path.exists(RUFF) else "ruff"
    res = subprocess.run([ruff, "check", "--fix", "--quiet", path], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    if res.returncode:   # json.dumps экранирует кириллицу в ASCII — дойдёт при любой кодировке консоли
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"ruff нашёл ошибки, которые не исправил сам, в {os.path.basename(path)}:\n"
                                 + (res.stdout or res.stderr)[-2000:]}}))


if __name__ == "__main__":
    main()
