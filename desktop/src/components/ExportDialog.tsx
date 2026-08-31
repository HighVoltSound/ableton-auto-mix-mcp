import { useState } from 'react'
import { Download, FileAudio, Radio, CircleCheck, TriangleAlert, X, HelpCircle } from 'lucide-react'
import type { EqBand, ExportResult, TrackCorrection } from '@/types'
import { api } from '@/lib/api'
import { Badge, Button, Spinner } from './ui'
import { useLanguage } from '@/i18n'

interface ExportDialogProps {
  corrections: TrackCorrection[]
  eqBands?: EqBand[]
  previewPath?: string
  onClose: () => void
}

type ExportMode = 'file' | 'live' | 'json'
type ExportFormat = 'wav' | 'flac' | 'mp3'

const MODE_INFO: Record<ExportMode, { icon: typeof FileAudio; labelKey: string; descKey: string; tooltip: string }> = {
  file: { icon: FileAudio, labelKey: 'export.saveFile', descKey: 'export.worksOffline', tooltip: 'Save .als session file for Ableton Live 11/12' },
  live: { icon: Radio, labelKey: 'export.applyToLive', descKey: 'export.requiresAbleton', tooltip: 'Push corrections directly to running Ableton Live via OSC' },
  json: { icon: Download, labelKey: 'export.jsonSettings', descKey: 'export.jsonHint', tooltip: 'Universal JSON format importable into any DAW via scripting' },
}

