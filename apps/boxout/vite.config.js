// Vite build config for the Vue frontend

import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiBase = env.VITE_API_BASE || '/api/app'
  const backendUrl = env.VITE_BACKEND_URL || 'http://127.0.0.1:5000'
  const apiBasePattern = apiBase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)), // @/ → src/
      },
    },
    assetsInclude: ['**/*.wasm'], // rhino3dm needs its WASM file bundled
    optimizeDeps: {
      exclude: ['rhino3dm'], // don't pre-bundle rhino3dm (loads WASM at runtime)
    },
    server: {
      // Force IPv4 — Vite on Windows often binds [::1] only; 127.0.0.1 then refuses
      host: '127.0.0.1',
      port: 5174,
      strictPort: true,
      proxy: {
        [apiBase]: {
          target: backendUrl,
          changeOrigin: true,
          rewrite: (path) => path.replace(new RegExp(`^${apiBasePattern}`), ''),
        },
      },
    },
  }
})
