/**
 * Auto-update utilities using Tauri 2 updater plugin.
 *
 * In dev mode the updater is unavailable — all functions no-op gracefully.
 */
import { IS_TAURI } from './api'

export interface UpdateInfo {
  version: string
  currentVersion: string
  releaseNotes?: string
  date?: string
}

export interface UpdateState {
  available: boolean
  info: UpdateInfo | null
  downloading: boolean
  downloaded: boolean
  progress: number
  error: string | null
}

let cachedUpdate: Awaited<ReturnType<typeof import('@tauri-apps/plugin-updater').check>> | null = null

/**
 * Check for available updates. Returns the update info or null.
 * Silently returns null in dev mode or on errors.
 */
export async function checkForUpdate(): Promise<UpdateInfo | null> {
  if (!IS_TAURI) return null
  try {
    const { check } = await import('@tauri-apps/plugin-updater')
    const update = await check()
    if (!update) return null
    cachedUpdate = update
    return {
      version: update.version,
      currentVersion: update.currentVersion,
      releaseNotes: update.body ?? undefined,
      date: update.date ?? undefined,
    }
  } catch {
    return null
  }
}

/**
 * Download and install the update.
 * Calls onProgress with 0–100 percent.
 * Returns true on success, false on failure.
 */
export async function installUpdate(
  onProgress?: (percent: number) => void,
): Promise<boolean> {
  if (!IS_TAURI) return false
  try {
    const { check } = await import('@tauri-apps/plugin-updater')
    const update = cachedUpdate ?? (await check())
    if (!update) return false

    let downloaded = 0
    let total = 0

    await update.downloadAndInstall((event) => {
      switch (event.event) {
        case 'Started':
          total = event.data.contentLength ?? 0
          onProgress?.(0)
          break
        case 'Progress':
          downloaded += event.data.chunkLength
          onProgress?.(total > 0 ? Math.round((downloaded / total) * 100) : -1)
          break
        case 'Finished':
          onProgress?.(100)
          break
      }
    })

    return true
  } catch {
    return false
  }
}

/**
 * Restart the app to apply the update.
 */
export async function restartApp(): Promise<void> {
  if (!IS_TAURI) return
  try {
    // Use @tauri-apps/plugin-process if available, otherwise fallback
    const { relaunch } = await import('@tauri-apps/plugin-process')
    await relaunch()
  } catch {
    // fallback: just reload the window
    window.location.reload()
  }
}
