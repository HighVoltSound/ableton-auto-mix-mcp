import ambientImg from '@/assets/styles/ambient.jpg'
import balancedImg from '@/assets/styles/balanced.jpg'
import breaksImg from '@/assets/styles/breaks.jpg'
import dnbImg from '@/assets/styles/drum_n_bass.jpg'
import dubstepImg from '@/assets/styles/dubstep.jpg'
import hiphopImg from '@/assets/styles/hip_hop.jpg'
import lofiImg from '@/assets/styles/lo_fi.jpg'
import popImg from '@/assets/styles/pop.jpg'
import technoImg from '@/assets/styles/techno.jpg'
import tranceImg from '@/assets/styles/trance.jpg'
import trapImg from '@/assets/styles/trap.jpg'

export interface StyleMeta {
  name: string
  subtitle: string
  glowColor: string
  accentColor: string
  gradientFrom: string
  gradientTo: string
  tags: string[]
  lufsHint: string
  bpmHint: string
}

export const STYLE_IMAGES: Record<string, string> = {
  ambient: ambientImg,
  balanced: balancedImg,
  breaks: breaksImg,
  drum_n_bass: dnbImg,
  dubstep: dubstepImg,
  hip_hop: hiphopImg,
  lo_fi: lofiImg,
  pop: popImg,
  techno: technoImg,
  trance: tranceImg,
  trap: trapImg,
}

