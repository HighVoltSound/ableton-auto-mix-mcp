import type {
  AnalysisResult,
  ConflictsResult,
  MatchEqCurveResult,
  MixResult,
  PreviewResult,
  ReleaseResult,
  StyleProfile,
  StylesResponse,
  SuggestResult,
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
}

export const api = {
  /** Cheap health probe — also returns styles, so it doubles as the styles list. */
  async health(): Promise<StylesResponse> {
    return request<StylesResponse>('/api/styles', undefined, 5_000)
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

  preview(payload: PreviewPayload): Promise<PreviewResult> {
    return post<PreviewResult>('/api/preview', payload)
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
}

/** Build a streamable audio URL for a rendered WAV on disk. */
export function audioUrl(path: string): string {
  return `${BACKEND_BASE}/api/audio?path=${encodeURIComponent(path)}`
}
