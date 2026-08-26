/**
 * Loose API types for the ableton-auto-mix backend.
 * The backend contract may vary slightly between versions — every field is
 * optional and the UI uses optional chaining everywhere so a missing field
 * never breaks rendering. Unknown extra fields are allowed via index
 * signatures.
 */

export interface StyleTargets {
  lufs?: number
  lra?: number
  peak_db?: number
  rms?: number
  [key: string]: unknown
}

export interface MixStyle {
  id: string
  name?: string
  targets?: StyleTargets
  [key: string]: unknown
}

export interface StylesResponse {
  styles?: MixStyle[]
  [key: string]: unknown
}

/** GET /api/style/{id} — profile, shape may vary */
export interface StyleProfile {
  id?: string
  name?: string
  targets?: StyleTargets
  spectral_curve?: SpectrumPoint[]
  target_curve?: SpectrumPoint[]
  bands?: SpectrumPoint[]
  balance?: Record<string, unknown>
  compression?: Record<string, unknown>
  fx?: Record<string, unknown>
  notes?: string
  [key: string]: unknown
}

export interface SpectrumPoint {
  freq?: number
  hz?: number
  db?: number
  value?: number
  [key: string]: unknown
}

export interface TrackMetrics {
  file?: string
  name?: string
  path?: string
  lufs?: number
  rms?: number
  peak_db?: number
  true_peak_db?: number
  peak?: number
  lra?: number
  width?: number
  stereo_width?: number
  bands?: SpectrumPoint[]
  spectrum?: SpectrumPoint[]
  [key: string]: unknown
}

/** POST /api/analyze */
export interface AnalysisResult {
  directory?: string
  tracks?: TrackMetrics[]
  metrics?: TrackMetrics[]
  [key: string]: unknown
}

/** POST /api/suggest */
export interface SuggestResult {
  style_id?: string
  style?: string
  reason?: string
  [key: string]: unknown
}

export interface ConflictPair {
  a?: string
  b?: string
  track_a?: string
  track_b?: string
  band?: string
  frequency_hz?: number
  freq?: number
  severity?: string | number
  gap_db?: number
  suggestion?: string
  fix?: string
  [key: string]: unknown
}

/** POST /api/conflicts */
export interface ConflictsResult {
  conflicts?: ConflictPair[]
  pairs?: ConflictPair[]
  [key: string]: unknown
}

export interface EqDelta {
  type?: string
  filter?: string
  freq?: number
  gain_db?: number
  gain?: number
  q?: number
  [key: string]: unknown
}

export interface TrackCorrection {
  file?: string
  name?: string
  volume_db?: number
  gain_db?: number
  pan?: number
  eq?: EqDelta[]
  eq_deltas?: EqDelta[]
  notes?: string
  [key: string]: unknown
}

/** POST /api/mix (dry_run) */
export interface MixResult {
  style?: string
  dry_run?: boolean
  corrections?: TrackCorrection[]
  tracks?: TrackCorrection[]
  master_notes?: string
  notes?: string
  [key: string]: unknown
}

/** One point of a match-EQ gain curve. */
export interface MatchEqPoint {
  hz?: number
  freq?: number
  gain_db?: number
  gain?: number
  [key: string]: unknown
}

/** match-EQ payload embedded in the preview response. */
export interface MatchEq {
  curve?: MatchEqPoint[]
  [key: string]: unknown
}

/** A single applied EQ correction, e.g. kick · mids · +2.3 dB. */
export interface AppliedEqCorrection {
  track?: string
  file?: string
  band?: string
  range_hz?: number[]
  delta_db?: number
  [key: string]: unknown
}

/** POST /api/preview */
export interface PreviewResult {
  output_path?: string
  path?: string
  /** Un-mastered render of the same length (only when render_before=true). */
  before_path?: string
  /** Applied match-EQ curve (only when reference_path was sent). */
  match_eq?: MatchEq
  eq_applied?: AppliedEqCorrection[]
  duration_s?: number
  duration?: number
  [key: string]: unknown
}

/** POST /api/match_eq */
export interface MatchEqCurveResult {
  curve?: MatchEqPoint[]
  [key: string]: unknown
}

/** POST /api/release */
export interface ReleaseResult {
  verdict?: 'ready' | 'needs_work' | string
  metrics?: {
    lufs?: number
    lra?: number
    true_peak_db?: number
    peak_db?: number
    rms?: number
    spectral_tilt?: number
    [key: string]: unknown
  }
  details?: Record<string, unknown>
  [key: string]: unknown
}

/** GET /api/waveform?path=...&points=N */
export interface WaveformResult {
  peaks?: number[]
  peak_count?: number
  duration_s?: number
  [key: string]: unknown
}
