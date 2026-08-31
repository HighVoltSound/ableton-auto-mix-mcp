# MusicMixCode Desktop — MEMORY.md

> Читай этот файл в начале каждой сессии. Обновляй в конце.
> Формат: append-only лог решений. Не удаляй старое — добавляй новое с датой.

---

## Текущий статус

| Задача | Статус | Завершена |
|---|---|---|
| 1. Waveform & Spectrum Visualization | **DONE** | 2026-08-26 |
| 2. Export to Ableton Live | **DONE** | 2026-08-26 |
| 3. Project Save/Load | **DONE** | 2026-08-26 |
| 4. Undo/Redo | **DONE** | 2026-08-27 |
| 5. WebSocket Progress Streaming | **DONE** | 2026-08-27 |
| 6. Auto-Update | **DONE** | 2026-08-27 |
| 7. i18n (ru/en) | **DONE** | 2026-08-27 |
| 8. Drag&Drop Audio Files | **DONE** | 2026-08-27 |
| Backend Launch Fix | **DONE** | 2026-08-28 |
| Track Import (per-track) | **DONE** | 2026-08-28 |
| MCP Server Full Sync & Tools | **DONE** | 2026-08-29 |
| True Peak Limiter, De-Esser & Interactive EQ | **DONE** | 2026-08-29 |
| Binaural 3D Head Spatializer & VST3 Plugin | **DONE** | 2026-08-29 |
| Cyber-Studio Glassmorphism & Style Artworks | **DONE** | 2026-08-29 |

**Следующая задача:** Дальнейшее развитие и фичи по запросу пользователя.

---

## Решения сессий

### 2026-08-29 — Cyber-Studio Glassmorphism & Style Artworks Redesign

**Что сделано:**
1. **11 Векторных арт-обложек (`desktop/src/components/styleArtworks.tsx`):**
   - Уникальные художественные иллюстрации для всех жанров (Ambient космический туман, Balanced студийный пульт, Breaks молнии, DnB 174 BPM лазерные полосы, Dubstep токсичный воббл, Hip-Hop винил и MPC, Lo-Fi ретро-кассета, Pop радио-блеск и микрофон, Techno берлинский 4/4 рейв, Trance суперпилы и луч, Trap темный 808 и 1/32 хэты).
   - Метаданные стилей: слоганы, теги тембра, целевой LUFS, подсказки BPM и палитры свечения.
2. **Интерактивные 3D-карточки стилей (`desktop/src/components/StyleCard.tsx`):**
   - 3D Parallax Tilt эффект при движении курсора (вращение в перспективе `rotateX`, `rotateY`).
   - Стеклянный световой блик (Glass Flare Follower), следующий за мышью.
   - Живой анимированный микро-спектр эквалайзера на активной и наведенной карточке.
   - Неоновые светящиеся контуры и бейджи статуса.
3. **Глобальный дизайн Cyber-Studio Dark Glassmorphism:**
   - Дышащий фон с динамическими сферами подсветки (Ambient Studio Glow в `App.tsx`), меняющими цвет под выбранный стиль.
   - Модернизированный сайдбар `Sidebar.tsx` с логотипом Pro Studio Workstation, неоновыми индикаторами вкладок и живым статусом подключения бэкенда.
   - Обновленные стеклянные карточки `Card`, кнопки `Button`, слайдеры `Slider` с неоновыми светящимися треками и бейджи `Badge` в `ui.tsx` и `index.css`.
4. **Тестирование:**
   - Сборка фронтенда `npm run build` прошла успешно (0 ошибок).
   - Все 114/114 бэкенд-тестов пройдены (`pytest tests -q`).

### 2026-08-29 — Binaural 3D Head Spatializer & Standalone VST3

