# MusicMixCode Desktop — MEMORY.md

> Читай этот файл в начале каждой сессии. Обновляй в конце.
> Формат: append-only лог решений. Не удаляй старое — добавляй новое с датой.

---

## Текущий статус

| Задача | Статус | Завершена |
|---|---|---|
| 1. Waveform & Spectrum Visualization | **DONE** | 2026-08-26 |
| 2. Export to Ableton Live | PLANNED | — |
| 3. Project Save/Load | PLANNED | — |
| 4. Undo/Redo | PLANNED | — |
| 5. WebSocket Progress Streaming | PLANNED | — |
| 6. Auto-Update | PLANNED | — |
| 7. i18n (ru/en) | PLANNED | — |
| 8. Drag&Drop Audio Files | PLANNED | — |

**Следующая задача:** Task 2 (Export to Ableton Live) или Task 3 (Project Save/Load) — независимы, можно выбрать.

---

## Решения сессий

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

## Контекст для следующей сессии

1. Прочитай `HANDOFFS/00_OVERALL_HANDOFF.md` для roadmap
2. Прочитай `MEMORY.md` (этот файл) для текущего статуса
3. Выбери задачу: Task 2 (Export) или Task 3 (Save/Load)
4. Прочитай соответствующий хенджофф

---

## Известные проблемы

- Build warning: chunk size 614 KB (recharts) — не критично, можно code-split позже
- Git репо: коммиты только по запросу пользователя

---

*Последнее обновление: 2026-08-26*
