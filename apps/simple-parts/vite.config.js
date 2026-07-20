import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiBase = env.VITE_API_BASE || '/api'
  const backendUrl = env.VITE_BACKEND_URL || 'http://127.0.0.1:5001'
  const apiBasePattern = apiBase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    assetsInclude: ['**/*.wasm'],
    optimizeDeps: {
      exclude: ['rhino3dm'],
    },
    server: {
      // Force IPv4 — Vite on Windows often binds [::1] only; 127.0.0.1 then refuses
      host: '127.0.0.1',
      port: 5175,
      strictPort: true,
      proxy: {
        [apiBase]: {
          target: backendUrl,
          changeOrigin: true,
          // Backend routes are /api/...; only rewrite when the Vite prefix differs.
          rewrite: (path) => {
            if (apiBase === '/api') return path
            return path.replace(new RegExp(`^${apiBasePattern}`), '/api')
          },
        },
      },
    },
  }
})
