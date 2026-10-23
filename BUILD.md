# F1 Analytics Hub — сборка (Windows .exe, Android .apk)

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
    --product-name "F1 Analytics Hub" --product-version "2.1.0" --file-version "2.1.0.0"
```

- `assets/` — шрифт заголовков (работает без сети) и иконка;
- `data/seed.json` — снимок данных: при первом запуске без интернета приложение сразу показывает таблицы;
- ручной `.spec` не нужен: `flet pack` генерирует его сам, а клиент Flet кладёт в архив, который .exe распаковывает при первом запуске в `%USERPROFILE%\.flet\client`.

Почему не PyInstaller со своим `.spec`: без шага `flet pack` клиент Flet не попадает в нужный архив,
и .exe на чистом компьютере пытается скачать его из интернета.

`flet build windows` тоже работает, но требует Flutter SDK и Visual Studio с C++ — для одного .exe это лишнее.

## Где приложение хранит данные

- База и журнал: `%USERPROFILE%\.f1_analytics_hub\` (`f1_hub.db`, `f1_hub.log`).
- Клиент Flet: `%USERPROFILE%\.flet\client\`.

## Проверка сборки

```bat
dist\F1AnalyticsHub.exe
```

Окно открывается за несколько секунд (при первом запуске клиент распаковывается). Если окна нет —
смотрите `%USERPROFILE%\.f1_analytics_hub\f1_hub.log`. Для отладки можно собрать вариант с консолью:
добавьте к `flet pack` параметр `--debug-console true`.

Известное ограничение Windows: путь к профилю пользователя не должен быть очень длинным (>~120 символов) —
иначе распаковка клиента упирается в лимит путей 260 символов.

## Android

APK собирается командой `flet build apk` (настройки — в `pyproject.toml`: имя, пакет `com.f1hub`,
разрешение INTERNET, тёмный фон адаптивной иконки и сплэша; иконка — `assets/icon_android.png`).

```bash
pip install -r requirements.txt
flet build apk --yes          # результат: build/apk/f1-analytics-hub.apk
```

`flet build` сам скачивает Flutter SDK, JDK 17 и Android SDK (несколько гигабайт, первый раз — надолго).
**Windows:** путь к проекту и к профилю пользователя должен быть без кириллицы — Gradle и Flutter
на таких путях ломаются. Обходной путь — собирать из папки вроде `C:1bpp` и перед сборкой
направить `USERPROFILE`, `TEMP`, `ANDROID_HOME`, `GRADLE_USER_HOME`, `PUB_CACHE` в ASCII-папки.
Проще всего — взять готовый APK из CI (ниже).

Установка на телефон: скопировать APK и открыть (разрешить установку из этого источника) или
`adb install build/apk/f1-analytics-hub.apk`.

На телефоне приложение хранит базу и кэш картинок в папке данных приложения
(`FLET_APP_STORAGE_DATA`); снимок данных и картинки сезона встроены в APK — первый запуск работает без сети.

## CI

`.github/workflows/build.yml` (запуск вручную или при создании релиза):

- **Windows** — тот же `build.bat`, артефакт `F1AnalyticsHub-Windows` (.exe);
- **macOS** — `flet pack`, артефакт `F1AnalyticsHub-macOS` (.app в zip);
- **Android** — `flet build apk` на Ubuntu, артефакт `F1AnalyticsHub-Android` (.apk).

При публикации релиза на GitHub файлы прикрепляются к нему автоматически.
