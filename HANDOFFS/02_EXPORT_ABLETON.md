# Handoff: Task 2 — Export to Ableton Live

> Status: PLANNED | Priority: HIGH | Complexity: HIGH
> Dependencies: None | Blocks: None

## Goal
Apply computed corrections back to Ableton Live session: track volumes, pan, EQ (via stock plugins), and return a ready-to-mix state.

## Files to Create/Modify

### 1. `src/ableton_auto_mix/ableton_export.py` (NEW)
Export engine that translates corrections into Ableton actions.
- `export_to_ableton(corrections: list[TrackCorrection], plan: Plan, session_path: str | None = None) -> ExportResult`
- Uses existing `ableton_client.py` (AbletonOSC) for Live integration
- Translates corrections to AbletonOSC calls:
  - `volume_db` → `set_track_volume(track_name, db_to_ableton_gain(vol))`
  - `pan` → `set_track_pan(track_name, pan)`
  - `band_corrections` → `set_track_eq(track_name, bands)` (using EQ Eight device)
- Creates Ableton session snapshot (if no Live connection: exports .als XML)
- Returns `ExportResult { applied: int, skipped: int, errors: list, session_path: str }`

### 2. `src/ableton_auto_mix/als_xml.py` (NEW)
Minimal Ableton .als XML builder for offline export.
- Builds XML matching Ableton 11/12 Session format
- Creates track elements with Volume, Pan, and EQ Eight devices
- `build_session(corrections, tempo, time_signature) -> str` returns XML string
- Write to `.als` file (actually .xml renamed, Ableton can import)

### 3. `src/ableton_auto_mix/api_app.py` (MODIFY)
- New endpoint: `POST /api/export { corrections, plan, session_path?, mode: "live"|"file" }`
- `mode=live`: use AbletonOSC to apply in real-time
- `mode=file`: generate .als XML file, return path
- Validates corrections format before export

### 4. `desktop/src/components/MixPanel.tsx` (MODIFY)
- Add "Export to Ableton" button (visible after mix/preview)
- Two options: "Apply to Live" (if connected) / "Save .als file"
- Show export result (applied count, errors)

### 5. `desktop/src/components/ExportDialog.tsx` (NEW)
- Modal dialog for export options
- Shows corrections summary before applying
- Progress indicator during export
- Success/error state with details

### 6. `desktop/src/lib/api.ts` (MODIFY)
- Add `api.export(data)` function

## API Contract

### POST /api/export
```json
Request: {
  "corrections": [TrackCorrection],
  "plan": Plan,
  "session_path": "C:/project/MySong.als",  // optional
  "mode": "live" | "file"
}
Response: {
  "applied": 8,
  "skipped": 0,
  "errors": [],
  "session_path": "C:/project/MySong_modified.als"
}
```

## Test Strategy
- `test_als_xml.py`: generate session XML, validate structure
- `test_ableton_export.py`: mock AbletonOSC, verify correct calls
- `test_api_export.py`: API endpoint with mocked export
- Integration: export real corrections → verify .als file readable

## Acceptance Criteria
1. Export generates valid .als XML (verifiable in Ableton)
2. Live export applies volume/pan/EQ via AbletonOSC
3. UI shows export dialog with summary
4. Errors are caught and reported (missing tracks, connection failures)
5. Works without Ableton Live running (file mode)
