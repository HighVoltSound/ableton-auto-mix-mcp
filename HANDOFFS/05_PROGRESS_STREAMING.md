# Handoff: Task 5 — WebSocket Progress Streaming

> Status: PLANNED | Priority: MEDIUM | Complexity: MEDIUM
> Depends on: None | Blocks: None

## Goal
Stream progress for long operations (preview render, analyze, export) instead of blocking.

## Files to Create/Modify

### 1. `src/ableton_auto_mix/ws_manager.py` (NEW)
WebSocket connection manager.
- `ConnectionManager` class (FastAPI WebSocket)
- Room-based: each operation gets a room ID
- `connect(ws, room_id)`, `disconnect(room_id)`, `broadcast(room_id, message)`
- Messages: `{ type: "progress", stage: str, percent: int, detail: str }`
- Messages: `{ type: "complete", result: dict }`
- Messages: `{ type: "error", message: str }`

### 2. `src/ableton_auto_mix/api_app.py` (MODIFY)
- Add WebSocket endpoint: `WS /ws/progress/{room_id}`
- Long operations (preview, analyze, mix, export) spawn background tasks
- Return `room_id` immediately, progress streams via WS
- Fallback: if WS unavailable, return sync response (backward compat)

### 3. `src/ableton_auto_mix/preview.py` (MODIFY)
- Add optional `progress_callback: Callable[[str, int], None]` parameter
- Call at key stages: "loading tracks" (10%), "applying EQ" (30%), "sidechain" (50%), "mastering" (70%), "rendering" (90%), "done" (100%)

### 4. `src/ableton_auto_mix/analyzer.py` (MODIFY)
- Add progress callback per file analyzed

### 5. `desktop/src/lib/api.ts` (MODIFY)
- Add `api.subscribeProgress(roomId, onProgress, onComplete, onError)` using native WebSocket
- Auto-reconnect with exponential backoff
- Returns cleanup function

### 6. `desktop/src/components/MixPanel.tsx` (MODIFY)
- Replace sync spinner with progress bar during preview/export
- Show stage name: "Applying EQ...", "Rendering... 60%"
- Smooth animation between progress updates

### 7. `desktop/src/components/ProgressBar.tsx` (NEW)
- Animated progress bar component
- Props: `{ percent: number, stage: string, indeterminate?: boolean }`
- Gradient fill, smooth transitions

## API Contract

### WS /ws/progress/{room_id}
Client connects after receiving room_id from sync endpoint.
```json
// Server → Client
{ "type": "progress", "stage": "applying_eq", "percent": 35, "detail": "Track 4/12" }
{ "type": "progress", "stage": "rendering", "percent": 80 }
{ "type": "complete", "result": { "output_path": "...", "duration_s": 28 } }
{ "type": "error", "message": "File not found: ..." }
```

### POST /api/preview (modified)
```json
Request: { ...same..., "async": true }
Response: { "room_id": "abc-123", "estimated_duration_s": 15 }
```

## Test Strategy
- Unit: ConnectionManager connects/broadcasts/disconnects
- Integration: start preview → receive progress events → receive complete
- Fallback: async=false returns sync response as before
- WebSocket reconnection: simulate disconnect → verify auto-reconnect

## Acceptance Criteria
1. Preview shows real-time progress (stage + percent)
2. Export shows progress during AbletonOSC calls
3. Graceful fallback when WS unavailable
4. No memory leaks (connections cleaned up)
5. Progress updates at least every 500ms during active work
