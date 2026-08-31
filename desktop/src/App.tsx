import { useCallback, useEffect, useRef, useState } from 'react'
import { ServerOff, RefreshCw } from 'lucide-react'
import type {
  AnalysisResult,
  AsyncResponse,
  ConflictsResult,
  MixResult,
  MixStyle,
  PreviewResult,
  ProjectState,
  ReleaseResult,
  StyleProfile,
  StylesResponse,
  SuggestResult,
} from '@/types'
import { ApiError, BACKEND_HINT, api } from '@/lib/api'
import { useLanguage } from '@/i18n'
import { HistoryManager } from '@/lib/history'
import { Sidebar } from '@/components/Sidebar'
import type { ViewId } from '@/components/Sidebar'
import { SetupScreen } from '@/components/SetupScreen'
import { TrackImport } from '@/components/TrackImport'
import type { TrackEntry } from '@/components/TrackImport'
import { StylePicker } from '@/components/StylePicker'
import { Dashboard } from '@/components/Dashboard'
import { MixPanel } from '@/components/MixPanel'
import type { PreviewOptions } from '@/components/MixPanel'
import { SaveDialog } from '@/components/SaveDialog'
import { UpdateBanner, useUpdateCheck } from '@/components/UpdateBanner'
import { STYLES_METADATA } from '@/components/styleArtworks'

const RECENTS_KEY = 'musicmixcode.recent_dirs'
const RECENTS_MAX = 6

function pushRecent(list: string[], dir: string): string[] {
  const next = [dir, ...list.filter((d) => d !== dir)].slice(0, RECENTS_MAX)
  try {
    localStorage.setItem(RECENTS_KEY, JSON.stringify(next))
  } catch {
    /* storage full or unavailable — recents are best-effort */
  }
  return next
}

