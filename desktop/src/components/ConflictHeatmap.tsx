import { useMemo, useState } from 'react'
import type { ConflictPair } from '@/types'
import { Card } from './ui'
import { useLanguage } from '@/i18n'

interface ConflictHeatmapProps {
  tracks: string[]
  conflicts: ConflictPair[]
}

interface CellData {
  gap: number
  band: string
  suggestion: string
}

function gapSeverity(gap: number): { bg: string; text: string } {
  if (gap <= 0.5) return { bg: 'bg-emerald-500/20', text: 'text-emerald-300' }
  if (gap <= 1.5) return { bg: 'bg-yellow-500/20', text: 'text-yellow-300' }
  return { bg: 'bg-red-500/25', text: 'text-red-300' }
}

export function ConflictHeatmap({ tracks, conflicts }: ConflictHeatmapProps) {
  const { t } = useLanguage()
  const [tooltip, setTooltip] = useState<{
    x: number
    y: number
    data: CellData
    label: string
  } | null>(null)

  const matrix = useMemo(() => {
    const map = new Map<string, CellData>()
    for (const c of conflicts) {
      const a = c.track_a ?? c.a ?? ''
      const b = c.track_b ?? c.b ?? ''
      const gap = c.gap_db ?? 0
      const band = c.band ?? ''
      const suggestion = c.suggestion ?? c.fix ?? ''
      const key = `${a}::${b}`
      const existing = map.get(key)
      if (!existing || gap > existing.gap) {
        map.set(key, { gap, band, suggestion })
      }
    }
    return map
  }, [conflicts])

  if (tracks.length === 0 || conflicts.length === 0) {
    return (
      <Card className="p-5 text-sm text-white/45">
        {t('dashboard.noConflicts')}
      </Card>
    )
  }

  return (
    <div className="relative">
      <div
        className="inline-grid gap-px"
        style={{ gridTemplateColumns: `80px repeat(${tracks.length}, 1fr)` }}
      >
        <div />
        {tracks.map((t) => (
          <div
            key={`h-${t}`}
            className="px-1 py-2 text-center text-[10px] font-medium text-white/50 truncate"
            title={t}
          >
            {t}
          </div>
        ))}

        {tracks.map((row) => (
          <>
            <div
              key={`v-${row}`}
              className="flex items-center pr-2 text-[10px] font-medium text-white/50 truncate"
              title={row}
            >
              {row}
            </div>
            {tracks.map((col) => {
              if (row === col) {
                return (
                  <div
                    key={`${row}-${col}`}
                    className="aspect-square rounded bg-white/[0.03]"
                  />
                )
              }
              const key = `${row}::${col}`
              const reverse = `${col}::${row}`
              const cell = matrix.get(key) ?? matrix.get(reverse)
              if (!cell) {
                return (
                  <div
                    key={`${row}-${col}`}
                    className="aspect-square rounded bg-white/[0.03]"
                  />
                )
              }
              const sev = gapSeverity(cell.gap)
              return (
                <div
                  key={`${row}-${col}`}
                  className={`aspect-square cursor-pointer rounded transition-colors ${sev.bg} hover:brightness-125`}
                  onMouseEnter={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect()
                    setTooltip({
                      x: rect.left + rect.width / 2,
                      y: rect.top - 8,
                      data: cell,
                      label: `${row} ↔ ${col}`,
                    })
                  }}
                  onMouseLeave={() => setTooltip(null)}
                />
              )
            })}
          </>
        ))}
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="pointer-events-none fixed z-50 -translate-x-1/2 -translate-y-full rounded-xl border border-white/15 bg-[#101018] px-3 py-2 text-xs shadow-xl"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          <div className="font-medium text-white/85">{tooltip.label}</div>
          <div className="text-white/60">
            {tooltip.data.band} · {tooltip.data.gap.toFixed(1)} dB
          </div>
          {tooltip.data.suggestion && (
            <div className="mt-1 max-w-[220px] text-[11px] text-white/45">
              {tooltip.data.suggestion}
            </div>
          )}
        </div>
      )}

      {/* Legend */}
      <div className="mt-3 flex items-center gap-4 text-[10px] text-white/45">
        <span>{t('dashboard.severity')}</span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded bg-emerald-500/20" /> {t('dashboard.low')}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded bg-yellow-500/20" /> {t('dashboard.medium')}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded bg-red-500/25" /> {t('dashboard.high')}
        </span>
      </div>
    </div>
  )
}