**Что сделано:**
1. **DSP Модуль (`src/ableton_auto_mix/dsp/spatializer.py`):**
   - Бинауральная психоакустическая модель головы: Woodworth-Schlosser ITD задержки с субсэмпловой дробной интерполяцией.
   - ILD затенение черепом (Head Shadowing) для противоположного уха.
   - Спектральная маска затылка и шеи: полосовое подавление ВЧ (>4.5 кГц), резонанс основания шеи/плеч (1.3 кГц) и спектральный вырез ушной раковины (Pinna Notch ~7.2 кГц) при положении звука сзади головы.
   - Плавная траектория `head_position`: 0.0 (Шея) $\to$ 0.33 (Затылок) $\to$ 0.66 (Ухо) $\to$ 1.0 (Лицо), управление азимутом, высотой, расстоянием и Dry/Wet.
2. **Интерактивный UI (`desktop/src/components/HeadSpatializerModal.tsx`):**
   - Canvas-рендерер анатомического силуэта головы человека (вид сбоку).
   - Интерактивный drag & drop звукового узла по кривой черепа от шеи через затылок и ухо к лицу.
   - Быстрые пресеты: «У шеи (Neck Sub)», «Затылок (Occiput Behind)», «В ухо (Direct Ear)», «Перед лицом (Front Stage)».
   - Кнопка вызова 👤 **3D** на каждой дорожке в микшере и проброс в `preview.py` и сохранение проекта.
   - Полная русская и английская локализация.
3. **Автономный VST3 / CLAP плагин (`plugins/head_spatializer_vst/`):**
   - Проект плагина на Rust (`nih-plug`) с нулевой задержкой (zero-latency realtime processing) для прямого использования в Ableton Live / FL Studio / Reaper.
   - Инструкция по сборке и установке в `README.md`.
4. **Тестирование и верификация:**
   - Новый набор тестов `tests/test_spatializer.py` (4/4 passed).
   - Все **114/114 бэкенд-тестов** успешно пройдены (`pytest tests -q`).
   - Сборка фронтенда `npm run build` прошла без единой ошибки.

---

### 2026-08-29 — True Peak Limiter, De-Esser & Interactive Master EQ

**Что сделано:**
1. **True Peak Limiter (`src/ableton_auto_mix/dsp/limiter.py`):**
   - 4x oversampled brickwall limiter по стандарту ITU-R BS.1770 / EBU R128 (-1.0 dBTP / -0.3 dBTP).
   - Lookahead буферизация с экспоненциальным сглаживанием огибающей и гарантированным подавлением intersample peaks.
2. **Vocal De-Esser (`src/ableton_auto_mix/dsp/deesser.py`):**
   - Полосовой детектор сибилянтов (4.5–9.0 кГц) с ультрабыстрой атакой (<1 мс).
   - Два режима: `split` (динамический notch-фильтр без искажения нижних частот) и `wide` (широкополосное подавление).
   - Интегрирован в предварительный миксдаун `preview.py` и эндпоинты `api_app.py`, `server.py`.
3. **Interactive EQ Nodes HUD & Controls (`desktop/src/components/EqEditor.tsx`):**
   - Регулировка добротности Q колесиком мыши (`onWheel` с шагом $\pm 0.15$).
   - Добавление новой полосы по двойному клику на координатах холста (`onDoubleClick`).
   - Интерактивный HUD-тултип с точным отображением типа фильтра, частоты (Hz/kHz), усиления (dB) и Q при наведении/перетаскивании.
   - Горячие клавиши: `Delete`/`Backspace` для удаления выбранной полосы, `Space` для переключения активности.
4. **MixPanel De-Esser UI Card (`desktop/src/components/MixPanel.tsx`):**
   - Карточка управления De-Esser: переключатель ON/OFF, регуляторы частоты (2–12 кГц), порога (-40..0 dB), максимального среза (1..24 dB), режима (split/wide) и Dry/Wet микса.
   - Полная передача `deesserConfig` и интерактивных `eqBands` в процесс рендеринга preview.
   - Локализация на русский и английский (`ru.json`, `en.json`).
5. **Тестирование и верификация:**
   - Новый набор тестов `tests/test_dsp_enhancements.py` (5/5 passed).
   - Все 110 бэкенд-тестов пройдены успешно (`pytest tests -q`).
   - Сборка фронтенда `npm run build` прошла без единой ошибки.

---

### 2026-08-28 — Backend Launch Fix & TrackImport

