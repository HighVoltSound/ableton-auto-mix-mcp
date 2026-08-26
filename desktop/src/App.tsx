import { useCallback, useEffect, useState } from 'react'
import { ServerOff } from 'lucide-react'
import type {
  AnalysisResult,
  ConflictsResult,
  MixResult,
  PreviewResult,
  ReleaseResult,
  StyleProfile,
  StylesResponse,
  SuggestResult,
} from '@/types'
import { ApiError, BACKEND_HINT, api } from '@/lib/api'
import { Sidebar } from '@/components/Sidebar'
import type { ViewId } from '@/components/Sidebar'
import { SetupScreen } from '@/components/SetupScreen'
import { StylePicker } from '@/components/StylePicker'
import { Dashboard } from '@/components/Dashboard'
import { MixPanel } from '@/components/MixPanel'
import type { PreviewOptions } from '@/components/MixPanel'

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
  /* ---------- global state ---------- */
  const [view, setView] = useState<ViewId>('setup')
  const [backendOk, setBackendOk] = useState<boolean | null>(null)
  const [backendMsg, setBackendMsg] = useState<string | null>(null)

  const [directory, setDirectory] = useState(
    'C:\\Users\\highv\\Documents\\Default Project\\ableton-auto-mix-mcp\\renders',
  )
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
  const styles = stylesResp?.styles ?? []
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

  /* ---------- backend probe on mount ---------- */
  useEffect(() => {
    let cancelled = false
    api
      .health()
      .then((resp) => {
        if (cancelled) return
        setBackendOk(true)
        setBackendMsg(null)
        setStylesResp(resp)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setBackendOk(false)
        setBackendMsg(err instanceof ApiError ? err.message : `Cannot reach backend (${BACKEND_HINT})`)
      })
    return () => {
      cancelled = true
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

  /* ---------- actions ---------- */

  const runAnalyze = useCallback(async () => {
    const dir = directory.trim()
    if (!dir) return
    setAnalyzing(true)
    const a = await runAction(() => api.analyze(dir))
    setAnalyzing(false)
    if (a) {
      setAnalysis(a)
      setView('dashboard')
      setRecents((prev) => pushRecent(prev, dir))
      // conflicts scan is independent — don't block the dashboard on it
      void runAction(() => api.conflicts(dir)).then((c) => {
        if (c) setConflicts(c)
      })
    }
  }, [directory, runAction])

  const selectStyle = useCallback(
    async (id: string) => {
      setSelectedStyleId(id)
      const profile = await runAction(() => api.getStyle(id))
      if (profile) setStyleProfile(profile)
    },
    [runAction],
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
    if (r) setMixResult(r)
  }, [selectedStyleId, directory, manualGain, sidechainDb, runAction])

  const runPreview = useCallback(
    async (opts: PreviewOptions = {}) => {
      if (!selectedStyleId || !directory.trim()) return
      setPreviewing(true)
      const r = await runAction(() =>
        api.preview({
          style: selectedStyleId,
          directory: directory.trim(),
          manual_gain:
            Object.keys(manualGain).length > 0 ? manualGain : undefined,
          sidechain_db: sidechainDb !== 0 ? sidechainDb : undefined,
          render_before: opts.render_before,
          reference_path: opts.reference_path,
        }),
      )
      setPreviewing(false)
      if (r) setPreview(r)
    },
    [selectedStyleId, directory, manualGain, sidechainDb, runAction],
  )

  const runReleaseCheck = useCallback(async () => {
    if (!selectedStyleId || !directory.trim()) return
    setCheckingRelease(true)
    const r = await runAction(() =>
      api.release(selectedStyleId, directory.trim()),
    )
    setCheckingRelease(false)
    if (r) setRelease(r)
  }, [selectedStyleId, directory, runAction])

  /* ---------- render ---------- */

  return (
    <div className="app-bg flex h-full">
      <Sidebar view={view} onViewChange={setView} backendOk={backendOk} />

      <main className="z-10 flex-1 overflow-y-auto px-8 pb-16">
        {backendMsg && (
          <div
            role="alert"
            className="mt-6 flex items-start gap-3 rounded-2xl border border-red-400/30 bg-red-500/[0.08] px-4 py-3 text-sm text-red-200"
          >
            <ServerOff size={17} className="mt-0.5 shrink-0 text-red-300" />
            <div>
              <span className="font-medium">
                {backendMsg.startsWith('Backend not running')
                  ? 'Backend not running'
                  : 'Request failed'}
              </span>
              <span className="text-red-200/70"> — {backendMsg}</span>
              {backendOk === false && (
                <div className="mt-1 font-mono text-xs text-red-200/60">
                  start it with: {BACKEND_HINT}
                </div>
              )}
            </div>
          </div>
        )}

        {view === 'setup' && (
          <SetupScreen
            directory={directory}
            onDirectoryChange={setDirectory}
            onAnalyze={() => void runAnalyze()}
            analyzing={analyzing}
            recents={recents}
            onSelectRecent={setDirectory}
          />
        )}

        {view === 'styles' && (
          <StylePicker
            styles={styles}
            selectedId={selectedStyleId}
            onSelect={(id) => void selectStyle(id)}
            suggest={() => void runSuggest()}
            suggestResult={suggestResult}
            suggesting={suggesting}
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
            onManualGainChange={(file, db) =>
              setManualGain((prev) => ({ ...prev, [file]: db }))
            }
            sidechainDb={sidechainDb}
            onSidechainChange={setSidechainDb}
            preview={preview}
            previewing={previewing}
            onPreview={(opts) => void runPreview(opts)}
            release={release}
            checkingRelease={checkingRelease}
            onReleaseCheck={() => void runReleaseCheck()}
          />
        )}
      </main>
    </div>
  )
}
