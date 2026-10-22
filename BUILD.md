# F1 Analytics Hub — сборка Windows .exe

## Быстро

```bat
build.bat
```

Скрипт без вопросов выполняет четыре шага:

1. ставит зависимости из `requirements.txt` и PyInstaller (в `venv`, если он есть);
2. запускает автотесты — при падении сборка останавливается;
3. обновляет начальный снимок данных `data/seed.json` (нужен интернет; без сети остаётся прежний снимок);
4. собирает `dist\F1AnalyticsHub.exe` через `flet pack`.

Результат — один файл ~60 МБ. Python на целевом компьютере не нужен.

## Как устроена сборка

`flet pack` — это PyInstaller плюс клиент Flet (окно на Flutter), упакованный внутрь .exe.
Вручную то же самое:

```bat
venv\Scripts\flet.exe pack main.py -y --name F1AnalyticsHub --icon assets\icon.ico ^
    --add-data "assets;assets" "data;data" ^
    --product-name "F1 Analytics Hub" --product-version "1.0.0" --file-version "1.0.0.0"
```

- `assets/` — шрифт заголовков (работает без сети) и иконка;
- `data/seed.json` — снимок данных: при первом запуске без интернета приложение сразу показывает таблицы;
- ручной `.spec` не нужен: `flet pack` генерирует его сам, а клиент Flet кладёт в архив, который .exe распаковывает при первом запуске в `%USERPROFILE%\.flet\client`.

Почему не PyInstaller со своим `.spec`: без шага `flet pack` клиент Flet не попадает в нужный архив,
и .exe на чистом компьютере пытается скачать его из интернета.

`flet build windows` тоже работает, но требует Flutter SDK и Visual Studio с C++ — для одного .exe это лишнее.

## Где приложение хранит данные

- База и журнал: `%USERPROFILE%\.ferrari_leclerc_hub\` (`f1_hub.db`, `f1_hub.log`).
- Клиент Flet: `%USERPROFILE%\.flet\client\`.

## Проверка сборки

```bat
dist\F1AnalyticsHub.exe
```

Окно открывается за несколько секунд (при первом запуске клиент распаковывается). Если окна нет —
смотрите `%USERPROFILE%\.ferrari_leclerc_hub\f1_hub.log`. Для отладки можно собрать вариант с консолью:
добавьте к `flet pack` параметр `--debug-console true`.

Известное ограничение Windows: путь к профилю пользователя не должен быть очень длинным (>~120 символов) —
иначе распаковка клиента упирается в лимит путей 260 символов.

## CI

`.github/workflows/build.yml` на Windows вызывает тот же `build.bat` и выкладывает `dist\F1AnalyticsHub.exe`.
