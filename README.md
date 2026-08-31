# MusicMixCode Desktop

> 🇷🇺 [Читать на русском](README.ru.md)

[![CI](https://github.com/HighVoltSound/ableton-auto-mix-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/HighVoltSound/ableton-auto-mix-mcp/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

![Desktop App](assets/demo_waveform.png)

AI-powered mixing and mastering — both as an MCP server for AI agents and a standalone desktop app.

## What's Inside

| Layer | Stack | What it does |
|-------|-------|-------------|
| **Desktop App** | Tauri 2 + React + TypeScript | Visual mixing interface with waveform, EQ, 3D spatializer |
| **Backend API** | FastAPI (Python 3.10+) | REST API for analysis, preview render, export |
| **MCP Server** | stdio/OSC | 13 tools for AI agents (opencode, Claude Code) |
| **DSP Engine** | numpy + scipy | Full mastering chain: EQ, compression, sidechain, limiting |

## Desktop Features

- **Waveform Editor** — visual track import, drag & drop, volume/pan per track
- **Style Profiles** — 18 genre presets (techno, hip-hop, ambient, jazz, metal, R&B...)
- **AI Recommendations** — RAG-powered suggestions for compression, sidechain, EQ
- **Master Preview** — render mastered mix to WAV with full DSP chain
- **Live Spectrum** — real-time FFT visualization during playback
- **3D Spatializer** — binaural head-tracking positioning per track
- **EQ Editor** — interactive frequency curve with drag handles
- **Export** — Ableton Live (.als), JSON (universal), or WAV/FLAC/MP3 format conversion
- **i18n** — English & Russian
- **Auto-Update** — via GitHub Releases

## Quick Start

### Desktop App

```bash
# Windows
cd desktop
npm install
npm run tauri dev    # development
npm run tauri build  # release build → src-tauri/target/release/bundle/

# macOS (requires Xcode CLI tools)
cd desktop
npm install
npm run tauri dev
npm run tauri build  # → DMG
```

### Backend Only (API / MCP Server)

```bash
pip install -e ".[dev]"
python -m ableton_auto_mix          # MCP server
python -m uvicorn ableton_auto_mix.api_app:app --port 8787  # REST API
```

## Architecture

```
desktop/src-tauri/
  ├── src/main.rs          # Tauri entry point
  └── tauri.conf.json      # App config, bundling, auto-update

desktop/src/
  ├── components/
  │   ├── WaveformEditor.tsx     # Track waveform + per-track controls
  │   ├── MixPanel.tsx           # Main mixing interface
  │   ├── LiveSpectrum.tsx       # Real-time FFT via WebAudio
  │   ├── Spatializer3D.tsx      # Binaural positioning
  │   ├── EqCurveChart.tsx       # Interactive EQ editor
  │   ├── ReferencePlayer.tsx    # A/B reference playback
  │   ├── ExportDialog.tsx       # Export to Ableton/JSON/Audio
  │   └── ui/                    # Glassmorphism UI primitives
  ├── lib/api.ts           # FastAPI client
  └── i18n/                # en.json, ru.json

src/ableton_auto_mix/
  ├── analyzer.py          # LUFS/LRA, spectrum, stereo width
  ├── mixer.py             # Style-based corrections engine
  ├── preview.py           # Mastering chain render
  ├── reference_store.py   # RAG reference database
  ├── ai_recommender.py    # AI mixing recommendations
  ├── ableton_export.py    # .als + JSON export
  ├── logging_utils.py     # Structured logging
  ├── ableton_client.py    # AbletonOSC bridge
  ├── dsp/                 # Biquad filters, EQ, compression, spatial
  └── styles/              # 18 genre profiles (JSON)
```

## Style Profiles (18)

Electronic: `techno`, `trance`, `breaks`, `dubstep`, `drum_n_bass`, `trap`, `lo_fi`
Pop/Hip-Hop: `pop`, `hip_hop`, `rnb`
Rock/Metal: `rock`, `metal`
Jazz/Soul: `jazz`, `funk`, `country`, `classical`
Ambient/Cinematic: `ambient`
General: `balanced`

Each defines: target LUFS/LRA, spectral curve (6 bands), per-role levels, HPF, sidechain, compression, FX recommendations.

## MCP Tools

| Tool | Description |
|------|-------------|
| `list_styles` | List all available style profiles |
| `get_style(name)` | Full profile details |
| `get_ableton_status` | Check Ableton Live connection |
| `analyze_audio(path)` | Metrics for one WAV |
| `analyze_render_dir(dir)` | Metrics for all renders |
| `auto_mix(style, dir, dry_run)` | Corrections (dry-run or apply) |
| `suggest_style(dir)` | Best-fitting style for material |
| `preview_mix(style, dir)` | Render mastered preview WAV |
| `analyze_conflicts(dir)` | Frequency clashes between tracks |
| `release_check(style, dir)` | LUFS/TP/LRA vs label targets |

## Export Modes

| Mode | Description |
|------|-------------|
| **Ableton (.als)** | Full session with audio tracks, gain, pan, EQ Eight |
| **JSON** | Universal format for any DAW via scripting |
| **Apply to Live** | Push corrections directly via AbletonOSC |
| **Audio** | WAV (16/24/32-bit), FLAC, MP3 (128–320kbps) |

## Tests

```bash
python -m pytest tests/test_core_units.py -q    # 16 unit tests
python -m pytest tests/test_rag.py -q           # 13 RAG tests
python -m pytest tests/test_preview_harness.py -q  # 9 e2e tests
```

## CI/CD

- **CI** (`.github/workflows/ci.yml`) — Python 3.10–3.12, ruff, mypy, frontend build
- **Release** (`.github/workflows/release.yml`) — Windows NSIS + macOS DMG (Intel + ARM)
- **Pre-commit** — ruff lint/format, mypy

To trigger a release build:

```bash
git tag v0.1.0
git push origin v0.1.0
# → GitHub Actions builds Windows .exe + macOS .dmg
# → Creates draft release with artifacts
```

## License

[MIT](LICENSE) © 2026 MusicMixCode / HighVoltSound
