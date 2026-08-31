import { useState, useEffect, useCallback } from 'react'
import { FileAudio, Plus, Trash2, ChevronDown, Music } from 'lucide-react'
import { IS_TAURI } from '@/lib/api'
import { Button, Card, SectionTitle } from './ui'
import { useLanguage } from '@/i18n'

const INSTRUMENT_ROLES = [
  { id: 'kick', label: 'Kick' },
  { id: 'sub_bass', label: 'Sub Bass' },
  { id: 'bass', label: 'Bass' },
  { id: 'snare', label: 'Snare' },
  { id: 'clap', label: 'Clap' },
  { id: 'hihat', label: 'Hi-Hat' },
  { id: 'percussion', label: 'Percussion' },
  { id: 'lead', label: 'Lead' },
  { id: 'pad', label: 'Pad' },
  { id: 'chord', label: 'Chord' },
  { id: 'arp', label: 'Arp' },
  { id: 'vocal', label: 'Vocal' },
  { id: 'fx', label: 'FX' },
  { id: 'ambient', label: 'Ambient' },
  { id: 'other', label: 'Other' },
]

export interface TrackEntry {
  id: string
  file: File
  name: string
  role: string
}

interface TrackImportProps {
  onReady: (tracks: TrackEntry[], directory: string) => void
}

function guessRole(filename: string): string {
  const lower = filename.toLowerCase()
  if (/kick|kd|kik/.test(lower)) return 'kick'
  if (/sub/.test(lower)) return 'sub_bass'
  if (/bass|bs/.test(lower)) return 'bass'
  if (/snare|sd|sn/.test(lower)) return 'snare'
  if (/clap|cp/.test(lower)) return 'clap'
  if (/hat|hh|oh|ch/.test(lower)) return 'hihat'
  if (/perc|tom|cong|bong/.test(lower)) return 'percussion'
  if (/lead|ld/.test(lower)) return 'lead'
  if (/pad|atmo/.test(lower)) return 'pad'
  if (/chord|st|stab/.test(lower)) return 'chord'
  if (/arp/.test(lower)) return 'arp'
  if (/vox|voc|voi/.test(lower)) return 'vocal'
  if (/fx|fx_|sweep|riser|downlifter/.test(lower)) return 'fx'
  return 'other'
}

let nextId = 0
function makeId() { return `track-${++nextId}-${Date.now()}` }

