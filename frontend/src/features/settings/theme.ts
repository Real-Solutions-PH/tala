// The theme setting, after the prototype: Blue (follows the phone's light or dark mode), Mint, Night and High
// contrast. Applied as data-skin on <html> (tokens.css holds each palette), remembered per device in
// localStorage and re-applied when the app starts.
import { useLayoutEffect } from 'react'

export const THEME_KEY = 'kapiling.theme'
export const THEMES = ['blue', 'mint', 'navy', 'contrast'] as const
export type Theme = (typeof THEMES)[number]

export function readTheme(): Theme {
  try {
    const v = localStorage.getItem(THEME_KEY)
    return (THEMES as readonly string[]).includes(v ?? '') ? (v as Theme) : 'blue'
  } catch {
    return 'blue' // storage blocked: the default look
  }
}

function setAttr(theme: Theme): void {
  if (theme === 'blue') delete document.documentElement.dataset.skin
  else document.documentElement.dataset.skin = theme
}

/** Apply now and remember for next time. */
export function applyTheme(theme: Theme): void {
  setAttr(theme)
  try { localStorage.setItem(THEME_KEY, theme) } catch { /* not remembered; still applied */ }
}

/** Mounted once at the app root: re-applies the remembered theme before the first paint. */
export function useStoredTheme(): void {
  useLayoutEffect(() => { setAttr(readTheme()) }, [])
}
