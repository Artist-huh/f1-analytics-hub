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
| `e19eeb8` | SEC-9 | Путь `_MEIPASS` в отчёте заменяется на `<приложение>` | `test_problem_report` |
| `dd55ad3` | XP-15, XP-16 | QUICKSTART: закреплённые версии, Linux не обещан, как открыть приложение на macOS | — (документация) |
| `80dcd35`, `5252ce1`, `ef18b08` | Самопроверка радио в CI | Журнал по шагам; на Android — признаки эмулятора вместо одного `ro.debuggable`; на iPhone — расшифровка отдельно от перевода, сбор отчётов о падении | прогон CI `41981171788`: Android — Passed |
| `9057d4d` | UX-10, UX-16 | Графики на canvas описаны словами для диктора; подписи меню уже 400 px — оставлены по замыслу (проверено снимком) | `test_line_chart` |
| `4f6b93a` | XP-2, XP-9, XP-10, S-1 | Монохромный значок уведомления; точный будильник, где разрешено; перерисовка виджета в момент старта; 2000 id отправленных уведомлений | сборка APK в CI |
| `fc34fd1` | UX-8, UX-9 | DANGER ≥ 4.5:1 на SURFACE_ELEVATED; рамки полей ввода ≥ 3:1 | `test_elevated_chips_and_field_border` |
| `9415568` | UX-13, UX-24, UX-27, UX-28, UX-29 | Пометка о Монако в «Стратегии»; имена переключателей для диктора; выключенные стрелки «Истории»; «Отчёт скопирован» после копирования; тексты | `test_race_strategy`, полный набор |
| `39cdcbe`, `1988be0` | XP-5, UX-25 | Радио на телефоне проверяется ответом info() (до 300 с, самопроверка — после); аватары с откликом и подсказкой | `test_phone_radio_off_when_extension_silent` |
| `38b4792` | S-4 | В течение 12 ч после квалификации, спринта или гонки результаты — раз в 30 минут | `test_results_checked_often_after_qualifying` |
| `7814df2` | UX-31, UX-32, UX-33 | Подписи графиков и Live через scaled(); единые переключатели; кнопки мини-окна 48 dp | полный набор, снимок |
| `042dac3` | UX-26 | Пустые экраны со следующим шагом | `test_every_screen_renders_with_empty_db` |
| `ae91307` | UX-23 | «Вернуть» после удаления из избранного | `test_favorite_removal_can_be_undone` |
| `989b939` | UX-14, UX-21 | Заголовки Live над колонками; переключатель отрыва отдельной строкой | `test_live_timing`, снимок |
| `43e1c86` | UX-30, UX-32, UX-34 | api_color() для цветов из ответов; SectionHeader у «Мои прогнозы»; одна кнопка в герое | `test_api_colors_checked` |
| `40b50ee` | XP-8, XP-12 | tools/check_16k.py в CI; запуск .exe из папки «Тест Пользователь» | `test_elf_alignment_read_from_apk`, прогон CI |
| `b62fd85` | S-3 | setOnlyAlertOnce у будильника и уведомлений из приложения | сборка APK в CI |
| `b5f6cbe` | S-2 | Поток расшифровки сбрасывает себя под замком; ошибка on_done не останавливает очередь | `test_request_after_worker_decided_to_exit` |
| `c5de7a7` | UX-22 | «Лидер» и «быстрее всех» — золото, время главной сессии — жирным; полоска заголовков оставлена | снимок «Чемпионат» |
| `e3dea73` | — | Эталоны снимков visual.yml обновлены после намеренных правок дизайна | прогон visual.yml с update |
