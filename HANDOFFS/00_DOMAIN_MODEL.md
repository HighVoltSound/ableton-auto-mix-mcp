# MusicMixCode Desktop — Domain Model & Architecture

> Generated: 2026-08-26 | Version: 0.3.0

## Bounded Contexts

```
┌─────────────────────────────────────────────────────────────┐
│                    MUSICMIXCODE DESKTOP                      │
├─────────────┬──────────────┬──────────────┬─────────────────┤
│  ANALYSIS   │    MIXING    │  MASTERING   │   PRESENTATION  │
│  Context    │   Context    │   Context    │    Context      │
├─────────────┼──────────────┼──────────────┼─────────────────┤
│ analyzer.py │ mixer.py     │ preview.py   │ App.tsx         │
│ profiles.py │ planner.py   │ reference.py │ components/*    │
│ qa.py       │              │              │ api.ts          │
│             │              │              │ types.ts        │
└─────────────┴──────────────┴──────────────┴─────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
    ┌──────────────────────────────────────────────────────┐
    │                   api_app.py (FastAPI)                │
    │            HTTP + WebSocket transport layer           │
    └──────────────────────────────────────────────────────┘
         │
         ▼
    ┌──────────────────────────────────────────────────────┐
    │              Tauri 2 (Rust + React)                   │
    │         Sidecar lifecycle + Desktop shell             │
    └──────────────────────────────────────────────────────┘
```

## Core Aggregates

### TrackAnalysis (value object)
- `name: str` — filename stem
- `role: str` — detected role (kick/snare/bass/lead/vocal/pad/hats/other)
- `lufs: float` — integrated loudness
- `lra: float` — loudness range
- `true_peak_dbtp: float` — true peak
- `stereo_width: float` — 0=mono, 1=decorrelated
- `bandwidth_db: dict[str, float]` — energy per band (sub_bass, bass, low_mids, mids, upper_mids, presence, brilliance)

### StyleProfile (value object)
- `id: str` — techno, hip_hop, etc.
- `targets: dict` — lufs, lra, tempo_range, stereo_width
- `frequency_balance: dict` — target curve per band
- `track_balance: dict` — expected role → gain relationship
- `compression: dict` — mastering compressor settings
- `sidechain: dict` — kick/snare ducking params

### TrackCorrection (value object)
- `track: str` — filename
- `role: str`
- `volume_db: float`
- `pan: float | None`
- `band_corrections: list[BandCorrection]`
- `reasons: list[str]`

### Plan (aggregate root)
- `mix_actions: list[Action]` — per-track corrections
- `master_actions: list[Action]` — bus-level corrections
- `summary: dict`

### Action (value object)
- `kind: str` — gain/eq/pan/width/loudness
- `params: dict` — filter params, gain, etc.
- `reason: str` — human-readable justification

## Data Flow

```
User drops WAV files
       │
       ▼
  POST /api/analyze {directory}
       │
       ▼
  analyzer.analyze_render_dir()
  → list[TrackAnalysis]
       │
       ├──→ Dashboard (metrics table, spectrum chart)
       │
       ▼
  POST /api/suggest {directory}
  → suggested style + ranked alternatives
       │
       ▼
  StylePicker → user selects style
       │
       ▼
  POST /api/mix {style, directory, dry_run, use_planner}
  → list[TrackCorrection] + Plan
       │
       ├──→ MixPanel (per-track sliders, plan visualization)
       │
       ▼
  POST /api/preview {style, directory, render_before, reference_path, use_planner}
  → mastered WAV + before WAV + Plan + match_eq curve
       │
       ├──→ ABPlayer (before/after)
       ├──→ EqCurveChart (match-eq curve)
       │
       ▼
  POST /api/release {style, directory}
  → verdict (ready/needs_work) + metrics
```

## File Inventory

### Backend (Python)
| File | Lines | Responsibility |
|---|---|---|
| `analyzer.py` | ~130 | LUFS/LRA/spectrum/stereo analysis via librosa+pyloudnorm |
| `mixer.py` | ~470 | Computes per-track corrections vs style profile |
| `planner.py` | ~410 | Decision engine: mix vs mastering classification |
| `preview.py` | ~650 | Preview mix render + mastering chain (EQ/sidechain/limit) |
| `reference.py` | ~280 | Match-EQ: compute + apply correction curve from reference |
| `profiles.py` | ~130 | Style profile loader from JSON |
| `qa.py` | ~200 | Conflict analysis + release readiness check |
| `api_app.py` | ~480 | FastAPI wrapper: 10 endpoints |
| `cli.py` | ~220 | CLI interface (backward compat) |
| `server.py` | ~510 | MCP server (backward compat) |
| `ableton_client.py` | ~140 | AbletonOSC integration |

