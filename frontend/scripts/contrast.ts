// Re-checks the WCAG contrast of the colour tokens in src/design/tokens.css, in both themes.
// Run: bun scripts/contrast.ts   (part of `bun run test`). Exits 1 on any failure.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

const root = join(import.meta.dirname, '..')
const css = readFileSync(join(root, 'src/design/tokens.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')

function vars(block: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const m of block.matchAll(/(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;/g)) out[m[1]] = m[2]
  return out
}

const lightBlock = css.match(/^:root\s*\{([\s\S]*?)\}/m)?.[1]
const darkBlock = css.match(/prefers-color-scheme:\s*dark\)\s*\{\s*:root\s*\{([\s\S]*?)\}/)?.[1]
if (!lightBlock) { console.error('contrast: could not find the :root block in tokens.css'); process.exit(1) }
const light = vars(lightBlock)
// Light only today; a dark block, if one comes back, is checked too.
const themes: Record<string, Record<string, string>> = darkBlock ? { light, dark: { ...light, ...vars(darkBlock) } } : { light }

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(c => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
export function ratio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const MIN = 4.5
const pairs: [fg: string, bg: string][] = []
for (const fg of ['--ink', '--muted', '--primary', '--accent', '--warn', '--danger'])
  for (const bg of ['--bg', '--surface']) pairs.push([fg, bg])
pairs.push(
  ['--on-gold', '--gold'],            // gold fills always carry dark ink text (both themes)
  ['--on-primary', '--primary-fill'], // primary buttons, both themes
  ['--on-strong', '--primary-strong'],       // hero card text
  ['--on-strong-muted', '--primary-strong'], // hero card secondary text
  ['--on-danger', '--danger-fill'],   // emergency and danger buttons, both themes
  ['--primary', '--primary-soft'],    // info badge, selected tab
  ['--accent', '--accent-soft'],      // ok badge
  ['--warn', '--warn-soft'],          // warn badge
  ['--danger', '--danger-soft'],      // danger badge
  ['--ink', '--surface-2'],           // inputs, pressed secondary
  ['--muted', '--surface-2'],
)

let failures = 0
// Spec §10: --ink on --gold is 8.7:1. Dark --ink is light, so dark gold fills use --on-gold instead.
{
  const r = ratio(light['--ink'], light['--gold'])
  if (r < MIN) failures++
  console.log(`${r >= MIN ? '✓' : '✗'} light --ink on --gold`.padEnd(42) + `${r.toFixed(2)}:1`)
}
for (const [theme, t] of Object.entries(themes)) {
  for (const [fg, bg] of pairs) {
    if (!t[fg] || !t[bg]) { console.error(`✗ ${theme}: missing ${t[fg] ? bg : fg}`); failures++; continue }
    const r = ratio(t[fg], t[bg])
    const ok = r >= MIN
    if (!ok) failures++
    console.log(`${ok ? '✓' : '✗'} ${theme.padEnd(5)} ${fg} on ${bg}`.padEnd(42) + `${r.toFixed(2)}:1`)
  }
}

// Gold is never text, and colour values live only in tokens.css.
function walk(dir: string): string[] {
  return readdirSync(dir).flatMap(n => {
    const p = join(dir, n)
    return statSync(p).isDirectory() ? walk(p) : [p]
  })
}
for (const file of walk(join(root, 'src'))) {
  if (!/\.(css|tsx?)$/.test(file)) continue
  const rel = relative(root, file)
  const text = readFileSync(file, 'utf8')
  if (/(^|[^\w-])color\s*:\s*['"]?var\(\s*--gold\s*\)/m.test(text)) {
    console.error(`✗ ${rel}: sets color: var(--gold). Gold is never text.`); failures++
  }
  if (rel !== join('src', 'design', 'tokens.css') && !/\.test\.tsx?$/.test(rel)) {
    for (const m of text.matchAll(/#[0-9a-fA-F]{3,8}\b/g)) {
      console.error(`✗ ${rel}: raw colour ${m[0]}; use a token from tokens.css`); failures++
    }
  }
}

if (failures) { console.error(`\ncontrast: ${failures} failure(s)`); process.exit(1) }
console.log('\ncontrast: all pairs ≥ 4.5:1, gold is never text, no raw colours outside tokens.css')
