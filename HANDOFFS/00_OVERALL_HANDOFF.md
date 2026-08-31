# MusicMixCode Desktop — Overall Handoff

> Generated: 2026-08-26 | Version: 0.4.0
> This document enables any session/agent to continue development from where we left off.

## Current State

### What Works
- **Backend**: FastAPI on port 8787, 11 endpoints + WS, 87 tests passing
- **Frontend**: Tauri 2 + React + Tailwind, dark theme, 15 components, i18n (ru/en)
- **Engine**: 11 style profiles, real EQ in preview, match-EQ, smart planner (mix vs mastering), Ableton export
- **Desktop**: Sidecar auto-starts, NSIS installer (37MB), works offline
- **Tests**: 87/87 passing (`python -m pytest tests -q`)

### Quick Start
```powershell
# Backend
cd ableton-auto-mix-mcp
python -m ableton_auto_mix.api_app  # http://127.0.0.1:8787

# Frontend (dev)
cd desktop
npm.cmd install
npm.cmd run tauri dev

# Build installer
scripts/build_all.ps1
```

## Task Roadmap

| # | Task | Status | Handoff Doc | Est. Hours |
|---|---|---|---|---|
| 1 | Waveform & Spectrum Visualization | **DONE** | `HANDOFFS/01_WAVEFORM_SPECTRUM.md` | 8-12h |
| 2 | Export to Ableton Live | **DONE** | `HANDOFFS/02_EXPORT_ABLETON.md` | 10-15h |
| 3 | Project Save/Load | **DONE** | `HANDOFFS/03_PROJECT_SAVE_LOAD.md` | 4-6h |
| 4 | Undo/Redo | **DONE** | `HANDOFFS/04_UNDO_REDO.md` | 3-4h |
| 5 | WebSocket Progress Streaming | **DONE** | `HANDOFFS/05_PROGRESS_STREAMING.md` | 6-8h |
| 6 | Auto-Update | PLANNED | `HANDOFFS/06_AUTO_UPDATE.md` | 4-6h |
| 7 | i18n (Russian/English) | **DONE** | `HANDOFFS/07_I18N.md` | 4-5h |
| 8 | Drag&Drop Audio Files | PLANNED | `HANDOFFS/08_DRAG_DROP_AUDIO.md` | 3-4h |

**Total estimated**: 42-60 hours

## Recommended Execution Order

```
Phase 1 (Core UX):     Task 1 → Task 3 → Task 4
Phase 2 (Integration): Task 2 → Task 5
Phase 3 (Polish):      Task 7 → Task 8 → Task 6
```

- Tasks 1, 3, 4 can run in parallel (no dependencies)
- Task 2 (Export) needs AbletonOSC testing
- Task 5 (Progress) enhances Tasks 1, 2
- Tasks 6, 7, 8 are independent polish

## Architecture Constraints

### Backend
- Python 3.10, no type hints > 3.10 (no `X | Y` in runtime, use `Optional[X]`)
- All new modules go in `src/ableton_auto_mix/`
- API endpoints in `api_app.py` — keep backward compat
- Tests in `tests/test_*.py`, use pytest + synthetic data (numpy/soundfile)
- Profiles in `styles/*.json` — never hardcode style data

### Frontend
- React 19, TypeScript strict, Tailwind 4 (CSS-first config)
- Dark theme: bg `#0a0a0f`, accent violet→fuchsia gradients
- Components in `src/components/`, shared UI in `ui.tsx`
- API client in `src/lib/api.ts` — all fetches go through it
- Types in `src/types.ts` — loose (all optional) for backend compat

### Build
- PyInstaller spec: `build_backend.spec` (139MB onedir, excludes torch/sklearn/matplotlib)
- Tauri: `desktop/src-tauri/` (Rust, tauri-plugin-shell for sidecar)
- Installer: NSIS only (WiX has permission issues on this machine)

## Key Files Index

