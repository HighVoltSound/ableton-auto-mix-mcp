import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import {
  CircleCheck,
  Download,
  FolderOpen,
  Loader2,
  Play,
  ShieldCheck,
  SlidersHorizontal,
  TriangleAlert,
} from 'lucide-react'
import type {
  AppliedEqCorrection,
  EqBand,
  MatchEqPoint,
  MixResult,
  MultibandConfig,
  PreviewResult,
  ReleaseResult,
  SpatialConfig,
} from '@/types'
import type { MatchEqCurveResult } from '@/types'
import { api, audioUrl } from '@/lib/api'
import { trackName } from './Dashboard'
import { ABPlayer } from './ABPlayer'
import type { ABPlayerHandle } from './ABPlayer'
import { CorrectionsTable } from './mix/CorrectionsTable'
import { DspChainCard } from './mix/DspChainCard'
import { ExportDialog } from './ExportDialog'
import { PresetDialog } from './PresetDialog'
import { HeadSpatializerModal } from './HeadSpatializerModal'
const EqCurveChart = lazy(() => import('./EqCurveChart').then(m => ({ default: m.EqCurveChart })))
const EqEditor = lazy(() => import('./EqEditor').then(m => ({ default: m.EqEditor })))
import { ReferenceMatcher } from './ReferenceMatcher'
import { ProgressBar } from './ProgressBar'
import { LiveSpectrum } from './LiveSpectrum'
import { WaveformCanvas } from './WaveformCanvas'
import { Badge, Button, Card, EmptyState, SectionTitle, Slider, Spinner } from './ui'
import { useLanguage } from '@/i18n'

export interface PreviewOptions {
  render_before?: boolean
  reference_path?: string
  multiband?: MultibandConfig
  limiter_ceiling_db?: number
  dynamic_eq?: import('@/types').DynamicEqConfig
  midside_eq?: import('@/types').MidSideEqConfig
  transient?: import('@/types').TransientConfig
  sidechain?: import('@/types').SidechainConfig
  deesser?: import('@/types').DeEsserConfig
  eq_bands?: import('@/types').EqBand[]
  spatial_configs?: Record<string, SpatialConfig>
  transient_configs?: Record<string, import('@/types').TransientConfig>
  reference_match_bands?: import('@/types').EqBand[]
  onProgress?: (stage: string, percent: number, detail?: string) => void
  onComplete?: (result: PreviewResult) => void
  onError?: (message: string) => void
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

  styles: Array<{ id: string; name?: string }>
  directory: string
}

