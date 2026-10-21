import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev: `npm run dev` on :5173, API calls proxied to `ilovestock serve` on :3000 (first free port).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Built into the Python package so `pip install` ships the UI.
  build: { outDir: '../src/ilovestock/static', emptyOutDir: true },
  server: { proxy: { '/api': 'http://127.0.0.1:3000' } },
})