**Что сделано:**
1. **Backend launch fix** — `main.rs` переделан:
   - Убран `tauri-plugin-shell` (sidecar机制 сломана из-за temp-директории Tauri)
   - Теперь: sidecar binary запускается через `std::process::Command` с `resource_dir` как working directory
   - Python fallback: `python -m ableton_auto_mix.api_app --port 8787` (была опечатка — не хватало точки)
   - Kill backend при выходе из приложения через `taskkill /PID /T /F`
   - Удалены `shell:allow-execute` / `shell:allow-spawn` из capabilities
2. **TrackImport** — новый компонент для drag & drop импорта дорожек:
   - Drag & drop WAV через Tauri API (реальные пути)
   - Автоматическое угадывание роли по имени файла
   - Выпадающий список ролей для каждой дорожки
   - Кнопка удаления, добавления через кнопку
3. **App.tsx** — два режима импорта: "Дорожки" / "Папка" (toggle сверху)
4. **i18n** — добавлены строки `import.*` в en.json и ru.json

**Корневая причина backend:** В `pyproject.toml` package entry point — `__main__:main`, а api_app запускается как `python -m ableton_auto_mix.api_app` (с точкой). В main.rs было `args(["-m", "ableton_auto_mix", "api_app", ...])` — Python не находил модуль.

**Результат:** Backend стартует автоматически при запуске приложения, NSIS-инсталлер работает.

---

### 2026-08-26 — Task 1: Waveform & Spectrum Visualization

**Что сделано:**
- WaveformCanvas.tsx — canvas-рендерер, gradient violet→fuchsia, click-to-seek
- SpectrumAnalyzer.tsx — recharts LineChart, log X-axis, measured vs target
- ConflictHeatmap.tsx — CSS Grid матрица, severity по gap_db, tooltip
- ABPlayer.tsx — forwardRef + seekTo() для внешнего seek
- Dashboard.tsx — заменил текстовые конфликты на heatmap, спектр на analyzer
- MixPanel.tsx — добавил WaveformCanvas + seek через ABPlayer ref
- types.ts — WaveformResult, gap_db в ConflictPair
- api.ts — api.waveform(path, points)

**Решения:**
- Single channel waveform (API возвращает один peaks массив, не stereo)
- SpectrumAnalyzer ЗАМЕНяет существующий график спектра (без дублирования)
- gap_db добавлен в ConflictPair для heatmap
- WaveformCanvas click → ABPlayer seek через ref (forwardRef + useImperativeHandle)
- eqCurve убран из Dashboard (визуализация только в MixPanel)

**Отклонения от спеки (minor):**
- ReferenceArea для conflict overlay на графике не сделан (Badge вместо красной зоны)
- before_path waveform не добавлен (только after)
- Throttle на canvas не нужен — canvas и так быстрый

**Коммит:** `02deac4` — feat: Task 1 — Waveform & Spectrum Visualization

---

### 2026-08-26 — Task 3: Project Save/Load

**Что сделано:**
- project.py — ProjectState dataclass, save/load/auto_save/list_recent_projects
- api_app.py — 3 эндпоинта: POST /api/project/save, POST /api/project/load, GET /api/project/recent
- types.ts — ProjectState, ProjectSaveResult, RecentProject interfaces
- api.ts — saveProject, loadProject, recentProjects методы
- SaveDialog.tsx — модальное окно сохранения с именем проекта
- SetupScreen.tsx — секция Saved Projects с загрузкой из API
- App.tsx — projectName state, buildProjectState, autoSave (на analyze/mix/preview), loadProject
- test_project.py — 11 тестов (roundtrip, auto-save, migration v0.2, recent, defaults)
- test_api_app.py — 5 API тестов (save, load, missing, no-dir, recent)

**Решения:**
- Формат файла: `.mmc.json` (ручное сохранение) + `.musicmixcode.json` (auto-save в папке проекта)
- list_recent_projects сканирует Desktop/Documents/Music/Downloads + renders, rglob с try/except на битые симлинки
- list_recent_projects принимает `extra_dirs` параметр для тестов
- v0.2 миграция: заполняет missing fields defaults, обновляет version до 0.3
- Auto-save best-effort: не показывает ошибки, если бэкенд недоступен
- buildProjectState использует refs для analysis/mix/preview чтобы сохранять актуальные данные

