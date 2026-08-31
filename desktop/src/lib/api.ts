import type {
  ABComparePayload,
  ABCompareResult,
  AnalysisResult,
  AsyncResponse,
  BatchPayload,
  BatchResult,
  ConflictsResult,
  DetectRolesResult,
  ExportFormatPayload,
  ExportFormatResult,
  ExportPayload,
  ExportResult,
  MatchEqCurveResult,
  MixPreset,
  PresetListEntry,
  MixResult,
  PreviewResult,
  ProgressWsMessage,
  ProjectSaveResult,
  ProjectState,
  RecentProject,
  RecommendResult,
  ReleaseResult,
  StyleProfile,
  StylesResponse,
  SuggestResult,
  UploadResult,
  WaveformResult,
} from '@/types'

export const BACKEND_BASE = 'http://127.0.0.1:8787'
export const BACKEND_HINT = 'python -m ableton_auto_mix.api_app'

/**
 * True when the UI runs inside the Tauri webview. In that mode the Rust
 * shell already spawned (or attempted to spawn) the packaged backend
 * sidecar on 127.0.0.1:8787, so the "run python -m ..." hint is wrong.
 */
export const IS_TAURI =
  typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

export class ApiError extends Error {
  readonly offline: boolean
  constructor(message: string, offline = false) {
    super(message)
    this.name = 'ApiError'
    this.offline = offline
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
  timeoutMs = 120_000,
): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`${BACKEND_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
    })
    if (!res.ok) {
      let detail = `${res.status} ${res.statusText}`
      try {
        const body = await res.json()
        detail = body?.detail ?? body?.error ?? body?.message ?? detail
      } catch {
        /* body was not JSON — keep status text */
      }
      throw new ApiError(`Backend error: ${detail}`)
    }
    return (await res.json()) as T
  } catch (err) {
    if (err instanceof ApiError) throw err
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError('Request timed out')
    }
    // fetch network failure => backend not running.
    // Under Tauri the sidecar should already be up (spawned from Rust);
    // only surface the offline banner here, without the manual-start hint.
    throw new ApiError(
      IS_TAURI
        ? 'Backend is offline. Please restart MusicMixCode Desktop.'
        : `Backend not running: ${BACKEND_HINT}`,
      true,
    )
  } finally {
    clearTimeout(timer)
  }
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: JSON.stringify(body) })
}

export interface MixPayload {
  style: string
  directory: string
  dry_run?: boolean
  manual_gain?: Record<string, number>
  sidechain_db?: number
}

export interface PreviewPayload {
  style: string
  directory: string
  max_duration?: number
  manual_gain?: Record<string, number>
  sidechain_db?: number
  /** Path to a reference WAV for match-EQ (optional, new backend only). */
  reference_path?: string
  /** When true the response also contains before_path for A/B listening. */
  render_before?: boolean
  /** When true, returns room_id for WebSocket progress streaming. */
  async?: boolean
  /** Multiband compressor config. */
  multiband?: {
    enabled?: boolean
    mix?: number
    bands?: {
      freq_lo?: number
      freq_hi?: number
      threshold_db?: number
      ratio?: number
      makeup_db?: number
      enabled?: boolean
      [key: string]: unknown
    }[]
    [key: string]: unknown
  }
  /** True-peak limiter ceiling in dBTP. */
  limiter_ceiling_db?: number
  /** Dynamic EQ config. */
  dynamic_eq?: {
    enabled?: boolean
    mix?: number
    bands?: { freq_lo?: number; freq_hi?: number; threshold_db?: number; ratio?: number; gain_db?: number; mode?: string; enabled?: boolean; [key: string]: unknown }[]
    [key: string]: unknown
  }
  /** Mid/Side EQ config. */
  midside_eq?: {
    enabled?: boolean
    mix?: number
    mid_nodes?: { hz?: number; gain_db?: number; q?: number; type?: string; [key: string]: unknown }[]
    side_nodes?: { hz?: number; gain_db?: number; q?: number; type?: string; [key: string]: unknown }[]
    [key: string]: unknown
  }
  /** Transient shaper config. */
  transient?: {
    attack_db?: number
    sustain_db?: number
    sensitivity?: number
    frequency_hz?: number
    mix?: number
    enabled?: boolean
    [key: string]: unknown
  }
  /** Sidechain config. */
  sidechain?: {
    enabled?: boolean
    trigger?: string
    targets?: string[]
    amount_db?: number
    attack_ms?: number
    release_ms?: number
    mix?: number
    [key: string]: unknown
  }
  /** De-Esser config. */
  deesser?: {
    enabled?: boolean
    frequency_hz?: number
    threshold_db?: number
    ratio?: number
    max_reduction_db?: number
    mode?: string
    mix?: number
    [key: string]: unknown
  }
  /** Master EQ bands. */
  eq_bands?: {
    id?: number
    type?: string
    freq?: number
    gain?: number
    q?: number
    enabled?: boolean
    [key: string]: unknown
  }[]
  /** Per-track 3D Spatial configs. */
  spatial_configs?: Record<string, import('@/types').SpatialConfig>
  /** Per-track Transient configs. */
  transient_configs?: Record<string, import('@/types').TransientConfig>
  /** AI Reference match EQ bands. */
  reference_match_bands?: import('@/types').EqBand[]
}

export const api = {
  /** Cheap health probe — also returns styles, so it doubles as the styles list. */
  async health(): Promise<StylesResponse> {
    return request<StylesResponse>('/api/styles', undefined, 15_000)
  },

  /** Analyze target reference track. */
  analyzeReference(audioPath: string): Promise<import('@/types').ReferenceAnalysis> {
    return post<import('@/types').ReferenceAnalysis>('/api/reference/analyze', { audio_path: audioPath })
  },

  /** Compute matching EQ bands towards reference. */
  computeMatchEq(currentEnvelope: number[], targetEnvelope: number[], strength = 0.8): Promise<any[]> {
    return post<any[]>('/api/reference/match', {
      current_envelope: currentEnvelope,
      target_envelope: targetEnvelope,
      strength,
    })
  },

  /** Open exported ALS project directly in Ableton Live. */
  openAls(alsPath: string): Promise<{ status: string; opened: string }> {
    return post<{ status: string; opened: string }>('/api/export/open-als', { als_path: alsPath })
  },

  getStyles(): Promise<StylesResponse> {
    return request<StylesResponse>('/api/styles')
  },

  getStyle(id: string): Promise<StyleProfile> {
    return request<StyleProfile>(`/api/style/${encodeURIComponent(id)}`)
  },

  analyze(directory: string): Promise<AnalysisResult> {
    return post<AnalysisResult>('/api/analyze', { directory })
  },

  suggest(directory: string): Promise<SuggestResult> {
    return post<SuggestResult>('/api/suggest', { directory })
  },

  mix(payload: MixPayload): Promise<MixResult> {
    return post<MixResult>('/api/mix', payload)
  },

  preview(payload: PreviewPayload): Promise<PreviewResult | AsyncResponse> {
    return post<PreviewResult | AsyncResponse>('/api/preview', payload)
  },

  /**
   * Preview the match-EQ curve without rendering.
   * New endpoint — may be missing on older backends (surfaced as ApiError).
   */
  matchEq(mixWavPath: string, referencePath: string): Promise<MatchEqCurveResult> {
    return post<MatchEqCurveResult>('/api/match_eq', {
      mix_wav_path: mixWavPath,
      reference_path: referencePath,
    })
  },

  release(style: string, directory: string): Promise<ReleaseResult> {
    return post<ReleaseResult>('/api/release', { style, directory })
  },

  conflicts(directory: string): Promise<ConflictsResult> {
    return post<ConflictsResult>('/api/conflicts', { directory })
  },

  waveform(path: string, points = 600): Promise<WaveformResult> {
    return request<WaveformResult>(
      `/api/waveform?path=${encodeURIComponent(path)}&points=${points}`,
    )
  },

  /** Save project state to disk. */
  saveProject(state: ProjectState, savePath?: string): Promise<ProjectSaveResult> {
    return post<ProjectSaveResult>('/api/project/save', { state, path: savePath ?? null })
  },

  /** Load project state from disk. */
  loadProject(path: string): Promise<ProjectState> {
    return post<ProjectState>('/api/project/load', { path })
  },

  /** List recently saved projects. */
  recentProjects(maxCount = 10): Promise<{ projects: RecentProject[] }> {
    return request<{ projects: RecentProject[] }>(
      `/api/project/recent?max_count=${maxCount}`,
    )
  },

  /** Export corrections to Ableton Live (real-time) or as .als file. */
  exportCorrections(payload: ExportPayload): Promise<ExportResult> {
    return post<ExportResult>('/api/export', payload)
  },

  /** Get AI-powered mix recommendations for a directory. */
  recommend(directory: string, style?: string): Promise<RecommendResult> {
    return post<RecommendResult>('/api/recommend', { directory, style })
  },

  /** Detect instrument roles for all tracks in a directory. */
  detectRoles(directory: string): Promise<DetectRolesResult> {
    return post<DetectRolesResult>('/api/detect_roles', { directory })
  },

  /** Batch process multiple directories. */
  batchProcess(payload: BatchPayload): Promise<BatchResult> {
    return post<BatchResult>('/api/batch', payload)
  },

  /** A/B compare: render same tracks with two different styles. */
  abCompare(payload: ABComparePayload): Promise<ABCompareResult> {
    return post<ABCompareResult>('/api/preview/ab', payload)
  },

  /** List saved mix presets. */
  listPresets(): Promise<{ presets: PresetListEntry[] }> {
    return request<{ presets: PresetListEntry[] }>('/api/presets')
  },

  /** Save a mix preset. */
  savePreset(preset: MixPreset): Promise<{ saved: boolean; path: string }> {
    return post<{ saved: boolean; path: string }>('/api/presets/save', preset)
  },

  /** Load a mix preset by name. */
  loadPreset(name: string): Promise<MixPreset> {
    return post<MixPreset>('/api/presets/load', { name })
  },

  /** Delete a mix preset by name. */
  async deletePreset(name: string): Promise<{ deleted: boolean }> {
    const res = await fetch(
      `${BACKEND_BASE}/api/presets/${encodeURIComponent(name)}`,
      { method: 'DELETE' },
    )
    if (!res.ok) throw new Error(`Delete failed: ${res.status}`)
    return res.json()
  },

  /** Export a preview WAV to another format (wav/flac/mp3). */
  exportFormat(payload: ExportFormatPayload): Promise<ExportFormatResult> {
    return post<ExportFormatResult>('/api/export/format', payload)
  },

  /** Upload a WAV file to a target directory on the server. */
  async uploadFile(file: File, targetDir: string): Promise<UploadResult> {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(
      `${BACKEND_BASE}/api/upload?directory=${encodeURIComponent(targetDir)}`,
      { method: 'POST', body: formData },
    )
    if (!res.ok) {
      let detail = `${res.status} ${res.statusText}`
      try {
        const body = await res.json()
        detail = body?.detail ?? body?.error ?? body?.message ?? detail
      } catch {
        /* body was not JSON */
      }
      throw new ApiError(`Upload failed: ${detail}`)
    }
    return (await res.json()) as UploadResult
  },

  /**
   * Subscribe to progress updates via WebSocket for an async operation.
   * Returns a cleanup function that closes the connection.
   */
  subscribeProgress(
    roomId: string,
    handlers: {
      onProgress?: (stage: string, percent: number, detail?: string) => void
      onComplete?: (result?: Record<string, unknown>) => void
      onError?: (message: string) => void
    },
  ): () => void {
    const wsUrl = BACKEND_BASE.replace(/^http/, 'ws') + `/ws/progress/${roomId}`
    let ws: WebSocket | null = null
    let reconnectDelay = 500
    let closed = false

    const connect = () => {
      if (closed) return
      ws = new WebSocket(wsUrl)

      ws.onmessage = (event) => {
        try {
          const msg: ProgressWsMessage = JSON.parse(event.data)
          if (msg.type === 'progress') {
            handlers.onProgress?.(msg.stage, msg.percent, msg.detail)
          } else if (msg.type === 'complete') {
            handlers.onComplete?.(msg.result)
          } else if (msg.type === 'error') {
            handlers.onError?.(msg.message)
          }
        } catch {
          /* ignore malformed messages */
        }
      }

      ws.onclose = () => {
        if (!closed) {
          // Auto-reconnect with exponential backoff
          setTimeout(() => {
            reconnectDelay = Math.min(reconnectDelay * 2, 5000)
            connect()
          }, reconnectDelay)
        }
      }

      ws.onerror = () => {
        ws?.close()
      }
    }

    connect()

    return () => {
      closed = true
      ws?.close()
    }
  },
}

/** Build a streamable audio URL for a rendered WAV on disk. */
export function audioUrl(path: string): string {
  return `${BACKEND_BASE}/api/audio?path=${encodeURIComponent(path)}`
}
