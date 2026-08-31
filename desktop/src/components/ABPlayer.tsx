import { useCallback, useEffect, useImperativeHandle, useRef, useState, forwardRef } from 'react'
import { Pause, Play } from 'lucide-react'
import { audioUrl } from '@/lib/api'
import { useLanguage } from '@/i18n'

const SYNC_TOLERANCE_S = 0.08

function fmtTime(s: number): string {
  if (!Number.isFinite(s) || s < 0) return '0:00'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

type Side = 'before' | 'after'

export interface ABPlayerHandle {
  seekTo: (ratio: number) => void
}

/**
 * Synchronized BEFORE | AFTER player: one shared transport drives two
 * <audio> elements, only the active side is audible, position is common.
 * Exposes seekTo via ref so external components (WaveformCanvas) can seek.
 */
export const ABPlayer = forwardRef<ABPlayerHandle, {
  beforePath: string
  afterPath: string
}>(({ beforePath, afterPath }, ref) => {
  const { t } = useLanguage()
  const beforeRef = useRef<HTMLAudioElement>(null)
  const afterRef = useRef<HTMLAudioElement>(null)
  const [active, setActive] = useState<Side>('after')
  const [playing, setPlaying] = useState(false)
  const [position, setPosition] = useState(0)
  const [duration, setDuration] = useState(0)

  const els = useCallback(
    () => [beforeRef.current, afterRef.current].filter((e): e is HTMLAudioElement => !!e),
    [],
  )

  useImperativeHandle(ref, () => ({
    seekTo(ratio: number) {
      const t = ratio * duration
      setPosition(t)
      for (const el of els()) el.currentTime = t
    },
  }))

  /* keep the muted state in sync with the active side */
  useEffect(() => {
    if (beforeRef.current) beforeRef.current.muted = active !== 'before'
    if (afterRef.current) afterRef.current.muted = active !== 'after'
  }, [active])

  /* hard-sync the inactive element to the active one while playing */
  useEffect(() => {
    const master = active === 'before' ? beforeRef.current : afterRef.current
    const slave = active === 'before' ? afterRef.current : beforeRef.current
    if (!master || !slave) return
    const sync = () => {
      if (Math.abs(slave.currentTime - master.currentTime) > SYNC_TOLERANCE_S) {
        slave.currentTime = master.currentTime
      }
      setPosition(master.currentTime)
    }
    const onPlay = () => {
      slave.currentTime = master.currentTime
      setPlaying(true)
    }
    const onPause = () => setPlaying(false)
    const onMeta = () =>
      setDuration((d) => Math.max(d, Number.isFinite(master.duration) ? master.duration : 0))
    master.addEventListener('timeupdate', sync)
    master.addEventListener('play', onPlay)
    master.addEventListener('pause', onPause)
    master.addEventListener('loadedmetadata', onMeta)
    return () => {
      master.removeEventListener('timeupdate', sync)
      master.removeEventListener('play', onPlay)
      master.removeEventListener('pause', onPause)
      master.removeEventListener('loadedmetadata', onMeta)
    }
  }, [active])

  const togglePlay = () => {
    if (playing) {
      for (const el of els()) el.pause()
      setPlaying(false)
    } else {
      const master = active === 'before' ? beforeRef.current : afterRef.current
      if (master) setPosition(master.currentTime)
      for (const el of els()) void el.play().catch(() => {})
      setPlaying(true)
    }
  }

  const switchTo = (side: Side) => {
    if (side === active) return
    const master = active === 'before' ? beforeRef.current : afterRef.current
    const slave = side === 'before' ? beforeRef.current : afterRef.current
    if (master && slave) {
      slave.currentTime = master.currentTime
      setPosition(master.currentTime)
    }
    setActive(side)
  }

  const seek = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
    const t = ratio * duration
    setPosition(t)
    for (const el of els()) el.currentTime = t
  }

  const pct = duration > 0 ? (position / duration) * 100 : 0

  return (
    <div className="space-y-3">
      {/* A/B toggle + transport */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={togglePlay}
          aria-label={playing ? t('player.pause') : t('player.play')}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-[0_4px_20px_rgb(139_92_246/0.4)] transition-all hover:brightness-110 active:brightness-95"
        >
          {playing ? <Pause size={18} /> : <Play size={18} className="ml-0.5" />}
        </button>

        <div className="grid flex-1 grid-cols-2 gap-1 rounded-xl border border-white/10 bg-black/40 p-1">
          {(['before', 'after'] as const).map((side) => (
            <button
              key={side}
              type="button"
              onClick={() => switchTo(side)}
              aria-pressed={active === side}
              className={`rounded-lg py-1.5 text-xs font-semibold uppercase tracking-wider transition-all ${
                active === side
                  ? side === 'after'
                    ? 'bg-gradient-to-r from-violet-500/30 to-fuchsia-500/25 text-white ring-1 ring-inset ring-fuchsia-400/40'
                    : 'bg-white/15 text-white ring-1 ring-inset ring-white/25'
                  : 'text-white/35 hover:text-white/70'
              }`}
            >
              {side === 'before' ? t('player.before') : t('player.after')}
            </button>
          ))}
        </div>
      </div>

      {/* progress bar (clickable) */}
      <div>
        <div
          role="slider"
          tabIndex={0}
          aria-label="Seek"
          aria-valuemin={0}
          aria-valuemax={Math.round(duration)}
          aria-valuenow={Math.round(position)}
          onClick={seek}
          onKeyDown={(e) => {
            const step = e.key === 'ArrowRight' ? 5 : e.key === 'ArrowLeft' ? -5 : 0
            if (!step || !duration) return
            e.preventDefault()
            const t = Math.min(duration, Math.max(0, position + step))
            setPosition(t)
            for (const el of els()) el.currentTime = t
          }}
          className="group relative h-3 cursor-pointer overflow-hidden rounded-full bg-white/10"
        >
          <div
            className={`h-full rounded-full bg-gradient-to-r ${
              active === 'after'
                ? 'from-violet-500 to-fuchsia-400'
                : 'from-slate-400 to-slate-300'
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="mt-1 flex justify-between font-mono text-[10px] text-white/35">
          <span>{fmtTime(position)}</span>
          <span>{fmtTime(duration)}</span>
        </div>
      </div>

      {/* hidden audio elements — single shared transport above */}
      {/* biome-ignore lint/a11y/useMediaCaption: instrumental preview */}
      <audio ref={beforeRef} preload="none" src={audioUrl(beforePath)} muted />
      {/* biome-ignore lint/a11y/useMediaCaption: instrumental preview */}
      <audio ref={afterRef} preload="none" src={audioUrl(afterPath)} muted />
    </div>
  )
})