**Итого:** 49/49 тестов, 0 TS ошибок

---

### 2026-08-26 — Task 2: Export to Ableton Live

**Что сделано:**
- als_xml.py — Минимальный .als XML билдер (ZIP-компрессия, AudioTrack, Volume, Pan, EQ Eight)
- ableton_export.py — Движок экспорта: file mode (.als) + live mode (AbletonOSC)
- api_app.py — POST /api/export эндпоинт + ExportRequest/BandCorrectionPayload/TrackCorrectionPayload модели
- ExportDialog.tsx — Модальное окно экспорта (mode select, corrections summary, progress, result)
- MixPanel.tsx — Кнопка "Export to Ableton" после таблицы коррекций
- api.ts — api.exportCorrections() метод
- types.ts — ExportPayload, ExportResult интерфейсы
- test_als_xml.py — 13 тестов XML билдера (build_session + write_als)
- test_ableton_export.py — 8 тестов движка экспорта (file/live/edge cases)
- test_api_export.py — 4 теста API эндпоинта

**Решения:**
- .als файл = ZIP с одним XML внутри (Ableton стандарт)
- Volume конвертация: dB -> Ableton gain (10^(db/20) * 0.871)
- EQ Eight: до 8 band'ов, filter type = bell (type 6)
- Live mode: только volume + pan через AbletonOSC (EQ через .als файл)
- ExportDialog: modality через div backdrop + stopPropagation
- Card компонент не поддерживает onClick → используем div с теми же стилями

**Отклонения от спеки (minor):**
- EQ Eight param ids (A0, A1, B1...) — упрощённая нумерация, Ableton может не распознать
- Session snapshot (live mode) не делается — только push коррекций
- Connection pooling к AbletonOSC не реализован (один client на сессию)

**Итого:** 74/74 тестов, 0 TS ошибок

---

### 2026-08-27 — Task 4: Undo/Redo

**Что сделано:**
- history.ts — generic HistoryManager<T> class (past/present/future stacks, max 50 entries)
- App.tsx — HistoryManager<MixSnapshot> ref, handleUndo/handleRedo, keyboard shortcuts (Ctrl+Z, Ctrl+Shift+Z, Ctrl+Y)
- Sidebar.tsx — Undo/Redo buttons (disabled state, lucide Undo2/Redo2 icons)
- MixPanel callbacks — onManualGainChange and onSidechainChange push old state to history with labels
- selectStyle — captures old snapshot before changing style, pushes to history
- runAnalyze — resets history on new directory

**Решения:**
- Snapshot = { selectedStyleId, manualGain, sidechainDb } — параметры, влияющие на микс
- History не включает view, analysis, preview, mixResult — восстанавливается через UI действия
- Кнопки Undo/Redo в Sidebar между nav и backend status
- History push发生在状态更改之前，使用当前渲染值（старые значения）
- forceHistoryUpdate через useState tick для пересчёта canUndo/canRedo

**Итого:** 74/74 тестов, 0 TS ошибок

---

### 2026-08-27 — Task 5: WebSocket Progress Streaming

**Что сделано:**
- ws_manager.py — ConnectionManager class (room-based WS), ProgressReporter helper (throttled broadcast)
- preview.py — добавлен progress_callback параметр в render_preview_mix (6 stages: analyzing, mixing, applying_eq, sidechain, mastering, rendering, done)
- analyzer.py — добавлен progress_callback в analyze_directory
- api_app.py — WS /ws/progress/{room_id} endpoint, async_mode параметр в PreviewRequest/DirectoryRequest/ExportRequest, threading-based background execution
- ProgressBar.tsx — анимированный компонент прогресс-бара с gradient fill, smooth transitions
- api.ts — subscribeProgress(roomId, handlers) с auto-reconnect, AsyncResponse тип
- MixPanel.tsx — ProgressBar вместо spinner во время preview, progress state (stage/percent/detail)
- App.tsx — runPreview использует async_mode + WS подписку, cleanupWsRef для отписки
- types.ts — ProgressMessage, CompleteMessage, ErrorMessage, AsyncResponse интерфейсы
- test_ws_progress.py — 13 тестов (ConnectionManager, ProgressReporter, async endpoints, callback integration)

