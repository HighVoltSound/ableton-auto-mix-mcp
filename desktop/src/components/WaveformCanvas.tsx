import { useCallback, useEffect, useRef } from 'react'

interface WaveformCanvasProps {
  peaks: number[]
  width?: number
  height?: number
  color?: string
  highlight?: { start: number; end: number }
  onSeek?: (position: number) => void
}

const GRADIENT_START = '#7c3aed'
const GRADIENT_END = '#d946ef'
const HIGHLIGHT_COLOR = 'rgba(217,70,239,0.25)'

export function WaveformCanvas({
  peaks,
  width = 600,
  height = 64,
  highlight,
  onSeek,
}: WaveformCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const peaksRef = useRef(peaks)
  peaksRef.current = peaks

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    canvas.width = width * dpr
    canvas.height = height * dpr
    ctx.scale(dpr, dpr)

    ctx.clearRect(0, 0, width, height)

    const data = peaksRef.current
    if (data.length === 0) return

    const mid = height / 2
    const maxPeak = Math.max(...data, 0.01)
    const barWidth = width / data.length

    const grad = ctx.createLinearGradient(0, 0, width, 0)
    grad.addColorStop(0, GRADIENT_START)
    grad.addColorStop(1, GRADIENT_END)

    if (highlight) {
      const x0 = highlight.start * width
      const x1 = highlight.end * width
      ctx.fillStyle = HIGHLIGHT_COLOR
      ctx.fillRect(x0, 0, x1 - x0, height)
    }

    for (let i = 0; i < data.length; i++) {
      const x = i * barWidth
      const amplitude = (data[i] / maxPeak) * (mid - 2)
      ctx.fillStyle = grad
      ctx.fillRect(x, mid - amplitude, Math.max(barWidth - 0.5, 1), amplitude)
      ctx.fillRect(x, mid, Math.max(barWidth - 0.5, 1), amplitude)
    }

    ctx.strokeStyle = 'rgba(255,255,255,0.12)'
    ctx.lineWidth = 0.5
    ctx.beginPath()
    ctx.moveTo(0, mid)
    ctx.lineTo(width, mid)
    ctx.stroke()
  }, [width, height, highlight])

  useEffect(() => {
    draw()
  }, [draw])

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!onSeek) return
      const rect = e.currentTarget.getBoundingClientRect()
      const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
      onSeek(ratio)
    },
    [onSeek],
  )

  return (
    <canvas
      ref={canvasRef}
      style={{ width, height }}
      onClick={handleClick}
      className={onSeek ? 'cursor-pointer' : undefined}
    />
  )
}
