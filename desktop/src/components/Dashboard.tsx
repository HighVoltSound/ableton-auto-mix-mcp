import { lazy, Suspense, useMemo, useState } from 'react'
import { LayoutDashboard } from 'lucide-react'
import type {
  AnalysisResult,
  ConflictsResult,
  SpectrumPoint,
  StyleProfile,
  TrackMetrics,
} from '@/types'
import { Card, EmptyState, SectionTitle, Spinner } from './ui'
const SpectrumAnalyzer = lazy(() => import('./SpectrumAnalyzer').then(m => ({ default: m.SpectrumAnalyzer })))
import { ConflictHeatmap } from './ConflictHeatmap'
import { useLanguage } from '@/i18n'

/* ---------- helpers (tolerant to loose backend shapes) ---------- */

export function trackName(t: TrackMetrics): string {
  return t.name ?? t.file ?? t.path?.split(/[\\/]/).pop() ?? 'unknown'
}

function spectrumOf(t: TrackMetrics | undefined): SpectrumPoint[] {
  const raw = t?.bands ?? t?.spectrum
  if (!Array.isArray(raw)) return []
  return raw.filter(
    (p) => typeof (p.freq ?? p.hz) === 'number' && typeof (p.db ?? p.value) === 'number',
  )
}

const fmt = (v: unknown, digits = 1, suffix = ''): string =>
  typeof v === 'number' && Number.isFinite(v)
    ? `${v.toFixed(digits)}${suffix}`
    : '—'

/* ------------------------------ view ------------------------------ */

export function Dashboard({
  analysis,
  conflicts,
  styleProfile,
}: {
  analysis: AnalysisResult | null
  conflicts: ConflictsResult | null
  styleProfile: StyleProfile | null
}) {
  const { t } = useLanguage()
  const tracks = useMemo(
    () => analysis?.tracks ?? analysis?.metrics ?? [],
    [analysis],
  )
  const [selectedTrackIdx, setSelectedTrackIdx] = useState(0)
  const selectedTrack = tracks[selectedTrackIdx]

  const measuredSpectrum = useMemo(() => spectrumOf(selectedTrack), [selectedTrack])

  const targetSpectrum = useMemo(() => {
    const raw =
      styleProfile?.spectral_curve ??
      styleProfile?.target_curve ??
      styleProfile?.bands ??
      []
    return Array.isArray(raw) ? raw : []
  }, [styleProfile])

  const conflictList = useMemo(
    () => conflicts?.conflicts ?? conflicts?.pairs ?? [],
    [conflicts],
  )

  const trackNames = useMemo(
    () => tracks.map((t) => trackName(t)),
    [tracks],
  )

  if (!analysis || tracks.length === 0) {
    return (
      <EmptyState
        icon={<LayoutDashboard size={36} />}
        message={t('dashboard.noAnalysis')}
        hint={t('dashboard.noAnalysisHint')}
      />
    )
  }

  return (
    <div className="space-y-6 pt-10">
      <SectionTitle
        title={t('dashboard.title')}
        subtitle={`${tracks.length} ${tracks.length === 1 ? t('dashboard.tracksAnalyzed').replace('{count}', String(tracks.length)) : t('dashboard.tracksAnalyzedPlural').replace('{count}', String(tracks.length))}${
          styleProfile?.name ? ` · style: ${styleProfile.name}` : ''
        }`}
      />

      {/* Metrics table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-white/10 text-[11px] uppercase tracking-wider text-white/40">
                <th className="px-5 py-3 font-medium">{t('dashboard.track')}</th>
                <th className="px-4 py-3 font-medium">{t('dashboard.lufs')}</th>
                <th className="px-4 py-3 font-medium">{t('dashboard.rms')}</th>
                <th className="px-4 py-3 font-medium">{t('dashboard.peak')}</th>
                <th className="px-4 py-3 font-medium">{t('dashboard.lra')}</th>
                <th className="px-4 py-3 font-medium">{t('dashboard.width')}</th>
              </tr>
            </thead>
            <tbody>
              {tracks.map((t, i) => (
                <tr
                  key={trackName(t) + i}
                  onClick={() => setSelectedTrackIdx(i)}
                  className={`cursor-pointer border-b border-white/[0.05] transition-colors last:border-0 ${
                    i === selectedTrackIdx
                      ? 'bg-violet-500/10'
                      : 'hover:bg-white/[0.03]'
                  }`}
                >
                  <td className="max-w-[280px] truncate px-5 py-3 font-medium text-white/85">
                    {trackName(t)}
                  </td>
                  <td className="px-4 py-3 font-mono text-white/70">
                    {fmt(t.lufs, 1)}
                  </td>
                  <td className="px-4 py-3 font-mono text-white/55">
                    {fmt(t.rms, 1)}
                  </td>
                  <td className="px-4 py-3 font-mono text-white/70">
                    {fmt(t.true_peak_db ?? t.peak_db, 1)}
                  </td>
                  <td className="px-4 py-3 font-mono text-white/55">
                    {fmt(t.lra, 1)}
                  </td>
                  <td className="px-4 py-3">
                    <WidthBar width={t.width ?? t.stereo_width} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Spectrum analyzer */}
      <Suspense fallback={<div className="h-48 rounded-xl border border-white/10 bg-black/30 flex items-center justify-center"><Spinner /></div>}>
        <SpectrumAnalyzer
          measured={measuredSpectrum}
          target={targetSpectrum}
          conflicts={conflictList}
        />
      </Suspense>

      {/* Conflicts heatmap */}
      <div>
        <SectionTitle
          title={t('dashboard.frequencyConflicts')}
          subtitle={t('dashboard.frequencyConflictsSubtitle')}
        />
        <ConflictHeatmap tracks={trackNames} conflicts={conflictList} />
      </div>
    </div>
  )
}

function WidthBar({ width }: { width: number | undefined }) {
  if (typeof width !== 'number' || !Number.isFinite(width)) {
    return <span className="font-mono text-white/35">—</span>
  }
  const pct = Math.max(4, Math.min(100, (width / 2) * 100))
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-400"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="font-mono text-xs text-white/55">{width.toFixed(2)}</span>
    </div>
  )
}