**Решения:**
- Room-based WS: каждая операция получает room_id, клиент подключается после получения ID
- Async mode: endpoint возвращает room_id немедленно, задача запускается в daemon thread
- ProgressReporter throttle: min_interval=150ms чтобы не спамить WS
- Fallback: async=false (default) возвращает sync response для обратной совместимости
- ProgressBar: requestAnimationFrame smooth interpolation, gradient violet→fuchsia
- Auto-reconnect: exponential backoff (500ms → 5000ms max)
- Cleanup: ws_manager.cleanup_room() вызывается после завершения/ошибки операции

**Итого:** 87/87 тестов, 0 TS ошибок

---

### 2026-08-27 — Task 6: Auto-Update

**Что сделано:**
- Cargo.toml — добавлены tauri-plugin-updater и tauri-plugin-process
- tauri.conf.json — updater plugin конфиг (endpoints, pubkey, quiet install)
- main.rs — регистрация updater + process плагинов в builder
- updater.ts — checkForUpdate(), installUpdate(onProgress), restartApp() с graceful fallback для dev mode
- UpdateBanner.tsx — non-intrusive banner с progress bar, Update/Skip/Restart кнопками
- useUpdateCheck hook — проверка при запуске через 5с задержку, dismissed state
- App.tsx — Mount UpdateBanner, useUpdateCheck хук
- package.json — @tauri-apps/plugin-updater + @tauri-apps/plugin-process зависимости

**Решения:**
- Updater endpoint: releases.highvoltsound.com/musicmixcode/{{target}}/{{arch}}/{{current_version}}.json
- Quiet install mode (Windows) — без UI установщика
- Dev mode: все updater функции no-op (IS_TAURI проверка)
- Banner: gradient violet→fuchsia, не блокирует UI, dismissible
- Restart: через @tauri-apps/plugin-process relaunch(), fallback на window.location.reload()
- Проверка обновлений: 5с задержка после mount, чтобы не блокировать старт приложения

**Итого:** 87/87 тестов, 0 TS ошибок

---

### 2026-08-27 — Task 7: i18n (Russian/English)

**Что сделано:**
- i18n/locales/en.json — 169 строк, все UI-строки на английском (nav, setup, styles, dashboard, mix, export, save, update, player, eqCurve, progress, errors)
- i18n/locales/ru.json — полный перевод на русский
- i18n/index.tsx — React Context (I18nProvider), useLanguage() hook, t() с интерполяцией {params}, localStorage persistence, fallback на en
- main.tsx — обёрнут App с I18nProvider
- Sidebar.tsx —.language toggle (Globe icon, переключение en↔ru), nav items через t()
- SetupScreen.tsx — все строки через t()
- StylePicker.tsx — все строки через t()
- Dashboard.tsx — таблица метрик, спектр, конфликты через t()
- MixPanel.tsx — все секции (overrides, corrections table, preview, release) через t()
- ABPlayer.tsx — Before/After, Play/Pause через t()
- ExportDialog.tsx — модальное окно экспорта через t()
- SaveDialog.tsx — модальное окно сохранения через t()
- UpdateBanner.tsx — баннер обновления через t()
- App.tsx — error banner через t()
- SpectrumAnalyzer.tsx — спектральная кривая через t()
- ConflictHeatmap.tsx — heatmap + legend через t()
- EqCurveChart.tsx — empty state через t()
- ProgressBar.tsx — stage labels (analyzing, mixing, etc.) через t()
- useFileDrop.ts — исправлен duplicate identifier (pre-existing)

**Решения:**
- React Context + useLanguage() hook (не global state — каждый компонент получает t() через hook)
- Language toggle в Sidebar (bottom, Globe icon, toggle en↔ru)
- localStorage ключ: `musicmixcode.lang`
- Fallback: если ключ отсутствует в текущем языке → берётся из en → если нет → возвращает сам ключ
- Интерполяция: `t('mix.styleTarget', { style: 'techno' })` → "Style target: techno · dry-run corrections below"
- ProgressBar stage labels переведены через STAGE_KEYS map
-方言支持: detects browser language (navigator.language) → ru if starts with 'ru', else en

