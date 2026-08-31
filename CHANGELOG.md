# Changelog

All notable changes to MusicMixCode Desktop.

## [0.1.0] - 2026-08-30

### Desktop App (Tauri 2 + React)

- **Waveform Editor** — visual track import with per-track volume/pan controls
- **Mix Panel** — corrections table, DSP chain cards, style selector
- **Live Spectrum** — real-time FFT visualization via WebAudio AnalyserNode
- **3D Spatializer** — binaural head-tracking positioning (per-track azimuth/elevation)
- **EQ Editor** — interactive frequency curve with draggable handles
- **Reference Player** — A/B reference playback with loop
- **Export Dialog** — Ableton .als, JSON (universal), or audio format conversion (WAV/FLAC/MP3)
- **Drag & Drop** — import WAV files directly into the app
- **Undo/Redo** — full edit history
- **Auto-Update** — via GitHub Releases with Tauri updater
- **i18n** — English & Russian
- **Dark Theme** — glassmorphism UI with violet/indigo accents

### Backend

- **18 Style Profiles** — techno, trance, breaks, dubstep, drum_n_bass, trap, lo_fi, pop, hip_hop, rnb, rock, metal, jazz, funk, country, classical, ambient, balanced
- **Preview Render** — full mastering chain: sidechain, HPF, mud-cut, soft-clipper, true-peak limiter
- **RAG Reference Store** — 24 seeded references, auto-saves after each preview
- **AI Recommendations** — RAG-powered suggestions for compression, sidechain, EQ
- **JSON Export** — universal format for any DAW
- **Ableton Export** — .als session with audio tracks, gain, pan, EQ Eight
- **Structured Logging** — Timer, @timed, @log_call decorators
- **Graceful Error Handling** — skip坏 files instead of crash

### Quality

- **160+ Tests** — core units (16), RAG (13), preview harness (9)
- **CI/CD** — GitHub Actions (Python 3.10–3.12 + ruff + mypy + frontend build)
- **Pre-commit** — ruff lint/format, mypy
- **Cross-platform Build** — Windows NSIS + macOS DMG (Intel + ARM)
