# Регрессия

## Порядок

После каждого исправления:

1. весь набор: `F1_HUB_LOG=off venv/Scripts/python.exe -m unittest discover -s tests -t .`;
2. `venv/Scripts/ruff.exe check .`;
3. коммит (хук не даст закоммитить при красных тестах) и пуш в `main`;
4. для изменений интерфейса — снимки `/shots` в тёмной и светлой теме;
5. для изменений сборки, нативного кода и зависимостей — `build.yml` в GitHub Actions.

## Итог

| Прогон | Тестов | Результат |
|---|---|---|
| До аудита (`f36da05`) | 173 | OK |
| После последнего исправления (`1988be0`) | 193 | OK, 35–100 с (зависит от загрузки машины) |
| `ruff check .` | — | чисто |

Ни один тест не удалён и не отключён. Изменены ожидания в трёх местах, и каждое изменение отражает исправленное
поведение, а не подгонку:

- `test_live_flags`: id флага теперь — время появления, а не номер круга (BUG-5);
- подставной календарь в `tests/ui_support.py` получил этап зачёта, совпадающий с ним (раньше зачёт фикстур
  был посчитан по более позднему этапу, чем есть в календаре, — после BUG-3 это стало видно);
- заглушки ответов умеют потоковое чтение (`iter_content`), а адрес запасного фото в тесте — с `formula1.com`
  (после SEC-3 и SEC-6).

## Новые тесты

| Тест | Закрепляет |
|---|---|
| `test_season_left_counts_from_standings_round` | BUG-3 |
| `test_title_terms_against_every_rival` | BUG-4 |
| `test_live_flags` (расширен) | BUG-5 |
| `test_prediction_reminder_uses_calendar_season` | BUG-1 (падает без исправления — проверено) |
| `test_season_rollover_keeps_one_season` | BUG-2 |
| `test_team_cards_readable_in_every_theme` | UX-1, UX-2 |
| `test_ios_podfile_gets_mlkit_simulator_patch` | XP-6 |
| `LimitsTest` (3 теста) | SEC-3, SEC-6 |
| `LogFormatTest` | SEC-5 |
| `test_problem_report` (расширен) | SEC-4, SEC-5, SEC-9 |
| `AudioLimitTest` | SEC-8 |
| `PhoneStorageTest` | XP-3 |
| `test_hotkeys` (расширен) | XP-4 |
| `test_every_screen_renders_with_empty_db` (расширен) | UX-7 |
| `test_first_run_onboarding` (расширен) | UX-19 |
| `test_small_texts`, `test_widget_data`, `test_predictions` (расширены) | BUG-6, BUG-7 |
| `test_line_chart` (расширен) | UX-10 |
| `test_elevated_chips_and_field_border`, `test_api_colors_checked` | UX-8, UX-9, UX-30 |
| `test_phone_radio_off_when_extension_silent` | XP-5 |
| `test_results_checked_often_after_qualifying` | S-4 |
| `test_favorite_removal_can_be_undone` | UX-23 |
| `test_elf_alignment_read_from_apk` | XP-8 |
| `test_request_after_worker_decided_to_exit` | S-2 |