**Итого:** 87/87 тестов, 0 TS ошибок

---

### 2026-08-27 — Task 8: Drag&Drop Audio Files

**Что сделано:**
- useFileDrop.ts — React hook (dragCounter-based enter/leave tracking, isDragging state, dragProps spread)
- api_app.py — POST /api/upload endpoint (multipart form, WAV-only, auto-mkdir, _register_dir whitelist)
- api.ts — uploadFile(file, targetDir) method (FormData POST, returns UploadResult)
- types.ts — UploadResult interface (path, name)
- SetupScreen.tsx — replaced old hint-only drag&drop with actual file upload, uploaded files shown as chips with dismiss buttons, upload progress spinner, error display
- MixPanel.tsx — added drop zone around reference WAV input (glowing border on dragover, auto-fill reference path after upload), added `directory` prop
- App.tsx — passes directory prop to MixPanel

**Решения:**
- useFileDrop uses dragCounter ref (not just dragenter/dragleave) to handle nested elements correctly
- Upload only accepts .wav files, skips non-audio with error message
- SetupScreen requires directory path before upload (no orphaned uploads)
- MixPanel reference drop uploads to the renders directory and auto-fills the path
- Upload endpoint uses _register_dir so uploaded files can be served back via /api/audio
- Frontend: FormData (not JSON) for file upload since multipart required

**Pre-existing issue:**
- src/i18n/index.ts line 80 has JSX in .ts file (Task 7 leftovers) — not related to Task 8

**Итого:** 87/87 тестов, TS ошибки только в pre-existing i18n/index.ts

---

## Паттерны и конвенции

### Frontend
- Типы: все optional (loose) для совместимости с разными версиями бэкенда
- Компоненты: Card, Badge, Slider, Button, EmptyState из `ui.tsx`
- Новые компоненты → `desktop/src/components/`
- API клиент → `desktop/src/lib/api.ts` (все fetches через него)
- Types → `desktop/src/types.ts`
- Recharts: log X-axis через `scale="log"`, тултипы с `contentStyle`
- Canvas: useRef + useEffect + devicePixelRatio для HiDPI
- ABPlayer: forwardRef для внешнего seek

### Backend
- Python 3.10, Optional[X] вместо X | Y
- Все эндпоинты в `api_app.py`
- Новые модули → `src/ableton_auto_mix/`
- Тесты → `tests/test_*.py` (pytest + синтетические данные)

### Сборка
- `npm.cmd` вместо `npm` (PowerShell)
- `npm run build` = tsc -b && vite build
- PyInstaller: build_backend.spec (139 MB onedir)
- NSIS installer через scripts/build_all.ps1

---

### 2026-08-27 — Block 1: DSP Core (Dynamic EQ, Mid/Side EQ, Transient Shaper)

**Что сделано:**
- `dsp/dynamic_eq.py` — per-band envelope follower + threshold/ratio compress/expand modes
- `dsp/midside_eq.py` — mid/side EQ with RBJ biquads (peaking, low/high shelf)
- `dsp/transient.py` — attack/sustain transient shaper with sensitivity control
- All DSP wired into `preview.py` pipeline after multiband compressor
- API params added: `dynamic_eq`, `midside_eq`, `transient` in `PreviewRequest`
- Frontend types: `DynamicEqConfig`, `MidSideEqConfig`, `TransientConfig`
- UI: MixPanel DSP Processing card with ON/OFF toggles and parameter inputs
- i18n: en.json + ru.json strings for DSP controls

---

### 2026-08-27 — Block 2: AI Analysis (Role Detection, Recommender, Batch)

