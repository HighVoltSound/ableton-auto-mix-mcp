import { useCallback, useEffect, useRef, useState } from 'react'
import { Card } from './ui'
import { useLanguage } from '@/i18n'

interface LiveSpectrumProps {
  audioRef: React.RefObject<HTMLAudioElement | null>
  fftSize?: number
  smoothing?: number
}

const BAND_COLORS: Record<string, string> = {
  sub: '#8b5cf6',
  bass: '#a78bfa',
  lowMids: '#c4b5fd',
  mids: '#e0d6ff',
  highMids: '#f0abfc',
  highs: '#f5d0fe',
}

const BAND_RANGES: [number, number][] = [
  [20, 60],    // sub
  [60, 250],   // bass
  [250, 500],  // lowMids
  [500, 2000], // mids
  [2000, 6000], // highMids
  [6000, 20000], // highs
]

const BAND_KEYS = ['sub', 'bass', 'lowMids', 'mids', 'highMids', 'highs']

export function LiveSpectrum({ audioRef, fftSize = 2048, smoothing = 0.8 }: LiveSpectrumProps) {
  const { t } = useLanguage()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const analyzerRef = useRef<AnalyserNode | null>(null)
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null)
  const rafRef = useRef<number>(0)
  const [active, setActive] = useState(false)

  const setup = useCallback(() => {
    const audio = audioRef.current
    if (!audio || analyzerRef.current) return

    try {
      const ctx = new AudioContext()
      analyzerRef.current = ctx.createAnalyser()
      analyzerRef.current.fftSize = fftSize
      analyzerRef.current.smoothingTimeConstant = smoothing

      // Reuse existing source if one exists on the audio element
      const src = ctx.createMediaElementSource(audio)
      src.connect(analyzerRef.current)
      analyzerRef.current.connect(ctx.destination)
      sourceRef.current = src
      setActive(true)
    } catch {
      // CORS or already connected — silently disable
    }
  }, [audioRef, fftSize, smoothing])

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    const analyzer = analyzerRef.current
    if (!canvas || !analyzer) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const { width, height } = canvas.getBoundingClientRect()
    canvas.width = width * window.devicePixelRatio
    canvas.height = height * window.devicePixelRatio
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)

    const bufferLength = analyzer.frequencyBinCount
    const dataArray = new Uint8Array(bufferLength)
    analyzer.getByteFrequencyData(dataArray)

    // Clear
    ctx.clearRect(0, 0, width, height)

    // Get audio sample rate for frequency mapping
    const sampleRate = analyzer.context.sampleRate
    const nyquist = sampleRate / 2

    // Draw frequency bars
    const barCount = 64
    const barWidth = width / barCount

    for (let i = 0; i < barCount; i++) {
      // Map bar index to frequency (log scale)
      const freq = 20 * Math.pow(nyquist / 20, i / barCount)
      const binIndex = Math.round((freq / nyquist) * bufferLength)
      const value = dataArray[Math.min(binIndex, bufferLength - 1)]

      const barHeight = (value / 255) * height * 0.85
      const x = i * barWidth

      // Determine color band
      let color = BAND_COLORS.highs
      for (let b = 0; b < BAND_RANGES.length; b++) {
        if (freq >= BAND_RANGES[b][0] && freq < BAND_RANGES[b][1]) {
          color = BAND_COLORS[BAND_KEYS[b]]
          break
        }
      }

      // Gradient bar
      const gradient = ctx.createLinearGradient(x, height, x, height - barHeight)
      gradient.addColorStop(0, color + '40')
      gradient.addColorStop(1, color)

      ctx.fillStyle = gradient
      ctx.fillRect(x + 1, height - barHeight, barWidth - 2, barHeight)

      // Glow effect on top
      ctx.fillStyle = color + '80'
      ctx.fillRect(x + 1, height - barHeight - 2, barWidth - 2, 2)
    }

    // Draw frequency labels
    ctx.fillStyle = 'rgba(255,255,255,0.3)'
    ctx.font = '10px monospace'
    ctx.textAlign = 'center'
    const labels = ['100', '200', '500', '1k', '2k', '5k', '10k']
    for (let i = 0; i < labels.length; i++) {
      const freq = [100, 200, 500, 1000, 2000, 5000, 10000][i]
      const x = (Math.log(freq / 20) / Math.log(nyquist / 20)) * width
      ctx.fillText(labels[i], x, height - 2)
    }

    rafRef.current = requestAnimationFrame(draw)
  }, [])

  useEffect(() => {
    if (active) {
      rafRef.current = requestAnimationFrame(draw)
    }
    return () => {
      cancelAnimationFrame(rafRef.current)
    }
  }, [active, draw])

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">{t('mix.liveSpectrum')}</h3>
        {active && (
          <div className="flex gap-1.5">
            {BAND_KEYS.map((key) => (
              <div
                key={key}
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: BAND_COLORS[key] }}
              />
            ))}
          </div>
        )}
      </div>
      <div className="relative">
        <canvas
          ref={canvasRef}
          className="h-40 w-full rounded-lg bg-black/30"
          style={{ imageRendering: 'pixelated' }}
        />
        {!active && (
          <button
            onClick={setup}
            className="absolute inset-0 flex items-center justify-center text-xs text-white/40 hover:text-white/60 transition-colors"
          >
            {t('mix.clickToActivate')}
          </button>
        )}
      </div>
    </Card>
  )
}
