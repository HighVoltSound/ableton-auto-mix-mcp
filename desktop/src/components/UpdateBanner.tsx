import { useState, useCallback, useEffect } from 'react'
import { Download, RefreshCw, X } from 'lucide-react'
import { Button } from './ui'
import { installUpdate, restartApp, checkForUpdate, type UpdateInfo } from '@/lib/updater'
import { useLanguage } from '@/i18n'

interface Props {
  update: UpdateInfo
  onDismiss: () => void
}

export function UpdateBanner({ update, onDismiss }: Props) {
  const { t } = useLanguage()
  const [downloading, setDownloading] = useState(false)
  const [progress, setProgress] = useState(-1)
  const [installed, setInstalled] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleInstall = useCallback(async () => {
    setDownloading(true)
    setError(null)
    const ok = await installUpdate((p) => setProgress(p))
    setDownloading(false)
    if (ok) {
      setInstalled(true)
    } else {
      setError(t('update.downloading'))
    }
  }, [t])

  const handleRestart = useCallback(() => {
    void restartApp()
  }, [])

  return (
    <div className="relative z-50 flex items-center gap-3 border-b border-violet-400/20 bg-gradient-to-r from-violet-500/10 via-fuchsia-500/5 to-transparent px-6 py-2.5 text-sm backdrop-blur-md">
      {installed ? (
        <>
          <RefreshCw size={15} className="shrink-0 text-emerald-300" />
          <span className="text-white/80">
            {t('update.installed')}
          </span>
          <Button variant="primary" className="ml-auto !px-3 !py-1 !text-xs" onClick={handleRestart}>
            {t('update.restartNow')}
          </Button>
        </>
      ) : (
        <>
          <Download size={15} className="shrink-0 text-violet-300" />
          <span className="text-white/80">
            {t('update.available')}{' '}
            <span className="font-medium text-white">v{update.version}</span>
            {update.releaseNotes && (
              <span className="ml-1.5 text-white/45">— {update.releaseNotes}</span>
            )}
          </span>

          {downloading && progress >= 0 && (
            <div className="mx-2 h-1.5 w-24 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-gradient-to-r from-violet-400 to-fuchsia-400 transition-all duration-300"
                style={{ width: `${Math.min(progress, 100)}%` }}
              />
            </div>
          )}

          {error && (
            <span className="text-xs text-red-300">{error}</span>
          )}

          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="primary"
              className="!px-3 !py-1 !text-xs"
              disabled={downloading}
              onClick={handleInstall}
            >
              {downloading ? t('update.downloading') : t('update.updateBtn')}
            </Button>
            <button
              onClick={onDismiss}
              className="rounded-lg px-2 py-1 text-xs text-white/40 transition-colors hover:bg-white/[0.06] hover:text-white/70"
              title="Skip this version"
            >
              {t('update.skip')}
            </button>
          </div>
        </>
      )}

      {/* Close / dismiss */}
      <button
        onClick={onDismiss}
        className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-white/30 transition-colors hover:bg-white/[0.06] hover:text-white/60"
        title="Dismiss"
      >
        <X size={13} />
      </button>
    </div>
  )
}

/**
 * Hook that manages the update-check lifecycle.
 * Call once from App. Returns the current UpdateInfo (or null).
 */
export function useUpdateCheck(delayMs = 5_000) {
  const [update, setUpdate] = useState<UpdateInfo | null>(null)
  const [dismissed, setDismissed] = useState(false)

  const dismiss = useCallback(() => {
    setDismissed(true)
    setUpdate(null)
  }, [])

  const check = useCallback(async () => {
    const info = await checkForUpdate()
    if (info) setUpdate(info)
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => {
      void check()
    }, delayMs)
    return () => clearTimeout(timer)
  }, [check, delayMs])

  return {
    update: dismissed ? null : update,
    dismiss,
  }
}
