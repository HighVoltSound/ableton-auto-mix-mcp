import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import en from './locales/en.json'
import ru from './locales/ru.json'

export type Lang = 'en' | 'ru'

export const LANGUAGES: { id: Lang; label: string }[] = [
  { id: 'en', label: 'English' },
  { id: 'ru', label: 'Русский' },
]

const STORAGE_KEY = 'musicmixcode.lang'

const bundles: Record<Lang, Record<string, unknown>> = { en, ru }

function detectLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'en' || stored === 'ru') return stored
  } catch { /* localStorage unavailable */ }
  const browser = navigator.language.slice(0, 2)
  if (browser === 'ru') return 'ru'
  return 'en'
}

/** Resolve a dotted key like "mix.title" from a nested object. */
function resolve(obj: unknown, path: string): string | undefined {
  let cur: unknown = obj
  for (const seg of path.split('.')) {
    if (cur == null || typeof cur !== 'object') return undefined
    cur = (cur as Record<string, unknown>)[seg]
  }
  return typeof cur === 'string' ? cur : undefined
}

/** Interpolate {placeholders} inside a string. */
function interpolate(
  template: string,
  params: Record<string, string | number> | undefined,
): string {
  if (!params) return template
  return template.replace(/\{(\w+)\}/g, (_, key: string) =>
    key in params ? String(params[key]) : `{${key}}`,
  )
}

interface I18nContextValue {
  lang: Lang
  setLang: (l: Lang) => void
  t: (key: string, params?: Record<string, string | number>) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<DetectLang>(detectLang)

  const setLang = useCallback((l: Lang) => {
    setLangState(l)
    try {
      localStorage.setItem(STORAGE_KEY, l)
    } catch { /* storage full or unavailable */ }
  }, [])

  const t = useCallback(
    (key: string, params?: Record<string, string | number>): string => {
      const val = resolve(bundles[lang], key)
      if (val !== undefined) return interpolate(val, params)
      // Fallback to English if missing in current lang
      const enVal = resolve(bundles.en, key)
      if (enVal !== undefined) return interpolate(enVal, params)
      // Last resort: return the key itself
      return key
    },
    [lang],
  )

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

type DetectLang = Lang

/** Hook: returns { lang, setLang, t }. Must be used inside <I18nProvider>. */
export function useLanguage() {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useLanguage must be used within <I18nProvider>')
  return ctx
}