export function TrackImport({ onReady }: TrackImportProps) {
  const { t } = useLanguage()
  const [tracks, setTracks] = useState<TrackEntry[]>([])
  const [dragOver, setDragOver] = useState(false)

  // Tauri file-drop listener
  useEffect(() => {
    if (!IS_TAURI) return
    let unlisten: (() => void) | null = null
    import('@tauri-apps/api/webview').then(({ getCurrentWebview }) => {
      getCurrentWebview().onDragDropEvent((event) => {
        if (event.payload.type !== 'drop') {
          setDragOver(false)
          return
        }
        setDragOver(false)
        const paths = event.payload.paths
        if (!paths || paths.length === 0) return
        addFilesFromPaths(paths)
      }).then((fn) => { unlisten = fn })
    }).catch(() => {})
    return () => { unlisten?.() }
  }, [tracks])

  const addFilesFromPaths = useCallback(async (paths: string[]) => {
    // In Tauri we get full paths — but can't read them as browser Files.
    // We store the paths and let the backend handle reading.
    const audioExts = ['.wav', '.flac', '.mp3', '.aiff', '.aif']
    const newTracks: TrackEntry[] = []
    for (const p of paths) {
      const ext = p.substring(p.lastIndexOf('.')).toLowerCase()
      if (audioExts.includes(ext)) {
        const name = p.substring(p.lastIndexOf('\\') + 1 || p.lastIndexOf('/') + 1)
        newTracks.push({
          id: makeId(),
          file: null as unknown as File, // path-only in Tauri
          name,
          role: guessRole(name),
        })
      }
    }
    if (newTracks.length > 0) {
      setTracks((prev) => [...prev, ...newTracks])
    }
  }, [])

  // Browser file input fallback
  const onFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    const newTracks = files.map((f) => ({
      id: makeId(),
      file: f,
      name: f.name,
      role: guessRole(f.name),
    }))
    setTracks((prev) => [...prev, ...newTracks])
    e.target.value = ''
  }

  const updateRole = (id: string, role: string) => {
    setTracks((prev) => prev.map((t) => t.id === id ? { ...t, role } : t))
  }

  const removeTrack = (id: string) => {
    setTracks((prev) => prev.filter((t) => t.id !== id))
  }

  const handleBrowserDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const files = Array.from(e.dataTransfer.files).filter((f) => {
      const ext = f.name.substring(f.name.lastIndexOf('.')).toLowerCase()
      return ['.wav', '.flac', '.mp3', '.aiff', '.aif'].includes(ext)
    })
    if (files.length > 0) {
      setTracks((prev) => [
        ...prev,
        ...files.map((f) => ({
          id: makeId(),
          file: f,
          name: f.name,
          role: guessRole(f.name),
        })),
      ])
    }
  }

  return (
    <div
      className="mx-auto max-w-3xl pt-10"
      onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleBrowserDrop}
    >
      <SectionTitle
        title={t('import.title') ?? 'Import Tracks'}
        subtitle={t('import.subtitle') ?? 'Drag WAV files here and assign each one a role.'}
      />

      <Card className={`p-5 transition-all ${dragOver ? 'border-violet-400/50 bg-violet-500/[0.07]' : ''}`}>
        {/* Drop zone / add button */}
        <div className="mb-4 flex items-center gap-3">
          <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-white/20 bg-white/[0.02] px-4 py-3 text-sm text-white/50 hover:border-violet-400/40 hover:text-white/70 transition-colors">
            <Plus size={16} />
            {t('import.addFiles') ?? 'Add WAV files'}
            <input
              type="file"
              multiple
              accept=".wav,.flac,.mp3,.aiff,.aif"
              className="hidden"
              onChange={onFileInput}
            />
          </label>
          <span className="text-xs text-white/30">
            {tracks.length > 0
              ? `${tracks.length} ${tracks.length === 1 ? (t('import.track') ?? 'track') : (t('import.tracks') ?? 'tracks')}`
              : (t('import.dropHint') ?? 'or drag & drop files anywhere')
            }
          </span>
        </div>

        {/* Track list */}
        {tracks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-white/20">
            <FileAudio size={48} strokeWidth={1} />
            <p className="mt-3 text-sm">{t('import.empty') ?? 'No tracks imported yet'}</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {tracks.map((track, idx) => (
              <div
                key={track.id}
                className="flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2"
              >
                <span className="w-6 text-center text-xs text-white/25">{idx + 1}</span>
                <Music size={14} className="shrink-0 text-white/30" />
                <span className="flex-1 truncate text-sm text-white/70 font-mono">{track.name}</span>
                <div className="relative">
                  <select
                    value={track.role}
                    onChange={(e) => updateRole(track.id, e.target.value)}
                    className="appearance-none rounded-lg border border-white/10 bg-black/40 px-3 py-1 pr-7 text-xs text-white/70 focus:border-violet-400/60 focus:outline-none"
                  >
                    {INSTRUMENT_ROLES.map((r) => (
                      <option key={r.id} value={r.id}>{r.label}</option>
                    ))}
                  </select>
                  <ChevronDown size={12} className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-white/30" />
                </div>
                <button
                  type="button"
                  onClick={() => removeTrack(track.id)}
                  className="rounded p-1 text-white/20 hover:bg-red-500/10 hover:text-red-300 transition-colors"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Continue button */}
        {tracks.length > 0 && (
          <div className="mt-4 flex justify-end">
            <Button onClick={() => {
              // Extract directory from first track's full path (Tauri)
              // In browser mode, tracks come from file input (no full path)
              // For Tauri, the path is embedded in `name` — we pass it as-is
              const dir = tracks[0]?.name.includes('\\')
                ? tracks[0].name.substring(0, tracks[0].name.lastIndexOf('\\'))
                : tracks[0]?.name.includes('/')
                  ? tracks[0].name.substring(0, tracks[0].name.lastIndexOf('/'))
                  : ''
              onReady(tracks, dir)
            }}>
              {t('import.continue') ?? 'Analyze & Mix'} →
            </Button>
          </div>
        )}
      </Card>
    </div>
  )
}
