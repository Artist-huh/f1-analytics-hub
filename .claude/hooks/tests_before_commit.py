"""PreToolUse (Bash: git commit): весь набор тестов перед коммитом; красные тесты — коммит блокируется (код 2)."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    env = dict(os.environ, F1_HUB_LOG="off", PYTHONIOENCODING="utf-8")
    res = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=ROOT,
                         env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode:
        tail = "\n".join(ln for ln in res.stderr.splitlines()
                         if ln.startswith(("FAIL:", "ERROR:", "AssertionError", "Ran ", "FAILED")))
        msg = "Коммит остановлен: тесты не прошли.\n" + (tail or res.stderr[-2000:]) + "\n"
        sys.stderr.buffer.write(msg.encode("utf-8"))   # не кодировка консоли Windows — кириллица дойдёт целой
        sys.exit(2)


if __name__ == "__main__":
    main()
