# F1 Analytics Hub — Архитектура проекта

## 🏗️ Общая схема

```
┌─────────────────────────────────────────────────┐
│           F1 Analytics Hub                      │
│         Flet Desktop Application                │
└─────────────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
    ┌───▼────┐                    ┌─────▼─────┐
    │ UI     │                    │ Services  │
    │ Layer  │◄───────────────────┤ Layer     │
    └────────┘                    └───────────┘
        │                               │
        │                               │
┌───────▼─────────┐            ┌────────▼────────┐
│ Design System   │            │   Data Layer    │
│ Components      │            │   API + Cache   │
│ Screens         │            │   SQLite        │
└─────────────────┘            └─────────────────┘
```

## 📂 Модульная структура

### 1. Точка входа — `main.py`

```python
main.py
├── Инициализация Flet app
├── Создание State (ui/state.py)
├── Настройка навигации (5 табов + подэкраны)
├── Ticker (авто-обновление UI)
└── Refresher (фоновое обновление данных)
```

**Правило потоков.** Во Flet 0.80+ `page.update()` из обычного потока не будит цикл событий:
изменения доходят до окна только после следующего действия пользователя. Поэтому всё, что
меняет интерфейс из фоновых потоков (обновление данных, таймер, загрузка результатов), идёт
через `state.render()` / `run_on_ui()` в `main.py` — они выполняют перерисовку в цикле событий
через `page.run_task`, а несколько запросов подряд сливаются в одну перерисовку.
Обработчики нажатий и так выполняются в цикле событий — там `control.update()` безопасен.

### 2. UI Layer — `ui/`

```
ui/
├── components.py          # Переиспользуемые компоненты
│   ├── ResponsiveContainer
│   ├── AnimatedCard
│   ├── GradientButton
│   ├── DriverAvatar
│   ├── PositionBadge
│   ├── StatCard
│   └── LoadingSpinner
│
├── screens/               # Экраны приложения
│   ├── home.py           # Главная
│   ├── season.py         # Чемпионат (таблицы)
│   ├── calendar.py       # Календарь гонок
│   ├── drivers.py        # Список пилотов
│   ├── driver_detail.py  # Страница пилота
│   ├── compare.py        # Сравнение пилотов
│   ├── favorites.py      # Избранное
│   └── more.py           # Настройки + прочее
│
├── state.py              # AppState (центральное хранилище)
├── fmt.py                # Форматирование данных
└── widgets.py            # Каркас экрана (шапка, статус сети, баннер), кнопки, графики-столбики
```

### 3. Design System — `design_system.py`

```python
design_system.py
├── Цветовая палитра
│   ├── Surfaces (6 уровней темноты)
│   ├── Text (primary/secondary/muted/dim)
│   ├── Accent colors (primary/secondary/tertiary)
│   ├── Status colors (success/warning/danger/info)
│   └── Team colors (10 команд Ф1)
│
├── Типографика
│   ├── Font families (Racing/Mono/Text)
│   ├── Font sizes (caption → display)
│   └── Font weights
│
├── Spacing
│   ├── SPACE_XXS → SPACE_XXL
│   └── Padding/margin токены
│
├── Radius
│   ├── RADIUS_SM → RADIUS_XL
│   └── RADIUS_FULL (999px)
│
├── Shadows
│   ├── SHADOW_SM/MD/LG
│   └── GLOW (для акцентов)
│
└── Animations
    ├── ANIM_FAST (150ms)
    ├── ANIM_NORMAL (250ms)
    └── ANIM_SLOW (400ms)
```

### 4. Services Layer — `services/`

```
services/
├── f1_api.py             # Фасад для работы с данными
│   ├── get_standings()   # Турнирная таблица
│   ├── get_schedule()    # Календарь
│   ├── get_results()     # Результаты гонок
│   └── get_drivers()     # Список пилотов
│
├── jolpica.py            # HTTP-клиент Jolpica F1 API
│   ├── fetch()           # Базовый GET-запрос
│   ├── fetch_drivers()
│   ├── fetch_constructors()
│   ├── fetch_schedule()
│   └── fetch_results()
│
├── db.py                 # SQLite кэш
│   ├── init_db()
│   ├── save_standings()
│   ├── load_standings()
│   └── cache_*()
│
├── seed.py               # Начальные данные
└── log.py                # Логирование
```

