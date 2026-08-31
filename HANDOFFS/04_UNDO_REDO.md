# Handoff: Task 4 — Undo/Redo

> Status: DONE | Priority: MEDIUM | Complexity: LOW
> Depends on: Task 3 (project state structure)

## Goal
History stack for parameter changes. Undo any mix/preview action.

## Files to Create/Modify

### 1. `desktop/src/lib/history.ts` (NEW)
Generic undo/redo manager.
```typescript
interface HistoryEntry<T> {
  id: string;
  timestamp: number;
  label: string;
  state: T;
}

class HistoryManager<T> {
  private past: HistoryEntry<T>[] = [];
  private present: HistoryEntry<T>;
  private future: HistoryEntry<T>[] = [];

  constructor(initial: T);
  push(state: T, label: string): void;
  undo(): T | null;
  redo(): T | null;
  canUndo(): boolean;
  canRedo(): boolean;
  getTimeline(): HistoryEntry<T>[];
}
```

### 2. `desktop/src/App.tsx` (MODIFY)
- Wrap global state in `HistoryManager`
- Track: style selection, manual gain changes, sidechain, directory, reference path
- Keyboard shortcuts: Ctrl+Z (undo), Ctrl+Shift+Z (redo)
- Expose `undo()`, `redo()`, `canUndo()`, `canRedo()` via context

### 3. `desktop/src/components/Sidebar.tsx` (MODIFY)
- Add undo/redo buttons (disabled state when not available)
- Show history timeline on hover/click (optional)

### 4. `desktop/src/components/MixPanel.tsx` (MODIFY)
- Manual gain slider changes push to history
- Sidechain slider changes push to history
- Label entries: "Bass gain → -2 dB", "Sidechain → -4 dB"

## Test Strategy
- Unit test HistoryManager: push/undo/redo/overflow
- Integration: change gain → undo → verify old value restored
- Keyboard: Ctrl+Z triggers undo

## Acceptance Criteria
1. Ctrl+Z undoes last parameter change
2. Ctrl+Shift+Z redoes
3. Undo/redo buttons in sidebar reflect state
4. History survives re-analyze (reset on new directory)
5. Max history: 50 entries (older pruned)
