import React, { useEffect, useRef, useState, useCallback } from 'react'
import type { SpatialConfig } from '@/types'
import { Button, Slider } from './ui'
import { X, RotateCcw, Sparkles } from 'lucide-react'

export interface HeadSpatializerModalProps {
  trackName: string
  config: SpatialConfig
  isOpen: boolean
  onClose: () => void
  onChange: (newConfig: SpatialConfig) => void
}

const CANVAS_W = 440
const CANVAS_H = 300

interface InstrumentPreset {
  id: string
  name: string
  icon: string
  tag: string
  desc: string
  config: Partial<SpatialConfig>
}

const INSTRUMENT_PRESETS: InstrumentPreset[] = [
  {
    id: 'kick_sub',
    name: 'Kick / 808 Sub',
    icon: '🥁',
    tag: 'Центр / Низ',
    desc: 'Моно-бас строго по центру снизу, плотный удар',
    config: {
      head_position: 0.0,
      azimuth_deg: 0,
      elevation_deg: -15,
      distance_m: 0.5,
      bass_mono: true,
      room_model: 'none',
      room_amount: 0.0,
      mix: 1.0,
    },
  },
  {
    id: 'snare_clap',
    name: 'Snare / Clap',
    icon: '🎯',
    tag: 'Перед лицом',
    desc: 'Четкий панч прямо перед слушателем',
    config: {
      head_position: 0.75,
      azimuth_deg: 0,
      elevation_deg: 5,
      distance_m: 0.8,
      bass_mono: false,
      room_model: 'studio',
      room_amount: 0.2,
      mix: 1.0,
    },
  },
  {
    id: 'hihats_cymbals',
    name: 'Hi-Hats / Cymbals',
    icon: '✨',
    tag: 'Над головой',
    desc: 'Воздух и тарелки в куполе над головой',
    config: {
      head_position: 1.0,
      azimuth_deg: 40,
      elevation_deg: 45,
      distance_m: 1.2,
      bass_mono: false,
      room_model: 'vocal_booth',
      room_amount: 0.15,
      mix: 1.0,
    },
  },
  {
    id: 'bass_line',
    name: 'Bass / Reese',
    icon: '🎸',
    tag: 'Затылок / Саб',
    desc: 'Обволакивающий низ с сохранением моно-саба',
    config: {
      head_position: 0.25,
      azimuth_deg: -15,
      elevation_deg: -10,
      distance_m: 0.7,
      bass_mono: true,
      room_model: 'none',
      room_amount: 0.0,
      mix: 1.0,
    },
  },
  {
    id: 'lead_vocal',
    name: 'Lead Vocal / Solo',
    icon: '🎤',
    tag: 'Лицо In-Your-Face',
    desc: 'Главный вокал впереди с легким студийным объемом',
    config: {
      head_position: 0.75,
      azimuth_deg: 0,
      elevation_deg: 10,
      distance_m: 0.6,
      bass_mono: false,
      room_model: 'studio',
      room_amount: 0.25,
      mix: 1.0,
    },
  },
  {
    id: 'pads_sky',
    name: 'Pads / Ambient Sky',
    icon: '🎹',
    tag: 'Небесный купол',
    desc: 'Широкая атмосфера прямо в небесах над головой',
    config: {
      head_position: 1.0,
      azimuth_deg: -60,
      elevation_deg: 65,
      distance_m: 2.5,
      bass_mono: false,
      room_model: 'cathedral',
      room_amount: 0.5,
      mix: 1.0,
    },
  },
  {
    id: 'fx_sweeps',
    name: 'FX / Risers / Sweeps',
    icon: '🚀',
    tag: 'Зенит-в-Космос',
    desc: 'Полет звука над макушкой и затылком',
    config: {
      head_position: 1.0,
      azimuth_deg: 75,
      elevation_deg: 75,
      distance_m: 2.0,
      bass_mono: false,
      room_model: 'club',
      room_amount: 0.45,
      mix: 1.0,
    },
  },
  {
    id: 'backing_vocals',
    name: 'Backing Vocals',
    icon: '👥',
    tag: 'Широкие уши',
    desc: 'Бэк-вокалы широко по бокам с легкой высотой',
    config: {
      head_position: 0.5,
      azimuth_deg: -50,
      elevation_deg: 25,
      distance_m: 1.5,
      bass_mono: false,
      room_model: 'studio',
      room_amount: 0.3,
      mix: 1.0,
    },
  },
]