### 5. Data Layer — `data/`

```
%USERPROFILE%\.ferrari_leclerc_hub\f1_hub.db   # SQLite (путь меняется переменной F1_HUB_DB)
├── meta                    # Сезон, этап, время последней загрузки
├── standings               # Личный зачёт
├── constructor_standings   # Кубок конструкторов
├── race_results            # Результаты гонок по пилотам
├── schedule                # Календарь
├── favorites               # Избранные пилоты
└── settings                # Настройки пользователя

data/seed.json              # Снимок данных для первого запуска без сети
                            # (python -m services.seed export --refresh)
```

## 🔄 Поток данных

```
Jolpica API
    │
    ▼
┌─────────────┐
│ jolpica.py  │  HTTP-запросы
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   db.py     │  Кэширование в SQLite
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  f1_api.py  │  Бизнес-логика
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   State     │  Центральное хранилище
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Screens    │  UI-компоненты
└─────────────┘
```

## 🎨 Компонентная модель

### Пример: Экран "Пилоты"

```
drivers.py
├── build(state) → ft.Column
    │
    ├── SectionHeader("Пилоты")
    │
    ├── SearchBar (поиск по имени)
    │
    ├── TeamFilter (цветные чипы команд)
    │
    └── ResponsiveContainer
        ├── DriverCard #1
        │   ├── DriverAvatar
        │   ├── PositionBadge
        │   ├── TeamColorBar
        │   └── Stats (Row)
        │
        ├── DriverCard #2
        └── ...
```

### Адаптивность

```
Mobile (≤430px)      Tablet (≤834px)     Desktop (≤1194px)    Wide (>1194px)
┌──────────┐         ┌────────────┐      ┌─────────────┐      ┌───────────────┐
│  Card 1  │         │ Card │ Card│      │ C │ C │ C  │       │ C │ C │ C │ C │
│  Card 2  │         │ Card │ Card│      │ C │ C │ C  │       │ C │ C │ C │ C │
│  Card 3  │         │ Card │ Card│      │ C │ C │ C  │       │ C │ C │ C │ C │
└──────────┘         └────────────┘      └─────────────┘      └───────────────┘
1 колонка            2 колонки           3 колонки            4 колонки
```

## ⚡ Производительность

### Кэширование

```
1. Первый запрос → API → SQLite → UI (медленно, ~2-3s)
2. Повторный    → SQLite → UI (быстро, ~100ms)
3. Обновление   → API (фон) → SQLite → UI
```

### Ленивая загрузка

- **Изображения**: загружаются по требованию
- **Данные**: по экранам (не все сразу)
- **Графики**: рендерятся только при открытии

### Оптимизации

- **Debounce** на поиск (300ms)
- **Throttle** на скролл
- **Виртуализация** списков (будущее)

## 🚀 Сборка

### Development

```bash
python main.py
# ИЛИ
flet run main.py
```

### Production (Windows .exe)

```bat
build.bat   :: тесты -> снимок данных -> flet pack -> dist\F1AnalyticsHub.exe
```

### Результат

```
Размер: ~80-120 МБ
Содержит:
├── Python runtime
├── Flet framework
├── Все зависимости
└── Приложение
```

## 🔮 Будущие улучшения

### Архитектурные

- [ ] Разделить State на модули (DriverState, RaceState, etc.)
- [ ] Добавить middleware для логирования
- [ ] Реализовать State persistence (сохранение UI-состояния)
- [ ] Event bus для коммуникации между компонентами

### Производительные

- [ ] Lazy imports для быстрого старта
- [ ] Worker threads для тяжелых вычислений
- [ ] WebSocket для live-данных
- [ ] Виртуализация списков (react-window аналог)

### Функциональные

- [ ] Offline-first архитектура
- [ ] Синхронизация с облаком
- [ ] Плагин-система для расширений
- [ ] Темизация (светлая тема)

---

Эта архитектура обеспечивает:
✅ **Модульность** — легко добавлять новые экраны
✅ **Тестируемость** — каждый слой изолирован
✅ **Масштабируемость** — готово к расширению
✅ **Производительность** — умное кэширование
