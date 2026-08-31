import { useMemo } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { MatchEqPoint } from '@/types'
import { useLanguage } from '@/i18n'

/** Tolerant normalization: accepts hz|freq, gain_db|gain, drops bad points. */
export function normalizeEqCurve(curve: MatchEqPoint[] | undefined): {
  hz: number
  gain: number
}[] {
  if (!Array.isArray(curve)) return []
  return curve
    .map((p) => ({
      hz: (p.hz ?? p.freq) as number | undefined,
      gain: (p.gain_db ?? p.gain) as number | undefined,
    }))
    .filter(
      (p): p is { hz: number; gain: number } =>
        typeof p.hz === 'number' &&
        Number.isFinite(p.hz) &&
        p.hz > 0 &&
        typeof p.gain === 'number' &&
        Number.isFinite(p.gain),
    )
    .sort((a, b) => a.hz - b.hz)
}

const fmtHz = (hz: number): string =>
  hz >= 1000 ? `${(hz / 1000).toFixed(hz % 1000 === 0 ? 0 : 1)}k` : `${Math.round(hz)}`

/**
 * Match-EQ gain curve: log-frequency X axis, dB Y axis, dashed zero line.
 * Used both for the /api/match_eq preview and for preview.match_eq.curve.
 */
export function EqCurveChart({ curve }: { curve: MatchEqPoint[] | undefined }) {
  const { t } = useLanguage()
  const data = useMemo(() => normalizeEqCurve(curve), [curve])

  const yDomain = useMemo(() => {
    const maxAbs = Math.max(1.5, ...data.map((d) => Math.abs(d.gain)))
    const bound = Math.ceil(maxAbs * 1.2)
    return [-bound, bound] as [number, number]
  }, [data])

  if (data.length === 0) {
    return (
      <div className="flex h-44 items-center justify-center text-xs text-white/35">
        {t('eqCurve.noData')}
      </div>
    )
  }

  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: -16 }}>
          <defs>
            <linearGradient id="eqCurveFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.35} />
              <stop offset="50%" stopColor="#a78bfa" stopOpacity={0.05} />
              <stop offset="100%" stopColor="#e879f9" stopOpacity={0.25} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
          <XAxis
            dataKey="hz"
            type="number"
            scale="log"
            domain={[data[0].hz, data[data.length - 1].hz]}
            allowDataOverflow
            ticks={[20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000].filter(
              (t) => t >= data[0].hz && t <= data[data.length - 1].hz,
            )}
            tickFormatter={fmtHz}
            stroke="rgba(255,255,255,0.15)"
          />
          <YAxis
            domain={yDomain}
            tickFormatter={(v: number) => `${v > 0 ? '+' : ''}${v}`}
            stroke="rgba(255,255,255,0.15)"
            width={52}
          />
          <Tooltip
            contentStyle={{
              background: 'rgba(16,16,24,0.95)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 12,
            }}
            labelFormatter={(hz) => `${fmtHz(Number(hz))} Hz`}
            formatter={(value: unknown): [string, string] => [
              `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(2)} dB`,
              'match-EQ',
            ]}
          />
          {/* dashed zero line */}
          <ReferenceLine
            y={0}
            stroke="rgba(255,255,255,0.3)"
            strokeDasharray="5 5"
          />
          <Area
            type="monotone"
            dataKey="gain"
            name="match-EQ"
            stroke="#a78bfa"
            strokeWidth={2}
            fill="url(#eqCurveFill)"
            dot={false}
            connectNulls
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
