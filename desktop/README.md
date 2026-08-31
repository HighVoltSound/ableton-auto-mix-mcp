# MusicMixCode Desktop

Desktop GUI (Tauri 2 + React 18-style API / React 19 + TypeScript + Vite + TailwindCSS 4) для Python-бэкенда авто-сведения музыки по стилям из проекта `ableton-auto-mix-mcp`.

Тёмная тема в духе Linear/Vercel: near-black фон `#0a0a0f`, violet/fuchsia градиенты, glassmorphism карточки.

## Стек

| Слой      | Технологии                                        |
|-----------|---------------------------------------------------|
| Shell     | Tauri 2 (`src-tauri/`, identifier `com.highvolt.musicmixcode`) |
| UI        | React + TypeScript + Vite                         |
| Styling   | TailwindCSS 4 (`@tailwindcss/vite`), ручные компоненты |
| Charts    | recharts                                          |
| Icons     | lucide-react                                      |

## Запуск dev

```powershell
cd desktop
npm.cmd install
npm.cmd run tauri dev
```

> На Windows с заблокированным `npm.ps1` всегда используйте `npm.cmd`.
> Первый `tauri dev` компилирует Rust — это может занять несколько минут.
> Frontend отдельно от шелла: `npm.cmd run dev` → http://localhost:5173

## Продакшн-сборка

```powershell
npm.cmd run build        # фронт: tsc -b && vite build
npm.cmd run tauri build  # полный бандл (.msi/.exe) — требует cargo
```

## Подъём бэкенда

GUI ожидает HTTP API на `http://127.0.0.1:8787`:

```powershell
python -m ableton_auto_mix.api_app
```

Если бэкенд не запущен, приложение показывает красный баннер
«Backend not running» и индикатор offline в sidebar.

## Контракт API (используемый клиентом)

Базовый URL: `http://127.0.0.1:8787`

| Метод | Путь                  | Назначение                          |
|-------|-----------------------|-------------------------------------|
| GET   | `/api/styles`         | список стилей (+ health probe)      |
| GET   | `/api/style/{id}`     | профиль стиля                       |
| POST  | `/api/analyze`        | метрики треков `{directory}`        |
| POST  | `/api/suggest`        | подбор стиля `{directory}`          |
| POST  | `/api/mix`            | dry-run коррекции per-track         |
| POST  | `/api/preview`        | рендер превью-микса                 |
| POST  | `/api/release`        | quality gate (ready/needs_work)     |
| POST  | `/api/conflicts`      | частотные конфликты                 |
| GET   | `/api/audio?path=…`   | стрим WAV для плеера                |

Клиент: `src/lib/api.ts`. Типы: `src/types.ts` — все поля optional, отсутствие
полей не ломает UI.

## Структура

```
desktop/
├── index.html
├── vite.config.ts
├── package.json
├── src/
│   ├── main.tsx              # entry
│   ├── App.tsx               # layout + глобальное состояние + роутинг view
│   ├── index.css             # Tailwind 4, тема, слайдеры, скроллбары
│   ├── types.ts              # loose-типы API (всё optional)
│   ├── lib/api.ts            # fetch-клиент, BASE=http://127.0.0.1:8787
│   └── components/
│       ├── Sidebar.tsx       # навигация + индикатор бэкенда
│       ├── SetupScreen.tsx   # путь к renders + Analyze
│       ├── StylePicker.tsx   # сетка стилей + suggest
│       ├── Dashboard.tsx     # таблица метрик + спектр (recharts) + конфликты
│       ├── MixPanel.tsx      # dry-run коррекции, слайдеры, preview, release
│       └── ui.tsx            # Card/Button/Badge/Slider/Spinner/EmptyState
└── src-tauri/
    ├── Cargo.toml
    ├── tauri.conf.json       # beforeDevCommand npm.cmd run dev, devUrl :5173
    ├── capabilities/default.json  # core:default
    ├── icons/icon.ico
    └── src/main.rs
```
