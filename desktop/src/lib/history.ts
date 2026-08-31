interface HistoryEntry<T> {
  id: string
  timestamp: number
  label: string
  state: T
}

const MAX_HISTORY = 50

export class HistoryManager<T> {
  private past: HistoryEntry<T>[] = []
  private present: HistoryEntry<T>
  private future: HistoryEntry<T>[] = []

  constructor(initial: T) {
    this.present = {
      id: crypto.randomUUID(),
      timestamp: Date.now(),
      label: 'Initial',
      state: initial,
    }
  }

  push(state: T, label: string): void {
    this.past.push(this.present)
    if (this.past.length > MAX_HISTORY) {
      this.past.shift()
    }
    this.future = []
    this.present = {
      id: crypto.randomUUID(),
      timestamp: Date.now(),
      label,
      state,
    }
  }

  undo(): T | null {
    if (this.past.length === 0) return null
    this.future.push(this.present)
    this.present = this.past.pop()!
    return this.present.state
  }

  redo(): T | null {
    if (this.future.length === 0) return null
    this.past.push(this.present)
    this.present = this.future.pop()!
    return this.present.state
  }

  canUndo(): boolean {
    return this.past.length > 0
  }

  canRedo(): boolean {
    return this.future.length > 0
  }

  getTimeline(): HistoryEntry<T>[] {
    return [...this.past, this.present, ...this.future]
  }
}
