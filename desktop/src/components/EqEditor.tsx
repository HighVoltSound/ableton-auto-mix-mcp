import { useCallback, useEffect, useRef, useState } from 'react'
import type { EqBand, EqBandType } from '@/types'
import { Button } from './ui'

const FREQ_MIN = 20
const FREQ_MAX = 20000
const GAIN_MIN = -24
const GAIN_MAX = 24
const CANVAS_H = 220
const PAD_TOP = 16
const PAD_BOTTOM = 24
const PAD_LEFT = 48
const PAD_RIGHT = 16

const BAND_COLORS: Record<EqBandType, string> = {
  bell: '#a78bfa',
  low_shelf: '#34d399',
  high_shelf: '#f472b6',
  low_cut: '#f87171',
  high_cut: '#60a5fa',
}

const BAND_LABELS: Record<EqBandType, string> = {
  bell: 'Bell',
  low_shelf: 'Low Shelf',
  high_shelf: 'High Shelf',
  low_cut: 'Low Cut',
  high_cut: 'High Cut',
}

const TYPE_ORDER: EqBandType[] = ['bell', 'low_shelf', 'high_shelf', 'low_cut', 'high_cut']

// ---- EQ math ----

function bellResponse(f: number, freq: number, gain: number, q: number): number {
  const ratio = f / freq
  const norm = (ratio * ratio - 1) / (ratio * q)
  return gain / Math.sqrt(1 + norm * norm)
}

function shelfResponse(f: number, freq: number, gain: number, q: number, high: boolean): number {
  const s = 1 / q
  const ratio = f / freq
  const dbGain = high
    ? gain * (1 / (1 + Math.exp(-s * (Math.log2(ratio) * 10))))
    : gain * (1 / (1 + Math.exp(s * (Math.log2(ratio) * 10))))
  return dbGain
}

function cutResponse(f: number, freq: number, order: number, high: boolean): number {
  const ratio = high ? freq / f : f / freq
  if (ratio <= 1) return 0
  const slope = order * 6
  return -slope * Math.log10(ratio)
}

function bandResponse(f: number, band: EqBand): number {
  if (!band.enabled) return 0
  switch (band.type) {
    case 'bell':
      return bellResponse(f, band.freq, band.gain, band.q)
    case 'low_shelf':
      return shelfResponse(f, band.freq, band.gain, band.q, false)
    case 'high_shelf':
      return shelfResponse(f, band.freq, band.gain, band.q, true)
    case 'low_cut':
      return cutResponse(f, band.freq, 2, false)
    case 'high_cut':
      return cutResponse(f, band.freq, 2, true)
  }
}

function combinedResponse(f: number, bands: EqBand[]): number {
  let total = 0
  for (const b of bands) total += bandResponse(f, b)
  return total
}

// ---- Canvas helpers ----

function hzToX(hz: number, w: number): number {
  const logMin = Math.log10(FREQ_MIN)
  const logMax = Math.log10(FREQ_MAX)
  return PAD_LEFT + ((Math.log10(hz) - logMin) / (logMax - logMin)) * (w - PAD_LEFT - PAD_RIGHT)
}

function xToHz(x: number, w: number): number {
  const logMin = Math.log10(FREQ_MIN)
  const logMax = Math.log10(FREQ_MAX)
  const t = (x - PAD_LEFT) / (w - PAD_LEFT - PAD_RIGHT)
  return Math.pow(10, logMin + t * (logMax - logMin))
}

function gainToY(gain: number, h: number): number {
  const plotH = h - PAD_TOP - PAD_BOTTOM
  const norm = (gain - GAIN_MIN) / (GAIN_MAX - GAIN_MIN)
  return PAD_TOP + plotH * (1 - norm)
}

function yToGain(y: number, h: number): number {
  const plotH = h - PAD_TOP - PAD_BOTTOM
  const norm = 1 - (y - PAD_TOP) / plotH
  return GAIN_MIN + norm * (GAIN_MAX - GAIN_MIN)
}

