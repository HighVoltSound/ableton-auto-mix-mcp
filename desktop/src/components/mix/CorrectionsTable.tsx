import type { TrackCorrection } from '@/types'
import { trackName } from '@/components/Dashboard'
import { Badge, Card } from '@/components/ui'
import { useLanguage } from '@/i18n'

const fmtDb = (v: unknown): string =>
  typeof v === 'number' && Number.isFinite(v)
    ? `${v > 0 ? '+' : ''}${v.toFixed(1)} dB`
    : '—'

const fmtPan = (v: unknown): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
  if (Math.abs(v) < 0.01) return 'C'
  return `${v > 0 ? 'R' : 'L'}${Math.round(Math.abs(v) * 100)}`
}

interface Props {
  corrections: TrackCorrection[]
  masterNotes?: string | null
}

export function CorrectionsTable({ corrections, masterNotes }: Props) {
  const { t } = useLanguage()
  if (corrections.length === 0) return null

  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-white/10 text-[11px] uppercase tracking-wider text-white/40">
              <th className="px-5 py-3 font-medium">{t('mix.track')}</th>
              <th className="px-4 py-3 font-medium">{t('mix.volume')}</th>
              <th className="px-4 py-3 font-medium">{t('mix.pan')}</th>
              <th className="px-4 py-3 font-medium">{t('mix.eqDeltas')}</th>
              <th className="px-4 py-3 font-medium">{t('mix.notes')}</th>
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
      {masterNotes && (
        <div className="border-t border-white/[0.07] bg-white/[0.02] px-5 py-3 text-xs leading-relaxed text-white/50">
          <span className="font-medium text-white/70">{t('mix.masterNotes')}</span>
          {masterNotes}
        </div>
      )}
    </Card>
  )
}
