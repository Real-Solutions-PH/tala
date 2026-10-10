// Writes src/brand/mark.svg, public/favicon.svg and the PNG app icons from the mark geometry.
// Run: bun scripts/icons.ts   (commit the output)
import { writeFileSync } from 'node:fs'
import { join } from 'node:path'
import sharp from 'sharp'
import { COMPANION, LENS, PERSON } from '../src/brand/geometry.ts'

const root = join(import.meta.dirname, '..')
const BLUE = '#0F62E6' // Kapiling Blue
const GOLD = '#F2A900' // Araw Gold
const WHITE = '#FFFFFF'

const circle = (c: { cx: number; cy: number; r: number }, fill: string) => `<circle cx="${c.cx}" cy="${c.cy}" r="${c.r}" fill="${fill}"/>`
const markShapes = (fill: string) => `${circle(PERSON, fill)}${circle(COMPANION, fill)}<path d="${LENS}" fill="${GOLD}"/>`

/** The plain mark in brand colours (for docs and anywhere outside the app). */
const markSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">${markShapes(BLUE)}</svg>\n`

/**
 * The app icon: white mark with gold lens on a blue square.
 * `inset` is the share of the side kept clear on each edge; `radius` is the corner radius as a share of the side.
 */
function iconSvg(px: number, inset: number, radius: number): string {
  const markSide = px * (1 - 2 * inset)
  const scale = markSide / 24
  const off = px * inset
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${px}" height="${px}" viewBox="0 0 ${px} ${px}">`
    + `<rect width="${px}" height="${px}" rx="${px * radius}" fill="${BLUE}"/>`
    + `<g transform="translate(${off} ${off}) scale(${scale})">${markShapes(WHITE)}</g></svg>`
}

writeFileSync(join(root, 'src/brand/mark.svg'), markSvg)
// Favicon: rounded square so it reads on light and dark browser tabs.
writeFileSync(join(root, 'public/favicon.svg'), iconSvg(32, 0.14, 0.22).replace(/ width="32" height="32"/, '') + '\n')

const outputs: [file: string, px: number, inset: number, radius: number][] = [
  ['icon-180.png', 180, 0.16, 0],          // apple-touch-icon: iOS rounds the corners itself
  ['icon-192.png', 192, 0.16, 0.22],
  ['icon-512.png', 512, 0.16, 0.22],
  ['icon-maskable-512.png', 512, 0.2, 0],  // maskable: full bleed, mark inside the 60% safe zone
]
for (const [file, px, inset, radius] of outputs) {
  await sharp(Buffer.from(iconSvg(px, inset, radius))).png({ compressionLevel: 9 }).toFile(join(root, 'public', file))
  console.log(`wrote public/${file}`)
}
console.log('wrote src/brand/mark.svg, public/favicon.svg')
