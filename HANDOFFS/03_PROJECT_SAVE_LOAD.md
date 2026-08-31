# Handoff: Task 3 — Project Save/Load

> Status: PLANNED | Priority: MEDIUM | Complexity: LOW
> Depends on: Task 1 (waveform data for full save)

## Goal
Save analysis results, mix state, and history to disk. Load previous sessions.

## Files to Create/Modify

### 1. `src/ableton_auto_mix/project.py` (NEW)
Project state serializer/deserializer.
- `ProjectState` dataclass:
  ```python
  @dataclass
  class ProjectState:
      version: str = "0.3"
      directory: str = ""
      style: str = ""
      analyses: list[dict] = field(default_factory=list)  # serialized TrackAnalysis
      corrections: list[dict] = field(default_factory=list)
      plan: dict | None = None
      preview_path: str | None = None
      before_path: str | None = None
      match_eq_curve: list[dict] | None = None
      created_at: str = ""
      updated_at: str = ""
  ```
- `save_project(state: ProjectState, path: str) -> str`: writes JSON `.mmc.json`
- `load_project(path: str) -> ProjectState`: reads + validates
- `auto_save(state: ProjectState, directory: str)`: saves to `<directory>/.musicmixcode.json`
- `list_recent_projects(max_count: int = 10) -> list[dict]`: scans common locations

### 2. `src/ableton_auto_mix/api_app.py` (MODIFY)
- `POST /api/project/save { state }` → saves to auto location, returns path
- `POST /api/project/load { path }` → loads and returns state
- `GET /api/project/recent` → returns list of recent projects

### 3. `desktop/src/components/SetupScreen.tsx` (MODIFY)
- Add "Load Project" button
- Show recent projects list (from localStorage + API)
- Auto-detect `.musicmixcode.json` in selected directory

### 4. `desktop/src/components/SaveDialog.tsx` (NEW)
- Simple save dialog: project name, location
- Auto-save indicator in sidebar

### 5. `desktop/src/App.tsx` (MODIFY)
- Add project state to global state
- Auto-save on significant changes (after analyze, after mix)
- Load project on startup if argument provided

### 6. `desktop/src/lib/api.ts` (MODIFY)
- Add `api.saveProject(state)`, `api.loadProject(path)`, `api.recentProjects()`

## File Format

```json
{
  "version": "0.3",
  "directory": "C:/renders/mytrack",
  "style": "breaks",
  "analyses": [{ "name": "KICK", "lufs": -10.2, "role": "kick", ... }],
  "corrections": [{ "track": "KICK", "volume_db": -1.5, ... }],
  "plan": { "mix_actions": [...], "master_actions": [...] },
  "preview_path": "C:/renders/preview_breaks.wav",
  "created_at": "2026-08-26T14:00:00Z",
  "updated_at": "2026-08-26T14:05:00Z"
}
```

## Test Strategy
- Save/load roundtrip: save state → load → verify all fields
- Auto-save: verify file created in directory
- Recent projects: verify list sorted by date
- Migration: load v0.2 file → upgrade gracefully

## Acceptance Criteria
1. Save creates `.musicmixcode.json` in project directory
2. Load restores full state (analyses, corrections, plan, preview)
3. Recent projects shown in SetupScreen
4. Auto-save triggers after analyze/mix operations
5. Version migration handles missing fields gracefully