const FREQ_TICKS = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
const GAIN_TICKS = [-24, -18, -12, -6, 0, 6, 12, 18, 24]

function drawGrid(ctx: CanvasRenderingContext2D, w: number, h: number) {
  ctx.clearRect(0, 0, w, h)

  // gain gridlines
  for (const g of GAIN_TICKS) {
    const y = gainToY(g, h)
    ctx.beginPath()
    ctx.strokeStyle = g === 0 ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.06)'
    ctx.lineWidth = g === 0 ? 1 : 0.5
    if (g === 0) ctx.setLineDash([5, 5])
    else ctx.setLineDash([])
    ctx.moveTo(PAD_LEFT, y)
    ctx.lineTo(w - PAD_RIGHT, y)
    ctx.stroke()
    ctx.setLineDash([])

    // label
    ctx.fillStyle = 'rgba(255,255,255,0.3)'
    ctx.font = '10px monospace'
    ctx.textAlign = 'right'
    ctx.textBaseline = 'middle'
    ctx.fillText(`${g > 0 ? '+' : ''}${g}`, PAD_LEFT - 6, y)
  }

  // freq gridlines + labels
  for (const f of FREQ_TICKS) {
    if (f < FREQ_MIN || f > FREQ_MAX) continue
    const x = hzToX(f, w)
    ctx.beginPath()
    ctx.strokeStyle = 'rgba(255,255,255,0.06)'
    ctx.lineWidth = 0.5
    ctx.moveTo(x, PAD_TOP)
    ctx.lineTo(x, h - PAD_BOTTOM)
    ctx.stroke()

    ctx.fillStyle = 'rgba(255,255,255,0.3)'
    ctx.font = '10px monospace'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'
    const label = f >= 1000 ? `${f / 1000}k` : `${f}`
    ctx.fillText(label, x, h - PAD_BOTTOM + 6)
  }
}

function drawCurve(ctx: CanvasRenderingContext2D, w: number, h: number, bands: EqBand[]) {
  const steps = 200
  const plotW = w - PAD_LEFT - PAD_RIGHT
  ctx.beginPath()
  ctx.strokeStyle = 'rgba(167,139,250,0.6)'
  ctx.lineWidth = 2
  for (let i = 0; i <= steps; i++) {
    const x = PAD_LEFT + (i / steps) * plotW
    const freq = xToHz(x, w)
    const gain = combinedResponse(freq, bands)
    const y = gainToY(gain, h)
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  }
  ctx.stroke()

  // fill under curve
  ctx.lineTo(PAD_LEFT + plotW, gainToY(0, h))
  ctx.lineTo(PAD_LEFT, gainToY(0, h))
  ctx.closePath()
  ctx.fillStyle = 'rgba(167,139,250,0.08)'
  ctx.fill()
}

function drawBands(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  bands: EqBand[],
  selectedId: number | null,
) {
  for (const b of bands) {
    if (!b.enabled) continue
    const x = hzToX(b.freq, w)
    const y = gainToY(b.gain, h)
    const color = BAND_COLORS[b.type]
    const isSelected = b.id === selectedId
    const r = isSelected ? 8 : 6

    // glow
    if (isSelected) {
      ctx.beginPath()
      ctx.arc(x, y, 14, 0, Math.PI * 2)
      ctx.fillStyle = color + '30'
      ctx.fill()
    }

    // circle
    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fillStyle = color
    ctx.fill()
    ctx.strokeStyle = isSelected ? '#fff' : 'rgba(255,255,255,0.3)'
    ctx.lineWidth = isSelected ? 2 : 1
    ctx.stroke()

    // freq label
    ctx.fillStyle = 'rgba(255,255,255,0.5)'
    ctx.font = '9px monospace'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'bottom'
    const label = b.freq >= 1000 ? `${(b.freq / 1000).toFixed(1)}k` : `${Math.round(b.freq)}`
    ctx.fillText(label, x, y - r - 3)

    // HUD tooltip on selected node
    if (isSelected) {
      const hudText = `${BAND_LABELS[b.type]} · ${b.freq >= 1000 ? (b.freq / 1000).toFixed(2) + ' kHz' : Math.round(b.freq) + ' Hz'} · ${b.gain > 0 ? '+' : ''}${b.gain.toFixed(1)} dB · Q ${b.q.toFixed(2)}`
      ctx.font = '10px monospace'
      const textWidth = ctx.measureText(hudText).width
      const hudW = textWidth + 14
      const hudH = 18
      const hudX = Math.max(PAD_LEFT + 2, Math.min(w - PAD_RIGHT - hudW - 2, x - hudW / 2))
      const hudY = y > 45 ? y - r - 26 : y + r + 12

      ctx.fillStyle = 'rgba(15, 15, 25, 0.88)'
      ctx.strokeStyle = color
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.roundRect(hudX, hudY, hudW, hudH, 4)
      ctx.fill()
      ctx.stroke()

      ctx.fillStyle = '#ffffff'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(hudText, hudX + hudW / 2, hudY + hudH / 2)
    }
  }
}

