import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { en } from './en'
import { tl } from './tl'

export type Lang = 'en' | 'tl'

type DeepStringify<T> = { [K in keyof T]: T[K] extends string ? string : DeepStringify<T[K]> }
export type Catalogue = DeepStringify<typeof en>

type Flatten<T, P extends string = ''> = {
  [K in keyof T & string]: T[K] extends string ? `${P}${K}` : Flatten<T[K], `${P}${K}.`>
}[keyof T & string]
export type Key = Flatten<typeof en>

export type Vars = Record<string, string | number>

const catalogues: Record<Lang, Catalogue> = { en, tl }
const STORAGE_KEY = 'kapiling.lang'
const LOCALE: Record<Lang, string> = { en: 'en-PH', tl: 'fil-PH' }

function lookup(c: Catalogue, key: string): string | undefined {
  let node: unknown = c
  for (const part of key.split('.')) {
    if (node && typeof node === 'object') node = (node as Record<string, unknown>)[part]
    else return undefined
  }
  return typeof node === 'string' ? node : undefined
}

export function translate(lang: Lang, key: Key, vars?: Vars): string {
  const s = lookup(catalogues[lang], key) ?? lookup(en, key) ?? key
  return vars ? s.replace(/\{(\w+)\}/g, (m, name: string) => (name in vars ? String(vars[name]) : m)) : s
}

function readStoredLang(): Lang {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'en' || v === 'tl') return v
  } catch { /* storage blocked: fall through */ }
  return 'tl'
}

type Ctx = { lang: Lang; setLang: (l: Lang) => void }
const I18nContext = createContext<Ctx | null>(null)

export function I18nProvider({ children, initialLang }: { children: ReactNode; initialLang?: Lang }) {
  const [lang, setLangState] = useState<Lang>(() => initialLang ?? readStoredLang())

  const setLang = useCallback((l: Lang) => {
    setLangState(l)
    try { localStorage.setItem(STORAGE_KEY, l) } catch { /* not persisted; still switches */ }
  }, [])

  useEffect(() => {
    document.documentElement.lang = lang === 'tl' ? 'fil' : 'en'
  }, [lang])

  const value = useMemo(() => ({ lang, setLang }), [lang, setLang])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

function useI18n(): Ctx {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useT/useLang must be used inside <I18nProvider>')
  return ctx
}

export function useLang(): [Lang, (l: Lang) => void] {
  const { lang, setLang } = useI18n()
  return [lang, setLang]
}

export function useT(): (key: Key, vars?: Vars) => string {
  const { lang } = useI18n()
  return useCallback((key: Key, vars?: Vars) => translate(lang, key, vars), [lang])
}

export function formatDate(d: Date | string, lang: Lang, opts: Intl.DateTimeFormatOptions = { dateStyle: 'medium' }): string {
  const date = typeof d === 'string' ? new Date(d.length === 10 ? `${d}T00:00:00` : d) : d
  return new Intl.DateTimeFormat(LOCALE[lang], opts).format(date)
}

export function formatNumber(n: number, lang: Lang, opts?: Intl.NumberFormatOptions): string {
  return new Intl.NumberFormat(LOCALE[lang], opts).format(n)
}
