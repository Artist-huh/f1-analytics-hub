# F1 Analytics Hub

Статистика Формулы-1 на Python 3.11 + Flet 1.0.5: Windows, macOS, Android, iPhone. Интерфейс и тексты — по-русски.

## Команды

```bash
F1_HUB_LOG=off venv/Scripts/python.exe -m unittest discover -s tests -t .   # все тесты (~40 с)
venv/Scripts/ruff.exe check .                                               # линтер (настройки в pyproject.toml)
venv/Scripts/python.exe main.py                                             # приложение в окне
```

- `F1_HUB_LOG=off` обязателен для тестов: иначе журнал пишется в папку данных пользователя.
- Сборка `.exe` локально — `build.bat`, запускать из PowerShell: `& "$PWD\build.bat"`. Из Git Bash/cmd он
  ломается на кириллице в пути проекта.
- Сборки всех платформ и проверки их запуска — GitHub Actions `build.yml` (`gh workflow run build.yml -f version=vX.Y.Z`).
  Токен для `gh` берётся из менеджера учётных данных git (`git credential fill`), в чат не печатать.

## Правила работы

- После изменений: тесты и ruff, затем коммит и пуш в `main`. Хук `.claude/hooks/tests_before_commit.py`
  не даст закоммитить при красных тестах; `.claude/hooks/ruff_fix.py` чинит ruff после каждой правки `.py`.
- Только бесплатное: никаких платных API и ключей. Данные — Jolpica (Ergast), поток F1 live timing,
  OpenF1 (расписание, история), MultiViewer (контуры трасс); радио — офлайн-модели.
- Выпуск версии — скил `/release`; проверка экрана по картинке — скил `/shots`; ревью интерфейса — субагент `ui-reviewer`.
- Документация Flet: MCP-сервер context7 (`.mcp.json`) — API Flet 1.0 сильно отличается от 0.x.

## Устройство

- `main.py` — оболочка: навигация, смена экранов, «назад», тема, мини-окно.
- `design_system.py` — все цвета, шрифты, отступы, анимации и темы. Экраны берут токены через
  `from design_system import *`, поэтому после смены темы модули интерфейса перезагружаются (`ui/theming.py`).
- `ui/screens/` — экраны; `ui/components.py`, `ui/widgets.py`, `ui/rows.py` — общие элементы; `ui/state.py` — состояние.
- `services/` — данные: `f1_api` (кэш в SQLite), `f1live` (поток SignalR), `track_map`, `radio`, `notify`, `widget`.
- `packages/flet_home_widget/` — своё расширение Flet: виджет Android (Java).
- `tools/` — проверки запуска сборок в CI: `android_smoke.py` (эмулятор), `ios_smoke.py` (симулятор iPhone),
  `desktop_smoke.py` (`.exe` и `.app`).

## Подводные камни

- В тестах интерфейса (`tests/test_ui_*.py`, заглушка — `tests/ui_support.py`) Flet подменён заглушкой, которая принимает **любые** аргументы. Ошибку в имени
  параметра элемента (например, `radius=` у Container) поймает только `tests/test_real_flet.py` — он строит все
  экраны настоящим Flet в отдельном процессе.
- Перерисовка из фоновых потоков — только через `run_on_ui` / `page.run_task` (см. `main.py`): `page.update()`
  из потока во Flet 1.0 не будит цикл событий.
- Телефон или компьютер — `notify.is_mobile()` (Android и iPhone); `is_android()` — только для того, чего на
  iPhone нет (виджет, системные уведомления).
- Анимации — через `anim()` из `ui/components.py`: он учитывает «Меньше движения».
- Тест на эмуляторе Android (`tools/android_smoke.py`) ищет надписи на экране. Поменял заголовок или кнопку —
  проверь, не ждёт ли он старый текст.
- Тесты доступности (`tests/test_accessibility.py`) запрещают `#RRGGBB` в `ui/`, проверяют контраст
  во всех темах и единый стиль иконок `_ROUNDED`.
