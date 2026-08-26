import { useEffect, useMemo, useRef, useState } from 'react'
import {
  CircleCheck,
  Loader2,
  Play,
  ShieldCheck,
  SlidersHorizontal,
  TriangleAlert,
} from 'lucide-react'
import type {
  AppliedEqCorrection,
  MatchEqPoint,
  MixResult,
  PreviewResult,
  ReleaseResult,
} from '@/types'
import type { MatchEqCurveResult } from '@/types'
import { api, audioUrl } from '@/lib/api'
import { trackName } from './Dashboard'
import { ABPlayer } from './ABPlayer'
import type { ABPlayerHandle } from './ABPlayer'
import { EqCurveChart } from './EqCurveChart'
import { WaveformCanvas } from './WaveformCanvas'
import { Badge, Button, Card, EmptyState, SectionTitle, Slider, Spinner } from './ui'

export interface PreviewOptions {
  render_before?: boolean
  reference_path?: string
}

export interface MixPanelProps {
  hasAnalysis: boolean
  selectedStyle: string | null
  mixResult: MixResult | null
  mixing: boolean
  onMix: () => void

  manualGain: Record<string, number>
  onManualGainChange: (file: string, db: number) => void

  sidechainDb: number
  onSidechainChange: (db: number) => void

  preview: PreviewResult | null
  previewing: boolean
  onPreview: (opts: PreviewOptions) => void

  release: ReleaseResult | null
  checkingRelease: boolean
  onReleaseCheck: () => void
}

const fmtDb = (v: unknown): string =>
  typeof v === 'number' && Number.isFinite(v)
    ? `${v > 0 ? '+' : ''}${v.toFixed(1)} dB`
    : '—'

const fmtPan = (v: unknown): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
  if (Math.abs(v) < 0.01) return 'C'
  return `${v > 0 ? 'R' : 'L'}${Math.round(Math.abs(v) * 100)}`
}

