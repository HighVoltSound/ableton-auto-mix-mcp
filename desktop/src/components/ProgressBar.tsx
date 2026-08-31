import { useEffect, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useLanguage } from '@/i18n'

export interface ProgressBarProps {
  percent: number
  stage?: string
  detail?: string
  indeterminate?: boolean
  className?: string
}

const STAGE_KEYS: Record<string, string> = {
  analyzing: 'progress.analyzing',
  mixing: 'progress.mixing',
  applying_eq: 'progress.applying_eq',
  sidechain: 'progress.sidechain',
  mastering: 'progress.mastering',
  rendering: 'progress.rendering',
  exporting: 'progress.exporting',
  done: 'progress.done',
}

export function ProgressBar({
  percent,
  stage,
  detail,
  indeterminate = false,
  className = '',
}: ProgressBarProps) {
  const { t } = useLanguage()
  const [smooth, setSmooth] = useState(percent)
  const raf = useRef(0)

  useEffect(() => {
    const target = Math.max(0, Math.min(100, percent))
    const animate = () => {
      setSmooth((prev) => {
        const diff = target - prev
        if (Math.abs(diff) < 0.5) return target
        return prev + diff * 0.15
      })
      raf.current = requestAnimationFrame(animate)
    }
    raf.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(raf.current)
  }, [percent])

  const label = stage ? t(STAGE_KEYS[stage] ?? stage) : ''
  const showPercent = !indeterminate && percent > 0

  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex items-center gap-3 rounded-xl border border-violet-400/25 bg-violet-500/[0.08] px-3 py-2.5 text-xs text-violet-200 ${className}`}
    >
      <Loader2 size={14} className="shrink-0 animate-spin text-violet-300" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {label && <span className="font-medium text-violet-100">{label}</span>}
          {detail && (
            <span className="truncate text-violet-300/60">— {detail}</span>
          )}
          {showPercent && (
            <span className="ml-auto shrink-0 font-mono text-violet-300/70">
              {Math.round(smooth)}%
            </span>
          )}
        </div>
        {/* Track */}
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-violet-900/40">
          <div
            className="h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 transition-[width] duration-200 ease-out"
            style={{ width: indeterminate ? '100%' : `${smooth}%` }}
          />
        </div>
      </div>
    </div>
  )
}
