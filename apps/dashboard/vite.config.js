import { fileURLToPath, URL } from 'node:url'
import path from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

const dashboardRoot = fileURLToPath(new URL('.', import.meta.url))
const boxoutSrc = fileURLToPath(new URL('../boxout/src', import.meta.url))
const simplePartsSrc = fileURLToPath(new URL('../simple-parts/src', import.meta.url))

/** Resolve `@/` to the importing tool's src when bundling nested apps. */
function toolAtAliasPlugin() {
  return {
    name: 'tool-at-alias',
    enforce: 'pre',
    resolveId(id, importer) {
      if (!id.startsWith('@/') || !importer) return null
      const normalized = importer.replace(/\\/g, '/')
      let root = null
      if (normalized.includes('/apps/boxout/')) root = boxoutSrc
      else if (normalized.includes('/apps/simple-parts/')) root = simplePartsSrc
      if (!root) return null
      return path.join(root, id.slice(2))
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const boxoutBackend = env.VITE_BOXOUT_BACKEND_URL || 'http://127.0.0.1:5000'
  const simplePartsBackend = env.VITE_SIMPLE_PARTS_BACKEND_URL || 'http://127.0.0.1:5001'

  return {
    plugins: [toolAtAliasPlugin(), vue()],
    resolve: {
      alias: [
        { find: '@dashboard/boxout', replacement: boxoutSrc },
        { find: '@dashboard/simple-parts', replacement: simplePartsSrc },
      ],
      dedupe: ['vue', 'three', 'rhino3dm'],
    },
    assetsInclude: ['**/*.wasm'],
    optimizeDeps: {
      exclude: ['rhino3dm'],
    },
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      fs: {
        allow: [dashboardRoot, path.join(dashboardRoot, '..')],
      },
      proxy: {
        '/api/boxout': {
          target: boxoutBackend,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api\/boxout/, ''),
        },
        '/api/simple-parts': {
          target: simplePartsBackend,
          changeOrigin: true,
          rewrite: (p) => {
            // simple-parts Flask routes are under /api/...
            const rest = p.replace(/^\/api\/simple-parts/, '')
            return `/api${rest}`
          },
        },
      },
    },
  }
})
