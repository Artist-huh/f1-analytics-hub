# Инструменты тестирования

| Инструмент | Что проверяет | Запуск |
|---|---|---|
| `unittest` (193 теста) | Данные, логика, экраны на заглушке Flet, доступность, записанные ответы API, фаззинг разбора | `F1_HUB_LOG=off venv/Scripts/python.exe -m unittest discover -s tests -t .` |
| `tests/test_real_flet.py` | Все экраны строятся настоящим Flet (ловит неверные имена параметров, которые заглушка принимает) | входит в набор |
| `tests/test_accessibility.py` | Контраст WCAG во всех темах, нет `#RRGGBB` в `ui/`, единый стиль иконок | входит в набор |
| `ruff` | Стиль и типичные ошибки Python | `venv/Scripts/ruff.exe check .` |
| `/shots` (`.claude/skills/shots`) | Снимок окна любого экрана в нужной теме, размере и шрифте | `sh .claude/skills/shots/scripts/shoot.sh <папка> <имя> <экран>` |
| `tools/visual_check.py` + `visual.yml` | Сравнение снимков с эталонами на раннере Windows | GitHub Actions |
| `tools/desktop_smoke.py` | Запуск `.exe` и `.app`, самопроверка радио на синтезированной речи | `build.yml` |
| `tools/android_smoke.py` | Эмулятор Android 14: экраны, вкладки, «назад», уведомление, радио | `build.yml`, job `test-android` |
| `tools/ios_smoke.py` | Симулятор iPhone: запуск и радио | `build.yml`, job `test-ios` |
| `tools/check_16k.py` | Выравнивание нативных библиотек APK по 16 КБ (Android 15+), по ELF-заголовкам | `build.yml`, отчётом |
| `tools/check_sources.py` + `sources.yml` | Источники данных живы и отвечают в ожидаемом формате | ежедневно |
| `tools/record_fixtures.py` | Запись настоящих ответов API для `test_recorded.py` | вручную |
| Хуки `.claude/hooks/` | Не дают закоммитить при красных тестах; чинят `ruff` после правки | автоматически |

Чего нет и почему:

- **Браузерных тестов (Playwright, Selenium)** — нет веб-сборки.
- **Тестов на физических устройствах** — нет устройств; эмулятор и симулятор их не заменяют.
- **Нагрузочных инструментов (k6, Locust)** — нет сервера; нагрузка на чужие API запрещена правилами аудита.