export default function App() {
  const { t } = useLanguage()
  /* ---------- global state ---------- */
  const [view, setView] = useState<ViewId>('setup')
  const [backendOk, setBackendOk] = useState<boolean | null>(null)
  const [backendMsg, setBackendMsg] = useState<string | null>(null)

  const [directory, setDirectory] = useState(
    'C:\\Users\\highv\\Documents\\Default Project\\ableton-auto-mix-mcp\\renders',
  )
  const [importMode, setImportMode] = useState<'folder' | 'tracks'>('tracks')
  const [_importedTracks, setImportedTracks] = useState<TrackEntry[]>([])
  const [recents, setRecents] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem(RECENTS_KEY)
      const parsed = raw ? (JSON.parse(raw) as unknown) : []
      return Array.isArray(parsed) ? parsed.filter((p): p is string => typeof p === 'string') : []
    } catch {
      return []
    }
  })
  const [analyzing, setAnalyzing] = useState(false)

  const [stylesResp, setStylesResp] = useState<StylesResponse | null>(null)
  const styles = stylesResp?.styles ?? (Array.isArray(stylesResp) ? (stylesResp as unknown as MixStyle[]) : [])
  const [selectedStyleId, setSelectedStyleId] = useState<string | null>(null)
  const [styleProfile, setStyleProfile] = useState<StyleProfile | null>(null)

  const [suggesting, setSuggesting] = useState(false)
  const [suggestResult, setSuggestResult] = useState<SuggestResult | null>(null)

  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [conflicts, setConflicts] = useState<ConflictsResult | null>(null)

  const [mixing, setMixing] = useState(false)
  const [mixResult, setMixResult] = useState<MixResult | null>(null)
  const [manualGain, setManualGain] = useState<Record<string, number>>({})
  const [sidechainDb, setSidechainDb] = useState(0)

  const [previewing, setPreviewing] = useState(false)
  const [preview, setPreview] = useState<PreviewResult | null>(null)

  const [checkingRelease, setCheckingRelease] = useState(false)
  const [release, setRelease] = useState<ReleaseResult | null>(null)

  /* ---------- project state ---------- */
  const [projectName, setProjectName] = useState('')
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [saving, setSaving] = useState(false)

  /* ---------- auto-update ---------- */
  const { update: availableUpdate, dismiss: dismissUpdate } = useUpdateCheck()
  const projectAnalysisRef = useRef<AnalysisResult | null>(null)
  const projectMixRef = useRef<MixResult | null>(null)
  const projectPreviewRef = useRef<PreviewResult | null>(null)

  /* ---------- undo / redo ---------- */
  interface MixSnapshot {
    selectedStyleId: string | null
    manualGain: Record<string, number>
    sidechainDb: number
  }

  const historyRef = useRef(
    new HistoryManager<MixSnapshot>({
      selectedStyleId: null,
      manualGain: {},
      sidechainDb: 0,
    }),
  )
  const [, setHistoryTick] = useState(0)
  const forceHistoryUpdate = useCallback(() => setHistoryTick((n) => n + 1), [])

  const handleUndo = useCallback(() => {
    const snap = historyRef.current.undo()
    if (!snap) return
    setSelectedStyleId(snap.selectedStyleId)
    setManualGain(snap.manualGain)
    setSidechainDb(snap.sidechainDb)
    forceHistoryUpdate()
  }, [forceHistoryUpdate])

  const handleRedo = useCallback(() => {
    const snap = historyRef.current.redo()
    if (!snap) return
    setSelectedStyleId(snap.selectedStyleId)
    setManualGain(snap.manualGain)
    setSidechainDb(snap.sidechainDb)
    forceHistoryUpdate()
  }, [forceHistoryUpdate])

  const canUndo = historyRef.current.canUndo()
  const canRedo = historyRef.current.canRedo()

  /* ---------- keyboard shortcuts ---------- */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey
      if (!mod) return
      if (e.key === 'z' && !e.shiftKey) {
        e.preventDefault()
        handleUndo()
      } else if ((e.key === 'z' && e.shiftKey) || e.key === 'y') {
        e.preventDefault()
        handleRedo()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [handleUndo, handleRedo])

  /* ---------- backend probe on mount (retry until backend is ready) ---------- */
  useEffect(() => {
    let cancelled = false
    let attempts = 0
    const MAX_ATTEMPTS = 12 // try for ~12 seconds
    const DELAY_MS = 1000

    async function tryHealth() {
      while (!cancelled && attempts < MAX_ATTEMPTS) {
        attempts++
        try {
          const resp = await api.health()
          if (cancelled) return
          setBackendOk(true)
          setBackendMsg(null)
          setStylesResp(resp)
          return
        } catch {
          if (cancelled) return
          if (attempts < MAX_ATTEMPTS) {
            await new Promise((r) => setTimeout(r, DELAY_MS))
          }
        }
      }
      if (!cancelled) {
        setBackendOk(false)
        setBackendMsg(`Backend not running (${BACKEND_HINT})`)
      }
    }

    void tryHealth()
    return () => {
      cancelled = true
    }
  }, [])

  const refreshStyles = useCallback(async () => {
    try {
      const resp = await api.health()
      setBackendOk(true)
      setBackendMsg(null)
      setStylesResp(resp)
    } catch (err: unknown) {
      setBackendOk(false)
      setBackendMsg(err instanceof ApiError ? err.message : `Cannot reach backend (${BACKEND_HINT})`)
    }
  }, [])

  /** Wrap an async action so network errors surface in the banner. */
  const runAction = useCallback(
    async <T,>(fn: () => Promise<T>): Promise<T | null> => {
      try {
        const result = await fn()
        setBackendOk(true)
        setBackendMsg(null)
        return result
      } catch (err) {
        if (err instanceof ApiError && err.offline) setBackendOk(false)
        setBackendMsg(err instanceof Error ? err.message : String(err))
        return null
      }
    },
    [],
  )

  /* ---------- project save / load (declared before actions that use autoSave) ---------- */

  const buildProjectState = useCallback((): ProjectState => {
    const tracks = projectAnalysisRef.current?.tracks ?? projectAnalysisRef.current?.metrics ?? []
    const corrs = mixResult?.corrections ?? mixResult?.tracks ?? []
    const planVal = (mixResult as Record<string, unknown> | null)?.plan
    return {
      directory: directory.trim(),
      style: selectedStyleId ?? '',
      analyses: tracks as ProjectState['analyses'],
      corrections: corrs as ProjectState['corrections'],
      plan: (typeof planVal === 'object' ? planVal : null) as Record<string, unknown> | null,
      preview_path: (preview?.output_path ?? preview?.path) ?? null,
      before_path: (preview?.before_path ?? undefined) as string | null,
      match_eq_curve: (preview?.match_eq?.curve as unknown as ProjectState['match_eq_curve']) ?? null,
      conflicts: (conflicts?.conflicts ?? conflicts?.pairs as unknown) as ProjectState['conflicts'],
      selected_style_id: selectedStyleId,
      manual_gain: Object.keys(manualGain).length > 0 ? manualGain : null,
      sidechain_db: sidechainDb !== 0 ? sidechainDb : null,
      name: projectName,
    }
  }, [directory, selectedStyleId, mixResult, preview, conflicts, manualGain, sidechainDb, projectName])

  const autoSave = useCallback(async () => {
    const dir = directory.trim()
    if (!dir) return
    try {
      const state = buildProjectState()
      await api.saveProject(state)
    } catch {
      /* auto-save is best-effort */
    }
  }, [directory, buildProjectState])

  /* ---------- actions ---------- */

  const runAnalyze = useCallback(async () => {
    const dir = directory.trim()
    if (!dir) return
    setAnalyzing(true)
    const a = await runAction(() => api.analyze(dir))
    setAnalyzing(false)
    if (a) {
      setAnalysis(a)
      projectAnalysisRef.current = a
      setView('dashboard')
      setRecents((prev) => pushRecent(prev, dir))
      // Reset history on new directory
      historyRef.current = new HistoryManager<MixSnapshot>({
        selectedStyleId: null,
        manualGain: {},
        sidechainDb: 0,
      })
      forceHistoryUpdate()
      void autoSave()
      // conflicts scan is independent — don't block the dashboard on it
      void runAction(() => api.conflicts(dir)).then((c) => {
        if (c) setConflicts(c)
      })
    }
  }, [directory, runAction, autoSave, forceHistoryUpdate])

  const handleTrackImport = useCallback(async (tracks: TrackEntry[], dir: string) => {
    setImportedTracks(tracks)
    if (dir) setDirectory(dir)
    // Auto-analyze
    const targetDir = dir || directory.trim()
    if (targetDir) {
      setAnalyzing(true)
      const a = await runAction(() => api.analyze(targetDir))
      setAnalyzing(false)
      if (a) {
        // Apply user-assigned roles to analysis results
        const roleMap = new Map(tracks.map((t) => {
          const basename = t.name.replace(/\.[^.]+$/, '')
          return [basename, t.role]
        }))
        // Update analysis roles if matched
        if (a.tracks) {
          for (const track of a.tracks) {
            const assigned = roleMap.get(track.file?.replace(/\.[^.]+$/, '') ?? '')
            if (assigned) track.role = assigned
          }
        }
        setAnalysis(a)
        projectAnalysisRef.current = a
        setView('dashboard')
        setRecents((prev) => pushRecent(prev, targetDir))
        historyRef.current = new HistoryManager<MixSnapshot>({
          selectedStyleId: null, manualGain: {}, sidechainDb: 0,
        })
        forceHistoryUpdate()
        void autoSave()
        void runAction(() => api.conflicts(targetDir)).then((c) => { if (c) setConflicts(c) })
      }
    }
  }, [directory, runAction, autoSave, forceHistoryUpdate])

  const selectStyle = useCallback(
    async (id: string) => {
      // Capture old state before the change
      const oldSnap: MixSnapshot = {
        selectedStyleId,
        manualGain,
        sidechainDb,
      }
      setSelectedStyleId(id)
      historyRef.current.push(oldSnap, `Style → ${id}`)
      forceHistoryUpdate()
      const profile = await runAction(() => api.getStyle(id))
      if (profile) setStyleProfile(profile)
    },
    [runAction, selectedStyleId, manualGain, sidechainDb, forceHistoryUpdate],
  )

  const runSuggest = useCallback(async () => {
    if (!directory.trim()) return
    setSuggesting(true)
    const r = await runAction(() => api.suggest(directory.trim()))
    setSuggesting(false)
    if (r) {
      setSuggestResult(r)
      const id = r.style_id ?? r.style ?? null
      if (id) void selectStyle(id)
    }
  }, [directory, runAction, selectStyle])

  const runMix = useCallback(async () => {
    if (!selectedStyleId || !directory.trim()) return
    setMixing(true)
    const r = await runAction(() =>
      api.mix({
        style: selectedStyleId,
        directory: directory.trim(),
        dry_run: true,
        manual_gain:
          Object.keys(manualGain).length > 0 ? manualGain : undefined,
        sidechain_db: sidechainDb !== 0 ? sidechainDb : undefined,
      }),
    )
    setMixing(false)
    if (r) {
      setMixResult(r)
      projectMixRef.current = r
      void autoSave()
    }
  }, [selectedStyleId, directory, manualGain, sidechainDb, runAction, autoSave])

  const cleanupWsRef = useRef<(() => void) | null>(null)

  const runPreview = useCallback(
    async (opts: PreviewOptions = {}) => {
      if (!selectedStyleId || !directory.trim()) return
      setPreviewing(true)
      cleanupWsRef.current?.()

      try {
        // Try async mode first for real-time progress
        const asyncResp = await runAction(() =>
          api.preview({
            style: selectedStyleId,
            directory: directory.trim(),
            manual_gain:
              Object.keys(manualGain).length > 0 ? manualGain : undefined,
            sidechain_db: sidechainDb !== 0 ? sidechainDb : undefined,
            render_before: opts.render_before,
            reference_path: opts.reference_path,
            multiband: opts.multiband,
            limiter_ceiling_db: opts.limiter_ceiling_db,
            dynamic_eq: opts.dynamic_eq,
            midside_eq: opts.midside_eq,
            transient: opts.transient,
            sidechain: opts.sidechain,
            deesser: opts.deesser,
            eq_bands: opts.eq_bands,
            spatial_configs: opts.spatial_configs,
            async: true,
          }),
        )

        if (asyncResp && 'room_id' in asyncResp) {
          // Async mode: subscribe to WebSocket progress
          const resp = asyncResp as AsyncResponse
          cleanupWsRef.current = api.subscribeProgress(resp.room_id, {
            onProgress: opts.onProgress,
            onComplete: (result) => {
              setPreviewing(false)
              cleanupWsRef.current?.()
              if (result) {
                const pr = result as unknown as PreviewResult
                setPreview(pr)
                projectPreviewRef.current = pr
                void autoSave()
              }
              opts.onComplete?.(result as unknown as PreviewResult)
            },
            onError: (message) => {
              setPreviewing(false)
              cleanupWsRef.current?.()
              opts.onError?.(message)
            },
          })
        } else {
          // Sync fallback (backward compat with older backends)
          setPreviewing(false)
          if (asyncResp) {
            setPreview(asyncResp as PreviewResult)
            projectPreviewRef.current = asyncResp as PreviewResult
            void autoSave()
          }
        }
      } catch {
        setPreviewing(false)
      }
    },
    [selectedStyleId, directory, manualGain, sidechainDb, runAction, autoSave],
  )

  useEffect(() => {
    return () => { cleanupWsRef.current?.() }
  }, [])

  const runReleaseCheck = useCallback(async () => {
    if (!selectedStyleId || !directory.trim()) return
    setCheckingRelease(true)
    const r = await runAction(() =>
      api.release(selectedStyleId, directory.trim()),
    )
    setCheckingRelease(false)
    if (r) setRelease(r)
  }, [selectedStyleId, directory, runAction])

  const handleSaveProject = useCallback(
    async (name: string) => {
      setProjectName(name)
      setSaving(true)
      try {
        const state = { ...buildProjectState(), name }
        await api.saveProject(state)
        setShowSaveDialog(false)
      } catch {
        /* error will surface via banner */
      } finally {
        setSaving(false)
      }
    },
    [buildProjectState],
  )

  const loadProject = useCallback(
    async (path: string) => {
      const state = await runAction(() => api.loadProject(path))
      if (!state) return
      if (state.directory) setDirectory(state.directory)
      if (state.name) setProjectName(state.name)
      if (state.style) {
        setSelectedStyleId(state.style)
        void runAction(() => api.getStyle(state.style!)).then((p) => {
          if (p) setStyleProfile(p)
        })
      }
      if (state.analyses && state.analyses.length > 0) {
        const a: AnalysisResult = { directory: state.directory, tracks: state.analyses }
        setAnalysis(a)
        projectAnalysisRef.current = a
      }
      if (state.corrections && state.corrections.length > 0) {
        const m: MixResult = { corrections: state.corrections }
        setMixResult(m)
        projectMixRef.current = m
      }
      if (state.preview_path) {
        const pr: PreviewResult = {
          output_path: state.preview_path,
          before_path: state.before_path ?? undefined,
        }
        setPreview(pr)
        projectPreviewRef.current = pr
      }
      if (state.conflicts) {
        setConflicts({ conflicts: state.conflicts })
      }
      if (state.manual_gain) setManualGain(state.manual_gain)
      if (state.sidechain_db != null) setSidechainDb(state.sidechain_db)
      setView('dashboard')
    },
    [runAction],
  )

  /* ---------- render ---------- */
  const currentStyleGlow = selectedStyleId
    ? STYLES_METADATA[selectedStyleId]?.glowColor ?? 'rgba(139, 92, 246, 0.35)'
    : 'rgba(139, 92, 246, 0.25)'

  return (
    <div className="app-bg relative flex h-full flex-col overflow-hidden bg-[#07070b]">
      {/* Dynamic Ambient Studio Glow mesh */}
      <div
        className="pointer-events-none fixed -top-48 -right-48 h-[650px] w-[650px] rounded-full blur-[150px] transition-all duration-1000 opacity-60 z-0"
        style={{ backgroundColor: currentStyleGlow }}
      />
      <div
        className="pointer-events-none fixed -bottom-48 left-1/4 h-[550px] w-[550px] rounded-full blur-[160px] transition-all duration-1000 opacity-40 z-0"
        style={{ backgroundColor: currentStyleGlow }}
      />

      {availableUpdate && <UpdateBanner update={availableUpdate} onDismiss={dismissUpdate} />}

      <div className="relative z-10 flex flex-1 overflow-hidden">
      <Sidebar
        view={view}
        onViewChange={setView}
        backendOk={backendOk}
        canUndo={canUndo}
        canRedo={canRedo}
        onUndo={handleUndo}
        onRedo={handleRedo}
      />

      <main className="z-10 flex-1 overflow-y-auto px-8 pb-16">
        {backendMsg && (
          <div
            role="alert"
            className="mt-6 flex items-start gap-3 rounded-2xl border border-red-400/30 bg-red-500/[0.08] px-4 py-3 text-sm text-red-200"
          >
            <ServerOff size={17} className="mt-0.5 shrink-0 text-red-300" />
            <div className="flex-1">
              <span className="font-medium">
                {backendMsg.startsWith('Backend not running')
                  ? t('errors.backendOffline')
                  : t('errors.requestFailed')}
              </span>
              <span className="text-red-200/70"> — {backendMsg}</span>
              {backendOk === false && (
                <div className="mt-2 flex items-center gap-3">
                  <span className="font-mono text-xs text-red-200/60">
                    {t('errors.startHint')} {BACKEND_HINT}
                  </span>
                  <button
                    onClick={refreshStyles}
                    className="inline-flex items-center gap-1 rounded-lg border border-red-400/30 bg-red-500/10 px-2.5 py-1 text-xs font-medium text-red-200 transition-colors hover:bg-red-500/20"
                  >
                    <RefreshCw size={12} /> {t('styles.retry')}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {view === 'setup' && (
          <>
            <div className="mx-auto mt-6 flex max-w-3xl justify-center gap-1 rounded-lg bg-white/[0.03] p-1">
              <button
                type="button"
                onClick={() => setImportMode('tracks')}
                className={`rounded-md px-4 py-1.5 text-xs font-medium transition-colors ${
                  importMode === 'tracks'
                    ? 'bg-violet-500/20 text-violet-300'
                    : 'text-white/40 hover:text-white/60'
                }`}
              >
                {t('import.tracksMode')}
              </button>
              <button
                type="button"
                onClick={() => setImportMode('folder')}
                className={`rounded-md px-4 py-1.5 text-xs font-medium transition-colors ${
                  importMode === 'folder'
                    ? 'bg-violet-500/20 text-violet-300'
                    : 'text-white/40 hover:text-white/60'
                }`}
              >
                {t('import.folderMode')}
              </button>
            </div>
            {importMode === 'tracks' ? (
              <TrackImport onReady={(tracks, dir) => void handleTrackImport(tracks, dir)} />
            ) : (
              <SetupScreen
                directory={directory}
                onDirectoryChange={setDirectory}
                onAnalyze={() => void runAnalyze()}
                analyzing={analyzing}
                recents={recents}
                onSelectRecent={setDirectory}
                onLoadProject={(p) => void loadProject(p)}
              />
            )}
          </>
        )}

        {view === 'styles' && (
          <StylePicker
            styles={styles}
            selectedId={selectedStyleId}
            onSelect={(id) => void selectStyle(id)}
            suggest={() => void runSuggest()}
            suggestResult={suggestResult}
            suggesting={suggesting}
            onRetry={refreshStyles}
          />
        )}

        {view === 'dashboard' && (
          <Dashboard
            analysis={analysis}
            conflicts={conflicts}
            styleProfile={styleProfile}
          />
        )}

        {view === 'mix' && (
          <MixPanel
            hasAnalysis={!!analysis && (analysis.tracks?.length ?? 0) + (analysis.metrics?.length ?? 0) > 0}
            selectedStyle={selectedStyleId}
            mixResult={mixResult}
            mixing={mixing}
            onMix={() => void runMix()}
            manualGain={manualGain}
            onManualGainChange={(file, db) => {
              const oldSnap: MixSnapshot = { selectedStyleId, manualGain, sidechainDb }
              setManualGain((prev) => ({ ...prev, [file]: db }))
              historyRef.current.push(oldSnap, `${file} gain → ${db > 0 ? '+' : ''}${db.toFixed(1)} dB`)
              forceHistoryUpdate()
            }}
            sidechainDb={sidechainDb}
            onSidechainChange={(db) => {
              const oldSnap: MixSnapshot = { selectedStyleId, manualGain, sidechainDb }
              setSidechainDb(db)
              historyRef.current.push(oldSnap, `Sidechain → ${db.toFixed(1)} dB`)
              forceHistoryUpdate()
            }}
            preview={preview}
            previewing={previewing}
            onPreview={(opts) => void runPreview(opts)}
            release={release}
            checkingRelease={checkingRelease}
            onReleaseCheck={() => void runReleaseCheck()}
            styles={styles}
            directory={directory}
          />
        )}
      </main>
      </div>

      {showSaveDialog && (
        <SaveDialog
          defaultName={projectName || 'My Track'}
          defaultDirectory={directory.trim()}
          onSave={(name) => void handleSaveProject(name)}
          onClose={() => setShowSaveDialog(false)}
          saving={saving}
        />
      )}
    </div>
  )
}