// Trajectory calculation including Overhead Crown Dome
function getHeadTrajectoryPoint(t: number, elevation: number, w: number, h: number): { x: number; y: number } {
  const cx = w * 0.46
  const cy = h * 0.56

  // Basic anatomical path: 0.0 Neck -> 0.25 Occiput -> 0.50 Ear -> 0.75 Face -> 1.0 Crown/Overhead
  let baseX = cx
  let baseY = cy

  if (t <= 0.25) {
    // Neck to Occiput
    const norm = t / 0.25
    baseX = cx - 85 - norm * 15
    baseY = cy + 65 - norm * 70
  } else if (t <= 0.50) {
    // Occiput to Ear
    const norm = (t - 0.25) / 0.25
    baseX = cx - 100 + norm * 100
    baseY = cy - 5 + Math.sin(norm * Math.PI * 0.5) * 10
  } else if (t <= 0.75) {
    // Ear to Face
    const norm = (t - 0.50) / 0.25
    baseX = cx + norm * 90
    baseY = cy + 5 - Math.sin(norm * Math.PI) * 20
  } else {
    // Face to Crown / Sky Dome
    const norm = (t - 0.75) / 0.25
    baseX = cx + 90 - norm * 90
    baseY = cy - 15 - norm * 85
  }

  // Elevate point upward towards the Sky Dome when elevation is positive
  if (elevation > 0) {
    const elevNorm = Math.min(1.0, elevation / 90.0)
    baseY -= elevNorm * 60
  } else if (elevation < 0) {
    const lowNorm = Math.abs(elevation) / 45.0
    baseY += lowNorm * 30
  }

  return { x: baseX, y: baseY }
}

