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

/** Interactive EQ band for the visual editor. */
export type EqBandType = 'bell' | 'low_shelf' | 'high_shelf' | 'low_cut' | 'high_cut'

export interface EqBand {
  id: number
  type: EqBandType
  freq: number     // Hz, 20..20000
  gain: number     // dB, -24..+24
  q: number        // 0.1..10
  enabled: boolean
  [key: string]: unknown
}

export interface TrackCorrection {
  file?: string
  name?: string
  role?: string
  volume_db?: number
  gain_db?: number
  pan?: number
  eq?: EqDelta[]
  eq_deltas?: EqDelta[]
  notes?: string
  spatial_config?: SpatialConfig
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

// ---------------------------------------------------------------------------
// Project save / load
// ---------------------------------------------------------------------------

/** Serializable project state (mirrors backend ProjectState dataclass). */
export interface ProjectState {
  version?: string
  directory?: string
  style?: string
  analyses?: TrackMetrics[]
  corrections?: TrackCorrection[]
  plan?: Record<string, unknown> | null
  preview_path?: string | null
  before_path?: string | null
  match_eq_curve?: MatchEqPoint[] | null
  conflicts?: ConflictPair[] | null
  selected_style_id?: string | null
  manual_gain?: Record<string, number> | null
  sidechain_db?: number | null
  name?: string
  created_at?: string
  updated_at?: string
  [key: string]: unknown
}

/** POST /api/project/save response */
export interface ProjectSaveResult {
  path?: string
  directory?: string
  updated_at?: string
  [key: string]: unknown
}

/** A recent project entry from GET /api/project/recent. */
export interface RecentProject {
  path?: string
  directory?: string
  name?: string
  style?: string
  updated_at?: string
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// Export to Ableton Live
// ---------------------------------------------------------------------------

/** Request payload for POST /api/export. */
export interface ExportPayload {
  corrections: TrackCorrection[]
  mode?: 'live' | 'file' | 'json'
  session_path?: string | null
  tempo?: number
}

/** POST /api/export response. */
export interface ExportResult {
  applied?: number
  skipped?: number
  errors?: string[]
  session_path?: string | null
  mode?: string
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// WebSocket Progress Streaming
// ---------------------------------------------------------------------------

/** WS message: progress update during an async operation. */
export interface ProgressMessage {
  type: 'progress'
  stage: string
  percent: number
  detail?: string
}

/** WS message: operation completed with result. */
export interface CompleteMessage {
  type: 'complete'
  result?: Record<string, unknown>
}

/** WS message: operation failed. */
export interface ErrorMessage {
  type: 'error'
  message: string
}

export type ProgressWsMessage = ProgressMessage | CompleteMessage | ErrorMessage

/** Response from an async endpoint (async_mode=true). */
export interface AsyncResponse {
  room_id: string
  estimated_duration_s?: number
}

// ---------------------------------------------------------------------------
// File Upload
// ---------------------------------------------------------------------------

/** POST /api/upload response. */
export interface UploadResult {
  path?: string
  name?: string
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// Multiband Compressor & Limiter
// ---------------------------------------------------------------------------

export interface MultibandBandConfig {
  freq_lo?: number
  freq_hi?: number
  threshold_db?: number
  ratio?: number
  attack_ms?: number
  release_ms?: number
  makeup_db?: number
  enabled?: boolean
  [key: string]: unknown
}

export interface MultibandConfig {
  enabled?: boolean
  mix?: number
  bands?: MultibandBandConfig[]
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// DSP: Dynamic EQ, Mid/Side EQ, Transient Shaper
// ---------------------------------------------------------------------------

export interface DynamicEqBand {
  freq_lo?: number
  freq_hi?: number
  threshold_db?: number
  ratio?: number
  attack_ms?: number
  release_ms?: number
  gain_db?: number
  q?: number
  mode?: string
  enabled?: boolean
  [key: string]: unknown
}

export interface DynamicEqConfig {
  enabled?: boolean
  mix?: number
  bands?: DynamicEqBand[]
  [key: string]: unknown
}

export interface EqNode {
  hz?: number
  gain_db?: number
  q?: number
  type?: string
  enabled?: boolean
  [key: string]: unknown
}

export interface MidSideEqConfig {
  enabled?: boolean
  mix?: number
  mid_nodes?: EqNode[]
  side_nodes?: EqNode[]
  [key: string]: unknown
}

export interface TransientConfig {
  attack_db?: number
  sustain_db?: number
  sensitivity?: number
  frequency_hz?: number
  mix?: number
  enabled?: boolean
  [key: string]: unknown
}

export interface DeEsserConfig {
  frequency_hz?: number
  threshold_db?: number
  ratio?: number
  max_reduction_db?: number
  attack_ms?: number
  release_ms?: number
  mode?: 'split' | 'wide' | string
  enabled?: boolean
  mix?: number
  [key: string]: unknown
}

export interface SpatialConfig {
  enabled?: boolean
  head_position?: number // 0.0 (Neck) -> 0.33 (Occiput/Back) -> 0.66 (Ear) -> 1.0 (Front)
  azimuth_deg?: number // -90 (L) to +90 (R)
  elevation_deg?: number // -45 to +45
  distance_m?: number // 0.3 to 3.0
  mix?: number // 0.0 to 1.0
  bass_mono?: boolean
  room_model?: 'none' | 'vocal_booth' | 'studio' | 'club' | 'cathedral'
  room_amount?: number
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// AI Recommendations & Batch Processing
// ---------------------------------------------------------------------------

export interface Recommendation {
  category?: string
  target?: string
  param?: string
  value?: unknown
  reason?: string
  confidence?: number
  [key: string]: unknown
}

export interface RecommendResult {
  recommendations?: Recommendation[]
  summary?: string
  role_map?: Record<string, string>
  [key: string]: unknown
}

export interface RoleDetection {
  name?: string
  role?: string
  confidence?: number
  [key: string]: unknown
}

export interface DetectRolesResult {
  roles?: RoleDetection[]
  [key: string]: unknown
}

export interface BatchPayload {
  directories: string[]
  style: string
  output_dir?: string
  max_duration?: number
  multiband?: MultibandConfig
  limiter_ceiling_db?: number
}

export interface BatchItem {
  directory?: string
  style?: string
  status?: string
  error?: string
  output_path?: string
  [key: string]: unknown
}

export interface BatchResult {
  total?: number
  completed?: number
  failed?: number
  items?: BatchItem[]
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// A/B Compare
// ---------------------------------------------------------------------------

export interface ABComparePayload {
  directory: string
  style_a: string
  style_b: string
  pattern?: string
  max_duration?: number
  multiband?: MultibandConfig
  limiter_ceiling_db?: number
  dynamic_eq?: DynamicEqConfig
  midside_eq?: MidSideEqConfig
  transient?: TransientConfig
}

export interface ABCompareResult {
  style_a?: string
  style_b?: string
  output_a?: string
  output_b?: string
  result_a?: PreviewResult
  result_b?: PreviewResult
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// Mix Presets
// ---------------------------------------------------------------------------

export interface MixPreset {
  name: string
  style?: string
  multiband?: MultibandConfig
  limiter_ceiling_db?: number
  dynamic_eq?: DynamicEqConfig
  midside_eq?: MidSideEqConfig
  transient?: TransientConfig
  sidechain?: SidechainConfig
  notes?: string
  created_at?: string
  [key: string]: unknown
}

export interface PresetListEntry {
  name: string
  path: string
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// Sidechain Config (Block 3)
// ---------------------------------------------------------------------------

export interface SidechainConfig {
  trigger?: string
  targets?: string[]
  amount_db?: number
  attack_ms?: number
  release_ms?: number
  band_filter?: [number, number] | null
  mix?: number
  enabled?: boolean
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// Export Formats
// ---------------------------------------------------------------------------

export interface ExportFormatPayload {
  input_path: string
  format: 'wav' | 'flac' | 'mp3'
  bit_depth?: string
  mp3_bitrate?: string
  flac_compression?: number
}

export interface ExportFormatResult {
  path?: string
  format?: string
  sample_rate?: number
  channels?: number
  duration_s?: number
  file_size_bytes?: number
  bit_depth?: string
  bitrate?: string
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// AI Reference Track Matcher
// ---------------------------------------------------------------------------

export interface ReferenceAnalysis {
  duration_s: number
  sample_rate: number
  lufs: number
  rms_db: number
  spectral_envelope: number[]
  freq_centers: number[]
  crest_factor_db: number
  stereo_width: number
  [key: string]: unknown
}
