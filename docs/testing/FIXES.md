# Исправления

Каждое исправление закреплено тестом, который падает без него (проверено для BUG-1 и BUG-3 откатом
исправления), а весь набор тестов и `ruff` после коммита зелёные.

| Коммит | Проблемы | Что сделано | Тест |
|---|---|---|---|
| `e1f5dbc` | STRESS-1 | Переключение избранного атомарно: сначала DELETE, потом INSERT | `test_favorite_toggles_from_many_threads` |
| `f36da05` | SEC-1/2 | Модели радио — закреплённая версия, SHA-256, `.part` удаляется при любом сбое, распаковка во временную папку с пределом размера | `ModelDownloadTest` |
| `ee6b35d` | BUG-3, BUG-4, BUG-5 | Оставшиеся этапы — от этапа зачёта; условия титула против каждого соперника; флаг — по смене, id по времени появления | `test_season_left_counts_from_standings_round`, `test_title_terms_against_every_rival`, `test_live_flags` |
| `9f2bcd5` | BUG-1, BUG-2 | Прогнозы — под сезоном календаря; последняя гонка — по сезону и этапу; результаты, квалификации и спринты — только сезона зачёта | `test_prediction_reminder_uses_calendar_season`, `test_season_rollover_keeps_one_season` |
| `31db1d0` | UX-1, UX-2 | Токены `GOLD_ON_COLOR` и `HERO_END` не зависят от темы; незнакомая команда — карбон | `test_team_cards_readable_in_every_theme` |
| `abd1a07` | XP-6, XP-7, CI-1, сбой CI Windows | ML Kit 0.15.1 и патч Podfile для arm64-симулятора; podspec 15.5; `TAG` через окружение; `PYTHONUTF8` | `test_ios_podfile_gets_mlkit_simulator_patch`, прогон CI |
| `f218d3e` | SEC-3…SEC-7 | `services/net.py`: чтение с пределом и проверка хоста; предел распаковки и сообщений; очистка отчёта; журнал без подделки строк; `ro.debuggable` | `LimitsTest`, `LogFormatTest`, `test_problem_report` |
| `946201c` | SEC-8 | Декодер C читает частями не дальше 5 минут (проверен `gcc` на 3 с и 400 с); `free` в `finally`; тот же предел на компьютере | `AudioLimitTest` |
| `c7e0101` | XP-1, XP-4, XP-11, XP-14 | Текст для iPhone; Cmd+M/H на Mac — системные; запертый файл базы; `tools` исключён из пакета | `test_hotkeys` |
| `04fb640` | XP-3 | На телефоне модели и картинки — в `FLET_APP_STORAGE_CACHE`, скачанное переносится | `PhoneStorageTest` |
| `70e2d48` | UX-5, UX-6, UX-7, UX-11, UX-12, UX-15, UX-19 | Тексты и кнопки повтора; индикатор первой загрузки; «назад» в знакомстве | `test_every_screen_renders_with_empty_db`, `test_first_run_onboarding` |
| `9d3606b` | BUG-6, BUG-7 | Виджет без данных; дробные очки; W/D; максимум прогноза; «досрочно» | `test_widget_data`, `test_small_texts`, `test_predictions` |
