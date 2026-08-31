import { useEffect, useRef, useState } from 'react'
import { ClipboardPaste, FileAudio, FolderSearch, History, Loader2, Radar, FolderOpen } from 'lucide-react'
import { IS_TAURI } from '@/lib/api'
import { Badge, Button, Card, SectionTitle, Spinner } from './ui'
import { api } from '@/lib/api'
import type { RecentProject } from '@/types'
import { useLanguage } from '@/i18n'

export function SetupScreen({
  directory,
  onDirectoryChange,
  onAnalyze,
  analyzing,
  recents,
  onSelectRecent,
  onLoadProject,
}: {
  directory: string
  onDirectoryChange: (d: string) => void
  onAnalyze: () => void
  analyzing: boolean
  recents: string[]
  onSelectRecent: (d: string) => void
  onLoadProject?: (path: string) => void
}) {
  const { t } = useLanguage()
  const [touched, setTouched] = useState(false)
  const [showRecents, setShowRecents] = useState(false)
  const [droppedFile, setDroppedFile] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const [savedProjects, setSavedProjects] = useState<RecentProject[]>([])
  const [loadingProjects, setLoadingProjects] = useState(false)
  const [showSavedProjects, setShowSavedProjects] = useState(false)
  const [recommendations, setRecommendations] = useState<unknown[] | null>(null)
  const [recommendLoading, setRecommendLoading] = useState(false)
  const [showRecs, setShowRecs] = useState(false)

  useEffect(() => {
    setLoadingProjects(true)
    api
      .recentProjects(5)
      .then((r) => setSavedProjects(r.projects ?? []))
      .catch(() => {})
      .finally(() => setLoadingProjects(false))
  }, [])

  const invalid = touched && directory.trim().length === 0
  // A path-like string must contain at least one separator; warn but don't block.
  const looksLikePath = /[\\/]/.test(directory.trim())
  const pathWarning = touched && !invalid && !looksLikePath

  const handleRecommend = async () => {
    if (!directory.trim()) return
    setRecommendLoading(true)
    setRecommendations(null)
    try {
      const res = await api.recommend(directory.trim())
      setRecommendations(res.recommendations ?? [])
      setShowRecs(true)
    } catch {
      setRecommendations([])
    } finally {
      setRecommendLoading(false)
    }
  }

  /* --- drag&drop ------------------------------------------------------- */
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

        // Find the first WAV/FLAC/MP3 file or a directory
        const audioExts = ['.wav', '.flac', '.mp3', '.aiff', '.aif', '.ogg']
        let targetDir = ''

        for (const p of paths) {
          const ext = p.substring(p.lastIndexOf('.')).toLowerCase()
          if (audioExts.includes(ext)) {
            // Extract directory from file path
            targetDir = p.substring(0, p.lastIndexOf('\\') || p.lastIndexOf('/'))
            break
          }
          // If it's a directory, use it directly
          if (!ext || ext.length > 5) {
            targetDir = p
            break
          }
        }

        // Fallback: use the first path's directory
        if (!targetDir) {
          const p = paths[0]
          targetDir = p.substring(0, p.lastIndexOf('\\') || p.lastIndexOf('/'))
        }

        if (targetDir) {
          onDirectoryChange(targetDir)
          setTouched(true)
          setDroppedFile(paths[0].substring(paths[0].lastIndexOf('\\') + 1 || paths[0].lastIndexOf('/') + 1))
        }
      }).then((unlistenFn) => { unlisten = unlistenFn })
    }).catch(() => { /* not in Tauri */ })
    return () => { unlisten?.() }
  }, [onDirectoryChange])

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer.types.includes('Files')) setDragOver(true)
  }
  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
  }
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    // Web browser fallback: can only get filename, not full path
    const file = e.dataTransfer.files?.[0]
    if (!file) return
    setDroppedFile(file.name)
    setTouched(true)
    inputRef.current?.focus()
  }

  return (
    <div className="mx-auto max-w-2xl pt-10">
      <SectionTitle
        title={t('setup.title')}
        subtitle={t('setup.subtitle')}
      />

      {/* Drop zone — wraps the setup card */}
      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        aria-label="Drag and drop zone — files land here, then paste the folder path below"
        className={`rounded-3xl transition-all duration-150 ${
          dragOver
            ? 'ring-2 ring-violet-400/60 ring-offset-4 ring-offset-[#0a0a0f]'
            : ''
        }`}
      >
        <Card className={`p-6 ${dragOver ? 'border-violet-400/40 bg-violet-500/[0.06]' : ''}`}>
          <label
            htmlFor="render-dir"
            className="mb-2 block text-xs font-medium uppercase tracking-wider text-white/45"
          >
            {t('setup.rendersDir')}
          </label>
          <div className="flex gap-3">
            <div className="relative flex-1">
              <FolderSearch
                size={16}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-white/30"
              />
              <input
                ref={inputRef}
                id="render-dir"
                type="text"
                value={directory}
                onChange={(e) => {
                  onDirectoryChange(e.target.value)
                  setDroppedFile(null)
                }}
                onBlur={() => setTouched(true)}
                placeholder="C:\Users\highv\Documents\Default Project\ableton-auto-mix-mcp\renders"
                aria-invalid={invalid}
                aria-describedby={invalid || pathWarning ? 'dir-hint' : undefined}
                className={`w-full rounded-xl border bg-black/40 py-2.5 pl-9 pr-3 font-mono text-sm text-white/90 placeholder:text-white/25 focus:outline-none focus:ring-2 ${
                  invalid || pathWarning
                    ? 'border-red-400/50 focus:ring-red-400/40'
                    : 'border-white/10 focus:border-violet-400/60 focus:ring-violet-400/30'
                }`}
              />
            </div>
            <Button onClick={onAnalyze} disabled={analyzing || !directory.trim()}>
              {analyzing ? (
                <>
                  <Spinner /> {t('setup.analyzing')}
                </>
              ) : (
                <>
                  <Radar size={16} /> {t('setup.analyze')}
                </>
              )}
            </Button>
            <Button
              variant="outline"
              onClick={handleRecommend}
              disabled={recommendLoading || !directory.trim()}
            >
              {recommendLoading ? (
                <>
                  <Spinner /> {t('setup.aiLoading')}
                </>
              ) : (
                <>
                  <Radar size={16} /> {t('setup.aiSuggest')}
                </>
              )}
            </Button>
          </div>

          {invalid && (
            <p id="dir-hint" className="mt-2 text-xs text-red-300">
              {t('setup.pathRequired')}
            </p>
          )}
          {pathWarning && (
            <p id="dir-hint" className="mt-2 text-xs text-amber-300">
              {t('setup.pathWarning')}
            </p>
          )}

          {/* Dropped-file indicator + hybrid dnd hint */}
          {(dragOver || droppedFile) && (
            <div className="mt-3 flex items-center gap-2 rounded-xl border border-dashed border-violet-400/40 bg-violet-500/[0.07] px-3 py-2 text-xs text-white/60">
              <FileAudio size={14} className="shrink-0 text-violet-300" />
              {dragOver ? (
                <span>{t('setup.dropHint')}</span>
              ) : (
                <>
                  <span className="max-w-[220px] truncate font-mono text-violet-200">
                    {droppedFile}
                  </span>
                  <span className="text-white/40">
                    {t('setup.dropPaste')}
                  </span>
                  <button
                    type="button"
                    onClick={() => setDroppedFile(null)}
                    className="ml-auto shrink-0 text-white/30 hover:text-white/70"
                    aria-label="Dismiss dropped file indicator"
                  >
                    ✕
                  </button>
                </>
              )}
            </div>
          )}
          {!dragOver && !droppedFile && (
            <p className="mt-3 flex items-center gap-1.5 text-[11px] text-white/30">
              <ClipboardPaste size={12} />
              {t('setup.dragDropHint')}
            </p>
          )}

          {/* AI Recommendations Panel */}
          {showRecs && recommendations && (
            <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-medium text-white/80">{t('setup.aiSuggestions')}</h3>
                <button
                  type="button"
                  onClick={() => setShowRecs(false)}
                  className="text-xs text-white/30 hover:text-white/60"
                >
                  ✕
                </button>
              </div>
              {recommendations.length === 0 ? (
                <p className="text-xs text-white/40">{t('setup.aiNone')}</p>
              ) : (
                <div className="space-y-2">
                  {recommendations.map((rec, i) => {
                    const r = rec as Record<string, unknown>
                    return (
                      <div
                        key={i}
                        className="rounded-lg border border-white/5 bg-white/[0.02] p-3 text-xs"
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-white/70">
                            {String(r.category ?? '').toUpperCase()}
                          </span>
                          {typeof r.confidence === 'number' && (
                            <span className="text-[10px] text-white/30">
                              {Math.round(r.confidence * 100)}% conf
                            </span>
                          )}
                        </div>
                        <p className="text-white/50">{String(r.reason ?? '')}</p>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* Recents */}
          <div className="mt-4 flex items-center gap-2">
            <Button
              variant="outline"
              className="px-3 py-1.5 text-xs"
              onClick={() => setShowRecents((s) => !s)}
              aria-expanded={showRecents}
              disabled={recents.length === 0}
            >
              <History size={13} /> {t('setup.recent')}{recents.length > 0 ? ` (${recents.length})` : ''}
            </Button>
            {recents.length === 0 && (
              <span className="text-[11px] text-white/25">{t('setup.noRecent')}</span>
            )}
          </div>
          {showRecents && recents.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {recents.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => {
                    onSelectRecent(r)
                    setShowRecents(false)
                  }}
                  title={r}
                  className={`group inline-flex max-w-full items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[11px] transition-colors ${
                    r === directory.trim()
                      ? 'border-violet-400/50 bg-violet-500/20 text-violet-200'
                      : 'border-white/15 bg-white/[0.04] text-white/55 hover:border-violet-400/40 hover:bg-white/[0.08] hover:text-white/85'
                  }`}
                >
                  <FolderSearch size={11} className="shrink-0 opacity-60" />
                  <span className="truncate">{r}</span>
                  {r === directory.trim() && <Badge tone="violet">{t('setup.current')}</Badge>}
                </button>
              ))}
            </div>
          )}

          {/* Saved projects */}
          {savedProjects.length > 0 && (
            <>
              <div className="mt-4 flex items-center gap-2 border-t border-white/[0.07] pt-4">
                <Button
                  variant="outline"
                  className="px-3 py-1.5 text-xs"
                  onClick={() => setShowSavedProjects((s) => !s)}
                  aria-expanded={showSavedProjects}
                >
                  <FolderOpen size={13} /> {t('setup.savedProjects')} ({savedProjects.length})
                </Button>
                {loadingProjects && <Spinner className="h-3 w-3" />}
              </div>
              {showSavedProjects && (
                <div className="mt-3 space-y-1.5">
                  {savedProjects.map((p) => (
                    <button
                      key={p.path}
                      type="button"
                      onClick={() => onLoadProject?.(p.path ?? '')}
                      className="group flex w-full items-center gap-3 rounded-xl border border-white/10 bg-white/[0.02] px-3 py-2 text-left transition-colors hover:border-violet-400/40 hover:bg-white/[0.06]"
                    >
                      <FolderOpen size={13} className="shrink-0 text-white/30 group-hover:text-violet-300" />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-xs font-medium text-white/70 group-hover:text-white/90">
                          {p.name || t('setup.untitled')}
                        </div>
                        <div className="truncate font-mono text-[10px] text-white/30">
                          {p.directory}
                        </div>
                      </div>
                      {p.style && <Badge tone="violet">{p.style}</Badge>}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}

          <div className="mt-6 space-y-2 border-t border-white/[0.07] pt-5 text-xs leading-relaxed text-white/40">
            <p>
              {t('setup.description')}
            </p>
            <p className="font-mono text-white/30">
              {t('setup.defaultDir')}
            </p>
          </div>
        </Card>
      </div>

      {analyzing && (
        <Card className="mt-4 flex items-center gap-3 p-4 text-sm text-white/60">
          <Loader2 size={16} className="animate-spin text-violet-300" />
          {t('setup.analyzingTracks')}
        </Card>
      )}
    </div>
  )
}