export const STYLES_METADATA: Record<string, StyleMeta> = {
  ambient: {
    name: 'Ambient / Drone',
    subtitle: 'Космические текстуры, глубокий воздух и бесконечный релакс',
    glowColor: 'rgba(56, 189, 248, 0.45)',
    accentColor: '#38bdf8',
    gradientFrom: 'from-sky-500/30',
    gradientTo: 'to-indigo-950/80',
    tags: ['Ethereal Space', 'Wide Air', 'Deep Drone'],
    lufsHint: '-14 LUFS',
    bpmHint: '60–90 BPM',
  },
  balanced: {
    name: 'Balanced Master',
    subtitle: 'Студийный эталон, кристальная прозрачность и нейтральный баланс',
    glowColor: 'rgba(234, 179, 8, 0.4)',
    accentColor: '#eab308',
    gradientFrom: 'from-amber-500/25',
    gradientTo: 'to-zinc-950/85',
    tags: ['Mastering Studio', 'Tube Warmth', 'Precision Linear'],
    lufsHint: '-10 LUFS',
    bpmHint: 'Universal',
  },
  breaks: {
    name: 'Breakbeat / Breaks',
    subtitle: 'Ломаный грув, плотные сбивки и винтажный аналоговый панч',
    glowColor: 'rgba(249, 115, 22, 0.45)',
    accentColor: '#f97316',
    gradientFrom: 'from-orange-500/30',
    gradientTo: 'to-stone-950/85',
    tags: ['Vinyl Heat', 'Punchy Break', 'Analog Grit'],
    lufsHint: '-8.5 LUFS',
    bpmHint: '128–138 BPM',
  },
  drum_n_bass: {
    name: 'Drum & Bass',
    subtitle: 'Скорость 174 BPM, мощнейший Reese Bass и острые транзиенты',
    glowColor: 'rgba(250, 204, 21, 0.5)',
    accentColor: '#facc15',
    gradientFrom: 'from-yellow-500/35',
    gradientTo: 'to-neutral-950/90',
    tags: ['174 BPM Rave', 'Reese Sub', 'Fast Transients'],
    lufsHint: '-7.5 LUFS',
    bpmHint: '172–176 BPM',
  },
  dubstep: {
    name: 'Dubstep / Riddim',
    subtitle: 'Агрессивный саб-бас, рычащие вобблы и сокрушительная динамика',
    glowColor: 'rgba(34, 197, 94, 0.45)',
    accentColor: '#22c55e',
    gradientFrom: 'from-emerald-500/30',
    gradientTo: 'to-slate-950/90',
    tags: ['Sub Wall', 'Toxic Wobble', 'Heavy Impact'],
    lufsHint: '-7.0 LUFS',
    bpmHint: '140–150 BPM',
  },
  hip_hop: {
    name: 'Hip-Hop / Boom-Bap',
    subtitle: 'Качающий 808 бас, винтажный MPC-свинг и плотный вокальный центр',
    glowColor: 'rgba(239, 68, 68, 0.4)',
    accentColor: '#ef4444',
    gradientFrom: 'from-rose-500/30',
    gradientTo: 'to-zinc-950/85',
    tags: ['MPC Sampler', 'Gold Vinyl', 'Heavy 808 Punch'],
    lufsHint: '-9.0 LUFS',
    bpmHint: '85–95 BPM',
  },
  lo_fi: {
    name: 'Lo-Fi Chillhop',
    subtitle: 'Теплый кассетный шум, сатурация ленты и ностальгический закат',
    glowColor: 'rgba(244, 114, 182, 0.45)',
    accentColor: '#f472b6',
    gradientFrom: 'from-pink-500/25',
    gradientTo: 'to-purple-950/85',
    tags: ['Retro Tape', 'Sunset Chill', 'Cozy Warmth'],
    lufsHint: '-12 LUFS',
    bpmHint: '70–85 BPM',
  },
  pop: {
    name: 'Modern Pop / Radio',
    subtitle: 'Глянцевый радио-блеск, яркий открытый вокал и плотный компрессор',
    glowColor: 'rgba(236, 72, 153, 0.5)',
    accentColor: '#ec4899',
    gradientFrom: 'from-fuchsia-500/30',
    gradientTo: 'to-rose-950/85',
    tags: ['Vocal Booth', 'Radio Hit', 'Commercial Polish'],
    lufsHint: '-8.0 LUFS',
    bpmHint: '110–128 BPM',
  },
  techno: {
    name: 'Industrial Techno',
    subtitle: 'Гипнотическая 4/4 бочка, рейв-мрак и монолитный низкочастотный рокот',
    glowColor: 'rgba(203, 213, 225, 0.45)',
    accentColor: '#cbd5e1',
    gradientFrom: 'from-slate-400/25',
    gradientTo: 'to-black/95',
    tags: ['Berlin Bunker', '4/4 Strobe', 'Raw Industrial'],
    lufsHint: '-7.5 LUFS',
    bpmHint: '130–145 BPM',
  },
  trance: {
    name: 'Uplifting Trance',
    subtitle: 'Эйфорические суперпилы, стадионный полет и кристальные арпеджио',
    glowColor: 'rgba(99, 102, 241, 0.5)',
    accentColor: '#6366f1',
    gradientFrom: 'from-indigo-500/35',
    gradientTo: 'to-blue-950/90',
    tags: ['Stadium Lasers', 'Euphoric Drop', 'Supersaw Power'],
    lufsHint: '-8.0 LUFS',
    bpmHint: '138–142 BPM',
  },
  trap: {
    name: 'Modern Trap',
    subtitle: 'Перегруженный 808 саб, пулеметные хэты 1/32 и темная атмосфера',
    glowColor: 'rgba(168, 85, 247, 0.5)',
    accentColor: '#a855f7',
    gradientFrom: 'from-purple-500/35',
    gradientTo: 'to-neutral-950/90',
    tags: ['Night City 808', 'Rapid 1/32 Rolls', 'Dark Luxury'],
    lufsHint: '-7.0 LUFS',
    bpmHint: '130–160 BPM',
  },
}

export function StyleArtwork({ styleId, className = '' }: { styleId: string; className?: string }) {
  const id = styleId.toLowerCase()
  const imgUrl = STYLE_IMAGES[id]

  if (!imgUrl) {
    return <div className={`w-full h-full bg-gradient-to-br from-violet-600/30 to-black ${className}`} />
  }

  return (
    <div className={`relative w-full h-full overflow-hidden ${className}`}>
      <img
        src={imgUrl}
        alt={styleId}
        className="w-full h-full object-cover object-center transform transition-transform duration-700 ease-out group-hover:scale-110"
        loading="lazy"
      />
      {/* Cinematic Gradient Vignette Overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-[#11121a] via-[#11121a]/50 to-transparent" />
      <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-transparent to-transparent" />
    </div>
  )
}