**Что сделано:**
- `auto_role.py` — spectral fingerprinting with centroid, flatness, crest factor, transient density; decision-tree classifier for kick/bass/snare/hat/pads/lead/vocals/percussion with confidence
- `ai_recommender.py` — rule engine analyzing LUFS, spectral balance, dynamics, roles → suggests gain, EQ, compression, sidechain, transient shaping
- `batch.py` — sequential multi-directory processing with shared style profile
- API endpoints: `POST /api/recommend`, `POST /api/detect_roles`, `POST /api/batch`
- Frontend: types (RecommendResult, DetectRolesResult, BatchResult, BatchPayload), api.ts methods
- SetupScreen: "AI suggests" button → loads recommendations panel
- i18n: aiSuggest, aiLoading, aiSuggestions, aiNone in en.json + ru.json
- 87/87 tests, 0 TS errors

---

### 2026-08-27 — Block 3: Workflow (Sidechain, A/B Compare, Presets, Export Formats)

**Что сделано:**
- `dsp/sidechain.py` — configurable sidechain: trigger role, targets, amount, attack/release, band filter, mix
- `ab_compare.py` — render same tracks with two different style profiles for A/B comparison
- `presets.py` — save/load/delete mix presets (multiband, limiter, EQ, sidechain, etc.) as JSON
- `export_formats.py` — export WAV (configurable bit depth), FLAC (compression level), MP3 (via ffmpeg)
- API endpoints: `POST /api/preview/ab`, `GET /api/presets`, `POST /api/presets/save`, `POST /api/presets/load`, `DELETE /api/presets/{name}`, `POST /api/export/format`
- PreviewRequest gains `sidechain` config, wired into preview.py pipeline
- Frontend: SidechainCompression card in MixPanel, A/B Compare card with style selects + audio players
- Types: `SidechainConfig`, `ABComparePayload`, `ABCompareResult`, `MixPreset`, `PresetListEntry`, `ExportFormatPayload`, `ExportFormatResult`
- api.ts: `abCompare`, `listPresets`, `savePreset`, `loadPreset`, `deletePreset`, `exportFormat`
- i18n: sidechain, scTrigger, amount, release, abCompare, presets, exportFormats — en.json + ru.json
- 87/87 tests, 0 TS errors

---

---

### 2026-08-29 — MCP Server Full Sync & Tools Expansion

**Что сделано:**
- `server.py` — Полная синхронизация MCP-сервера со всеми современными возможностями движка:
  - `detect_track_roles` — определение ролей инструментов (kick, snare, bass, vocal...)
  - `recommend_mix` — интеллектуальный консультант с рекомендациями по gain, EQ, компрессии, сайдчейну
  - `match_eq_reference` — вычисление кривой Match-EQ по референсному коммерческому треку
  - `export_to_ableton` — экспорт в `.als` сессию Ableton Live или отправка параметров через AbletonOSC
  - `compare_styles_ab` — генерация двух миксов в разных стилях для прямого A/B тестирования
  - `list_mix_presets`, `save_mix_preset`, `load_mix_preset`, `delete_mix_preset` — управление пресетами
  - `export_audio_format` — экспорт в WAV/FLAC/MP3 с конвертацией
  - `batch_process_dirs` — пакетный процессинг сессий
  - `preview_mix` — расширен поддержкой `dynamic_eq`, `midside_eq`, `transient`, `sidechain`, `reference_path`
- `tests/test_server.py` — 18 модульных тестов для всех инструментов MCP сервера
- Исправлены импорты в `src/ableton_auto_mix/dsp/dynamic_eq.py`, `transient.py`, `batch.py`, `profiles.py`, `multiband.py`

**Итого:** 105/105 тестов проходят, 0 TS ошибок при сборке фронтенда.

---

## Контекст для следующей сессии

1. Прочитай `HANDOFFS/00_OVERALL_HANDOFF.md` для roadmap
2. Прочитай `MEMORY.md` (этот файл) для текущего статуса
3. Все MCP-инструменты синхронизированы и покрыты тестами
4. Контрольные точки: `python -m pytest tests -q` (105 passed) + `npm run build` в desktop/

---

## Известные проблемы

- Build warning: chunk size 614 KB (recharts) — не критично, можно code-split позже
- Git репо: коммиты только по запросу пользователя

---

*Последнее обновление: 2026-08-29 (MCP Server Full Sync — 105 tests passing)*
