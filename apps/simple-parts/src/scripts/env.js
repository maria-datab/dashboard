/**
 * Frontend settings from apps/simple-parts/.env (VITE_* variables).
 */

/** API base path for Flask routes (e.g. /api). No trailing slash. */
export function getApiBase() {
  const base = import.meta.env.VITE_API_BASE
  const raw = typeof base === 'string' && base.length > 0 ? base : '/api'
  return raw.replace(/\/$/, '')
}

/** Join API base with a path segment (e.g. apiUrl('chat') → /api/chat). */
export function apiUrl(path) {
  const segment = path.startsWith('/') ? path.slice(1) : path
  return `${getApiBase()}/${segment}`
}