```
ableton-auto-mix-mcp/
├── src/ableton_auto_mix/
│   ├── analyzer.py          # LUFS/spectrum analysis
│   ├── mixer.py             # Per-track corrections
│   ├── planner.py           # Mix vs mastering decisions
│   ├── preview.py           # Preview render + mastering chain
│   ├── reference.py         # Match-EQ
│   ├── profiles.py          # Style loader
│   ├── qa.py                # Conflicts + release check
│   ├── ableton_export.py    # Export engine (live + file mode)
│   ├── als_xml.py           # Minimal .als XML builder
│   ├── api_app.py           # FastAPI (11 endpoints + WS)
│   ├── ws_manager.py        # WebSocket connection manager
│   ├── server.py            # MCP server (legacy)
│   ├── cli.py               # CLI (legacy)
│   └── styles/*.json        # 11 style profiles
├── tests/
│   ├── test_smoke.py        # Core engine tests
│   ├── test_api_app.py      # API endpoint tests
│   ├── test_reference_preview.py  # Match-EQ + preview tests
│   ├── test_als_xml.py      # .als XML builder tests
│   ├── test_ableton_export.py  # Export engine tests
│   ├── test_api_export.py   # POST /api/export tests
│   └── test_ws_progress.py  # WebSocket + async endpoint tests
├── build_backend.spec       # PyInstaller config
├── scripts/
│   ├── backend_entry.py     # Sidecar launcher
│   └── build_all.ps1        # Full build pipeline
├── desktop/
│   ├── src/
│   │   ├── App.tsx          # Main state + routing
│   │   ├── components/      # UI components
│   │   │   ├── ExportDialog.tsx  # Export to Ableton modal
│   │   │   ├── ProgressBar.tsx   # Animated progress bar (WS streaming)
│   │   ├── i18n/              # Internationalization
│   │   │   ├── index.tsx      # I18nProvider, useLanguage() hook, t()
│   │   │   └── locales/       # en.json, ru.json
│   │   ├── lib/api.ts       # HTTP client
│   │   ├── lib/history.ts   # Undo/redo manager
│   │   └── types.ts         # TypeScript types
│   └── src-tauri/
│       ├── src/main.rs      # Sidecar lifecycle
│       ├── Cargo.toml       # Rust deps
│       └── tauri.conf.json  # App config
└── HANDOFFS/
    ├── 00_DOMAIN_MODEL.md   # Architecture overview
    ├── 01_WAVEFORM_SPECTRUM.md
    ├── 02_EXPORT_ABLETON.md
    ├── 03_PROJECT_SAVE_LOAD.md
    ├── 04_UNDO_REDO.md
    ├── 05_PROGRESS_STREAMING.md
    ├── 06_AUTO_UPDATE.md
    ├── 07_I18N.md
    └── 08_DRAG_DROP_AUDIO.md
```

## Memory

Key decisions stored in agent memory:
- `mem_mta489ad` — Desktop app architecture (Tauri + FastAPI)
- `mem_mta4t6wm` — Match-EQ, A/B player, installer build
- `mem_mta8bvbt` — Planner engine, PyInstaller optimization, sidecar
- `mem_mta8yp0a` — Domain model, handoffs, delegation pattern
- `mem_mtabpo51` — Task 1: Waveform/Spectrum/Heatmap visualization
- `mem_mta8y1k7` — Task 2: Export to Ableton Live (als_xml, ableton_export, ExportDialog)
- `mem_mtart8jv` — Task 4: Undo/Redo (history.ts, keyboard shortcuts, sidebar buttons)
- `mem_mtb7f0ll` — Task 5: WebSocket Progress Streaming (ws_manager, ProgressBar, async endpoints)
- `mem_mtb8i2k` — Task 7: i18n (I18nProvider, useLanguage, locale files, language toggle)

## Delegation Pattern

For any task, spawn a subagent with:
1. The specific handoff doc as context
2. The domain model (`00_DOMAIN_MODEL.md`) for architecture understanding
3. Current test count (verify: `python -m pytest tests -q`)
4. Build verification: `npm.cmd run build` in desktop/
5. No commits unless explicitly requested
