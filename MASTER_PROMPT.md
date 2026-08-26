# MusicMixCode Desktop — Master Prompt

> Используй этот промпт в начале каждой новой сессии для продолжения разработки.

---

## Контекст проекта

Ты работаешь над **MusicMixCode Desktop** — десктопным приложением для авто-сведения и мастеринга музыки по стилям. Приложение использует Python-движок (FastAPI) + Tauri 2 (React/Rust).

### Ключевые файлы

```
C:\Users\highv\Documents\Default Project\ableton-auto-mix-mcp\
├── src\ableton_auto_mix\          # Python-движок
│   ├── analyzer.py               # Анализ LUFS/спектра
│   ├── mixer.py                  # Per-track коррекции
│   ├── planner.py                # Движок решений: mix vs mastering
│   ├── preview.py                # Рендер превью + мастеринг-цепочка
│   ├── reference.py              # Match-EQ по референсу
│   ├── profiles.py               # Загрузчик стилей
│   ├── qa.py                     # Конфликты + релиз-чек
│   ├── api_app.py                # FastAPI (10 эндпоинтов, порт 8787)
│   └── styles\*.json             # 11 профилей стилей
├── tests\                        # pytest тесты (33 passing)
├── build_backend.spec            # PyInstaller spec (139 MB onedir)
├── scripts\
│   ├── backend_entry.py          # Sidecar-лаунчер
│   └── build_all.ps1             # Полный пайплайн сборки
├── desktop\                      # Tauri 2 + React приложение
│   ├── src\
│   │   ├── App.tsx               # Глобальный стейт + роутинг
│   │   ├── components\           # UI компоненты
│   │   ├── lib\api.ts            # HTTP-клиент
│   │   └── types.ts              # TypeScript типы
│   └── src-tauri\
│       ├── src\main.rs           # Lifecycle sidecar'а
│       ├── Cargo.toml            # Rust зависимости
│       └── tauri.conf.json       # Конфиг приложения
└── HANDOFFS\                     # Хенджоффы для каждой задачи
    ├── 00_DOMAIN_MODEL.md        # Доменная модель + API contract
    ├── 00_OVERALL_HANDOFF.md     # Общий обзор + roadmap
    ├── 01_WAVEFORM_SPECTRUM.md   # Визуализация спектра/волны
    ├── 02_EXPORT_ABLETON.md      # Экспорт в Ableton Live
    ├── 03_PROJECT_SAVE_LOAD.md   # Сохранение/загрузка проектов
    ├── 04_UNDO_REDO.md           # Отмена/повтор
    ├── 05_PROGRESS_STREAMING.md  # WebSocket прогресс
    ├── 06_AUTO_UPDATE.md         # Автообновление
    ├── 07_I18N.md                # Интернационализация (ru/en)
    └── 08_DRAG_DROP_AUDIO.md     # Drag&drop аудиофайлов
```

## Инструкция

### 1. Начало сессии

**Обязательно прочитай первым:** `MEMORY.md` — лог решений и текущий статус проекта. Это даст контекст предыдущих сессий без повторных объяснений.

Затем прочитай `HANDOFFS/00_OVERALL_HANDOFF.md` для понимания текущего состояния. Определи какую задачу выполняешь из roadmap.

### 2. Перед началом работы

- Прочитай соответствующий хенджофф-файл (HANDOFFS/0N_*.md)
- Прочитай доменную модель (`HANDOFFS/00_DOMAIN_MODEL.md`) для контекста архитектуры
- Проверь текущее состояние тестов: `python -m pytest tests -q` (ожидается 33+ passing)
- Проверь фронт: в `desktop/` → `npm.cmd run build` (ожидается 0 TS ошибок)

### 3. Выполнение

- Следуй хенджоффу: файлы, API contract, acceptance criteria
- **НЕ ломай** существующий код — только расширяй с обратной совместимостью
- Новые Python-модули → `src/ableton_auto_mix/`
- Новые React-компоненты → `desktop/src/components/`
- API endpoints → в `api_app.py`
- Тесты → `tests/test_*.py` (pytest + синтетические данные)

### 4. Проверка

- `python -m pytest tests -q` — все тесты проходят
- `npm.cmd run build` в `desktop/` — без TS ошибок
- Ручная проверка: запусти бэкенд + фронт, убедись что ничего не сломалось

### 5. Конвенции

**Python:**
- Python 3.10, без `X | Y` синтаксиса в рантайме (используй `Optional[X]`)
- Переиспользуй существующие функции из analyzer/mixer/preview
- Каждое действие с `reason` строкой (для UI)

**TypeScript:**
- React 19, TypeScript strict, Tailwind 4
- Типы loose (все optional) для совместимости с разными версиями бэкенда
- Тёмная тема: bg `#0a0a0f`, accent violet→fuchsia

**Сборка:**
- PyInstaller: `build_backend.spec` (не трогай excludes без необходимости)
- Tauri: `npm.cmd` вместо `npm` (powershell policy)
- Installer: NSIS (`scripts/build_all.ps1`)

### 6. Завершение сессии

- **Обнови `MEMORY.md`** — добавь дату, что сделано, какие решения приняты, что дальше
- Сохрани важные решения в agent memory (`memory_save`)
- Обнови хенджофф-файл если изменились планы
- Не коммить если не просят

## API Contract (быстрая справка)

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/api/styles` | Список стилей |
| GET | `/api/style/{id}` | Профиль стиля |
| POST | `/api/analyze` | Анализ WAV в папке |
| POST | `/api/suggest` | Предложение стиля |
| POST | `/api/mix` | dry-run коррекции + план |
| POST | `/api/preview` | Рендер превью (A/B, match-EQ) |
| POST | `/api/release` | Проверка готовности к релизу |
| POST | `/api/conflicts` | Частотные конфликты |
| POST | `/api/match_eq` | Кривая match-EQ |
| GET | `/api/audio?path=` | WAV-файл (audio/wav) |
| GET | `/api/waveform?path=&points=` | Пик-огибающая для графика |

## Быстрый запуск

```powershell
# Бэкенд (порт 8787)
cd "C:\Users\highv\Documents\Default Project\ableton-auto-mix-mcp"
python -m ableton_auto_mix.api_app

# Фронтенд (dev)
cd desktop
npm.cmd install
npm.cmd run tauri dev

# Сборка установщика
scripts\build_all.ps1
```

## Модель памяти

Ключевые решения сохранены в agent memory:
- `mem_mta489ad` — Архитектура десктопа (Tauri + FastAPI)
- `mem_mta4t6wm` — Match-EQ, A/B плеер, сборка установщика
- `mem_mta8bvbt` — Планировщик, PyInstaller оптимизация, sidecar
- `mem_mta8yp0a` — Доменная модель, хенджоффы, delegation паттерн
- `mem_mtabpo51` — Task 1: Waveform/Spectrum/Heatmap визуализация

Дополнительно: `MEMORY.md` — лог решений по сессиям (читай в начале, обновляй в конце).