export function ExportDialog({ corrections, eqBands = [], previewPath, onClose }: ExportDialogProps) {
  const { t } = useLanguage()
  const [mode, setMode] = useState<ExportMode>('file')
  const [sessionPath, setSessionPath] = useState('')
  const [tempo, setTempo] = useState(120)
  const [exporting, setExporting] = useState(false)
  const [result, setResult] = useState<ExportResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Format export state
  const [fmt, setFmt] = useState<ExportFormat>('wav')
  const [bitDepth, setBitDepth] = useState('PCM_16')
  const [mp3Bitrate, setMp3Bitrate] = useState('192k')
  const [flacCompression, setFlacCompression] = useState(5)
  const [fmtExporting, setFmtExporting] = useState(false)
  const [fmtResult, setFmtResult] = useState<string | null>(null)
  const [fmtError, setFmtError] = useState<string | null>(null)

  const handleExport = async () => {
    setExporting(true)
    setError(null)
    setResult(null)
    try {
      const eqDeltas = eqBands
        .filter((b) => b.enabled)
        .map((b) => ({ type: b.type, freq: b.freq, gain_db: b.gain, q: b.q }))
      const merged = eqDeltas.length > 0
        ? corrections.map((c) => ({ ...c, eq: [...(c.eq ?? []), ...eqDeltas] }))
        : corrections
      const res = await api.exportCorrections({
        corrections: merged,
        mode,
        session_path: sessionPath.trim() || null,
        tempo,
      })
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('export.exportFailed'))
    } finally {
      setExporting(false)
    }
  }

  const success = (result?.applied ?? 0) > 0 && (result?.errors?.length ?? 0) === 0
  const hasErrors = (result?.errors?.length ?? 0) > 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-2xl border border-white/10 bg-white/[0.04] p-6 shadow-[0_8px_40px_rgb(0_0_0/0.35)] backdrop-blur-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-5 flex items-center justify-between">
          <h3 className="text-base font-semibold text-white">{t('export.title')}</h3>
          <button type="button" onClick={onClose} className="rounded-lg p-1 text-white/40 hover:bg-white/10 hover:text-white">
            <X size={18} />
          </button>
        </div>

        {/* Corrections summary */}
        {corrections.length > 0 && (
          <div className="mb-4 rounded-xl border border-white/[0.07] bg-black/25 p-3">
            <p className="mb-2 text-xs font-medium text-white/55">
              {corrections.length} {corrections.length === 1 ? t('export.trackCorrection').replace('{count}', '1').replace('1 ', '') : t('export.trackCorrections').replace('{count}', String(corrections.length))}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {corrections.map((c, i) => {
                const name = c.name ?? c.file ?? `Track ${i}`
                const vol = typeof c.volume_db === 'number' ? c.volume_db : undefined
                const pan = typeof c.pan === 'number' ? c.pan : undefined
                return (
                  <Badge key={i} tone="violet">
                    {name}
                    {typeof vol === 'number' && vol !== 0 ? ` ${vol > 0 ? '+' : ''}${vol.toFixed(1)}dB` : ''}
                    {typeof pan === 'number' && Math.abs(pan) > 0.01 ? ` ${pan < 0 ? 'L' : 'R'}${Math.round(Math.abs(pan) * 100)}` : ''}
                  </Badge>
                )
              })}
            </div>
          </div>
        )}

        {/* Mode selection — compact grid with tooltips */}
        <div className="mb-4">
          <p className="mb-2 text-xs font-medium text-white/55">{t('export.exportMode')}</p>
          <div className="grid grid-cols-3 gap-2">
            {(Object.keys(MODE_INFO) as ExportMode[]).map((m) => {
              const info = MODE_INFO[m]
              const Icon = info.icon
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  title={info.tooltip}
                  className={`group relative flex flex-col items-center gap-1.5 rounded-xl border px-3 py-3 text-center transition-all ${
                    mode === m
                      ? 'border-violet-400/50 bg-violet-500/10 text-violet-200'
                      : 'border-white/10 bg-white/[0.02] text-white/60 hover:border-white/20'
                  }`}
                >
                  <Icon size={18} />
                  <span className="text-[11px] font-medium">{t(info.labelKey)}</span>
                  <span className="text-[9px] text-white/35">{t(info.descKey)}</span>
                  <HelpCircle size={12} className="absolute top-1.5 right-1.5 text-white/20 opacity-0 group-hover:opacity-100 transition-opacity" />
                </button>
              )
            })}
          </div>
        </div>

        {/* Mode-specific options */}
        {mode === 'file' && (
          <div className="mb-4 space-y-3">
            <label className="block">
              <span className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-white/45">{t('export.outputPath')}</span>
              <input
                type="text"
                value={sessionPath}
                onChange={(e) => setSessionPath(e.target.value)}
                placeholder="session.als"
                className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 font-mono text-xs text-white/90 placeholder:text-white/25 focus:border-violet-400/60 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-white/45">{t('export.tempo')}</span>
              <input
                type="number"
                value={tempo}
                onChange={(e) => setTempo(Number(e.target.value) || 120)}
                min={20}
                max={300}
                className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 font-mono text-xs text-white/90 focus:border-violet-400/60 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
              />
            </label>
          </div>
        )}

        {mode === 'json' && (
          <div className="mb-4">
            <label className="block">
              <span className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-white/45">{t('export.outputPath')}</span>
              <input
                type="text"
                value={sessionPath}
                onChange={(e) => setSessionPath(e.target.value)}
                placeholder="mix_corrections.json"
                className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 font-mono text-xs text-white/90 placeholder:text-white/25 focus:border-violet-400/60 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
              />
            </label>
          </div>
        )}

        {/* Export button */}
        <div className="flex items-center gap-3">
          <Button onClick={handleExport} disabled={exporting || corrections.length === 0}>
            {exporting ? <Spinner /> : <Download size={15} />}
            {exporting ? t('export.exporting') : t('export.exportBtn')}
          </Button>
          <Button variant="ghost" onClick={onClose}>{t('export.cancel')}</Button>
        </div>

        {/* Result */}
        {result && (
          <div className="mt-4 rounded-xl border border-white/[0.07] bg-black/25 p-4">
            {success ? (
              <div className="flex items-start gap-3">
                <CircleCheck size={20} className="mt-0.5 shrink-0 text-emerald-300" />
                <div>
                  <p className="text-sm font-medium text-emerald-200">{t('export.exportSuccessful')}</p>
                  <p className="mt-1 text-xs text-white/50">
                    {result.applied} {result.applied === 1 ? 'correction' : 'corrections'} applied
                    {result.session_path && (
                      <span className="ml-2 font-mono text-white/70">→ {result.session_path}</span>
                    )}
                  </p>
                  {result.mode === 'file' && result.session_path && (
                    <Button
                      variant="primary"
                      className="mt-2 py-1 px-3 text-xs bg-gradient-to-r from-violet-600 to-indigo-600"
                      onClick={() => api.openAls(result.session_path!).catch((e) => setError(e.message))}
                    >
                      🎹 Open in Ableton Live
                    </Button>
                  )}
                </div>
              </div>
            ) : hasErrors ? (
              <div className="flex items-start gap-3">
                <TriangleAlert size={20} className="mt-0.5 shrink-0 text-amber-300" />
                <div>
                  <p className="text-sm font-medium text-amber-200">{t('export.exportIssues')}</p>
                  <ul className="mt-1 space-y-0.5 text-xs text-white/50">
                    {result.errors?.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                </div>
              </div>
            ) : null}
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-xl border border-red-400/30 bg-red-500/10 p-4">
            <div className="flex items-start gap-3">
              <TriangleAlert size={20} className="mt-0.5 shrink-0 text-red-300" />
              <div>
                <p className="text-sm font-medium text-red-200">{t('export.exportFailed')}</p>
                <p className="mt-1 text-xs text-white/50">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Audio format export */}
        {previewPath && (
          <div className="mt-4 rounded-xl border border-white/[0.07] bg-black/25 p-4">
            <p className="mb-2 text-xs font-medium text-white/55">{t('mix.exportFormats')}</p>
            <div className="flex items-center gap-2 mb-3">
              {(['wav', 'flac', 'mp3'] as ExportFormat[]).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFmt(f)}
                  title={f === 'wav' ? 'Lossless, any bit depth' : f === 'flac' ? 'Lossless, smaller files' : 'Lossy, compressed'}
                  className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                    fmt === f ? 'border-violet-400/50 bg-violet-500/10 text-violet-300' : 'border-white/10 text-white/50 hover:border-white/20'
                  }`}
                >
                  {f.toUpperCase()}
                </button>
              ))}
            </div>
            {fmt === 'wav' && (
              <label className="mb-2 block">
                <span className="text-[10px] text-white/40">{t('mix.bitDepth')}</span>
                <select value={bitDepth} onChange={(e) => setBitDepth(e.target.value)}
                  className="mt-0.5 w-full rounded bg-black/40 px-2 py-1 text-xs text-white/70 border border-white/10">
                  <option value="PCM_16">16-bit</option>
                  <option value="PCM_24">24-bit</option>
                  <option value="PCM_32">32-bit int</option>
                  <option value="FLOAT">32-bit float</option>
                </select>
              </label>
            )}
            {fmt === 'mp3' && (
              <label className="mb-2 block">
                <span className="text-[10px] text-white/40">{t('mix.mp3Bitrate')}</span>
                <select value={mp3Bitrate} onChange={(e) => setMp3Bitrate(e.target.value)}
                  className="mt-0.5 w-full rounded bg-black/40 px-2 py-1 text-xs text-white/70 border border-white/10">
                  <option value="128k">128 kbps</option>
                  <option value="192k">192 kbps</option>
                  <option value="256k">256 kbps</option>
                  <option value="320k">320 kbps</option>
                </select>
              </label>
            )}
            {fmt === 'flac' && (
              <label className="mb-2 block">
                <span className="text-[10px] text-white/40">Compression (0–8)</span>
                <input type="range" min={0} max={8} step={1} value={flacCompression}
                  onChange={(e) => setFlacCompression(Number(e.target.value))}
                  className="w-full accent-violet-500" />
                <span className="block text-center font-mono text-[10px] text-white/50">{flacCompression}</span>
              </label>
            )}
            <Button
              variant="outline"
              onClick={async () => {
                setFmtExporting(true)
                setFmtError(null)
                setFmtResult(null)
                try {
                  const res = await api.exportFormat({
                    input_path: previewPath,
                    format: fmt,
                    bit_depth: bitDepth,
                    mp3_bitrate: mp3Bitrate,
                    flac_compression: flacCompression,
                  })
                  setFmtResult(res.path ?? '')
                } catch (err) {
                  setFmtError(err instanceof Error ? err.message : 'Export failed')
                } finally {
                  setFmtExporting(false)
                }
              }}
              disabled={fmtExporting}
            >
              {fmtExporting ? <Spinner /> : <Download size={15} />}
              {t('mix.exportFormat')} → .{fmt}
            </Button>
            {fmtResult && <p className="mt-2 text-xs text-emerald-300 break-all">{fmtResult}</p>}
            {fmtError && <p className="mt-2 text-xs text-red-300">{fmtError}</p>}
          </div>
        )}
      </div>
    </div>
  )
}
