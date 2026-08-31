import { useState, useEffect } from 'react'
import { Save, FolderOpen, Trash2, X } from 'lucide-react'
import { api } from '@/lib/api'
import type { MixPreset, PresetListEntry, MultibandConfig, DynamicEqConfig, MidSideEqConfig, TransientConfig, SidechainConfig } from '@/types'
import { Button, Spinner } from './ui'
import { useLanguage } from '@/i18n'

interface PresetDialogProps {
  onClose: () => void
  onLoad: (preset: MixPreset) => void
  currentSettings: {
    style?: string
    multiband?: MultibandConfig
    limiter_ceiling_db?: number
    dynamic_eq?: DynamicEqConfig
    midside_eq?: MidSideEqConfig
    transient?: TransientConfig
    sidechain?: SidechainConfig
  }
}

export function PresetDialog({ onClose, onLoad, currentSettings }: PresetDialogProps) {
  const { t } = useLanguage()
  const [tab, setTab] = useState<'save' | 'load'>('load')
  const [presets, setPresets] = useState<PresetListEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [presetName, setPresetName] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    api.listPresets()
      .then((r) => setPresets(r.presets ?? []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    if (!presetName.trim()) return
    setSaving(true)
    try {
      await api.savePreset({
        name: presetName.trim(),
        ...currentSettings,
        notes,
      })
      const r = await api.listPresets()
      setPresets(r.presets ?? [])
      setTab('load')
      setPresetName('')
      setNotes('')
    } catch {
      // silent
    } finally {
      setSaving(false)
    }
  }

  const handleLoad = async (name: string) => {
    try {
      const preset = await api.loadPreset(name)
      onLoad(preset)
      onClose()
    } catch {
      // silent
    }
  }

  const handleDelete = async (name: string) => {
    setDeleting(name)
    try {
      await api.deletePreset(name)
      setPresets((prev) => prev.filter((p) => p.name !== name))
    } catch {
      // silent
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-white/10 bg-white/[0.04] p-6 shadow-[0_8px_40px_rgb(0_0_0/0.35)] backdrop-blur-xl"
        onClick={(e: React.MouseEvent) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-center justify-between">
          <h3 className="text-base font-semibold text-white">{t('mix.presets')}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-white/40 hover:bg-white/10 hover:text-white"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tabs */}
        <div className="mb-4 flex gap-1 rounded-lg bg-black/30 p-1">
          <button
            type="button"
            onClick={() => setTab('load')}
            className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              tab === 'load'
                ? 'bg-violet-500/20 text-violet-300'
                : 'text-white/50 hover:text-white/70'
            }`}
          >
            <FolderOpen size={13} className="mr-1 inline" />
            {t('mix.loadPreset')}
          </button>
          <button
            type="button"
            onClick={() => setTab('save')}
            className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              tab === 'save'
                ? 'bg-violet-500/20 text-violet-300'
                : 'text-white/50 hover:text-white/70'
            }`}
          >
            <Save size={13} className="mr-1 inline" />
            {t('mix.savePreset')}
          </button>
        </div>

        {/* Load tab */}
        {tab === 'load' && (
          <div className="max-h-64 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Spinner />
              </div>
            ) : presets.length === 0 ? (
              <p className="py-8 text-center text-xs text-white/30">
                {t('mix.noPresets')}
              </p>
            ) : (
              <div className="space-y-1.5">
                {presets.map((p) => (
                  <div
                    key={p.name}
                    className="flex items-center gap-2 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2"
                  >
                    <button
                      type="button"
                      onClick={() => handleLoad(p.name)}
                      className="flex-1 text-left text-sm text-white/70 hover:text-white"
                    >
                      {p.name}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(p.name)}
                      disabled={deleting === p.name}
                      className="rounded p-1 text-white/20 hover:bg-red-500/10 hover:text-red-300"
                    >
                      {deleting === p.name ? <Spinner /> : <Trash2 size={13} />}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Save tab */}
        {tab === 'save' && (
          <div className="space-y-3">
            <label className="block">
              <span className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-white/45">
                {t('mix.presetName')}
              </span>
              <input
                type="text"
                value={presetName}
                onChange={(e) => setPresetName(e.target.value)}
                placeholder="My mix settings"
                className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 font-mono text-xs text-white/90 placeholder:text-white/25 focus:border-violet-400/60 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-white/45">
                {t('mix.notes')}
              </span>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
                placeholder="Optional notes…"
                className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-xs text-white/90 placeholder:text-white/25 focus:border-violet-400/60 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
              />
            </label>
            <Button
              onClick={handleSave}
              disabled={saving || !presetName.trim()}
            >
              {saving ? <Spinner /> : <Save size={15} />}
              {saving ? '…' : t('mix.savePreset')}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