export function MixPanel(props: MixPanelProps) {
  const { t } = useLanguage()
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
    styles,
    directory,
  } = props

  const corrections = useMemo(
    () => mixResult?.corrections ?? mixResult?.tracks ?? [],
    [mixResult],
  )

  const previewPath = preview?.output_path ?? preview?.path
  const beforePath = preview?.before_path

  const abRef = useRef<ABPlayerHandle>(null)
  const audioRef = useRef<HTMLAudioElement>(null)

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

  /* progress tracking for async preview */
  const [progressStage, setProgressStage] = useState('')
  const [progressPercent, setProgressPercent] = useState(0)
  const [progressDetail, setProgressDetail] = useState('')
  const cleanupWs = useRef<(() => void) | null>(null)

  useEffect(() => {
    return () => { cleanupWs.current?.() }
  }, [])

  const runPreview = () => {
    setElapsed(0)
    setProgressStage('')
    setProgressPercent(0)
    setProgressDetail('')
    cleanupWs.current?.()
    onPreview({
      render_before: abEnabled || undefined,
      reference_path:
        applyMatchEq && referencePath.trim() ? referencePath.trim() : undefined,
      multiband: multibandConfig,
      limiter_ceiling_db: limiterCeiling,
      dynamic_eq: dynamicEqConfig,
      midside_eq: midsideEqConfig,
      transient: transientConfig,
      sidechain: sidechainConfig,
      deesser: deesserConfig,
      eq_bands: eqBands.length > 0 ? eqBands : undefined,
      spatial_configs: Object.keys(spatialConfigs).length > 0 ? spatialConfigs : undefined,
      transient_configs: Object.keys(transientConfigs).length > 0 ? transientConfigs : undefined,
      reference_match_bands: referenceMatchBands.length > 0 ? referenceMatchBands : undefined,
      onProgress: (stage, percent, detail) => {
        setProgressStage(stage)
        setProgressPercent(percent)
        setProgressDetail(detail ?? '')
      },
      onComplete: () => {
        setProgressStage('')
        setProgressPercent(0)
      },
      onError: () => {
        setProgressStage('')
        setProgressPercent(0)
      },
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

  /* ---------- export dialog ---------- */
  const [showExport, setShowExport] = useState(false)
  const [showPresetDialog, setShowPresetDialog] = useState(false)

  /* ---------- EQ band editor ---------- */
  const [eqBands, setEqBands] = useState<EqBand[]>([])

  /* ---------- multiband compressor + limiter ---------- */
  const [multibandEnabled, setMultibandEnabled] = useState(true)
  const [mbMix, setMbMix] = useState(1.0)
  const [mbBands, setMbBands] = useState([
    { freq_lo: 0, freq_hi: 120, threshold_db: -16, ratio: 2.5, makeup_db: 1.0, enabled: true },
    { freq_lo: 120, freq_hi: 2500, threshold_db: -14, ratio: 2.0, makeup_db: 0.0, enabled: true },
    { freq_lo: 2500, freq_hi: 8000, threshold_db: -12, ratio: 1.8, makeup_db: 0.0, enabled: true },
    { freq_lo: 8000, freq_hi: 20000, threshold_db: -14, ratio: 2.0, makeup_db: 0.5, enabled: true },
  ])
  const [limiterCeiling, setLimiterCeiling] = useState(-1.0)

  const multibandConfig: MultibandConfig | undefined = multibandEnabled
    ? { enabled: true, mix: mbMix, bands: mbBands }
    : undefined

  /* ---------- DSP: dynamic EQ, mid/side EQ, transient shaper ---------- */
  const [dynEqEnabled, setDynEqEnabled] = useState(false)
  const [dynEqMix, setDynEqMix] = useState(1.0)
  const [dynEqBands, setDynEqBands] = useState([
    { freq_lo: 200, freq_hi: 500, threshold_db: -18, ratio: 2.0, gain_db: 0, mode: 'compress', enabled: true },
  ])
  const dynamicEqConfig = dynEqEnabled
    ? { enabled: true, mix: dynEqMix, bands: dynEqBands }
    : undefined

  const [msEqEnabled, setMsEqEnabled] = useState(false)
  const [msMidNodes, setMsMidNodes] = useState([
    { hz: 100, gain_db: 0, q: 1, type: 'low_shelf', enabled: true },
  ])
  const [msSideNodes, setMsSideNodes] = useState([
    { hz: 8000, gain_db: 0, q: 1, type: 'high_shelf', enabled: true },
  ])
  const midsideEqConfig = msEqEnabled
    ? { enabled: true, mix: 1.0, mid_nodes: msMidNodes, side_nodes: msSideNodes }
    : undefined

  const [trEnabled, setTrEnabled] = useState(false)
  const [trMix, setTrMix] = useState(1.0)
  const [trAttack, setTrAttack] = useState(0.0)
  const [trSustain, setTrSustain] = useState(0.0)
  const transientConfig = trEnabled
    ? { enabled: true, mix: trMix, attack_db: trAttack, sustain_db: trSustain }
    : undefined

  /* ---------- Sidechain ---------- */
  const [scEnabled, setScEnabled] = useState(false)
  const [scTrigger, setScTrigger] = useState('kick')
  const [scAmount, setScAmount] = useState(-3.0)
  const [scAttack, setScAttack] = useState(5.0)
  const [scRelease, setScRelease] = useState(90.0)
  const [scMix, setScMix] = useState(1.0)
  const sidechainConfig = scEnabled
    ? { enabled: true, trigger: scTrigger, targets: ['bass', 'sub_bass', 'wobble'], amount_db: scAmount, attack_ms: scAttack, release_ms: scRelease, mix: scMix }
    : undefined

  /* ---------- De-Esser ---------- */
  const [deessEnabled, setDeessEnabled] = useState(false)
  const [deessFreq, setDeessFreq] = useState(6500)
  const [deessThreshold, setDeessThreshold] = useState(-20.0)
  const [deessMaxReduction, setDeessMaxReduction] = useState(10.0)
  const [deessMode, setDeessMode] = useState<'split' | 'wide'>('split')
  const [deessMix, setDeessMix] = useState(1.0)
  const deesserConfig: import('@/types').DeEsserConfig | undefined = deessEnabled
    ? {
        enabled: true,
        frequency_hz: deessFreq,
        threshold_db: deessThreshold,
        max_reduction_db: deessMaxReduction,
        mode: deessMode,
        mix: deessMix,
      }
    : undefined

  /* ---------- 3D Head Spatializer ---------- */
  const [spatialConfigs, setSpatialConfigs] = useState<Record<string, SpatialConfig>>({})
  const [selectedSpatialTrack, setSelectedSpatialTrack] = useState<{ file: string; name: string } | null>(null)

  useEffect(() => {
    if (mixResult?.corrections) {
      setSpatialConfigs((prev) => {
        const next = { ...prev }
        for (const c of mixResult.corrections ?? []) {
          const file = c.file ?? c.name ?? ''
          if (file && !next[file] && c.spatial_config) {
            next[file] = c.spatial_config
          }
        }
        return next
      })
    }
  }, [mixResult])

  const getSpatialLabel = (cfg?: SpatialConfig) => {
    if (!cfg) return '3D Позиция'
    const pos = cfg.head_position ?? 0.5
    const elev = cfg.elevation_deg ?? 0
    if (elev >= 40 || pos >= 0.9) return `👑 Над головой (+${Math.round(elev)}°)`
    if (pos < 0.2) return '🔴 Шея/Центр'
    if (pos < 0.4) return '🟣 Затылок'
    if (pos < 0.65) return '🔵 Ухо'
    if (pos < 0.85) return '🟡 Лицо'
    return '👑 Купол'
  }

  /* ---------- Transient Shaper per-track & Reference Matcher ---------- */
  const [transientConfigs, setTransientConfigs] = useState<Record<string, import('@/types').TransientConfig>>({})
  const [referenceMatchBands, setReferenceMatchBands] = useState<EqBand[]>([])

  /* ---------- A/B Compare ---------- */
  const [abStyleA, setAbStyleA] = useState('')
  const [abStyleB, setAbStyleB] = useState('')
  const [abLoading, setAbLoading] = useState(false)
  const [abResult, setAbResult] = useState<import('@/types').ABCompareResult | null>(null)

  if (!hasAnalysis) {
    return (
      <EmptyState
        icon={<SlidersHorizontal size={36} />}
        message={t('mix.nothingToMix')}
        hint={t('mix.nothingToMixHint')}
      />
    )
  }

  return (
    <div className="space-y-6 pt-10">
      <SectionTitle
        title={t('mix.title')}
        subtitle={
          selectedStyle
            ? t('mix.styleTarget', { style: selectedStyle })
            : t('mix.pickStyle')
        }
        right={
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => setSelectedSpatialTrack({ file: corrections[0]?.file ?? corrections[0]?.name ?? 'master', name: corrections[0] ? trackName(corrections[0]) : 'Master Mix' })}
              className="border-pink-500/40 bg-pink-500/15 text-pink-200 hover:bg-pink-500/25 hover:border-pink-400/60 shadow-sm shadow-pink-500/20"
            >
              <span className="text-base">👤</span> 3D Голова & Пространство
            </Button>
            <Button onClick={onMix} disabled={mixing || !selectedStyle}>
              {mixing ? <Spinner /> : null} {t('mix.autoMix')}
            </Button>
          </div>
        }
      />

      {/* Manual gain + sidechain controls */}
      <Card className="p-5">
        <h3 className="mb-4 text-sm font-semibold text-white">
          {t('mix.yourOverrides')}{' '}
          <span className="font-normal text-white/40">
            {t('mix.overridesHint')}
          </span>
        </h3>
        <div className="grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
          <Slider
            label={t('mix.sidechainDucking')}
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
            const hasSpatial = spatialConfigs[file]?.enabled
            return (
              <div key={file} className="flex items-end gap-3">
                <div className="flex-1">
                  <Slider
                    label={t('mix.manualGain', { track: trackName(c) })}
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
                </div>
                <button
                  type="button"
                  onClick={() => {
                    const cur = transientConfigs[file]
                    const nextAttack = (cur?.attack_db && cur.attack_db > 0) ? 0 : 4.0
                    setTransientConfigs((prev) => ({
                      ...prev,
                      [file]: {
                        enabled: true,
                        attack_db: nextAttack,
                        sustain_db: cur?.sustain_db ?? 0,
                        mix: 1.0,
                      },
                    }))
                  }}
                  className={`mb-0.5 flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all ${
                    transientConfigs[file]?.attack_db
                      ? 'border-emerald-500/50 bg-emerald-500/20 text-emerald-300 shadow-sm'
                      : 'border-white/10 bg-white/5 text-white/50 hover:border-white/20 hover:text-white'
                  }`}
                  title="Transient Punch (+4 dB Attack)"
                >
                  <span>⚡</span>
                  <span className="text-[11px] font-semibold">{transientConfigs[file]?.attack_db ? `+${transientConfigs[file]?.attack_db}dB` : 'Punch'}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedSpatialTrack({ file, name: trackName(c) })}
                  className={`mb-0.5 flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${
                    hasSpatial || c.spatial_config
                      ? 'border-pink-500/50 bg-pink-500/20 text-pink-200 shadow-sm shadow-pink-500/20 font-semibold'
                      : 'border-white/10 bg-white/5 text-white/50 hover:border-white/20 hover:text-white'
                  }`}
                  title={`3D Пространство дорожки (${trackName(c)}) - Шея / Затылок / Ухо / Лицо / Купол`}
                >
                  <span>👤</span>
                  <span className="text-[11px] truncate max-w-[140px]">
                    {getSpatialLabel(spatialConfigs[file] ?? c.spatial_config)}
                  </span>
                </button>
              </div>
            )
          })}
          {corrections.length === 0 && (
            <p className="text-xs text-white/35">
              {t('mix.runAutoMixHint')}
            </p>
          )}
        </div>
      </Card>

      {/* Dry-run corrections table */}
      <CorrectionsTable
        corrections={corrections}
        masterNotes={mixResult?.master_notes ?? mixResult?.notes}
      />

      {/* Mastering: Multiband Compressor + Limiter */}
      <Card className="p-5">
        <h3 className="mb-1 text-sm font-semibold text-white">{t('mix.mastering')}</h3>
        <p className="mb-3 text-xs text-white/45">{t('mix.masteringDesc')}</p>

        <div className="space-y-4">
          {/* Per-Track 3D Spatial Audio Status Banner */}
          <div className="rounded-xl border border-pink-500/20 bg-gradient-to-r from-pink-500/10 via-purple-500/5 to-transparent p-3.5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-pink-500 to-violet-600 shadow-md">
                <span className="text-lg">👤</span>
              </div>
              <div>
                <h4 className="text-xs font-bold text-white flex items-center gap-2">
                  Поканальное 3D Пространство (Per-Track Head &amp; Sky Dome)
                  <span className="rounded bg-pink-500/20 px-1.5 py-0.5 text-[9px] font-bold text-pink-300 border border-pink-500/30">СВЕДЕНИЕ</span>
                </h4>
                <p className="text-[11px] text-white/50">
                  Каждая дорожка сводится в индивидуальной точке 3D-пространства головы и купола. Настраивайте каналы кнопками 👤 3D выше!
                </p>
              </div>
            </div>
            <span className="rounded-lg bg-pink-500/20 border border-pink-500/30 px-2.5 py-1 text-xs font-mono text-pink-200">
              {corrections.length} дорожек в 3D
            </span>
          </div>

          {/* Multiband Compressor */}
          <div className="rounded-xl border border-white/10 bg-black/30 p-3">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setMultibandEnabled(!multibandEnabled)}
                  className={`text-xs px-2 py-0.5 rounded-md transition-colors ${
                    multibandEnabled
                      ? 'bg-violet-500/20 text-violet-300 border border-violet-400/30'
                      : 'bg-white/5 text-white/40 border border-white/10'
                  }`}
                >
                  {multibandEnabled ? 'ON' : 'OFF'}
                </button>
                <span className="text-xs font-medium text-white/70">{t('mix.multibandCompressor')}</span>
              </div>
              <label className="flex items-center gap-1.5 text-[10px] text-white/40">
                {t('mix.dryWet')}
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={mbMix}
                  onChange={(e) => setMbMix(Number(e.target.value))}
                  disabled={!multibandEnabled}
                  className="w-20 accent-violet-500"
                />
                <span className="font-mono text-white/50 w-8">{Math.round(mbMix * 100)}%</span>
              </label>
            </div>

            {multibandEnabled && (
              <div className="space-y-2">
                {mbBands.map((b, i) => (
                  <div key={i} className="flex items-center gap-2 text-[10px]">
                    <button
                      type="button"
                      onClick={() => {
                        const next = [...mbBands]
                        next[i] = { ...next[i], enabled: !next[i].enabled }
                        setMbBands(next)
                      }}
                      className={b.enabled ? 'text-violet-400' : 'text-white/20'}
                    >
                      {b.enabled ? '●' : '○'}
                    </button>
                    <span className="font-mono text-white/40 w-16">
                      {b.freq_lo >= 1000 ? `${b.freq_lo / 1000}k` : b.freq_lo}–{b.freq_hi >= 1000 ? `${b.freq_hi / 1000}k` : b.freq_hi}
                    </span>
                    <span className="text-white/30 w-6">Th</span>
                    <input
                      type="number"
                      value={b.threshold_db}
                      onChange={(e) => {
                        const next = [...mbBands]
                        next[i] = { ...next[i], threshold_db: Number(e.target.value) }
                        setMbBands(next)
                      }}
                      disabled={!multibandEnabled}
                      className="w-12 rounded bg-black/40 px-1 py-0.5 text-center font-mono text-white/70 border border-white/10"
                    />
                    <span className="text-white/30 w-4">R</span>
                    <input
                      type="number"
                      value={b.ratio}
                      step={0.1}
                      onChange={(e) => {
                        const next = [...mbBands]
                        next[i] = { ...next[i], ratio: Number(e.target.value) }
                        setMbBands(next)
                      }}
                      disabled={!multibandEnabled}
                      className="w-12 rounded bg-black/40 px-1 py-0.5 text-center font-mono text-white/70 border border-white/10"
                    />
                    <span className="text-white/30 w-6">Mk</span>
                    <input
                      type="number"
                      value={b.makeup_db}
                      step={0.5}
                      onChange={(e) => {
                        const next = [...mbBands]
                        next[i] = { ...next[i], makeup_db: Number(e.target.value) }
                        setMbBands(next)
                      }}
                      disabled={!multibandEnabled}
                      className="w-12 rounded bg-black/40 px-1 py-0.5 text-center font-mono text-white/70 border border-white/10"
                    />
                    <span className="text-white/30">dB</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Limiter Ceiling */}
          <div className="rounded-xl border border-white/10 bg-black/30 p-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-white/70">{t('mix.limiterCeiling')}</span>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min={-3}
                  max={0}
                  step={0.1}
                  value={limiterCeiling}
                  onChange={(e) => setLimiterCeiling(Number(e.target.value))}
                  className="w-32 accent-violet-500"
                />
                <span className="font-mono text-xs text-violet-300/70 w-12 text-right">
                  {limiterCeiling.toFixed(1)} dBTP
                </span>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* DSP: Dynamic EQ, Mid/Side EQ, Transient Shaper */}
      <DspChainCard
        dynEqEnabled={dynEqEnabled} setDynEqEnabled={setDynEqEnabled}
        dynEqMix={dynEqMix} setDynEqMix={setDynEqMix}
        dynEqBands={dynEqBands} setDynEqBands={setDynEqBands}
        msEqEnabled={msEqEnabled} setMsEqEnabled={setMsEqEnabled}
        msMidNodes={msMidNodes} setMsMidNodes={setMsMidNodes}
        msSideNodes={msSideNodes} setMsSideNodes={setMsSideNodes}
        trEnabled={trEnabled} setTrEnabled={setTrEnabled}
        trMix={trMix} setTrMix={setTrMix}
        trAttack={trAttack} setTrAttack={setTrAttack}
        trSustain={trSustain} setTrSustain={setTrSustain}
        scEnabled={scEnabled} setScEnabled={setScEnabled}
        scTrigger={scTrigger} setScTrigger={setScTrigger}
        scAmount={scAmount} setScAmount={setScAmount}
        scAttack={scAttack} setScAttack={setScAttack}
        scRelease={scRelease} setScRelease={setScRelease}
        scMix={scMix} setScMix={setScMix}
        deessEnabled={deessEnabled} setDeessEnabled={setDeessEnabled}
        deessFreq={deessFreq} setDeessFreq={setDeessFreq}
        deessThreshold={deessThreshold} setDeessThreshold={setDeessThreshold}
        deessMaxReduction={deessMaxReduction} setDeessMaxReduction={setDeessMaxReduction}
        deessMode={deessMode} setDeessMode={setDeessMode}
        deessMix={deessMix} setDeessMix={setDeessMix}
      />

      {/* A/B Compare + Presets */}
      <Card className="p-5">
        <h3 className="mb-1 text-sm font-semibold text-white">{t('mix.abCompare')}</h3>
        <p className="mb-3 text-xs text-white/45">{t('mix.abCompareDesc')}</p>
        <div className="flex items-center gap-3">
          <label className="flex-1">
            <span className="text-[10px] text-white/40">{t('mix.styleA')}</span>
            <select value={abStyleA} onChange={(e) => setAbStyleA(e.target.value)}
              className="mt-0.5 w-full rounded bg-black/40 px-2 py-1 text-xs text-white/70 border border-white/10">
              <option value="">{t('mix.selectStyle')}</option>
              {styles.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          <label className="flex-1">
            <span className="text-[10px] text-white/40">{t('mix.styleB')}</span>
            <select value={abStyleB} onChange={(e) => setAbStyleB(e.target.value)}
              className="mt-0.5 w-full rounded bg-black/40 px-2 py-1 text-xs text-white/70 border border-white/10">
              <option value="">{t('mix.selectStyle')}</option>
              {styles.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          <Button
            variant="outline"
            className="mt-4"
            disabled={abLoading || !abStyleA || !abStyleB}
            onClick={async () => {
              setAbLoading(true)
              try {
                const res = await api.abCompare({
                  directory,
                  style_a: abStyleA,
                  style_b: abStyleB,
                  multiband: multibandConfig,
                  limiter_ceiling_db: limiterCeiling,
                  dynamic_eq: dynamicEqConfig,
                  midside_eq: midsideEqConfig,
                  transient: transientConfig,
                })
                setAbResult(res)
              } catch {
                setAbResult(null)
              } finally {
                setAbLoading(false)
              }
            }}
          >
            {abLoading ? <Spinner /> : t('mix.runAB')}
          </Button>
        </div>
        {abResult && (
          <div className="mt-3 grid grid-cols-2 gap-2">
            <div className="rounded-lg border border-white/5 bg-white/[0.02] p-2">
              <p className="text-[10px] text-white/40 mb-1">A: {abResult.style_a}</p>
              <audio controls src={`file:///${abResult.output_a}`} className="w-full h-8" />
            </div>
            <div className="rounded-lg border border-white/5 bg-white/[0.02] p-2">
              <p className="text-[10px] text-white/40 mb-1">B: {abResult.style_b}</p>
              <audio controls src={`file:///${abResult.output_b}`} className="w-full h-8" />
            </div>
          </div>
        )}
      </Card>

      {/* AI Reference Track Matcher */}
      <ReferenceMatcher
        onApplyMatchEq={(bands) => {
          setReferenceMatchBands(bands)
          setEqBands((prev) => [...prev, ...bands])
        }}
      />

      {/* EQ Band Editor */}
      <Card className="p-5">
        <h3 className="mb-1 text-sm font-semibold text-white">{t('mix.eqEditor')}</h3>
        <p className="mb-3 text-xs text-white/45">{t('mix.eqEditorDesc')}</p>
        <Suspense fallback={<div className="h-64 flex items-center justify-center"><Spinner /></div>}>
          <EqEditor bands={eqBands} onChange={setEqBands} />
        </Suspense>
      </Card>

      {/* Export to Ableton button */}
      {corrections.length > 0 && (
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-white">{t('mix.exportAbleton')}</h3>
              <p className="mt-0.5 text-xs text-white/45">
                {t('mix.exportAbletonDesc')}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={() => setShowPresetDialog(true)}>
                <FolderOpen size={15} /> {t('mix.presets')}
              </Button>
              <Button variant="outline" onClick={() => setShowExport(true)}>
                <Download size={15} /> {t('mix.export')}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {showExport && (
        <ExportDialog corrections={corrections} eqBands={eqBands} previewPath={previewPath} onClose={() => setShowExport(false)} />
      )}

      {showPresetDialog && (
        <PresetDialog
          onClose={() => setShowPresetDialog(false)}
          onLoad={(preset) => {
            if (preset.multiband) { setMultibandEnabled(preset.multiband.enabled ?? true); setMbMix(preset.multiband.mix ?? 1.0) }
            if (typeof preset.limiter_ceiling_db === 'number') setLimiterCeiling(preset.limiter_ceiling_db)
            if (preset.dynamic_eq) { setDynEqEnabled(preset.dynamic_eq.enabled ?? false); setDynEqMix(preset.dynamic_eq.mix ?? 1.0) }
            if (preset.midside_eq) { setMsEqEnabled(preset.midside_eq.enabled ?? false) }
            if (preset.transient) { setTrEnabled(preset.transient.enabled ?? false); setTrMix(preset.transient.mix ?? 1.0); setTrAttack(preset.transient.attack_db ?? 0); setTrSustain(preset.transient.sustain_db ?? 0) }
            if (preset.sidechain) { setScEnabled(preset.sidechain.enabled ?? false); setScTrigger(preset.sidechain.trigger ?? 'kick'); setScAmount(preset.sidechain.amount_db ?? -3); setScAttack(preset.sidechain.attack_ms ?? 5); setScRelease(preset.sidechain.release_ms ?? 90); setScMix(preset.sidechain.mix ?? 1) }
          }}
          currentSettings={{
            multiband: multibandConfig,
            limiter_ceiling_db: limiterCeiling,
            dynamic_eq: dynamicEqConfig,
            midside_eq: midsideEqConfig,
            transient: transientConfig,
            sidechain: sidechainConfig,
          }}
        />
      )}

      {/* Preview + Release */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card className="flex flex-col p-5">
          <h3 className="mb-3 text-sm font-semibold text-white">{t('mix.previewMix')}</h3>
          <p className="mb-4 text-xs leading-relaxed text-white/45">
            {t('mix.previewMixDesc')}
          </p>

          {/* Reference / match-EQ / A/B options */}
          <div className="mb-4 space-y-3 rounded-xl border border-white/[0.07] bg-black/25 p-3">
            <label className="block">
              <span className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-white/45">
                {t('mix.referenceWav')}
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
                {t('mix.applyMatchEq')}
              </label>
              <label className="flex cursor-pointer select-none items-center gap-2 text-xs text-white/65">
                <input
                  type="checkbox"
                  checked={abEnabled}
                  onChange={(e) => setAbEnabled(e.target.checked)}
                  className="h-3.5 w-3.5 accent-violet-500"
                />
                {t('mix.abBeforeAfter')}
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
                {curveLoading ? <Spinner /> : null} {t('mix.showCurve')}
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={runPreview} disabled={previewing || !selectedStyle}>
              {previewing ? (
                <>
                  <Spinner /> {t('mix.rendering')}
                </>
              ) : (
                <>
                  <Play size={15} /> {t('mix.previewMix')}
                </>
              )}
            </Button>
            {preview?.duration_s != null && (
              <Badge>{preview.duration_s.toFixed(1)} s</Badge>
            )}
          </div>

          {/* long-render status: previews can easily take 15–20 s */}
          {previewing && (
            <div className="mt-3">
              {progressStage ? (
                <ProgressBar
                  percent={progressPercent}
                  stage={progressStage}
                  detail={progressDetail}
                />
              ) : (
                <div
                  role="status"
                  aria-live="polite"
                  className="flex items-center gap-2 rounded-xl border border-violet-400/25 bg-violet-500/[0.08] px-3 py-2 text-xs text-violet-200"
                >
                  <Loader2 size={14} className="animate-spin" />
                  {t('mix.renderingAb')}
                  {elapsed > 0 && <span className="font-mono text-violet-300/70">{elapsed}s</span>}
                  <span className="text-violet-200/50">{t('mix.hangTight')}</span>
                </div>
              )}
            </div>
          )}

          {/* Waveform canvas */}
          {wavePeaks.length > 0 && (
            <div className="mt-4 rounded-xl border border-white/10 bg-black/40 p-3">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-white/45">
                {t('mix.previewWaveform')}
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
                  {t('mix.appliedMatchEq')}
                </h4>
                <Badge tone="violet">{appliedCurve.length} {t('mix.bands')}</Badge>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/30 p-2">
                <Suspense fallback={<div className="h-48 flex items-center justify-center"><Spinner /></div>}>
                  <EqCurveChart curve={appliedCurve} />
                </Suspense>
              </div>
            </div>
          )}

          {/* Applied EQ corrections chips */}
          {(preview?.eq_applied?.length ?? 0) > 0 && (
            <div className="mt-4">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-white/45">
                {t('mix.appliedEqCorrections')}
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
                  {t('mix.matchEqCurve')}{' '}
                  <span className="font-normal normal-case text-white/35">{t('mix.matchEqCurveHint')}</span>
                </h4>
                <button
                  type="button"
                  onClick={() => setFetchedCurve(null)}
                  className="text-[10px] text-white/30 hover:text-white/60"
                >
                  {t('mix.hide')}
                </button>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/30 p-2">
                <Suspense fallback={<div className="h-48 flex items-center justify-center"><Spinner /></div>}>
                  <EqCurveChart curve={fetchedCurve} />
                </Suspense>
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
                  ref={audioRef}
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

          {/* Live spectrum visualization */}
          {previewPath && (
            <div className="mt-4">
              <LiveSpectrum audioRef={audioRef} />
            </div>
          )}
        </Card>

        <Card className="flex flex-col p-5">
          <h3 className="mb-3 text-sm font-semibold text-white">{t('mix.releaseCheck')}</h3>
          <p className="mb-4 text-xs leading-relaxed text-white/45">
            {t('mix.releaseCheckDesc')}
          </p>
          <div className="flex items-center gap-3">
            <Button variant="outline" onClick={onReleaseCheck} disabled={checkingRelease}>
              {checkingRelease ? (
                <>
                  <Spinner /> {t('mix.checking')}
                </>
              ) : (
                <>
                  <ShieldCheck size={15} /> {t('mix.releaseCheck')}
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
                  {ready ? t('mix.ready') : t('mix.needsWork')}
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

      {/* 3D Head Spatializer Modal */}
      {selectedSpatialTrack && (
        <HeadSpatializerModal
          trackName={selectedSpatialTrack.name}
          config={
            spatialConfigs[selectedSpatialTrack.file] ?? {
              enabled: true,
              head_position: 0.66,
              azimuth_deg: 30,
              elevation_deg: 0,
              distance_m: 1.0,
              mix: 1.0,
            }
          }
          isOpen={true}
          onClose={() => setSelectedSpatialTrack(null)}
          onChange={(newCfg) => {
            setSpatialConfigs((prev) => ({
              ...prev,
              [selectedSpatialTrack.file]: newCfg,
            }))
          }}
        />
      )}
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
