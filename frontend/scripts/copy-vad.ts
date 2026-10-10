// Copies the VAD model, its audio worklet and the onnxruntime-web wasm into public/vad/ so the app
// serves them itself (offline, same origin). Run from postinstall, dev and build. The copies are gitignored.
import { copyFileSync, existsSync, mkdirSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const out = join(root, 'public', 'vad')
const vad = join(root, 'node_modules', '@ricky0123', 'vad-web', 'dist')
const ort = join(root, 'node_modules', 'onnxruntime-web', 'dist')

// vad-web imports "onnxruntime-web/wasm", which loads the plain simd-threaded build.
const files = [
  [vad, 'silero_vad_v5.onnx'],
  [vad, 'vad.worklet.bundle.min.js'],
  [ort, 'ort-wasm-simd-threaded.wasm'],
  [ort, 'ort-wasm-simd-threaded.mjs'],
] as const

mkdirSync(out, { recursive: true })
for (const [dir, name] of files) {
  const src = join(dir, name)
  const dst = join(out, name)
  if (!existsSync(src)) { console.error(`copy-vad: missing ${src}`); process.exit(1) }
  if (existsSync(dst) && statSync(dst).size === statSync(src).size && statSync(dst).mtimeMs >= statSync(src).mtimeMs) continue
  copyFileSync(src, dst)
}
console.log(`copy-vad: ${files.length} files in public/vad/`)
