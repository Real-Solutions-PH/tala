import { expect, test } from 'vitest'
import { en } from './en'; import { tl } from './tl'
import { readFileSync } from 'node:fs'; import { globSync } from 'node:fs'
const flat = (o: object, p = ''): string[] => Object.entries(o).flatMap(([k, v]) => typeof v === 'string' ? [p + k] : flat(v, p + k + '.'))
const get = (o: any, k: string) => k.split('.').reduce((a, p) => a[p], o)
test('catalogues have identical keys', () => { expect(flat(tl).sort()).toEqual(flat(en).sort()) })
test('no catalogue value is empty', () => { for (const c of [en, tl]) for (const k of flat(c)) expect(String(get(c, k)).trim(), k).toBeTruthy() })
test('every t("...") key used in src exists', () => {
  const keys = new Set(flat(en))
  for (const f of globSync('src/**/*.tsx')) for (const m of readFileSync(f, 'utf8').matchAll(/\bt\(\s*'([\w.]+)'/g)) expect(keys, `${f}: ${m[1]}`).toContain(m[1])
})
test('placeholders match between languages', () => {
  const ph = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort().join()
  for (const k of flat(en)) expect(ph(get(tl, k)), k).toBe(ph(get(en, k)))
})
