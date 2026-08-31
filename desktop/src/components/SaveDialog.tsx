import { useState } from 'react'
import { Save, X } from 'lucide-react'
import { Button, Card } from './ui'
import { useLanguage } from '@/i18n'

export function SaveDialog({
  defaultName,
  defaultDirectory,
  onSave,
  onClose,
  saving,
}: {
  defaultName: string
  defaultDirectory: string
  onSave: (name: string) => void
  onClose: () => void
  saving: boolean
}) {
  const { t } = useLanguage()
  const [name, setName] = useState(defaultName)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose()
      }}
    >
      <Card className="w-full max-w-md p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-semibold text-white">{t('save.title')}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-white/40 hover:text-white/80"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        <label
          htmlFor="project-name"
          className="mb-1 block text-xs font-medium uppercase tracking-wider text-white/45"
        >
          {t('save.projectName')}
        </label>
        <input
          id="project-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="My Track"
          autoFocus
          className="mb-3 w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2.5 font-mono text-sm text-white/90 placeholder:text-white/25 focus:border-violet-400/60 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && name.trim()) onSave(name.trim())
          }}
        />

        <p className="mb-4 text-xs text-white/35">
          {t('save.savesTo')} <span className="font-mono text-white/50">{defaultDirectory}</span>
        </p>

        <div className="flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            {t('save.cancel')}
          </Button>
          <Button onClick={() => name.trim() && onSave(name.trim())} disabled={saving || !name.trim()}>
            {saving ? (
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/25 border-t-white" />
            ) : (
              <Save size={15} />
            )}
            {t('save.save')}
          </Button>
        </div>
      </Card>
    </div>
  )
}
