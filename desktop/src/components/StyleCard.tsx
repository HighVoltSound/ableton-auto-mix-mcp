import React, { useRef, useState } from 'react'
import { StyleArtwork, STYLES_METADATA } from './styleArtworks'
import type { MixStyle } from '@/types'
import { Sparkles, Check } from 'lucide-react'

export interface StyleCardProps {
  style: MixStyle
  active: boolean
  suggested: boolean
  onSelect: () => void
}

export function StyleCard({ style, active, suggested, onSelect }: StyleCardProps) {
  const cardRef = useRef<HTMLDivElement>(null)
  const [transform, setTransform] = useState('')
  const [glarePos, setGlarePos] = useState({ x: 50, y: 50, opacity: 0 })
  const [isHovered, setIsHovered] = useState(false)

  const meta = STYLES_METADATA[style.id] ?? {
    name: style.name ?? style.id,
    subtitle: 'Профессиональный студийный стиль сведения',
    glowColor: 'rgba(168, 85, 247, 0.4)',
    accentColor: '#a855f7',
    gradientFrom: 'from-purple-500/20',
    gradientTo: 'to-zinc-950/80',
    tags: ['Custom EQ', 'Master Chain'],
    lufsHint: style.targets?.lufs ? `${style.targets.lufs} LUFS` : '-9.0 LUFS',
    bpmHint: 'Universal',
  }

  // 3D Parallax Tilt Handler
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return
    const rect = cardRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    const centerX = rect.width / 2
    const centerY = rect.height / 2

    // Max tilt angle: 12 degrees
    const rotateX = ((y - centerY) / centerY) * -9
    const rotateY = ((x - centerX) / centerX) * 9

    setTransform(
      `perspective(800px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) scale3d(1.025, 1.025, 1.025)`,
    )
    setGlarePos({
      x: (x / rect.width) * 100,
      y: (y / rect.height) * 100,
      opacity: 0.25,
    })
  }

  const handleMouseEnter = () => {
    setIsHovered(true)
  }

  const handleMouseLeave = () => {
    setIsHovered(false)
    setTransform('perspective(800px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)')
    setGlarePos((p) => ({ ...p, opacity: 0 }))
  }

  return (
    <div
      ref={cardRef}
      role="radio"
      aria-checked={active}
      onClick={onSelect}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{
        transform,
        transition: isHovered ? 'transform 0.08s ease-out' : 'transform 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
      }}
      className={`group relative cursor-pointer overflow-hidden rounded-2xl border p-[1px] text-left transition-all duration-300 ${
        active
          ? 'border-transparent shadow-2xl'
          : 'border-white/10 hover:border-white/25 hover:shadow-xl'
      }`}
    >
      {/* Active Glowing Outer Border */}
      {active && (
        <div
          className="absolute -inset-[2px] rounded-2xl blur-[6px] transition-all duration-300"
          style={{ backgroundColor: meta.accentColor, opacity: 0.65 }}
        />
      )}

      {/* Main Glass Card Body */}
      <div className="relative flex h-full flex-col justify-between overflow-hidden rounded-[calc(1rem-1px)] bg-[#11121a] p-5">
        {/* Dynamic Background Artwork Container */}
        <div className="absolute inset-x-0 top-0 h-44 overflow-hidden opacity-90 transition-all duration-500 group-hover:opacity-100 group-hover:h-48">
          <StyleArtwork styleId={style.id} />
          {/* Gradient Fade to Card Bottom */}
          <div className="absolute inset-0 bg-gradient-to-b from-black/20 via-[#11121a]/70 to-[#11121a]" />
        </div>

        {/* 3D Glass Flare Light Reflector */}
        <div
          className="pointer-events-none absolute inset-0 transition-opacity duration-200"
          style={{
            background: `radial-gradient(circle at ${glarePos.x}% ${glarePos.y}%, rgba(255,255,255,${glarePos.opacity}) 0%, transparent 65%)`,
          }}
        />

        {/* Header Badges & Equalizer */}
        <div className="relative z-10 flex items-start justify-between">
          <div className="flex items-center gap-1.5">
            {suggested && (
              <span className="flex items-center gap-1 rounded-full bg-violet-500/30 px-2.5 py-0.5 text-[11px] font-semibold text-violet-200 border border-violet-400/50 shadow-md backdrop-blur-md">
                <Sparkles size={11} className="animate-pulse" /> Рекомендация
              </span>
            )}
            {active && (
              <span
                className="flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-bold text-white shadow-lg backdrop-blur-md"
                style={{ backgroundColor: meta.accentColor }}
              >
                <Check size={11} /> ВЫБРАН
              </span>
            )}
          </div>

          {/* Dancing Audio Visualizer Bars */}
          <div className="flex items-end gap-1 h-5 px-2 py-1 rounded-md bg-black/60 border border-white/15 backdrop-blur-md shadow-md">
            {[0.4, 0.9, 0.6, 1.0, 0.5].map((baseH, idx) => (
              <span
                key={idx}
                className="w-1 rounded-full transition-all duration-200"
                style={{
                  height: active || isHovered ? `${Math.max(20, Math.min(100, (baseH + Math.sin(idx * 2 + (isHovered ? 3 : 1)) * 0.4) * 100))}%` : '25%',
                  backgroundColor: active || isHovered ? meta.accentColor : 'rgba(255, 255, 255, 0.35)',
                }}
              />
            ))}
          </div>
        </div>

        {/* Bottom Content Info */}
        <div className="relative z-10 mt-24 space-y-3">
          <div>
            <div className="flex items-center justify-between">
              <h4 className="text-lg font-bold tracking-tight text-white drop-shadow-md">
                {meta.name}
              </h4>
              <span className="font-mono text-xs font-semibold text-white/90 bg-black/50 px-2 py-0.5 rounded-md border border-white/15 backdrop-blur-md">
                {meta.lufsHint}
              </span>
            </div>
            <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-white/70">
              {meta.subtitle}
            </p>
          </div>

          {/* Key Characteristic Tags */}
          <div className="flex flex-wrap gap-1.5 pt-1">
            {meta.tags.map((tag, tIdx) => (
              <span
                key={tIdx}
                className="rounded-md bg-white/[0.04] px-2 py-0.5 text-[10px] font-medium text-white/70 border border-white/[0.07]"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
