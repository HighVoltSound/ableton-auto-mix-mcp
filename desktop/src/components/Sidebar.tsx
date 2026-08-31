import {
  FolderOpen,
  LayoutDashboard,
  Music4,
  SlidersHorizontal,
  AudioWaveform,
  Undo2,
  Redo2,
  Globe,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useLanguage, LANGUAGES, type Lang } from '@/i18n'

export type ViewId = 'setup' | 'styles' | 'dashboard' | 'mix'

export function Sidebar({
  view,
  onViewChange,
  backendOk,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
}: {
  view: ViewId
  onViewChange: (v: ViewId) => void
  backendOk: boolean | null
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
}) {
  const { lang, setLang, t } = useLanguage()

  const NAV: { id: ViewId; labelKey: string; icon: LucideIcon }[] = [
    { id: 'setup', labelKey: 'nav.setup', icon: FolderOpen },
    { id: 'styles', labelKey: 'nav.styles', icon: Music4 },
    { id: 'dashboard', labelKey: 'nav.dashboard', icon: LayoutDashboard },
    { id: 'mix', labelKey: 'nav.mix', icon: SlidersHorizontal },
  ]

  const toggleLang = () => {
    const next: Lang = lang === 'en' ? 'ru' : 'en'
    setLang(next)
  }

  return (
    <aside className="z-10 flex w-64 shrink-0 flex-col border-r border-white/10 bg-[#090a0f]/80 backdrop-blur-2xl">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 pb-6 pt-6">
        <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 via-fuchsia-500 to-pink-500 shadow-[0_0_20px_rgba(168,85,247,0.5)]">
          <AudioWaveform size={20} className="text-white drop-shadow-md animate-pulse" />
          <div className="absolute -inset-0.5 rounded-xl bg-gradient-to-r from-violet-500 to-pink-500 opacity-40 blur-sm" />
        </div>
        <div>
          <div className="text-sm font-bold tracking-tight text-white flex items-center gap-1.5">
            MusicMixCode
            <span className="rounded bg-violet-500/20 px-1 py-0.2 text-[9px] font-mono font-semibold text-violet-300 border border-violet-500/30">PRO</span>
          </div>
          <div className="text-[10px] uppercase tracking-[0.2em] font-medium text-white/40">
            Studio Workstation
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1.5 px-3" aria-label="Main navigation">
        {NAV.map(({ id, labelKey, icon: Icon }) => {
          const active = view === id
          return (
            <button
              key={id}
              onClick={() => onViewChange(id)}
              aria-current={active ? 'page' : undefined}
              className={`group relative flex w-full items-center gap-3.5 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-all duration-200 ${
                active
                  ? 'bg-gradient-to-r from-violet-500/25 via-fuchsia-500/15 to-transparent text-white shadow-lg border border-violet-500/40'
                  : 'text-white/55 hover:bg-white/[0.05] hover:text-white'
              }`}
            >
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-1 rounded-r-full bg-gradient-to-b from-violet-400 to-fuchsia-400 shadow-[0_0_8px_#a855f7]" />
              )}
              <Icon
                size={18}
                className={
                  active
                    ? 'text-violet-300 drop-shadow-[0_0_8px_rgba(167,139,250,0.6)]'
                    : 'text-white/40 group-hover:text-white/80 transition-colors'
                }
              />
              <span className="tracking-wide">{t(labelKey)}</span>
            </button>
          )
        })}
      </nav>

      {/* Undo / Redo */}
      <div className="flex gap-1.5 px-3 pb-3">
        <button
          onClick={onUndo}
          disabled={!canUndo}
          title={t('sidebar.undoTitle')}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1.5 text-[11px] font-medium text-white/60 transition-all hover:bg-white/[0.08] hover:text-white hover:border-violet-500/30 disabled:cursor-not-allowed disabled:opacity-25 disabled:hover:bg-white/[0.03] disabled:hover:text-white/60"
        >
          <Undo2 size={13} />
          {t('sidebar.undo')}
        </button>
        <button
          onClick={onRedo}
          disabled={!canRedo}
          title={t('sidebar.redoTitle')}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1.5 text-[11px] font-medium text-white/60 transition-all hover:bg-white/[0.08] hover:text-white hover:border-violet-500/30 disabled:cursor-not-allowed disabled:opacity-25 disabled:hover:bg-white/[0.03] disabled:hover:text-white/60"
        >
          <Redo2 size={13} />
          {t('sidebar.redo')}
        </button>
      </div>

      {/* Language toggle */}
      <div className="px-3 pb-2">
        <button
          onClick={toggleLang}
          className="flex w-full items-center gap-2 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[11px] font-medium text-white/50 transition-all hover:bg-white/[0.06] hover:text-white/80"
          title={lang === 'en' ? 'Switch to Russian' : 'Переключить на English'}
        >
          <Globe size={13} />
          {LANGUAGES.find((l) => l.id === lang)?.label ?? lang}
        </button>
      </div>

      {/* Backend status */}
      <div className="px-5 py-4">
        <BackendDot ok={backendOk} />
      </div>
    </aside>
  )
}

function BackendDot({ ok }: { ok: boolean | null }) {
  const { t } = useLanguage()
  let color = 'bg-amber-400'
  let text = t('sidebar.backendChecking')
  if (ok === true) {
    color = 'bg-emerald-400'
    text = t('sidebar.backendOnline')
  } else if (ok === false) {
    color = 'bg-red-400'
    text = t('sidebar.backendOffline')
  }
  return (
    <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2">
      <span className="relative flex h-2 w-2">
        {ok !== null && (
          <span
            className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${color}`}
          />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${color}`} />
      </span>
      <span className="truncate text-[11px] text-white/50">{text}</span>
    </div>
  )
}
