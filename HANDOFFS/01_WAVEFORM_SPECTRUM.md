# Handoff: Task 1 — Waveform & Spectrum Visualization

> Status: PLANNED | Priority: HIGH | Complexity: MEDIUM
> Dependencies: None | Blocks: Tasks 3, 4

## Goal
Replace text-based metric tables with rich visualizations: real waveform canvas, spectrum analyzer, and conflict heatmap.

## Files to Create/Modify

### 1. `desktop/src/components/WaveformCanvas.tsx` (NEW)
Canvas-based waveform renderer.
- Props: `{ peaks: number[], width: number, height: number, color?: string, highlight?: { start: number, end: number } }`
- Draws from `GET /api/waveform?path=...&points=N`
- Two channels (L/R) stacked vertically
- Gradient fill: violet (#7c3aed) → fuchsia (#d946ef)
- Click-to-seek: onClick callback returns normalized position [0,1]
- Use `useRef` + `useEffect` + `canvas.getContext('2d')`
- Performance: throttle redraws, memoize peak data

### 2. `desktop/src/components/SpectrumAnalyzer.tsx` (NEW)
Real-time spectrum chart (recharts LineChart, logarithmic X-axis).
- Props: `{ measured: { hz: number, db: number }[], target?: { hz: number, db: number }[], conflicts?: BandConflict[] }`
- Log X-axis (20 Hz → 20 kHz), dB Y-axis
- Measured = solid violet line, Target = dashed fuchsia line
- Conflict zones highlighted with semi-transparent red overlay
- Use recharts `ReferenceArea` for conflict bands
- Existing `EqCurveChart.tsx` as reference for log-axis pattern

### 3. `desktop/src/components/ConflictHeatmap.tsx` (NEW)
Conflict matrix as colored grid.
- Props: `{ tracks: string[], conflicts: { track_a: string, track_b: string, band: string, gap_db: number }[] }`
- Grid: tracks × tracks, cell color = severity (green→yellow→red by gap_db)
- Diagonal = empty (self)
- Tooltip on hover: band name + gap_db
- Use CSS Grid, no external chart lib needed

### 4. `desktop/src/components/Dashboard.tsx` (MODIFY)
- Replace text conflict list with `ConflictHeatmap`
- Add `SpectrumAnalyzer` card below metrics table
- Keep metrics table but make it compact (horizontal scroll on mobile)

### 5. `desktop/src/components/MixPanel.tsx` (MODIFY)
- Add `WaveformCanvas` for preview output (after render)
- Add waveform for before_path (side-by-side or stacked)

### 6. `desktop/src/types.ts` (MODIFY)
- Add `WaveformResult`, `BandConflict`, `SpectrumPoint` types

### 7. `desktop/src/lib/api.ts` (MODIFY)
- Add `api.waveform(path, points)` function

## API Changes
None — all endpoints exist. Frontend consumes existing data.

## Test Strategy
- `WaveformCanvas`: renders without crash with 100 synthetic peaks, responds to click
- `SpectrumAnalyzer`: renders with measured+target arrays, log axis visible
- `ConflictHeatmap`: renders grid with 5 tracks, cells colored correctly
- Build: `npm.cmd run build` passes with no TS errors

## Acceptance Criteria
1. Dashboard shows spectrum chart (measured vs target) for analyzed tracks
2. Dashboard shows conflict heatmap instead of text list
3. MixPanel shows waveform for preview output
4. All visualizations responsive (min-width 1024px)
5. No performance regression (canvas redraw < 16ms)
