import { Sparkles, CheckCircle2, Loader2, Music4, RefreshCw } from 'lucide-react'
import type { MixStyle, SuggestResult } from '@/types'
import { Badge, Button, Card, SectionTitle, Spinner } from './ui'
import { StyleCard } from './StyleCard'
import { useLanguage } from '@/i18n'

export function StylePicker({
  styles,
  selectedId,
  onSelect,
  suggest,
  suggestResult,
  suggesting,
  onRetry,
}: {
  styles: MixStyle[]
  selectedId: string | null
  onSelect: (id: string) => void
  suggest: () => void
  suggestResult: SuggestResult | null
  suggesting: boolean
  onRetry?: () => void
}) {
  const { t } = useLanguage()
  const suggestedId = suggestResult?.style_id ?? suggestResult?.style

  if (styles.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center pt-20 text-center">
        <div className="mb-4 rounded-full bg-white/[0.04] p-4">
          <Music4 size={36} className="text-white/30" />
        </div>
        <h3 className="text-lg font-medium text-white/80">{t('styles.noStyles')}</h3>
        <p className="mt-2 max-w-sm text-sm text-white/45">{t('styles.noStylesHint')}</p>
        {onRetry && (
          <Button variant="outline" onClick={onRetry} className="mt-5">
            <RefreshCw size={14} /> {t('styles.retry')}
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className="pt-10">
      <SectionTitle
        title={t('styles.title')}
        subtitle={t('styles.subtitle')}
        right={
          <Button variant="outline" onClick={suggest} disabled={suggesting}>
            {suggesting ? (
              <>
                <Spinner /> {t('styles.suggesting')}
              </>
            ) : (
              <>
                <Sparkles size={15} /> {t('styles.suggest')}
              </>
            )}
          </Button>
        }
      />

      {suggestResult && (
        <Card className="mb-5 flex items-start gap-3 border-violet-400/25 bg-violet-500/[0.08] p-4">
          <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-violet-300" />
          <div>
            <Badge tone="violet">{t('styles.suggested')} · {suggestedId ?? '?'}</Badge>
            {suggestResult.reason && (
              <p className="mt-1.5 text-sm leading-relaxed text-white/65">
                {suggestResult.reason}
              </p>
            )}
          </div>
        </Card>
      )}

      <div
        className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3"
        role="radiogroup"
        aria-label="Mixing style"
      >
        {styles.map((style) => {
          const active = selectedId === style.id
          const suggested = suggestedId != null && suggestedId === style.id
          return (
            <StyleCard
              key={style.id}
              style={style}
              active={active}
              suggested={suggested}
              onSelect={() => onSelect(style.id)}
            />
          )
        })}
      </div>

      {suggesting && (
        <div className="mt-4 flex items-center gap-2 text-xs text-white/40">
          <Loader2 size={13} className="animate-spin" /> {t('styles.askingBackend')}
        </div>
      )}
    </div>
  )
}
