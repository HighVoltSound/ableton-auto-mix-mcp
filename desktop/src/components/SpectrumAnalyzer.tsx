import { useMemo } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ConflictPair, SpectrumPoint } from '@/types'
import { Badge, Card } from './ui'
import { useLanguage } from '@/i18n'

interface SpectrumAnalyzerProps {
  measured: SpectrumPoint[]
  target?: SpectrumPoint[]
  conflicts?: ConflictPair[]
}

interface ChartPoint {
  f: number
  measured?: number
  target?: number
}

function freqOf(p: SpectrumPoint): number | undefined {
  const f = p.freq ?? p.hz
  return typeof f === 'number' ? f : undefined
}

function dbOf(p: SpectrumPoint): number | undefined {
  const v = p.db ?? p.value
  return typeof v === 'number' ? v : undefined
}

function mergeCurves(measured: SpectrumPoint[], target: SpectrumPoint[]): ChartPoint[] {
  const map = new Map<number, ChartPoint>()
  for (const p of measured) {
    const f = Math.round(freqOf(p)!)
    map.set(f, { ...(map.get(f) ?? { f }), measured: dbOf(p)! })
  }
  for (const p of target) {
    const f = Math.round(freqOf(p)!)
    map.set(f, { ...(map.get(f) ?? { f }), target: dbOf(p)! })
  }
  return [...map.values()].sort((a, b) => a.f - b.f)
}

function bandToHzRange(band: string): [number, number] | null {
  const ranges: Record<string, [number, number]> = {
    sub_bass: [20, 60],
    bass: [60, 250],
    low_mids: [250, 500],
    mids: [500, 2000],
    upper_mids: [2000, 4000],
    presence: [4000, 6000],
    brilliance: [6000, 20000],
  }
  return ranges[band] ?? null
}

export function SpectrumAnalyzer({ measured, target, conflicts }: SpectrumAnalyzerProps) {
  const { t } = useLanguage()
  const chartData = useMemo(() => mergeCurves(measured, target ?? []), [measured, target])
  const hasTargetCurve = chartData.some((d) => d.target !== undefined)

  const conflictRanges = useMemo(() => {
    if (!conflicts?.length) return []
    const ranges: { from: number; to: number }[] = []
    for (const c of conflicts) {
      const band = c.band ?? ''
      const r = bandToHzRange(band)
      if (r) ranges.push({ from: r[0], to: r[1] })
    }
    return ranges
  }, [conflicts])

  if (chartData.length === 0) {
    return (
      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between gap-4">
          <h3 className="text-sm font-semibold text-white">{t('dashboard.spectralCurve')}</h3>
        </div>
        <div className="flex h-72 items-center justify-center text-xs text-white/35">
          {t('dashboard.noSpectralData')}
        </div>
      </Card>
    )
  }

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h3 className="text-sm font-semibold text-white">
          {t('dashboard.spectralCurve')}{' '}
          <span className="font-normal text-white/40">{t('dashboard.clickRowHint')}</span>
        </h3>
        <div className="flex gap-2">
          <Badge tone="violet">{t('dashboard.measured')}</Badge>
          {hasTargetCurve && <Badge tone="green">{t('dashboard.styleTarget')}</Badge>}
          {conflictRanges.length > 0 && <Badge tone="red">{t('dashboard.conflicts')}</Badge>}
        </div>
      </div>
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 4, left: -12 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <XAxis
              dataKey="f"
              type="number"
              scale="log"
              domain={['auto', 'auto']}
              tickFormatter={(f: number) =>
                f >= 1000 ? `${(f / 1000).toFixed(f % 1000 === 0 ? 0 : 1)}k` : `${f}`
              }
              stroke="rgba(255,255,255,0.15)"
            />
            <YAxis
              stroke="rgba(255,255,255,0.15)"
              tickFormatter={(v: number) => `${v}`}
              width={44}
            />
            <Tooltip
              contentStyle={{
                background: 'rgba(16,16,24,0.95)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 12,
              }}
              labelFormatter={(f) => `${f} Hz`}
              formatter={(value: unknown, name: unknown): [string, string] => [
                `${Number(value).toFixed(1)} dB`,
                String(name ?? ''),
              ]}
            />
            <Line
              type="monotone"
              dataKey="measured"
              name="measured"
              stroke="#a78bfa"
              strokeWidth={2}
              dot={false}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="target"
              name="style target"
              stroke="#34d399"
              strokeWidth={1.75}
              strokeDasharray="6 4"
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