### Frontend (React/TypeScript)
| File | Responsibility |
|---|---|
| `App.tsx` | State management, routing, API calls |
| `Sidebar.tsx` | Navigation (Setup/Styles/Dashboard/Mix) |
| `SetupScreen.tsx` | Directory input + drag&drop + recent paths |
| `StylePicker.tsx` | Style card grid + suggest button |
| `Dashboard.tsx` | Metrics table + spectrum chart + conflicts |
| `MixPanel.tsx` | Dry-run corrections + manual gain + preview + release |
| `ABPlayer.tsx` | Before/after synchronized player |
| `EqCurveChart.tsx` | Match-EQ curve visualization |
| `ui.tsx` | Shared components (Card/Button/Badge/Slider/Spinner) |
| `types.ts` | Loose TypeScript types for API responses |
| `lib/api.ts` | HTTP client + audio URL helper |

### Infrastructure
| File | Responsibility |
|---|---|
| `build_backend.spec` | PyInstaller spec (139MB onedir) |
| `scripts/backend_entry.py` | Sidecar launcher |
| `scripts/build_all.ps1` | Full build pipeline |
| `desktop/src-tauri/src/main.rs` | Tauri sidecar lifecycle |
| `desktop/src-tauri/Cargo.toml` | Rust dependencies |
| `desktop/src-tauri/tauri.conf.json` | App config + bundle |

## API Contract (v1)

All responses are JSON. `application/json` content type.

### GET /api/styles
```json
{ "styles": [{ "id": "techno", "name": "Techno / Club", "targets": { "lufs": -8.0, "lra": 3.5 } }] }
```

### POST /api/analyze
```json
Request:  { "directory": "C:/renders", "pattern": "*.wav" }
Response: { "directory": "...", "tracks": [{ "name": "kick", "lufs": -10.2, ... }], "elapsed_s": 0.8 }
```

### POST /api/suggest
```json
Request:  { "directory": "C:/renders" }
Response: { "suggested_style": "techno", "label": "Techno", "ranked": [...], "elapsed_s": 1.2 }
```

### POST /api/mix
```json
Request:  { "style": "techno", "directory": "C:/renders", "dry_run": true, "use_planner": true, "manual_gain": { "bass": -2.0 }, "sidechain_db": -3.0 }
Response: { "track_corrections": [...], "plan": { "mix_actions": [...], "master_actions": [...] }, "master_notes": [...] }
```

### POST /api/preview
```json
Request:  { "style": "breaks", "directory": "C:/renders", "max_duration": 30, "render_before": true, "reference_path": "C:/ref.wav", "use_planner": true }
Response: { "output_path": "...", "before_path": "...", "duration_s": 28.2, "peak_db": -1.5, "eq_applied": [...], "match_eq": { "curve": [...] }, "plan": {...} }
```

### POST /api/release
```json
Request:  { "style": "breaks", "directory": "C:/renders" }
Response: { "verdict": "ready", "metrics": [{ "metric": "lufs", "measured": -8.2, "target": -8.0, "status": "ok" }] }
```

### POST /api/conflicts
```json
Request:  { "directory": "C:/renders" }
Response: { "conflicts_found": 3, "conflicts": [{ "track_a": "bass", "track_b": "kick", "band": "sub_bass", "gap_db": 1.4 }] }
```

### POST /api/match_eq
```json
Request:  { "mix_wav_path": "...", "reference_path": "..." }
Response: { "curve": [{ "hz": 44.7, "gain_db": 1.2 }], "gain_range": [-6, 6] }
```

### GET /api/audio?path=...
Binary WAV stream. `audio/wav` content type.

### GET /api/waveform?path=...&points=600
```json
{ "peaks": [0.01, 0.83, ...], "peak_count": 600, "duration_s": 2.0 }
```

## Style Profiles

11 JSON profiles in `src/ableton_auto_mix/styles/`:
techno, hip_hop, pop, lo_fi, ambient, balanced, trance, breaks, dubstep, drum_n_bass, trap

Each defines: frequency_balance (target dB per band), track_balance (role → relative gain), compression (threshold/ratio/attack/release), sidechain (kick/snare ducking).
