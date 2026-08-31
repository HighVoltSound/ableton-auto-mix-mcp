import { useState } from 'react'
import { Disc3, CheckCircle2, Sliders, Upload, Sparkles } from 'lucide-react'
import { Card, Button, Slider, Spinner, Badge } from './ui'
import { api } from '@/lib/api'
import type { ReferenceAnalysis, EqBand } from '@/types'

export interface ReferenceMatcherProps {
  currentEnvelope?: number[]
  onApplyMatchEq: (bands: EqBand[]) => void
}

export function ReferenceMatcher({
  currentEnvelope,
  onApplyMatchEq,
}: ReferenceMatcherProps) {
  const [refPath, setRefPath] = useState('')
  const [analysis, setAnalysis] = useState<ReferenceAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [strength, setStrength] = useState(0.8)
  const [matchBands, setMatchBands] = useState<EqBand[]>([])
  const [applied, setApplied] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAnalyze = async (path: string) => {
    if (!path.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.analyzeReference(path.trim())
      setAnalysis(res)

      // Auto compute match curve if current envelope is available
      if (currentEnvelope && currentEnvelope.length > 0) {
        const bands = await api.computeMatchEq(currentEnvelope, res.spectral_envelope, strength)
        const formattedBands: EqBand[] = bands.map((b, idx) => ({
          id: idx + 500,
          type: 'bell',
          freq: b.frequency,
          gain: b.gain_db,
          q: b.q ?? 1.4,
          enabled: true,
        }))
        setMatchBands(formattedBands)
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Не удалось проанализировать референсный трек')
    } finally {
      setLoading(false)
    }
  }

  const handleApply = () => {
    onApplyMatchEq(matchBands)
    setApplied(true)
  }

  return (
    <Card className="p-6 border-violet-500/30 bg-[#12131f]/80 backdrop-blur-2xl">
      <div className="flex items-center justify-between border-b border-white/[0.08] pb-4 mb-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-pink-500 shadow-md">
            <Disc3 size={20} className="text-white animate-spin-slow" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              AI Reference Track Matcher
              <span className="rounded bg-pink-500/20 px-2 py-0.5 text-[10px] font-bold text-pink-300 border border-pink-500/30">AI MATCH</span>
            </h3>
            <p className="text-xs text-white/50">
              Сравнение и автоматическая подгонка частотного баланса под любой эталонный трек
            </p>
          </div>
        </div>
        {analysis && (
          <Badge tone="violet">
            <Sparkles size={12} /> {analysis.lufs} LUFS
          </Badge>
        )}
      </div>

      {/* Path Input / Drop Zone */}
      <div className="space-y-4">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              type="text"
              value={refPath}
              onChange={(e) => setRefPath(e.target.value)}
              placeholder="Путь к референсному треку (WAV / MP3)..."
              className="w-full rounded-xl border border-white/15 bg-black/40 px-4 py-2.5 text-sm text-white placeholder-white/30 focus:border-violet-400 focus:outline-none"
            />
          </div>
          <Button
            variant="primary"
            onClick={() => handleAnalyze(refPath)}
            disabled={loading || !refPath.trim()}
          >
            {loading ? <Spinner /> : <Upload size={15} />}
            Анализировать
          </Button>
        </div>

        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300">
            {error}
          </div>
        )}

        {/* Metrics Grid */}
        {analysis && (
          <div className="space-y-4 pt-2">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="rounded-xl bg-white/[0.03] border border-white/[0.07] p-3 text-center">
                <span className="text-[10px] text-white/40 uppercase tracking-wider block">Громкость</span>
                <span className="text-base font-bold font-mono text-violet-300">{analysis.lufs} LUFS</span>
              </div>
              <div className="rounded-xl bg-white/[0.03] border border-white/[0.07] p-3 text-center">
                <span className="text-[10px] text-white/40 uppercase tracking-wider block">RMS Уровень</span>
                <span className="text-base font-bold font-mono text-white/90">{analysis.rms_db} dB</span>
              </div>
              <div className="rounded-xl bg-white/[0.03] border border-white/[0.07] p-3 text-center">
                <span className="text-[10px] text-white/40 uppercase tracking-wider block">Динамика (Crest)</span>
                <span className="text-base font-bold font-mono text-emerald-300">{analysis.crest_factor_db} dB</span>
              </div>
              <div className="rounded-xl bg-white/[0.03] border border-white/[0.07] p-3 text-center">
                <span className="text-[10px] text-white/40 uppercase tracking-wider block">Стереобаза</span>
                <span className="text-base font-bold font-mono text-pink-300">{(analysis.stereo_width * 100).toFixed(0)}%</span>
              </div>
            </div>

            {/* Match Controls */}
            <div className="rounded-xl bg-black/30 border border-white/10 p-4 space-y-3">
              <Slider
                label="Сила Match EQ (Target Strength)"
                value={strength}
                min={0.1}
                max={1.0}
                step={0.05}
                onChange={async (v) => {
                  setStrength(v)
                  if (currentEnvelope && analysis) {
                    const bands = await api.computeMatchEq(currentEnvelope, analysis.spectral_envelope, v)
                    setMatchBands(bands.map((b, idx) => ({
                      id: idx + 500,
                      type: 'bell',
                      freq: b.frequency,
                      gain: b.gain_db,
                      q: b.q ?? 1.4,
                      enabled: true,
                    })))
                  }
                }}
                format={(v) => `${Math.round(v * 100)}%`}
              />

              <div className="flex items-center justify-between pt-2">
                <span className="text-xs text-white/60">
                  Сгенерировано <span className="font-mono font-bold text-white">{matchBands.length}</span> корректирующих полос EQ
                </span>
                <Button
                  variant="primary"
                  onClick={handleApply}
                  className="bg-gradient-to-r from-emerald-500 to-teal-500 shadow-emerald-500/30"
                >
                  {applied ? <CheckCircle2 size={15} /> : <Sliders size={15} />}
                  {applied ? 'Match EQ Применен!' : 'Применить к Мастеру'}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}