export function HeadSpatializerModal({
  trackName,
  config,
  isOpen,
  onClose,
  onChange,
}: HeadSpatializerModalProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [isDragging, setIsDragging] = useState(false)

  const headPos = config.head_position ?? 0.50
  const azimuth = config.azimuth_deg ?? 30
  const elevation = config.elevation_deg ?? 0
  const distance = config.distance_m ?? 1.0
  const mix = config.mix ?? 1.0
  const bassMono = config.bass_mono ?? true
  const roomModel = config.room_model ?? 'none'
  const roomAmount = config.room_amount ?? 0.25

  const update = (patch: Partial<SpatialConfig>) => {
    onChange({
      ...config,
      ...patch,
    })
  }

  // Draw Head & 3D Sky Dome on canvas
  const redraw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const w = CANVAS_W
    const h = CANVAS_H

    ctx.clearRect(0, 0, w, h)

    const cx = w * 0.46
    const cy = h * 0.56

    // 1. Subtle Grid
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)'
    ctx.lineWidth = 1
    for (let x = 20; x < w; x += 30) {
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x, h)
      ctx.stroke()
    }
    for (let y = 20; y < h; y += 30) {
      ctx.beginPath()
      ctx.moveTo(0, y)
      ctx.lineTo(w, y)
      ctx.stroke()
    }

    // 2. 3D Overhead Sky Dome (Полусфера над головой)
    // Dome rings (+15°, +30°, +45°, +60°, +90° Zenith)
    const domeRadii = [80, 110, 140, 170]
    domeRadii.forEach((r, idx) => {
      ctx.save()
      ctx.beginPath()
      ctx.arc(cx, cy - 20, r, Math.PI, 0) // upper hemisphere
      ctx.strokeStyle = `rgba(236, 72, 153, ${0.06 + idx * 0.04})`
      ctx.lineWidth = idx === 2 ? 1.5 : 1
      if (idx === 2) ctx.setLineDash([4, 4])
      ctx.stroke()
      ctx.restore()
    })

    // Zenith / Sky Dome Label
    ctx.font = '9px system-ui, sans-serif'
    ctx.fillStyle = 'rgba(236, 72, 153, 0.6)'
    ctx.fillText('✨ КУПОЛ НАД ГОЛОВОЙ (+90° ЗЕНИТ)', cx - 80, 26)

    // 3. Anatomical Head Silhouette
    ctx.beginPath()
    // Neck base (back)
    ctx.moveTo(cx - 80, cy + 75)
    // Nape up to Occiput
    ctx.bezierCurveTo(cx - 85, cy + 35, cx - 105, cy + 10, cx - 100, cy - 25)
    // Occiput to Crown (Top of skull)
    ctx.bezierCurveTo(cx - 95, cy - 70, cx - 35, cy - 88, cx + 10, cy - 85)
    // Forehead
    ctx.bezierCurveTo(cx + 45, cy - 80, cx + 68, cy - 45, cx + 72, cy - 20)
    // Nose bridge & tip
    ctx.lineTo(cx + 70, cy - 8)
    ctx.lineTo(cx + 90, cy + 5)
    ctx.lineTo(cx + 70, cy + 18)
    // Lips & Chin
    ctx.lineTo(cx + 75, cy + 28)
    ctx.lineTo(cx + 68, cy + 42)
    ctx.bezierCurveTo(cx + 72, cy + 55, cx + 60, cy + 68, cx + 45, cy + 72)
    // Jaw to Throat
    ctx.lineTo(cx + 25, cy + 78)

    // Gradient fill head
    const headGrad = ctx.createRadialGradient(cx, cy - 10, 10, cx, cy - 10, 110)
    headGrad.addColorStop(0, 'rgba(236, 72, 153, 0.12)')
    headGrad.addColorStop(0.6, 'rgba(139, 92, 246, 0.08)')
    headGrad.addColorStop(1, 'rgba(0, 0, 0, 0.4)')
    ctx.fillStyle = headGrad
    ctx.fill()

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)'
    ctx.lineWidth = 1.5
    ctx.stroke()

    // 4. Ear contour
    ctx.beginPath()
    ctx.ellipse(cx - 5, cy + 5, 14, 22, 0, 0, Math.PI * 2)
    ctx.strokeStyle = 'rgba(236, 72, 153, 0.4)'
    ctx.lineWidth = 1.5
    ctx.stroke()

    // 5. Trajectory Guide Path
    ctx.beginPath()
    ctx.setLineDash([3, 3])
    ctx.strokeStyle = 'rgba(236, 72, 153, 0.35)'
    ctx.lineWidth = 1.5
    for (let step = 0; step <= 40; step++) {
      const pt = getHeadTrajectoryPoint(step / 40, elevation, w, h)
      if (step === 0) ctx.moveTo(pt.x, pt.y)
      else ctx.lineTo(pt.x, pt.y)
    }
    ctx.stroke()
    ctx.setLineDash([])

    // 6. Anchor point labels
    const anchors = [
      { t: 0.0, label: 'Шея', icon: '🔴' },
      { t: 0.25, label: 'Затылок', icon: '🟣' },
      { t: 0.50, label: 'Ухо', icon: '🔵' },
      { t: 0.75, label: 'Лицо', icon: '🟡' },
      { t: 1.0, label: 'Купол/Небо', icon: '👑' },
    ]

    anchors.forEach((a) => {
      const pt = getHeadTrajectoryPoint(a.t, elevation, w, h)
      ctx.beginPath()
      ctx.arc(pt.x, pt.y, 3.5, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(255, 255, 255, 0.4)'
      ctx.fill()

      ctx.font = '9px system-ui, sans-serif'
      ctx.fillStyle = 'rgba(255, 255, 255, 0.6)'
      ctx.fillText(a.label, pt.x - 12, pt.y + 14)
    })

    // 7. Active Sound Source Orb
    const activePt = getHeadTrajectoryPoint(headPos, elevation, w, h)

    // Glowing aura
    const auraGrad = ctx.createRadialGradient(activePt.x, activePt.y, 2, activePt.x, activePt.y, 28)
    auraGrad.addColorStop(0, 'rgba(236, 72, 153, 0.8)')
    auraGrad.addColorStop(0.4, 'rgba(168, 85, 247, 0.4)')
    auraGrad.addColorStop(1, 'rgba(0, 0, 0, 0)')
    ctx.beginPath()
    ctx.arc(activePt.x, activePt.y, 28, 0, Math.PI * 2)
    ctx.fillStyle = auraGrad
    ctx.fill()

    // Sound wave ripples
    for (let r = 1; r <= 2; r++) {
      ctx.beginPath()
      ctx.arc(activePt.x, activePt.y, 10 + r * 8, 0, Math.PI * 2)
      ctx.strokeStyle = `rgba(236, 72, 153, ${0.4 - r * 0.15})`
      ctx.lineWidth = 1
      ctx.stroke()
    }

    // Core Ball
    ctx.beginPath()
    ctx.arc(activePt.x, activePt.y, 7, 0, Math.PI * 2)
    ctx.fillStyle = '#ffffff'
    ctx.shadowColor = '#ec4899'
    ctx.shadowBlur = 12
    ctx.fill()
    ctx.shadowBlur = 0

  }, [headPos, elevation])

  useEffect(() => {
    redraw()
  }, [redraw])

  const handlePointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    setIsDragging(true)
    handlePointerMove(e)
  }

  const handlePointerUp = () => {
    setIsDragging(false)
  }

  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!isDragging && e.buttons === 0) return
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    // Find closest t along trajectory (0.0 to 1.0)
    let bestT = 0
    let minDist = 999999
    for (let step = 0; step <= 50; step++) {
      const t = step / 50
      const pt = getHeadTrajectoryPoint(t, elevation, CANVAS_W, CANVAS_H)
      const dist = Math.hypot(pt.x - x, pt.y - y)
      if (dist < minDist) {
        minDist = dist
        bestT = t
      }
    }

    update({ head_position: Math.round(bestT * 100) / 100 })
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-md p-4 overflow-y-auto">
      <div className="relative w-full max-w-2xl rounded-2xl border border-pink-500/30 bg-[#0d0d14] p-5 shadow-[0_0_50px_rgba(236,72,153,0.15)] space-y-4 my-auto">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-pink-500 to-violet-600 shadow-md">
              <span className="text-base">👤</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-white">
                  Binaural 3D Head Spatializer 2.5
                </h3>
                <span className="rounded bg-pink-500/20 px-1.5 py-0.5 text-[9px] font-bold text-pink-300 border border-pink-500/30">
                  CROWN & SKY DOME
                </span>
              </div>
              <p className="text-xs text-white/50">
                Трек: <span className="font-mono text-pink-300 font-semibold">{trackName}</span>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-white/40 hover:bg-white/10 hover:text-white transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Instrument Presets Quick Selector */}
        <div className="space-y-1.5">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-pink-300/80 flex items-center gap-1.5">
            <Sparkles size={13} /> Пресеты для инструментов:
          </span>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {INSTRUMENT_PRESETS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => update(p.config)}
                className="group relative flex flex-col items-start rounded-xl border border-white/10 bg-white/[0.03] p-2.5 text-left hover:border-pink-500/50 hover:bg-pink-500/10 transition-all shadow-sm"
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <span className="text-sm">{p.icon}</span>
                  <span className="text-[9px] font-semibold text-pink-300 bg-pink-500/20 px-1.5 py-0.5 rounded border border-pink-500/30">
                    {p.tag}
                  </span>
                </div>
                <span className="text-xs font-bold text-white group-hover:text-pink-200">{p.name}</span>
                <span className="text-[10px] text-white/40 line-clamp-1">{p.desc}</span>
              </button>
            ))}
          </div>
        </div>

        {/* 3D Canvas & Anatomical Head */}
        <div className="relative flex justify-center rounded-2xl border border-white/10 bg-black/60 p-2 overflow-hidden">
          <canvas
            ref={canvasRef}
            width={CANVAS_W}
            height={CANVAS_H}
            onPointerDown={handlePointerDown}
            onPointerUp={handlePointerUp}
            onPointerMove={handlePointerMove}
            className="cursor-crosshair touch-none select-none rounded-xl"
          />

          {/* Quick anatomical anchor pills */}
          <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between gap-1.5">
            {[
              { t: 0.0, label: '🔴 Шея', elev: -15 },
              { t: 0.25, label: '🟣 Затылок', elev: 0 },
              { t: 0.50, label: '🔵 Ухо', elev: 10 },
              { t: 0.75, label: '🟡 Лицо', elev: 15 },
              { t: 1.0, label: '👑 НАД ГОЛОВОЙ', elev: 65 },
            ].map((anc) => (
              <button
                key={anc.label}
                type="button"
                onClick={() => update({ head_position: anc.t, elevation_deg: anc.elev })}
                className={`flex-1 rounded-lg border px-1.5 py-1 text-center text-[10px] font-medium transition-all ${
                  Math.abs(headPos - anc.t) < 0.15
                    ? 'border-pink-400 bg-pink-500/25 text-white shadow-sm shadow-pink-500/30 font-bold'
                    : 'border-white/10 bg-black/40 text-white/60 hover:border-white/30'
                }`}
              >
                {anc.label}
              </button>
            ))}
          </div>
        </div>

        {/* Controls Grid */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 pt-1">
          <Slider
            label="Траектория (Шея ➔ Затылок ➔ Ухо ➔ Лицо ➔ Макушка)"
            value={headPos}
            min={0.0}
            max={1.0}
            step={0.01}
            onChange={(v) => update({ head_position: v })}
            format={(v) => {
              if (v < 0.2) return '🔴 Шея (Neck)'
              if (v < 0.4) return '🟣 Затылок (Back)'
              if (v < 0.65) return '🔵 Ухо (Ear)'
              if (v < 0.85) return '🟡 Лицо (Face)'
              return '👑 Над головой (Sky)'
            }}
          />
          <Slider
            label="Высота / Купол (Elevation: Шея ➔ Зенит над головой)"
            value={elevation}
            min={-45}
            max={90}
            step={1}
            unit="°"
            onChange={(v) => update({ elevation_deg: v })}
            format={(v) => `${v > 0 ? '+' : ''}${v}° ${v >= 45 ? '👑 (Над головой)' : ''}`}
          />
          <Slider
            label="Азимут (Панорама)"
            value={azimuth}
            min={-90}
            max={90}
            step={1}
            unit="°"
            onChange={(v) => update({ azimuth_deg: v })}
            format={(v) => `${v > 0 ? 'R ' : v < 0 ? 'L ' : ''}${Math.abs(v)}°`}
          />
          <Slider
            label="Дистанция"
            value={distance}
            min={0.3}
            max={3.0}
            step={0.1}
            unit="m"
            onChange={(v) => update({ distance_m: v })}
            format={(v) => `${v.toFixed(1)} m`}
          />
          <Slider
            label="Dry / Wet Микс"
            value={mix}
            min={0.0}
            max={1.0}
            step={0.01}
            onChange={(v) => update({ mix: v })}
            format={(v) => `${Math.round(v * 100)}%`}
          />
          <div className="flex items-center justify-between pt-3">
            <span className="text-xs text-white/70 font-medium">Mono-Maker (&lt;120Hz Саб в центре)</span>
            <button
              type="button"
              onClick={() => update({ bass_mono: !bassMono })}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                bassMono
                  ? 'bg-violet-500/30 text-violet-200 border border-violet-400/40'
                  : 'bg-white/5 text-white/40 border border-white/10'
              }`}
            >
              {bassMono ? 'ВКЛЮЧЕН (Центр)' : 'ВЫКЛЮЧЕН'}
            </button>
          </div>
        </div>

        {/* Room Acoustics Simulator */}
        <div className="rounded-xl bg-black/40 border border-white/10 p-3 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-white/70 font-medium">Акустика помещения (Room Model)</span>
            <span className="text-white/40 text-[11px] font-mono">{(roomAmount * 100).toFixed(0)}% Отражений</span>
          </div>
          <div className="grid grid-cols-5 gap-1.5">
            {[
              { id: 'none', label: 'Dry' },
              { id: 'vocal_booth', label: 'Booth' },
              { id: 'studio', label: 'Studio' },
              { id: 'club', label: 'Club' },
              { id: 'cathedral', label: 'Cathedral' },
            ].map((rm) => (
              <button
                key={rm.id}
                type="button"
                onClick={() => update({ room_model: rm.id as any })}
                className={`py-1 rounded-lg text-center text-[10px] font-medium transition-all ${
                  roomModel === rm.id
                    ? 'bg-gradient-to-r from-pink-500 to-violet-600 text-white shadow-sm'
                    : 'bg-white/5 text-white/60 hover:bg-white/10'
                }`}
              >
                {rm.label}
              </button>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-white/10 pt-3">
          <Button
            variant="outline"
            onClick={() =>
              update({
                head_position: 0.50,
                azimuth_deg: 0,
                elevation_deg: 0,
                distance_m: 1.0,
                mix: 1.0,
                bass_mono: true,
                room_model: 'none',
                room_amount: 0.25,
              })
            }
          >
            <RotateCcw size={14} /> Сбросить
          </Button>
          <Button variant="primary" onClick={onClose}>
            Применить и Закрыть
          </Button>
        </div>
      </div>
    </div>
  )
}