// ---- Component ----

export interface EqEditorProps {
  bands: EqBand[]
  onChange: (bands: EqBand[]) => void
  maxBands?: number
}

export function EqEditor({ bands, onChange, maxBands = 8 }: EqEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [dragging, setDragging] = useState(false)
  const [canvasW, setCanvasW] = useState(400)

  const selected = bands.find((b) => b.id === selectedId) ?? null

  // Resize observer
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        setCanvasW(e.contentRect.width)
      }
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Redraw
  useEffect(() => {
    const ctx = canvasRef.current?.getContext('2d')
    if (!ctx) return
    const dpr = window.devicePixelRatio || 1
    const w = canvasW
    const h = CANVAS_H
    ctx.canvas.width = w * dpr
    ctx.canvas.height = h * dpr
    ctx.scale(dpr, dpr)
    drawGrid(ctx, w, h)
    drawCurve(ctx, w, h, bands)
    drawBands(ctx, w, h, bands, selectedId)
  }, [bands, selectedId, canvasW])

  // Hit test
  const hitTest = useCallback(
    (mx: number, my: number): number | null => {
      const ctx = canvasRef.current?.getContext('2d')
      if (!ctx) return null
      for (const b of [...bands].reverse()) {
        if (!b.enabled) continue
        const bx = hzToX(b.freq, canvasW)
        const by = gainToY(b.gain, CANVAS_H)
        const dist = Math.hypot(mx - bx, my - by)
        if (dist < 12) return b.id
      }
      return null
    },
    [bands, canvasW],
  )

  // Mouse handlers
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      const rect = canvasRef.current?.getBoundingClientRect()
      if (!rect) return
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top
      const hit = hitTest(mx, my)
      if (hit !== null) {
        setSelectedId(hit)
        setDragging(true)
        e.preventDefault()
      } else {
        setSelectedId(null)
      }
    },
    [hitTest],
  )

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!dragging || selectedId === null) return
      const rect = canvasRef.current?.getBoundingClientRect()
      if (!rect) return
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top
      const newFreq = Math.max(FREQ_MIN, Math.min(FREQ_MAX, xToHz(mx, canvasW)))
      const newGain = Math.max(GAIN_MIN, Math.min(GAIN_MAX, yToGain(my, CANVAS_H)))
      onChange(
        bands.map((b) =>
          b.id === selectedId ? { ...b, freq: Math.round(newFreq), gain: Math.round(newGain * 10) / 10 } : b,
        ),
      )
    },
    [dragging, selectedId, bands, onChange, canvasW],
  )

  const handleMouseUp = useCallback(() => setDragging(false), [])

  // Touch handlers
  const handleTouchStart = useCallback(
    (e: React.TouchEvent) => {
      const rect = canvasRef.current?.getBoundingClientRect()
      if (!rect) return
      const touch = e.touches[0]
      const mx = touch.clientX - rect.left
      const my = touch.clientY - rect.top
      const hit = hitTest(mx, my)
      if (hit !== null) {
        setSelectedId(hit)
        setDragging(true)
        e.preventDefault()
      }
    },
    [hitTest],
  )

  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (!dragging || selectedId === null) return
      const rect = canvasRef.current?.getBoundingClientRect()
      if (!rect) return
      const touch = e.touches[0]
      const mx = touch.clientX - rect.left
      const my = touch.clientY - rect.top
      const newFreq = Math.max(FREQ_MIN, Math.min(FREQ_MAX, xToHz(mx, canvasW)))
      const newGain = Math.max(GAIN_MIN, Math.min(GAIN_MAX, yToGain(my, CANVAS_H)))
      onChange(
        bands.map((b) =>
          b.id === selectedId ? { ...b, freq: Math.round(newFreq), gain: Math.round(newGain * 10) / 10 } : b,
        ),
      )
    },
    [dragging, selectedId, bands, onChange, canvasW],
  )

  const handleTouchEnd = useCallback(() => setDragging(false), [])

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      const rect = canvasRef.current?.getBoundingClientRect()
      if (!rect) return
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top
      const hit = hitTest(mx, my) ?? selectedId
      if (hit !== null) {
        e.preventDefault()
        const delta = e.deltaY < 0 ? 0.15 : -0.15
        onChange(
          bands.map((b) => {
            if (b.id === hit) {
              const newQ = Math.max(0.2, Math.min(18.0, Math.round((b.q + delta) * 100) / 100))
              return { ...b, q: newQ }
            }
            return b
          }),
        )
      }
    },
    [hitTest, selectedId, bands, onChange],
  )

  const handleDoubleClick = useCallback(
    (e: React.MouseEvent) => {
      if (bands.length >= maxBands) return
      const rect = canvasRef.current?.getBoundingClientRect()
      if (!rect) return
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top
      const freq = Math.round(Math.max(FREQ_MIN, Math.min(FREQ_MAX, xToHz(mx, canvasW))))
      const gain = Math.round(Math.max(GAIN_MIN, Math.min(GAIN_MAX, yToGain(my, CANVAS_H))) * 10) / 10
      const id = Math.max(0, ...bands.map((b) => b.id)) + 1
      onChange([...bands, { id, type: 'bell', freq, gain, q: 1.0, enabled: true }])
      setSelectedId(id)
    },
    [bands, canvasW, maxBands, onChange],
  )

  // Keyboard shortcut listener (Delete/Backspace to remove, Space to toggle)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (selectedId === null) return
      if (e.key === 'Delete' || e.key === 'Backspace') {
        const target = e.target as HTMLElement
        if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) return
        e.preventDefault()
        onChange(bands.filter((b) => b.id !== selectedId))
        setSelectedId(null)
      } else if (e.key === ' ' || e.code === 'Space') {
        const target = e.target as HTMLElement
        if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'BUTTON')) return
        e.preventDefault()
        onChange(bands.map((b) => (b.id === selectedId ? { ...b, enabled: !b.enabled } : b)))
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [selectedId, bands, onChange])

  // Band actions
  const addBand = () => {
    if (bands.length >= maxBands) return
    const id = Math.max(0, ...bands.map((b) => b.id)) + 1
    onChange([...bands, { id, type: 'bell' as EqBandType, freq: 1000, gain: 0, q: 1, enabled: true }])
    setSelectedId(id)
  }

  const removeBand = (id: number) => {
    onChange(bands.filter((b) => b.id !== id))
    if (selectedId === id) setSelectedId(null)
  }

  const toggleBand = (id: number) => {
    onChange(bands.map((b) => (b.id === id ? { ...b, enabled: !b.enabled } : b)))
  }

  const updateBand = (id: number, patch: Partial<EqBand>) => {
    onChange(bands.map((b) => (b.id === id ? { ...b, ...patch } : b)))
  }

  return (
    <div className="space-y-3">
      {/* Canvas */}
      <div ref={containerRef} className="w-full">
        <canvas
          ref={canvasRef}
          width={canvasW}
          height={CANVAS_H}
          className="w-full cursor-crosshair rounded-xl border border-white/10 bg-black/40"
          style={{ height: CANVAS_H }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onDoubleClick={handleDoubleClick}
          onWheel={handleWheel}
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
        />
      </div>

      {/* Band controls */}
      <div className="flex flex-wrap gap-2">
        {bands.map((b) => (
          <div
            key={b.id}
            className={`flex items-center gap-1.5 rounded-lg border px-2 py-1 text-xs transition-colors ${
              b.id === selectedId
                ? 'border-white/30 bg-white/10'
                : 'border-white/10 bg-black/30'
            } ${b.enabled ? '' : 'opacity-40'}`}
            onClick={() => setSelectedId(b.id)}
          >
            {/* Color dot */}
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: BAND_COLORS[b.type] }}
            />

            {/* Type select */}
            <select
              value={b.type}
              onChange={(e) => updateBand(b.id, { type: e.target.value as EqBandType })}
              className="bg-transparent text-[10px] text-white/70 outline-none"
            >
              {TYPE_ORDER.map((t) => (
                <option key={t} value={t} className="bg-[#1a1a2e]">
                  {BAND_LABELS[t]}
                </option>
              ))}
            </select>

            {/* Freq */}
            <span className="font-mono text-[10px] text-white/50">
              {b.freq >= 1000 ? `${(b.freq / 1000).toFixed(1)}k` : b.freq}
            </span>

            {/* Gain */}
            <span className="font-mono text-[10px] text-violet-300/70">
              {b.gain > 0 ? '+' : ''}{b.gain.toFixed(1)}
            </span>

            {/* Toggle */}
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); toggleBand(b.id) }}
              className="text-[10px] text-white/30 hover:text-white/60"
            >
              {b.enabled ? '●' : '○'}
            </button>

            {/* Remove */}
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); removeBand(b.id) }}
              className="text-[10px] text-white/20 hover:text-red-400"
            >
              ×
            </button>
          </div>
        ))}

        {bands.length < maxBands && (
          <Button
            onClick={addBand}
            className="h-7 px-2 text-[10px]"
          >
            + Band
          </Button>
        )}
      </div>

      {/* Selected band detail sliders */}
      {selected && (
        <div className="grid grid-cols-3 gap-3 rounded-xl border border-white/10 bg-black/30 p-3">
          <label className="space-y-1">
            <span className="text-[10px] text-white/40">Freq</span>
            <input
              type="range"
              min={20}
              max={20000}
              step={1}
              value={selected.freq}
              onChange={(e) => updateBand(selected.id, { freq: Number(e.target.value) })}
              className="w-full accent-violet-500"
            />
            <span className="block text-center font-mono text-[10px] text-white/50">
              {selected.freq >= 1000 ? `${(selected.freq / 1000).toFixed(1)}k Hz` : `${selected.freq} Hz`}
            </span>
          </label>
          <label className="space-y-1">
            <span className="text-[10px] text-white/40">Gain</span>
            <input
              type="range"
              min={-24}
              max={24}
              step={0.1}
              value={selected.gain}
              onChange={(e) => updateBand(selected.id, { gain: Number(e.target.value) })}
              className="w-full accent-violet-500"
            />
            <span className="block text-center font-mono text-[10px] text-white/50">
              {selected.gain > 0 ? '+' : ''}{selected.gain.toFixed(1)} dB
            </span>
          </label>
          <label className="space-y-1">
            <span className="text-[10px] text-white/40">Q</span>
            <input
              type="range"
              min={0.1}
              max={10}
              step={0.1}
              value={selected.q}
              onChange={(e) => updateBand(selected.id, { q: Number(e.target.value) })}
              className="w-full accent-violet-500"
            />
            <span className="block text-center font-mono text-[10px] text-white/50">
              {selected.q.toFixed(1)}
            </span>
          </label>
        </div>
      )}
    </div>
  )
}
