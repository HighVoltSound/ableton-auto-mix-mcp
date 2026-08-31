# Handoff: Task 8 — Drag&Drop Audio Files

> Status: PLANNED | Priority: LOW | Complexity: LOW
> Depends on: None | Blocks: None

## Goal
Drop WAV files directly into the app as reference tracks or additional renders.

## Files to Create/Modify

### 1. `desktop/src/components/SetupScreen.tsx` (MODIFY)
- Expand existing drag&drop zone to accept actual files
- Extract directory path from dropped File objects (webkitRelativePath when available)
- Show dropped file names as chips
- Detect if drop contains a single WAV → offer as reference

### 2. `desktop/src/components/MixPanel.tsx` (MODIFY)
- Add drop zone for reference WAV (next to reference path input)
- On drop: auto-fill reference path field
- Visual indicator: glowing border on dragover

### 3. `desktop/src/hooks/useFileDrop.ts` (NEW)
```typescript
function useFileDrop(onDrop: (files: File[]) => void): {
  dragProps: { onDragOver, onDragLeave, onDrop };
  isDragging: boolean;
}
```
- Handles drag events
- Extracts file list
- Prevents default browser behavior

### 4. `desktop/src/lib/api.ts` (MODIFY)
- `api.uploadFile(file: File, targetDir: string)`: upload WAV to backend
  - Uses `POST /api/upload` with FormData
  - Returns server path

### 5. `src/ableton_auto_mix/api_app.py` (MODIFY)
- New endpoint: `POST /api/upload` (multipart form)
- Saves uploaded WAV to target directory
- Returns file path

### 6. `desktop/src/types.ts` (MODIFY)
- Add `UploadResult` type

## API Contract

### POST /api/upload
```
Content-Type: multipart/form-data
Body: file=<WAV>, directory=<target>

Response: { "path": "C:/renders/uploaded_track.wav", "name": "uploaded_track" }
```

## Test Strategy
- Drop single WAV → file uploaded, path shown
- Drop folder → all WAVs uploaded
- Drop non-audio → error message
- Network error → retry prompt

## Acceptance Criteria
1. WAV files can be dropped on SetupScreen or MixPanel
2. Files uploaded to backend directory
3. Reference path auto-fills on single-file drop
4. Visual feedback during drag (border glow)
5. Error handling for non-audio files
