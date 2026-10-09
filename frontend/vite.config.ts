import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: { outDir: '../backend/static', emptyOutDir: true },
  server: { proxy: { '/api': 'http://127.0.0.1:8787' } },
  test: { environment: 'jsdom' },
})