export function MixPanel(props: MixPanelProps) {
  const {
    hasAnalysis,
    selectedStyle,
    mixResult,
    mixing,
    onMix,
    manualGain,
    onManualGainChange,
    sidechainDb,
    onSidechainChange,
    preview,
    previewing,
    onPreview,
    release,
    checkingRelease,
    onReleaseCheck,
  } = props

  const corrections = useMemo(
    () => mixResult?.corrections ?? mixResult?.tracks ?? [],
    [mixResult],
  )

  const previewPath = preview?.output_path ?? preview?.path
  const beforePath = preview?.before_path

  const abRef = useRef<ABPlayerHandle>(null)

  /* ---------- waveform ---------- */
  const [wavePeaks, setWavePeaks] = useState<number[]>([])
  useEffect(() => {
    if (!previewPath) {
      setWavePeaks([])
      return
    }
    let cancelled = false
    api
      .waveform(previewPath, 600)
      .then((r) => {
        if (!cancelled) setWavePeaks(r.peaks ?? [])
      })
      .catch(() => {
        if (!cancelled) setWavePeaks([])
      })
    return () => {
      cancelled = true
    }
  }, [previewPath])

  const handleWaveSeek = (ratio: number) => {
    abRef.current?.seekTo(ratio)
  }

  /* ---------- reference / match-EQ controls ---------- */
  const [referencePath, setReferencePath] = useState('')
  const [applyMatchEq, setApplyMatchEq] = useState(false)
  const [abEnabled, setAbEnabled] = useState(true)

  /* curve fetched via /api/match_eq (preview without render) */
  const [curveLoading, setCurveLoading] = useState(false)
  const [fetchedCurve, setFetchedCurve] = useState<MatchEqPoint[] | null>(null)
  const [curveError, setCurveError] = useState<string | null>(null)
  const appliedCurve = preview?.match_eq?.curve

  /* elapsed timer while rendering (previews can take 15–20 s) */
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    if (!previewing) return
    const started = Date.now()
    const t = setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    )
    return () => clearInterval(t)
  }, [previewing])

  const runPreview = () => {
    setElapsed(0)
    onPreview({
      render_before: abEnabled || undefined,
      reference_path:
        applyMatchEq && referencePath.trim() ? referencePath.trim() : undefined,
    })
  }

  const showCurve = async () => {
    if (!previewPath || !referencePath.trim()) return
    setCurveLoading(true)
    setCurveError(null)
    try {
      const r: MatchEqCurveResult = await api.matchEq(previewPath, referencePath.trim())
      setFetchedCurve(r.curve ?? [])
    } catch (err) {
      setFetchedCurve(null)
      setCurveError(
        err instanceof Error
          ? err.message.includes('404')
            ? 'match-EQ endpoint not available on this backend'
            : err.message
          : 'Failed to compute match-EQ curve',
      )
    } finally {
      setCurveLoading(false)
    }
  }

  const verdict = release?.verdict
  const ready = verdict === 'ready'
  const needsWork = verdict === 'needs_work'

  if (!hasAnalysis) {
    return (
      <EmptyState
        icon={<SlidersHorizontal size={36} />}
        message="Nothing to mix yet"
        hint="Run Analyze in Setup first — the mixer needs per-track metrics."
      />
    )
  }

  return (
    <div className="space-y-6 pt-10">
      <SectionTitle
        title="Mix"
        subtitle={
          selectedStyle
            ? `Style target: ${selectedStyle} · dry-run corrections below`
            : 'Pick a style first, then run the auto-mixer.'
        }
        right={
          <div className="flex gap-2">
            <Button onClick={onMix} disabled={mixing || !selectedStyle}>
              {mixing ? <Spinner /> : null} Auto-mix (dry run)
            </Button>
          </div>
        }
      />

      {/* Manual gain + sidechain controls */}
      <Card className="p-5">
        <h3 className="mb-4 text-sm font-semibold text-white">
          Your overrides{' '}
          <span className="font-normal text-white/40">
            — applied on top of the auto-mix when you run Preview / Release check
          </span>
        </h3>
        <div className="grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
          <Slider
            label="Sidechain ducking"
            value={sidechainDb}
            min={-10}
            max={0}
            step={0.5}
            unit=" dB"
            onChange={onSidechainChange}
            format={(v) => `${v.toFixed(1)} dB`}
          />
          {corrections.map((c) => {
            const file = c.file ?? c.name ?? ''
            const base = typeof c.volume_db === 'number' ? c.volume_db : (c.gain_db ?? 0)
            const extra = manualGain[file] ?? 0
            return (
              <Slider
                key={file}
                label={`Manual gain · ${trackName(c)}`}
                value={extra}
                min={-12}
                max={12}
                step={0.5}
                onChange={(v) => onManualGainChange(file, v)}
                format={(v) => {
                  const total = base + v
                  return `${v >= 0.05 || v <= -0.05 ? `${v > 0 ? '+' : ''}${v.toFixed(1)}` : '±0'} dB → auto ${total >= 0 ? '+' : ''}${total.toFixed(1)} dB`
                }}
              />
            )
          })}
          {corrections.length === 0 && (
            <p className="text-xs text-white/35">
              Run "Auto-mix (dry run)" to get per-track correction sliders.
            </p>
          )}
        </div>
      </Card>

      {/* Dry-run corrections table */}
      {corrections.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-white/10 text-[11px] uppercase tracking-wider text-white/40">
                  <th className="px-5 py-3 font-medium">Track</th>
                  <th className="px-4 py-3 font-medium">Volume</th>
                  <th className="px-4 py-3 font-medium">Pan</th>
                  <th className="px-4 py-3 font-medium">EQ deltas</th>
                  <th className="px-4 py-3 font-medium">Notes</th>
                </tr>
              </thead>
              <tbody>
                {corrections.map((c, i) => {
                  const eq = c.eq ?? c.eq_deltas ?? []
                  return (
                    <tr
                      key={(c.file ?? c.name ?? '') + i}
                      className="border-b border-white/[0.05] last:border-0 hover:bg-white/[0.02]"
                    >
                      <td className="max-w-[220px] truncate px-5 py-3 font-medium text-white/85">
                        {trackName(c)}
                      </td>
                      <td className="px-4 py-3 font-mono text-white/70">
                        {fmtDb(typeof c.volume_db === 'number' ? c.volume_db : c.gain_db)}
                      </td>
                      <td className="px-4 py-3 font-mono text-white/70">{fmtPan(c.pan)}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1.5">
                          {(Array.isArray(eq) ? eq : []).map((e, j) => {
                            const freq = e.freq ?? (e as Record<string, unknown>).frequency_hz
                            const g = e.gain_db ?? e.gain
                            const label =
                              typeof freq === 'number' && typeof g === 'number'
                                ? `${freq >= 1000 ? `${(freq / 1000).toFixed(freq % 1000 === 0 ? 0 : 1)}k` : freq}Hz ${g > 0 ? '+' : ''}${g}`
                                : `EQ #${j + 1}`
                            return (
                              <Badge key={j} tone={typeof g === 'number' && g < 0 ? 'amber' : 'violet'}>
                                {label}
                              </Badge>
                            )
                          })}
                          {!Array.isArray(eq) || eq.length === 0 ? (
                            <span className="text-xs text-white/25">—</span>
                          ) : null}
                        </div>
                      </td>
                      <td className="max-w-[240px] px-4 py-3 text-xs leading-relaxed text-white/45">
                        {c.notes ?? ''}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {(mixResult?.master_notes ?? mixResult?.notes) && (
            <div className="border-t border-white/[0.07] bg-white/[0.02] px-5 py-3 text-xs leading-relaxed text-white/50">
              <span className="font-medium text-white/70">Master notes: </span>
              {mixResult.master_notes ?? mixResult.notes}
            </div>
          )}
        </Card>
      )}

      {/* Preview + Release */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card className="flex flex-col p-5">
          <h3 className="mb-3 text-sm font-semibold text-white">Preview mix</h3>
          <p className="mb-4 text-xs leading-relaxed text-white/45">
            Renders volumes + pans into a summed stereo preview, normalized to the
            style's target loudness, and streams it back for listening.
          </p>

          {/* Reference / match-EQ / A/B options */}
          <div className="mb-4 space-y-3 rounded-xl border border-white/[0.07] bg-black/25 p-3">
            <label className="block">
              <span className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-white/45">
                Reference WAV (optional — enables match-EQ)
              </span>
              <input
                type="text"
                value={referencePath}
                onChange={(e) => setReferencePath(e.target.value)}
                placeholder="C:\path\to\reference.wav"
                aria-label="Path to reference WAV for match-EQ"
                className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 font-mono text-xs text-white/90 placeholder:text-white/25 focus:border-violet-400/60 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
              />
            </label>

            <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
              <label className="flex cursor-pointer select-none items-center gap-2 text-xs text-white/65">
                <input
                  type="checkbox"
                  checked={applyMatchEq}
                  onChange={(e) => setApplyMatchEq(e.target.checked)}
                  disabled={!referencePath.trim()}
                  className="h-3.5 w-3.5 accent-violet-500"
                />
                Apply match-EQ
              </label>
              <label className="flex cursor-pointer select-none items-center gap-2 text-xs text-white/65">
                <input
                  type="checkbox"
                  checked={abEnabled}
                  onChange={(e) => setAbEnabled(e.target.checked)}
                  className="h-3.5 w-3.5 accent-violet-500"
                />
                A/B before/after
              </label>
              <Button
                variant="outline"
                className="ml-auto px-3 py-1.5 text-xs"
                onClick={() => void showCurve()}
                disabled={curveLoading || !previewPath || !referencePath.trim()}
                title={
                  previewPath
                    ? 'Preview the match-EQ gain curve (no re-render)'
                    : 'Run Preview mix first — the curve is computed against its output'
                }
              >
                {curveLoading ? <Spinner /> : null} Show curve
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={runPreview} disabled={previewing || !selectedStyle}>
              {previewing ? (
                <>
                  <Spinner /> Rendering…
                </>
              ) : (
                <>
                  <Play size={15} /> Preview mix
                </>
              )}
            </Button>
            {preview?.duration_s != null && (
              <Badge>{preview.duration_s.toFixed(1)} s</Badge>
            )}
          </div>

          {/* long-render status: previews can easily take 15–20 s */}
          {previewing && (
            <div
              role="status"
              aria-live="polite"
              className="mt-3 flex items-center gap-2 rounded-xl border border-violet-400/25 bg-violet-500/[0.08] px-3 py-2 text-xs text-violet-200"
            >
              <Loader2 size={14} className="animate-spin" />
              Rendering{abEnabled ? ' before + after' : ''}…
              {elapsed > 0 && <span className="font-mono text-violet-300/70">{elapsed}s</span>}
              <span className="text-violet-200/50">— this can take 15–20 s, hang tight.</span>
            </div>
          )}

          {/* Waveform canvas */}
          {wavePeaks.length > 0 && (
            <div className="mt-4 rounded-xl border border-white/10 bg-black/40 p-3">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-white/45">
                Preview waveform
              </h4>
              <WaveformCanvas
                peaks={wavePeaks}
                height={48}
                onSeek={handleWaveSeek}
              />
            </div>
          )}

          {/* Applied match-EQ curve from the preview response */}
          {appliedCurve && appliedCurve.length > 0 && (
            <div className="mt-4">
              <div className="mb-1 flex items-center justify-between">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-white/45">
                  Applied match-EQ
                </h4>
                <Badge tone="violet">{appliedCurve.length} bands</Badge>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/30 p-2">
                <EqCurveChart curve={appliedCurve} />
              </div>
            </div>
          )}

          {/* Applied EQ corrections chips */}
          {(preview?.eq_applied?.length ?? 0) > 0 && (
            <div className="mt-4">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-white/45">
                Applied EQ corrections
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {(preview?.eq_applied ?? []).map((c: AppliedEqCorrection, i) => (
                  <EqChip key={`${c.track}-${i}`} c={c} />
                ))}
              </div>
            </div>
          )}

          {/* Fetched curve from POST /api/match_eq */}
          {curveError && (
            <p role="alert" className="mt-3 text-xs text-red-300">
              {curveError}
            </p>
          )}
          {fetchedCurve && !curveError && (
            <div className="mt-4">
              <div className="mb-1 flex items-center justify-between">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-white/45">
                  Match-EQ curve{' '}
                  <span className="font-normal normal-case text-white/35">(preview vs reference)</span>
                </h4>
                <button
                  type="button"
                  onClick={() => setFetchedCurve(null)}
                  className="text-[10px] text-white/30 hover:text-white/60"
                >
                  hide
                </button>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/30 p-2">
                <EqCurveChart curve={fetchedCurve} />
              </div>
            </div>
          )}

          {/* Player: synchronized A/B or single fallback */}
          {beforePath && previewPath ? (
            <div className="mt-4 rounded-xl border border-white/10 bg-black/40 p-3">
              <ABPlayer ref={abRef} key={previewPath} beforePath={beforePath} afterPath={previewPath} />
              <p className="mt-2 truncate font-mono text-[10px] text-white/30">
                A/B · GET /api/audio?path=…{beforePath.slice(-40)}
              </p>
            </div>
          ) : (
            previewPath && (
              <div className="mt-4 rounded-xl border border-white/10 bg-black/40 p-3">
                {/* biome-ignore lint/a11y/useMediaCaption: instrumental preview */}
                <audio
                  controls
                  preload="none"
                  src={audioUrl(previewPath)}
                  className="w-full"
                />
                <p className="mt-2 truncate font-mono text-[10px] text-white/30">
                  GET /api/audio?path=…{previewPath.slice(-48)}
                </p>
              </div>
            )
          )}
        </Card>

        <Card className="flex flex-col p-5">
          <h3 className="mb-3 text-sm font-semibold text-white">Release check</h3>
          <p className="mb-4 text-xs leading-relaxed text-white/45">
            Runs the label-style quality gate: LUFS, LRA, true peak, RMS and
            spectral tilt against top-label targets.
          </p>
          <div className="flex items-center gap-3">
            <Button variant="outline" onClick={onReleaseCheck} disabled={checkingRelease}>
              {checkingRelease ? (
                <>
                  <Spinner /> Checking…
                </>
              ) : (
                <>
                  <ShieldCheck size={15} /> Release check
                </>
              )}
            </Button>
          </div>

          {(ready || needsWork) && (
            <div className="mt-4 space-y-3">
              <div
                role="status"
                aria-live="polite"
                className={`flex items-center justify-center gap-3 rounded-2xl border px-4 py-5 text-center ${
                  ready
                    ? 'border-emerald-400/30 bg-emerald-500/10'
                    : 'border-amber-400/30 bg-amber-500/10'
                }`}
              >
                {ready ? (
                  <CircleCheck size={26} className="text-emerald-300" />
                ) : (
                  <TriangleAlert size={26} className="text-amber-300" />
                )}
                <span
                  className={`text-xl font-bold tracking-tight ${
                    ready ? 'text-emerald-300' : 'text-amber-300'
                  }`}
                >
                  {ready ? 'READY' : 'NEEDS WORK'}
                </span>
              </div>

              {release?.metrics && (
                <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                  <MetricChip label="LUFS" value={release.metrics.lufs} digits={1} />
                  <MetricChip label="LRA" value={release.metrics.lra} digits={1} />
                  <MetricChip label="True peak" value={release.metrics.true_peak_db ?? release.metrics.peak_db} digits={1} unit="dBTP" />
                  <MetricChip label="RMS" value={release.metrics.rms} digits={1} />
                  <MetricChip label="Tilt" value={release.metrics.spectral_tilt} digits={2} />
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

/** Chip like `kick · mids · +2.3 dB`, tolerant to missing fields. */
function EqChip({ c }: { c: AppliedEqCorrection }) {
  const track = c.track ?? c.file?.split(/[\\/]/).pop() ?? '?'
  const range = Array.isArray(c.range_hz) ? c.range_hz : []
  const band =
    c.band ??
    (range.length === 2 &&
    typeof range[0] === 'number' &&
    typeof range[1] === 'number'
      ? `${fmtHzShort(range[0])}–${fmtHzShort(range[1])}`
      : '?')
  const delta =
    typeof c.delta_db === 'number'
      ? `${c.delta_db > 0 ? '+' : ''}${c.delta_db.toFixed(1)} dB`
      : '—'
  const up = typeof c.delta_db === 'number' && c.delta_db > 0
  return (
    <Badge tone={up ? 'violet' : 'neutral'}>
      {track} · {band} · {delta}
    </Badge>
  )
}

const fmtHzShort = (hz: number): string =>
  hz >= 1000 ? `${(hz / 1000).toFixed(hz % 1000 === 0 ? 0 : 1)}k` : `${Math.round(hz)}`

function MetricChip({
  label,
  value,
  digits = 1,
  unit = '',
}: {
  label: string
  value: number | undefined
  digits?: number
  unit?: string
}) {
  return (
    <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-center">
      <div className="font-mono text-sm text-white/85">
        {typeof value === 'number' && Number.isFinite(value)
          ? `${value.toFixed(digits)}${unit ? ` ${unit}` : ''}`
          : '—'}
      </div>
      <div className="mt-0.5 text-[10px] uppercase tracking-wider text-white/35">
        {label}
      </div>
    </div>
  )
}
